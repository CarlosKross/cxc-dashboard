import pandas as pd
import json
from pathlib import Path

EXCEL_PATH = r"C:\Users\kross\Downloads\CXC_Informe_18-03-26.xlsx"
OUTPUT_PATH = r"C:\Users\kross\Downloads\CXC_Dashboard.html"
BASE_MAESTRA_PATH = r"C:\Users\kross\Downloads\reporte_clientes_2026-02-12.xlsx"

EXECUTIVE_SHEETS = [
    "Armiro Perez",
    "Carlos Echeverria",
    "Carol Ibaceta",
    "Francisco Carreño",
    "Gerson Astudillo",
]

COLORS = {
    "Armiro Perez":       "#4F8EF7",
    "Carlos Echeverria":  "#F7874F",
    "Carol Ibaceta":      "#4FBF8F",
    "Francisco Carreño":  "#BF4F8F",
    "Gerson Astudillo":   "#F7C94F",
}

# Valores en columna Ejecutivo que NO son ejecutivos reales → van a "Sin Ejecutivo"
SIN_EJECUTIVO_ALIASES = {
    "ex cliente", "ex-cliente", "ex_cliente",
    "clausurado", "clausurada",
    "sin patente", "sin ejecutivo", "sin asignar", "sin asignacion",
    "inactivo", "inactiva", "dado de baja", "baja", "cerrado", "cerrada",
    "no asignado", "no asignada", "pendiente", "varios",
}

def normalize_rut(rut_str):
    """Normalize RUT: remove dots, strip leading zeros, uppercase K."""
    cleaned = str(rut_str).strip().replace(".", "").upper()
    # Strip leading zeros from the numeric part (before the dash)
    if "-" in cleaned:
        parts = cleaned.rsplit("-", 1)
        cleaned = parts[0].lstrip("0") + "-" + parts[1]
    return cleaned


def load_fantasy_names(path):
    """Return dict of normalized_rut -> Nombre de Fantasía from base maestra."""
    try:
        df = pd.read_excel(path, usecols=["RUT", "Nombre de Fantasía"])
        lookup = {}
        for _, row in df.iterrows():
            rut = row["RUT"]
            name = row["Nombre de Fantasía"]
            if pd.notna(rut) and pd.notna(name) and str(name).strip():
                lookup[normalize_rut(rut)] = str(name).strip()
        print(f"[BASE MAESTRA] {len(lookup)} clientes cargados desde {path}")
        return lookup
    except Exception as e:
        print(f"[WARN] No se pudo cargar base maestra: {e}")
        return {}


def fmt_clp(value):
    """Format number as CLP currency string."""
    try:
        v = int(round(float(value)))
        return f"${v:,.0f}".replace(",", ".")
    except Exception:
        return "$0"

def fmt_pct(value):
    try:
        return f"{float(value)*100:.1f}%"
    except Exception:
        return "0.0%"

# Column name aliases — maps standard key → list of accepted names (uppercase, stripped)
COL_ALIASES = {
    "RUT":        ["RUT"],
    "CLIENTE":    ["CLIENTE", "RAZÓN SOCIAL", "RAZON SOCIAL", "NOMBRE"],
    "N FACTURA":  ["N FACTURA", "NÚMERO", "NUMERO", "N° FACTURA", "FACTURA", "NRO"],
    "EMISION":    ["EMISION", "EMISIÓN", "F. EMISION", "FECHA EMISION"],
    "VENCIMIENTO":["VENCIMIENTO", "VENCTO", "F. VENCIMIENTO", "FECHA VENCIMIENTO"],
    "DIAS MORA":  ["DIAS MORA", "DÍAS MORA"],
    "NO VENCIDO": ["NO VENCIDO", "ANTERIOR"],
    "1-30 DIAS":  ["1-30 DIAS", "1 - 30", "1-30", "RANGO 1"],
    "31-60 DIAS": ["31-60 DIAS", "31 - 60", "31-60", "RANGO 2"],
    "61-90 DIAS": ["61-90 DIAS", "61 - 90", "61-90", "RANGO 3"],
    "> 90 DIAS":  ["> 90 DIAS", "RESTO", ">90 DIAS", "+90 DIAS", "MAS 90"],
    "TOTAL":      ["TOTAL"],
}

def _resolve_cols(col_map):
    """Map standard column keys to actual indices using aliases."""
    resolved = {}
    for key, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in col_map:
                resolved[key] = col_map[alias]
                break
    return resolved


def parse_executive_sheet(xls, sheet_name):
    """Parse an executive sheet and return summary + detail rows."""
    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

    # Find header row — row containing a cell that normalizes to "RUT"
    header_row = None
    for i, row in df.iterrows():
        if any(str(v).strip().upper() == "RUT" for v in row.values):
            header_row = i
            break

    if header_row is None:
        return None, []

    # Optional summary block (format A has TOTAL CARTERA row)
    summary_labels_row = None
    summary_values_row = None
    for i in range(header_row):
        row_vals = [str(v).strip().upper() for v in df.iloc[i].values]
        if "TOTAL CARTERA" in row_vals:
            summary_labels_row = i
            summary_values_row = i + 1
            break

    summary = {}
    if summary_labels_row is not None:
        labels = df.iloc[summary_labels_row].tolist()
        values = df.iloc[summary_values_row].tolist()
        for lbl, val in zip(labels, values):
            lbl_str = str(lbl).strip().upper()
            if lbl_str in ("TOTAL CARTERA", "NO VENCIDO", "VENCIDO", "% VENCIDO", "N CLIENTES"):
                try:
                    summary[lbl_str] = float(val) if val == val else 0
                except Exception:
                    summary[lbl_str] = 0

    # Build raw col_map from header row
    col_headers = df.iloc[header_row].tolist()
    data = df.iloc[header_row + 1:].copy()
    data.columns = range(len(data.columns))

    raw_col_map = {str(h).strip().upper(): idx for idx, h in enumerate(col_headers)}
    col_map = _resolve_cols(raw_col_map)

    required = ["RUT", "CLIENTE", "DIAS MORA", "NO VENCIDO",
                "1-30 DIAS", "31-60 DIAS", "61-90 DIAS", "> 90 DIAS", "TOTAL"]
    if not all(c in col_map for c in required):
        return summary, []

    # Detect optional Ejecutivo column for filtering
    exec_col = None
    for h, idx in raw_col_map.items():
        if "EJECUTIVO" in h:
            exec_col = idx
            break

    def norm(s):
        import unicodedata
        s = unicodedata.normalize("NFD", str(s).strip().lower())
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    sheet_norm = norm(sheet_name)

    rows = []
    current_rut = None
    current_client = None

    for _, row in data.iterrows():
        rut_val    = row[col_map["RUT"]]
        client_val = row[col_map["CLIENTE"]]

        # Skip empty or total rows
        if pd.isna(rut_val) and pd.isna(client_val):
            continue
        total_val = row[col_map["TOTAL"]]
        if pd.isna(total_val):
            continue

        # Filter by executive if column exists — skip rows with no executive or mismatched
        if exec_col is not None:
            exec_val = row[exec_col]
            if pd.isna(exec_val) or str(exec_val).strip() == "":
                continue
            if norm(str(exec_val)) != sheet_norm:
                continue

        if not pd.isna(rut_val):
            current_rut = str(rut_val).strip()
        if not pd.isna(client_val):
            current_client = str(client_val).strip()

        def safe_float(v):
            try:
                return float(v) if not pd.isna(v) else 0.0
            except Exception:
                return 0.0

        def fmt_date(v):
            if v is None: return ""
            try:
                import pandas as _pd
                ts = _pd.to_datetime(v, errors="coerce", dayfirst=True)
                return ts.strftime("%d/%m/%Y") if not _pd.isna(ts) else str(v).split(" ")[0]
            except Exception:
                return str(v).split(" ")[0]

        factura_idx   = col_map.get("N FACTURA")
        emision_idx   = col_map.get("EMISION")
        vencim_idx    = col_map.get("VENCIMIENTO")
        rows.append({
            "rut":         current_rut,
            "cliente":     current_client,
            "factura":     str(row[factura_idx]).strip() if factura_idx is not None and not pd.isna(row[factura_idx]) else "",
            "emision":     fmt_date(row[emision_idx])   if emision_idx  is not None and not pd.isna(row[emision_idx])  else "",
            "vencimiento": fmt_date(row[vencim_idx])    if vencim_idx   is not None and not pd.isna(row[vencim_idx])   else "",
            "dias_mora":   safe_float(row[col_map["DIAS MORA"]]),
            "no_vencido":  safe_float(row[col_map["NO VENCIDO"]]),
            "d1_30":       safe_float(row[col_map["1-30 DIAS"]]),
            "d31_60":      safe_float(row[col_map["31-60 DIAS"]]),
            "d61_90":      safe_float(row[col_map["61-90 DIAS"]]),
            "d90plus":     safe_float(row[col_map["> 90 DIAS"]]),
            "total":       safe_float(row[col_map["TOTAL"]]),
        })

    return summary, rows


def parse_sin_ejecutivo(xls):
    """Recolecta filas sin ejecutivo asignado desde la primera hoja con columna Ejecutivo."""
    import unicodedata

    def norm(s):
        s = unicodedata.normalize("NFD", str(s).strip().lower())
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, header=None)
        header_row = None
        for i, row in df.iterrows():
            if any(str(v).strip().upper() == "RUT" for v in row.values):
                header_row = i
                break
        if header_row is None:
            continue
        col_headers = df.iloc[header_row].tolist()
        raw_col_map = {str(h).strip().upper(): idx for idx, h in enumerate(col_headers)}
        col_map = _resolve_cols(raw_col_map)
        exec_col = next((idx for h, idx in raw_col_map.items() if "EJECUTIVO" in h), None)
        if exec_col is None:
            continue
        required = ["RUT", "CLIENTE", "NO VENCIDO", "1-30 DIAS", "31-60 DIAS", "61-90 DIAS", "> 90 DIAS", "TOTAL"]
        if not all(c in col_map for c in required):
            continue

        data = df.iloc[header_row + 1:].copy()
        data.columns = range(len(data.columns))
        rows = []
        current_rut = current_client = None
        for _, row in data.iterrows():
            rut_val    = row[col_map["RUT"]]
            client_val = row[col_map["CLIENTE"]]
            if pd.isna(rut_val) and pd.isna(client_val):
                continue
            total_val = row[col_map["TOTAL"]]
            if pd.isna(total_val):
                continue
            exec_val = row[exec_col]
            if not (pd.isna(exec_val) or str(exec_val).strip() == ""):
                continue  # tiene ejecutivo, ignorar
            if not pd.isna(rut_val):
                current_rut = str(rut_val).strip()
            if not pd.isna(client_val):
                current_client = str(client_val).strip()

            def safe_float(v):
                try: return float(v) if not pd.isna(v) else 0.0
                except: return 0.0

            def fmt_date(v):
                if v is None: return ""
                try:
                    ts = pd.to_datetime(v, errors="coerce", dayfirst=True)
                    return ts.strftime("%d/%m/%Y") if not pd.isna(ts) else str(v).split(" ")[0]
                except: return str(v).split(" ")[0]

            fi = col_map.get("N FACTURA"); ei = col_map.get("EMISION"); vi = col_map.get("VENCIMIENTO")
            rows.append({
                "rut": current_rut, "cliente": current_client,
                "factura":     str(row[fi]).strip() if fi is not None and not pd.isna(row[fi]) else "",
                "emision":     fmt_date(row[ei]) if ei is not None and not pd.isna(row[ei]) else "",
                "vencimiento": fmt_date(row[vi]) if vi is not None and not pd.isna(row[vi]) else "",
                "dias_mora": safe_float(row[col_map["DIAS MORA"]]) if "DIAS MORA" in col_map else 0.0,
                "no_vencido": safe_float(row[col_map["NO VENCIDO"]]),
                "d1_30": safe_float(row[col_map["1-30 DIAS"]]),
                "d31_60": safe_float(row[col_map["31-60 DIAS"]]),
                "d61_90": safe_float(row[col_map["61-90 DIAS"]]),
                "d90plus": safe_float(row[col_map["> 90 DIAS"]]),
                "total": safe_float(row[col_map["TOTAL"]]),
            })
        if rows:
            return rows  # encontrados, salir
    return []


def parse_analisis_deuda(xls, exec_lookup=None, fantasy_lookup=None):
    """Parse ANALISISDEUDA format — single sheet, all invoices, no Ejecutivo column.
    exec_lookup: {normalized_rut: exec_name} — viene de la base maestra (Google Sheets).
    Retorna {exec_name: (summary_dict, rows_list)}.
    """
    import unicodedata
    from collections import defaultdict

    def norm_str(s):
        s = unicodedata.normalize("NFD", str(s).strip().lower())
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    # Buscar hoja con "analisis" o "deuda" en el nombre
    target = None
    for s in xls.sheet_names:
        if "analisis" in norm_str(s) or "deuda" in norm_str(s):
            target = s
            break
    if target is None:
        return {}

    df_raw = pd.read_excel(xls, sheet_name=target, header=None)

    # Buscar fila de encabezado: la que tiene "RUT" o "Rut"
    header_row = None
    for i, row in df_raw.iterrows():
        if any(str(v).strip().upper() == "RUT" for v in row.values):
            header_row = i
            break
    if header_row is None:
        return {}

    # La fila de grupos está justo antes (tiene "Anterior", "Resto", "Total")
    group_row = header_row - 1 if header_row > 0 else None

    def clean(v):
        s = str(v).strip()
        return "" if s.lower() in ("nan", "") else s

    header_vals = [clean(v) for v in df_raw.iloc[header_row].values]
    group_vals  = ([clean(v) for v in df_raw.iloc[group_row].values]
                   if group_row is not None else [""] * len(header_vals))

    # Combinar: usar header_row si tiene valor, sino usar group_row
    col_names = [h if h else g for h, g in zip(header_vals, group_vals)]

    raw_col_map = {name.upper(): idx for idx, name in enumerate(col_names) if name}
    col_map = _resolve_cols(raw_col_map)

    required = ["RUT", "CLIENTE", "NO VENCIDO", "1-30 DIAS", "31-60 DIAS", "61-90 DIAS", "> 90 DIAS", "TOTAL"]
    if not all(c in col_map for c in required):
        return {}

    factura_idx = col_map.get("N FACTURA")
    emision_idx = col_map.get("EMISION")
    vencim_idx  = col_map.get("VENCIMIENTO")

    exec_lookup    = exec_lookup or {}
    fantasy_lookup = fantasy_lookup or {}

    # Extraer fecha del informe desde el archivo (fila con "Fecha Informe:")
    fecha_informe = pd.Timestamp.today().normalize()
    for i in range(min(header_row, 10)):
        for v in df_raw.iloc[i].values:
            s = str(v).strip()
            if "fecha informe" in s.lower():
                # buscar la celda siguiente con fecha
                row_vals = [str(x).strip() for x in df_raw.iloc[i].values]
                for rv in row_vals:
                    try:
                        ts = pd.to_datetime(rv, dayfirst=True, errors="coerce")
                        if not pd.isna(ts):
                            fecha_informe = ts.normalize()
                            break
                    except Exception:
                        pass
                break

    def safe_float(v):
        try:   return float(v) if not pd.isna(v) else 0.0
        except: return 0.0

    def fmt_date(v):
        if v is None: return ""
        try:
            ts = pd.to_datetime(v, errors="coerce", dayfirst=True)
            return ts.strftime("%d/%m/%Y") if not pd.isna(ts) else str(v).split(" ")[0]
        except: return str(v).split(" ")[0]

    def calc_dias_mora(vencim_val):
        """Días transcurridos desde el vencimiento hasta la fecha del informe."""
        if vencim_val is None or pd.isna(vencim_val):
            return 0.0
        try:
            ts = pd.to_datetime(vencim_val, errors="coerce", dayfirst=True)
            if pd.isna(ts):
                return 0.0
            delta = (fecha_informe - ts.normalize()).days
            return max(0.0, float(delta))
        except Exception:
            return 0.0

    # Agrupar filas por ejecutivo
    data = df_raw.iloc[header_row + 1:].copy()
    data.columns = range(len(data.columns))
    exec_rows = defaultdict(list)

    for _, row in data.iterrows():
        rut_val    = row[col_map["RUT"]]
        client_val = row[col_map["CLIENTE"]]
        total_val  = row[col_map["TOTAL"]]

        # Saltar filas vacías, totales o "Fin Informe"
        if pd.isna(rut_val) or str(rut_val).strip().lower() in ("nan", "", "fin informe"):
            continue
        if pd.isna(total_val):
            continue

        rut     = normalize_rut(str(rut_val).strip())
        cliente = str(client_val).strip() if not pd.isna(client_val) else ""
        if fantasy_lookup.get(rut):
            cliente = fantasy_lookup[rut]

        exec_name = exec_lookup.get(rut, "Sin Ejecutivo")

        # Remap pseudo-ejecutivos a "Sin Ejecutivo"
        import unicodedata as _ud
        _en = _ud.normalize("NFD", exec_name.strip().lower())
        _en = "".join(c for c in _en if _ud.category(c) != "Mn")
        if _en in SIN_EJECUTIVO_ALIASES:
            exec_name = "Sin Ejecutivo"

        vencim_raw = row[vencim_idx] if vencim_idx is not None else None
        dias_mora  = calc_dias_mora(vencim_raw)

        r = {
            "rut": rut, "cliente": cliente,
            "factura": "", "emision": "", "vencimiento": "",
            "dias_mora":  dias_mora,
            "no_vencido": safe_float(row[col_map["NO VENCIDO"]]),
            "d1_30":      safe_float(row[col_map["1-30 DIAS"]]),
            "d31_60":     safe_float(row[col_map["31-60 DIAS"]]),
            "d61_90":     safe_float(row[col_map["61-90 DIAS"]]),
            "d90plus":    safe_float(row[col_map["> 90 DIAS"]]),
            "total":      safe_float(row[col_map["TOTAL"]]),
        }
        if factura_idx is not None and not pd.isna(row[factura_idx]):
            try:    r["factura"] = str(int(float(row[factura_idx])))
            except: r["factura"] = str(row[factura_idx]).strip()
        if emision_idx is not None:
            r["emision"] = fmt_date(row[emision_idx])
        if vencim_idx is not None:
            r["vencimiento"] = fmt_date(row[vencim_idx])

        exec_rows[exec_name].append(r)

    # Construir resultado con summary por ejecutivo
    result = {}
    for exec_name, rows in exec_rows.items():
        summary = {
            "TOTAL CARTERA": sum(r["total"] for r in rows),
            "NO VENCIDO":    sum(r["no_vencido"] for r in rows),
            "N CLIENTES":    len(set(r["rut"] for r in rows)),
        }
        result[exec_name] = (summary, rows)

    return result


def aggregate_by_client(rows):
    """Group facturas by client and sum amounts, keeping invoice detail."""
    clients = {}
    for r in rows:
        key = r["rut"]
        if key not in clients:
            clients[key] = {
                "rut": r["rut"], "cliente": r["cliente"],
                "no_vencido": 0, "d1_30": 0, "d31_60": 0,
                "d61_90": 0, "d90plus": 0, "total": 0,
                "invoices": [],
            }
        clients[key]["no_vencido"] += r["no_vencido"]
        clients[key]["d1_30"]      += r["d1_30"]
        clients[key]["d31_60"]     += r["d31_60"]
        clients[key]["d61_90"]     += r["d61_90"]
        clients[key]["d90plus"]    += r["d90plus"]
        clients[key]["total"]      += r["total"]
        # Only store invoices that have some overdue amount
        if r["d1_30"] + r["d31_60"] + r["d61_90"] + r["d90plus"] > 0:
            clients[key]["invoices"].append(r)

    result = list(clients.values())
    for c in result:
        c["vencido"]     = c["d1_30"] + c["d31_60"] + c["d61_90"] + c["d90plus"]
        c["pct_vencido"] = (c["vencido"] / c["total"] * 100) if c["total"] > 0 else 0
    return sorted(result, key=lambda x: -x["vencido"])


def build_exec_kpis(summary, rows, name, fantasy_lookup=None):
    clients = aggregate_by_client(rows)
    if fantasy_lookup:
        for c in clients:
            fantasy = fantasy_lookup.get(normalize_rut(c["rut"]))
            if fantasy:
                c["cliente"] = fantasy
    vencido = sum(c["vencido"] for c in clients)
    total_cartera = summary.get("TOTAL CARTERA", sum(r["total"] for r in rows))
    pct_vencido = (vencido / total_cartera * 100) if total_cartera else 0
    n_clientes_mora = sum(1 for c in clients if c["vencido"] > 0)
    d1_30 = sum(r["d1_30"] for r in rows)
    d31_60 = sum(r["d31_60"] for r in rows)
    d61_90 = sum(r["d61_90"] for r in rows)
    d90plus = sum(r["d90plus"] for r in rows)

    # Días de calle: tramo más alto con saldo (sin ponderar por monto)
    # Criterio: se usa el punto medio del tramo de mayor antigüedad que tenga saldo
    # >90d→120, 61-90d→75, 31-60d→45, 1-30d→15
    def _dias_calle_from_row(r):
        if r["dias_mora"] > 0:
            return r["dias_mora"]
        if r["d90plus"] > 0:  return 120.0
        if r["d61_90"]  > 0:  return 75.0
        if r["d31_60"]  > 0:  return 45.0
        if r["d1_30"]   > 0:  return 15.0
        return 0.0

    # Días de calle por cliente: factura más antigua (max días post vencimiento)
    for c in clients:
        c_rows = [r for r in rows if r["rut"] == c["rut"]
                  and r["d1_30"]+r["d31_60"]+r["d61_90"]+r["d90plus"] > 0]
        c["dias_calle"] = max((_dias_calle_from_row(r) for r in c_rows), default=0.0)
        # Guardar días exactos en cada factura para mostrar en detalle
        for inv in c.get("invoices", []):
            inv["dias_atraso"] = _dias_calle_from_row(inv)

    # KPI ejecutivo: factura más antigua de toda su cartera
    rows_vencidos = [r for r in rows if r["d1_30"]+r["d31_60"]+r["d61_90"]+r["d90plus"] > 0]
    dias_calle = max((_dias_calle_from_row(r) for r in rows_vencidos), default=0.0)

    return {
        "nombre": name,
        "total_cartera": total_cartera,
        "no_vencido": summary.get("NO VENCIDO", total_cartera - vencido),
        "vencido": vencido,
        "pct_vencido": pct_vencido,
        "n_clientes": int(summary.get("N CLIENTES", len(clients))),
        "n_clientes_mora": n_clientes_mora,
        "d1_30": d1_30,
        "d31_60": d31_60,
        "d61_90": d61_90,
        "d90plus": d90plus,
        "dias_calle": dias_calle,
        "clientes": clients,  # all clients with invoice detail
    }


def risk_badge(pct):
    if pct >= 30:
        return '<span class="badge badge-red">ALTO</span>'
    elif pct >= 15:
        return '<span class="badge badge-yellow">MEDIO</span>'
    else:
        return '<span class="badge badge-green">BAJO</span>'


def generate_individual_html(e, report_date=""):
    """Genera un informe HTML individual para un ejecutivo con detalle de facturas expandible."""
    pct   = e["pct_vencido"]
    color = COLORS.get(e["nombre"], "#4F8EF7")

    # Construir filas de clientes + facturas expandibles
    client_rows = ""
    for i, c in enumerate(e["clientes"]):
        if c["vencido"] <= 0:
            continue
        uid  = f"c{i}"
        rb   = risk_badge(c["pct_vencido"])
        ninv = len(c.get("invoices", []))
        arrow = f'<span id="arr_{uid}" style="margin-right:6px;cursor:pointer;font-size:11px">▶</span>' if ninv else ""

        client_rows += f"""
        <tr class="client-row" onclick="toggleInv('{uid}')" style="cursor:{'pointer' if ninv else 'default'}">
          <td>{arrow}<span style="font-size:10px;color:#888">{c['rut']}</span></td>
          <td class="client-name">{c['cliente']}</td>
          <td class="num" style="color:#888">{fmt_clp(c['no_vencido'])}</td>
          <td class="num bold">{fmt_clp(c['total'])}</td>
          <td class="num" style="color:#f39c12">{fmt_clp(c['d1_30'])}</td>
          <td class="num" style="color:#e67e22">{fmt_clp(c['d31_60'])}</td>
          <td class="num" style="color:#c0392b">{fmt_clp(c['d61_90'])}</td>
          <td class="num" style="color:#7b241c">{fmt_clp(c['d90plus'])}</td>
          <td class="num bold" style="color:#111111">{fmt_clp(c['vencido'])}</td>
          <td class="num">{c['dias_calle']:.0f} días</td>
          <td>{rb}</td>
          <td class="num" style="color:#888;font-size:11px">{ninv if ninv else '—'}</td>
        </tr>"""

        # Filas de facturas
        if ninv:
            inv_rows = ""
            for inv in c["invoices"]:
                tramo_color = ""
                tramo_label = ""
                if inv["d90plus"] > 0:
                    tramo_color = "#7b241c"; tramo_label = "&gt;90 d."
                elif inv["d61_90"] > 0:
                    tramo_color = "#c0392b"; tramo_label = "61–90 d."
                elif inv["d31_60"] > 0:
                    tramo_color = "#e67e22"; tramo_label = "31–60 d."
                elif inv["d1_30"] > 0:
                    tramo_color = "#f39c12"; tramo_label = "1–30 d."
                dias_atraso = int(inv.get("dias_atraso", 0))
                dias_cell = (f'<strong style="color:{tramo_color}">{dias_atraso} días</strong> '
                             f'<span style="color:{tramo_color};font-size:10px">({tramo_label})</span>'
                             if dias_atraso > 0 and tramo_color else "")
                monto_v = inv["d1_30"] + inv["d31_60"] + inv["d61_90"] + inv["d90plus"]
                inv_rows += f"""<tr class="inv-row">
                  <td colspan="2" style="padding-left:32px;color:#555;font-size:11px">
                    📄 Factura {inv['factura'] or '—'}</td>
                  <td class="num" style="font-size:11px;color:#888">{inv['emision'] or '—'}</td>
                  <td class="num" style="font-size:11px;color:#888">{inv['vencimiento'] or '—'}</td>
                  <td colspan="4" style="text-align:center">{dias_cell}</td>
                  <td class="num bold" style="font-size:11px">{fmt_clp(monto_v)}</td>
                  <td colspan="3"></td>
                </tr>"""
            client_rows += f'<tr id="inv_{uid}" style="display:none"><td colspan="12" style="padding:0"><table style="width:100%;border-radius:0;box-shadow:none;background:#fafbfd">{inv_rows}</table></td></tr>'

    if not client_rows:
        client_rows = '<tr><td colspan="12" style="text-align:center;padding:20px;color:#888">Sin clientes con deuda vencida</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Informe CxC — {e['nombre']}</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F7F5EF;color:#222;font-size:13px}}
  .header{{background:linear-gradient(135deg,#111111,#222222);color:#F5C200;padding:24px 32px}}
  .header h1{{font-size:20px;font-weight:700}}
  .header .sub{{font-size:12px;color:#999999;margin-top:4px}}
  .kpis{{display:flex;gap:14px;padding:20px 32px;flex-wrap:wrap}}
  .kpi{{background:#fff;border-radius:10px;padding:16px 20px;flex:1;min-width:130px;
        box-shadow:0 2px 8px rgba(0,0,0,.07);border-top:4px solid {color}}}
  .kpi.red{{border-top-color:#e74c3c}}.kpi.yellow{{border-top-color:#f39c12}}.kpi.green{{border-top-color:#27ae60}}
  .kpi .label{{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px}}
  .kpi .value{{font-size:18px;font-weight:700;margin-top:5px;color:#111111}}
  .kpi.red .value{{color:#e74c3c}}.kpi.yellow .value{{color:#f39c12}}.kpi.green .value{{color:#27ae60}}
  .section{{padding:0 32px 32px}}
  .title{{font-size:13px;font-weight:700;color:#111111;text-transform:uppercase;
          letter-spacing:.5px;margin-bottom:12px;padding-left:8px;border-left:4px solid {color}}}
  .progress-wrap{{display:flex;align-items:center;gap:12px;padding:12px 32px 20px}}
  .track{{flex:1;height:10px;background:#e8edf3;border-radius:5px;overflow:hidden}}
  .fill{{height:100%;border-radius:5px;background:{color}}}
  .plabel{{font-size:12px;color:#555;min-width:120px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.07);font-size:12px}}
  thead tr{{background:#111111;color:#F5C200}}
  th{{padding:9px 11px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}}
  td{{padding:8px 11px;border-bottom:1px solid #f0f2f5;vertical-align:middle}}
  .client-row:hover{{background:#f0f4fa!important}}
  .client-name{{font-weight:600;color:#111111}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .bold{{font-weight:700}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;text-transform:uppercase}}
  .badge-red{{background:#fde8e8;color:#c0392b}}
  .badge-yellow{{background:#fef3cd;color:#d35400}}
  .badge-green{{background:#e8f8ee;color:#1e8449}}
  .inv-row td{{background:#fafbfd;font-size:11px}}
  .footer{{text-align:center;padding:20px;color:#aaa;font-size:11px}}
  .tip{{font-size:11px;color:#888;padding:8px 32px 0;font-style:italic}}
</style>
</head>
<body>
<div class="header">
  <h1>Informe Cuentas por Cobrar — {e['nombre']}</h1>
  <div class="sub">Fecha: {report_date} &nbsp;|&nbsp; Uso interno — confidencial</div>
</div>

<div class="kpis">
  <div class="kpi"><div class="label">Total Cartera</div><div class="value">{fmt_clp(e['total_cartera'])}</div></div>
  <div class="kpi green"><div class="label">No Vencido</div><div class="value">{fmt_clp(e['no_vencido'])}</div></div>
  <div class="kpi {'red' if pct>=30 else 'yellow' if pct>=15 else 'green'}"><div class="label">Vencido</div><div class="value">{fmt_clp(e['vencido'])}</div></div>
  <div class="kpi {'red' if pct>=30 else 'yellow' if pct>=15 else 'green'}"><div class="label">% Vencido</div><div class="value">{pct:.1f}%</div></div>
  <div class="kpi"><div class="label">Días de Calle</div><div class="value">{e['dias_calle']:.0f} d.</div></div>
  <div class="kpi"><div class="label">Clientes Totales</div><div class="value">{e['n_clientes']}</div></div>
  <div class="kpi"><div class="label">Clientes en Mora</div><div class="value">{e['n_clientes_mora']}</div></div>
</div>

<div class="kpis" style="padding-top:0">
  <div class="kpi"><div class="label">1–30 días</div><div class="value" style="color:#f39c12;font-size:16px">{fmt_clp(e['d1_30'])}</div></div>
  <div class="kpi"><div class="label">31–60 días</div><div class="value" style="color:#e67e22;font-size:16px">{fmt_clp(e['d31_60'])}</div></div>
  <div class="kpi"><div class="label">61–90 días</div><div class="value" style="color:#c0392b;font-size:16px">{fmt_clp(e['d61_90'])}</div></div>
  <div class="kpi"><div class="label">&gt;90 días</div><div class="value" style="color:#7b241c;font-size:16px">{fmt_clp(e['d90plus'])}</div></div>
</div>

<div class="progress-wrap">
  <div class="track"><div class="fill" style="width:{min(pct,100):.1f}%"></div></div>
  <span class="plabel">{pct:.1f}% cartera vencida</span>
</div>

<div class="section">
  <div class="title">Clientes con Deuda Vencida</div>
  <p class="tip">Haz clic en una fila para ver el detalle de facturas ▶</p>
  <br>
  <table>
    <thead><tr>
      <th>RUT</th><th>Cliente</th><th>No Vencido</th><th>Total Cartera</th>
      <th>1–30 d.</th><th>31–60 d.</th><th>61–90 d.</th><th>&gt;90 d.</th>
      <th>Total Vencido</th><th>Días Calle</th><th>Riesgo</th><th>Fact.</th>
    </tr></thead>
    <tbody>{client_rows}</tbody>
  </table>
</div>

<div class="footer">Informe CxC {report_date} · Cervecería Kross · Confidencial</div>

<script>
function toggleInv(uid) {{
  var row = document.getElementById('inv_' + uid);
  var arr = document.getElementById('arr_' + uid);
  if (!row) return;
  var hidden = row.style.display === 'none';
  row.style.display = hidden ? 'table-row' : 'none';
  if (arr) arr.textContent = hidden ? '▼' : '▶';
}}
</script>
</body></html>"""


KROSS_LOGO_URL = "https://raw.githubusercontent.com/CarlosKross/cxc-dashboard/main/kross_logo.png.png"


def generate_client_collection_email(cliente, rut, ejecutivo, facturas, total_vencido, report_date):
    """Genera email de cobranza para enviar directamente al cliente."""
    logo_html = (f'<img src="{KROSS_LOGO_URL}" '
                 f'width="80" height="80" style="flex-shrink:0;display:block" '
                 f'alt="Cervecería Kross"/>')
    inv_rows = ""
    for inv in facturas:
        monto_v = inv["d1_30"] + inv["d31_60"] + inv["d61_90"] + inv["d90plus"]
        if monto_v <= 0:
            continue
        dias = int(inv.get("dias_atraso", inv.get("dias_mora", 0)))
        if inv["d90plus"] > 0:    color_d, tramo = "#7b241c", "+90 días"
        elif inv["d61_90"] > 0:   color_d, tramo = "#c0392b", "61–90 días"
        elif inv["d31_60"] > 0:   color_d, tramo = "#e67e22", "31–60 días"
        else:                      color_d, tramo = "#f39c12", "1–30 días"

        inv_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0ece0;font-size:13px">
            Factura N° <strong>{inv['factura'] or '—'}</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0ece0;font-size:13px;color:#555">
            {inv['emision'] or '—'}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0ece0;font-size:13px;color:#555">
            {inv['vencimiento'] or '—'}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0ece0;font-size:13px;
              color:{color_d};font-weight:700;text-align:center">
            {dias} días<br><span style="font-size:10px;font-weight:400">({tramo})</span></td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0ece0;font-size:13px;
              font-weight:700;text-align:right">{fmt_clp(monto_v)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">
<title>Aviso de Saldo Pendiente — Cervecería Kross</title></head>
<body style="margin:0;padding:0;background:#F7F5EF;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:640px;margin:0 auto;padding:24px">

  <!-- Header Kross -->
  <div style="background:#111111;border-radius:10px 10px 0 0;border-bottom:4px solid #F5C200">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="padding:20px 28px;vertical-align:middle">
          <div style="font-size:24px;font-weight:900;color:#F5C200;text-transform:uppercase;
                      letter-spacing:2px;line-height:1">Cervecería Kross</div>
          <div style="font-size:11px;color:#aaa;margin-top:6px;font-weight:600;
                      letter-spacing:.5px;text-transform:uppercase">
            Área de Cobranza · {report_date}</div>
        </td>
        <td style="padding:12px 20px 12px 0;vertical-align:middle;text-align:right;width:100px">
          {logo_html}
        </td>
      </tr>
    </table>
  </div>

  <!-- Cuerpo -->
  <div style="background:#fff;padding:28px;border-radius:0 0 10px 10px;
              box-shadow:0 2px 12px rgba(0,0,0,.08)">

    <p style="font-size:15px;color:#111;margin-bottom:8px">Estimado/a cliente,</p>
    <p style="font-size:14px;color:#444;line-height:1.6;margin-bottom:20px">
      Nos comunicamos para informarle que registra facturas con saldo pendiente de pago.
      Le solicitamos gestionar la regularización a la brevedad posible.
    </p>

    <!-- Resumen deuda -->
    <div style="background:#F7F5EF;border-left:4px solid #F5C200;padding:14px 18px;
                border-radius:0 8px 8px 0;margin-bottom:24px">
      <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px">
        Total saldo vencido</div>
      <div style="font-size:28px;font-weight:900;color:#111;margin-top:2px">
        {fmt_clp(total_vencido)}</div>
      <div style="font-size:12px;color:#666;margin-top:4px">
        Cliente: <strong>{cliente}</strong> &nbsp;·&nbsp; RUT: {rut}
      </div>
    </div>

    <!-- Tabla facturas -->
    <p style="font-size:13px;font-weight:700;color:#111;text-transform:uppercase;
              letter-spacing:.5px;margin-bottom:10px">Detalle de facturas vencidas</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;border-radius:8px;
                  overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <thead>
        <tr style="background:#111;color:#F5C200">
          <th style="padding:9px 12px;text-align:left;font-size:11px;
                     text-transform:uppercase;letter-spacing:.3px">Documento</th>
          <th style="padding:9px 12px;text-align:left;font-size:11px;
                     text-transform:uppercase;letter-spacing:.3px">Emisión</th>
          <th style="padding:9px 12px;text-align:left;font-size:11px;
                     text-transform:uppercase;letter-spacing:.3px">Vencimiento</th>
          <th style="padding:9px 12px;text-align:center;font-size:11px;
                     text-transform:uppercase;letter-spacing:.3px">Días vencida</th>
          <th style="padding:9px 12px;text-align:right;font-size:11px;
                     text-transform:uppercase;letter-spacing:.3px">Monto</th>
        </tr>
      </thead>
      <tbody>{inv_rows}</tbody>
      <tfoot>
        <tr style="background:#F7F5EF">
          <td colspan="4" style="padding:10px 12px;font-weight:700;font-size:13px">
            Total vencido</td>
          <td style="padding:10px 12px;font-weight:900;font-size:15px;
                     text-align:right;color:#111">{fmt_clp(total_vencido)}</td>
        </tr>
      </tfoot>
    </table>

    <!-- Instrucciones pago -->
    <div style="margin-top:24px;padding:16px;background:#fffbea;border-radius:8px;
                border:1px solid #F5C200">
      <p style="font-size:13px;font-weight:700;color:#111;margin-bottom:6px">
        💳 Información de pago</p>
      <p style="font-size:13px;color:#555;margin:0;line-height:1.6">
        Para coordinar el pago o consultar sobre esta deuda, por favor contáctese con
        su ejecutivo de cuenta: <strong>{ejecutivo}</strong>.<br>
        También puede escribir a <strong>cobranzas@kross.cl</strong>.
      </p>
    </div>

    <p style="font-size:12px;color:#aaa;margin-top:24px;text-align:center">
      Este es un aviso automático del sistema de cobranza de Cervecería Kross.<br>
      Si ya realizó el pago, por favor ignore este mensaje.
    </p>
  </div>
</div>
</body></html>"""


def semaforo_class(pct):
    if pct >= 30:
        return "card-red"
    elif pct >= 15:
        return "card-yellow"
    return "card-green"


def generate_email_body(e, report_date=""):
    """HTML optimizado para enviar como cuerpo de correo: sin JS, facturas visibles, inline styles."""
    pct   = e["pct_vencido"]
    color = COLORS.get(e["nombre"], "#4F8EF7")
    sc_color = "#e74c3c" if pct >= 30 else "#f39c12" if pct >= 15 else "#27ae60"

    def kpi_card(label, value, border_color="#ddd", val_color="#111111"):
        return (f'<td style="padding:12px 16px;background:#fff;border-radius:8px;'
                f'border-top:4px solid {border_color};min-width:110px;text-align:center;'
                f'box-shadow:0 2px 6px rgba(0,0,0,.07);vertical-align:top">'
                f'<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px">{label}</div>'
                f'<div style="font-size:18px;font-weight:700;color:{val_color};margin-top:4px">{value}</div></td>')

    kpis_row = (
        kpi_card("Total Cartera",   fmt_clp(e["total_cartera"]), color) +
        kpi_card("No Vencido",      fmt_clp(e["no_vencido"]),    "#27ae60", "#27ae60") +
        kpi_card("Vencido",         fmt_clp(e["vencido"]),       sc_color,  sc_color) +
        kpi_card("% Vencido",       f"{pct:.1f}%",               sc_color,  sc_color) +
        kpi_card("Días de Calle",   f"{e['dias_calle']:.0f} d.", color) +
        kpi_card("Clientes Mora",   str(e["n_clientes_mora"]),   color)
    )

    tramos_row = (
        kpi_card("1–30 días",   fmt_clp(e["d1_30"]),   "#f39c12", "#f39c12") +
        kpi_card("31–60 días",  fmt_clp(e["d31_60"]),  "#e67e22", "#e67e22") +
        kpi_card("61–90 días",  fmt_clp(e["d61_90"]),  "#c0392b", "#c0392b") +
        kpi_card("&gt;90 días", fmt_clp(e["d90plus"]), "#7b241c", "#7b241c")
    )

    # Filas de clientes + facturas (todas visibles)
    client_rows = ""
    th = ('background:#111111;color:#F5C200;padding:8px 10px;text-align:left;'
          'font-size:10px;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap')
    th_r = th + ';text-align:right'

    for c in e["clientes"]:
        if c["vencido"] <= 0:
            continue
        rb_color = "#c0392b" if c["pct_vencido"] >= 30 else "#d35400" if c["pct_vencido"] >= 15 else "#1e8449"
        rb_bg    = "#fde8e8" if c["pct_vencido"] >= 30 else "#fef3cd" if c["pct_vencido"] >= 15 else "#e8f8ee"
        rb_txt   = "ALTO"   if c["pct_vencido"] >= 30 else "MEDIO"   if c["pct_vencido"] >= 15 else "BAJO"
        td = 'padding:7px 10px;border-bottom:1px solid #f0f2f5;vertical-align:middle;font-size:12px'
        td_r = td + ';text-align:right;font-variant-numeric:tabular-nums'

        client_rows += (
            f'<tr style="background:#f7f9fc">'
            f'<td style="{td};font-weight:700;color:#111111" colspan="2">{c["cliente"]}</td>'
            f'<td style="{td};font-size:10px;color:#888">{c["rut"]}</td>'
            f'<td style="{td_r}">{fmt_clp(c["no_vencido"])}</td>'
            f'<td style="{td_r};font-weight:700">{fmt_clp(c["total"])}</td>'
            f'<td style="{td_r};color:#f39c12">{fmt_clp(c["d1_30"])}</td>'
            f'<td style="{td_r};color:#e67e22">{fmt_clp(c["d31_60"])}</td>'
            f'<td style="{td_r};color:#c0392b">{fmt_clp(c["d61_90"])}</td>'
            f'<td style="{td_r};color:#7b241c">{fmt_clp(c["d90plus"])}</td>'
            f'<td style="{td_r};font-weight:700">{fmt_clp(c["vencido"])}</td>'
            f'<td style="{td_r}">{c["dias_calle"]:.0f} días</td>'
            f'<td style="{td};text-align:center"><span style="background:{rb_bg};color:{rb_color};'
            f'padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">{rb_txt}</span></td>'
            f'</tr>'
        )
        for inv in c.get("invoices", []):
            monto_v = inv["d1_30"] + inv["d31_60"] + inv["d61_90"] + inv["d90plus"]
            if monto_v <= 0:
                continue
            if inv["d90plus"] > 0:    tramo_c, tramo_t = "#7b241c", "&gt;90 d."
            elif inv["d61_90"] > 0:   tramo_c, tramo_t = "#c0392b", "61–90 d."
            elif inv["d31_60"] > 0:   tramo_c, tramo_t = "#e67e22", "31–60 d."
            else:                      tramo_c, tramo_t = "#f39c12", "1–30 d."
            dias_atraso = int(inv.get("dias_atraso", 0))
            dias_cell = (f'<strong style="color:{tramo_c}">{dias_atraso} días</strong> '
                         f'<span style="color:{tramo_c};font-size:10px">({tramo_t})</span>'
                         if dias_atraso > 0 else tramo_t)
            client_rows += (
                f'<tr style="background:#fff">'
                f'<td style="{td};padding-left:24px;color:#888;font-size:11px">📄</td>'
                f'<td style="{td};font-size:11px;color:#555">Fact. {inv["factura"] or "—"}</td>'
                f'<td style="{td};font-size:11px;color:#888">{inv["emision"] or "—"}</td>'
                f'<td style="{td};font-size:11px;color:#888" colspan="2">{inv["vencimiento"] or "—"}</td>'
                f'<td colspan="4" style="{td};text-align:center;font-size:11px">{dias_cell}</td>'
                f'<td style="{td_r};font-size:11px;font-weight:700">{fmt_clp(monto_v)}</td>'
                f'<td colspan="2"></td>'
                f'</tr>'
            )

    if not client_rows:
        client_rows = f'<tr><td colspan="12" style="text-align:center;padding:20px;color:#888">Sin clientes con deuda vencida</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Informe CxC — {e['nombre']}</title></head>
<body style="margin:0;padding:0;background:#F7F5EF;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:900px;margin:0 auto;padding:20px">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#111111,#222222);color:#F5C200;padding:24px 32px;border-radius:10px 10px 0 0">
    <div style="font-size:20px;font-weight:700">Informe Cuentas por Cobrar — {e['nombre']}</div>
    <div style="font-size:12px;color:#999999;margin-top:4px">Fecha: {report_date} &nbsp;|&nbsp; Uso interno — confidencial</div>
  </div>

  <!-- KPIs -->
  <div style="background:#F7F5EF;padding:16px 0">
    <table style="border-collapse:separate;border-spacing:10px;width:100%"><tr>{kpis_row}</tr></table>
    <table style="border-collapse:separate;border-spacing:10px;width:100%"><tr>{tramos_row}</tr></table>
  </div>

  <!-- Barra progreso -->
  <div style="background:#fff;padding:12px 20px;border-radius:6px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
    <div style="flex:1;height:10px;background:#e8edf3;border-radius:5px;overflow:hidden">
      <div style="height:100%;width:{min(pct,100):.1f}%;background:{sc_color};border-radius:5px"></div>
    </div>
    <span style="font-size:12px;color:#555;min-width:130px">{pct:.1f}% cartera vencida</span>
  </div>

  <!-- Tabla clientes -->
  <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.07);font-size:12px">
    <thead><tr>
      <th style="{th}" colspan="2">Cliente</th>
      <th style="{th}">RUT</th>
      <th style="{th_r}">No Vencido</th>
      <th style="{th_r}">Total</th>
      <th style="{th_r}">1–30 d.</th>
      <th style="{th_r}">31–60 d.</th>
      <th style="{th_r}">61–90 d.</th>
      <th style="{th_r}">&gt;90 d.</th>
      <th style="{th_r}">Vencido</th>
      <th style="{th_r}">Días C.</th>
      <th style="{th}">Riesgo</th>
    </tr></thead>
    <tbody>{client_rows}</tbody>
  </table>

  <div style="text-align:center;padding:20px;color:#aaa;font-size:11px">
    Informe CxC {report_date} · Cervecería Kross · Confidencial
  </div>
</div>
</body></html>"""


def generate_html(exec_data, report_date="18/03/2026", sin_exec_rows=None):
    total_global = sum(e["total_cartera"] for e in exec_data)
    vencido_global = sum(e["vencido"] for e in exec_data)
    pct_global = (vencido_global / total_global * 100) if total_global else 0

    nombres = [e["nombre"] for e in exec_data]
    colors = [COLORS.get(n, "#888") for n in nombres]

    # Chart data
    chart_tramos = {
        "labels": nombres,
        "d1_30": [e["d1_30"] for e in exec_data],
        "d31_60": [e["d31_60"] for e in exec_data],
        "d61_90": [e["d61_90"] for e in exec_data],
        "d90plus": [e["d90plus"] for e in exec_data],
    }

    chart_cartera = {
        "labels": nombres,
        "total": [e["total_cartera"] for e in exec_data],
        "vencido": [e["vencido"] for e in exec_data],
    }

    # Sin ejecutivo section
    sin_exec_html = ""
    if sin_exec_rows:
        sin_clients = aggregate_by_client(sin_exec_rows)
        def _dc_row(r):
            if r.get("dias_mora",0) > 0: return r["dias_mora"]
            if r["d90plus"] > 0: return 120.0
            if r["d61_90"]  > 0: return 75.0
            if r["d31_60"]  > 0: return 45.0
            if r["d1_30"]   > 0: return 15.0
            return 0.0
        for c in sin_clients:
            c_rows = [r for r in sin_exec_rows if r["rut"]==c["rut"]
                      and r["d1_30"]+r["d31_60"]+r["d61_90"]+r["d90plus"] > 0]
            c["dias_calle"] = (sum(_dc_row(r) for r in c_rows)/len(c_rows) if c_rows else 0)
        sin_client_rows = ""
        for c in sin_clients:
            rb = risk_badge(c["pct_vencido"])
            sin_client_rows += f"""
            <tr>
              <td>{c['rut']}</td><td class="client-name">{c['cliente']}</td>
              <td class="num muted">{fmt_clp(c['no_vencido'])}</td>
              <td class="num muted">{fmt_clp(c['total'])}</td>
              <td class="num">{fmt_clp(c['d1_30']) if c['d1_30'] else '—'}</td>
              <td class="num">{fmt_clp(c['d31_60']) if c['d31_60'] else '—'}</td>
              <td class="num">{fmt_clp(c['d61_90']) if c['d61_90'] else '—'}</td>
              <td class="num">{fmt_clp(c['d90plus']) if c['d90plus'] else '—'}</td>
              <td class="num bold">{fmt_clp(c['vencido'])}</td>
              <td class="num">{c['dias_calle']:.0f} días</td>
              <td>{rb}</td>
            </tr>"""
            for inv in c.get("invoices", []):
                vencido_inv = inv["d1_30"]+inv["d31_60"]+inv["d61_90"]+inv["d90plus"]
                if inv["d90plus"] > 0:   _tc, _tb = "#7b241c", "⛔ +90d"
                elif inv["d61_90"] > 0:  _tc, _tb = "#c0392b", "🔴 61-90d"
                elif inv["d31_60"] > 0:  _tc, _tb = "#e67e22", "🟠 31-60d"
                elif inv["d1_30"] > 0:   _tc, _tb = "#f39c12", "🟡 1-30d"
                else:                    _tc, _tb = "#888", "—"
                _da = int(inv.get("dias_atraso", 0))
                _dc = (f'<strong style="color:{_tc}">{_da} días</strong> '
                       f'<span style="font-size:10px;color:{_tc}">{_tb}</span>'
                       if _da > 0 and _tc != "#888" else _tb)
                sin_client_rows += f"""
            <tr class="inv-row">
              <td colspan="2"><span class="inv-cell">↳ Fac. <strong>{inv['factura']}</strong> &nbsp; Emis: {inv['emision']} &nbsp; Venc: {inv['vencimiento']}</span></td>
              <td class="inv-cell" colspan="2">{_dc}</td>
              <td class="num inv-cell">{fmt_clp(inv['d1_30']) if inv['d1_30'] else '—'}</td>
              <td class="num inv-cell">{fmt_clp(inv['d31_60']) if inv['d31_60'] else '—'}</td>
              <td class="num inv-cell">{fmt_clp(inv['d61_90']) if inv['d61_90'] else '—'}</td>
              <td class="num inv-cell">{fmt_clp(inv['d90plus']) if inv['d90plus'] else '—'}</td>
              <td class="num inv-cell bold">{fmt_clp(vencido_inv)}</td>
              <td colspan="2"></td>
            </tr>"""
        sin_exec_html = f"""
        <div class="exec-section sin-exec-section">
          <div class="exec-header" style="border-left:5px solid #f39c12;">
            <div class="exec-name" style="color:#d35400">⚠️ Sin Ejecutivo Asignado</div>
            <div class="exec-kpis">
              <div class="kpi-box card-yellow"><div class="kpi-label">Clientes</div><div class="kpi-value">{len(sin_clients)}</div></div>
              <div class="kpi-box card-yellow"><div class="kpi-label">Total Vencido</div><div class="kpi-value">{fmt_clp(sum(c['vencido'] for c in sin_clients))}</div></div>
            </div>
          </div>
          <div class="client-table-wrap">
            <table class="client-table">
              <thead><tr>
                <th>RUT / Factura</th><th>Cliente</th><th>No Vencido</th><th>Total Cartera</th>
                <th>1–30 días</th><th>31–60 días</th><th>61–90 días</th><th>&gt;90 días</th>
                <th>Total Vencido</th><th>Días Calle</th><th>Riesgo</th>
              </tr></thead>
              <tbody>{sin_client_rows}</tbody>
            </table>
          </div>
        </div>"""

    def build_client_detail(clients, uid_prefix):
        """Build collapsible client+invoice rows HTML."""
        html = ""
        for ci, c in enumerate(clients):
            if c["vencido"] <= 0:
                continue
            rb = risk_badge(c["pct_vencido"])
            uid = f"{uid_prefix}_{ci}"
            # Invoice sub-rows (only overdue)
            inv_rows = ""
            for inv in c.get("invoices", []):
                vencido_inv = inv["d1_30"] + inv["d31_60"] + inv["d61_90"] + inv["d90plus"]
                if inv["d90plus"] > 0:
                    tramo_color, tramo_badge = "#7b241c", "⛔ +90d"
                elif inv["d61_90"] > 0:
                    tramo_color, tramo_badge = "#c0392b", "🔴 61-90d"
                elif inv["d31_60"] > 0:
                    tramo_color, tramo_badge = "#e67e22", "🟠 31-60d"
                elif inv["d1_30"] > 0:
                    tramo_color, tramo_badge = "#f39c12", "🟡 1-30d"
                else:
                    tramo_color, tramo_badge = "#888", "—"
                dias_atraso = int(inv.get("dias_atraso", 0))
                dias_cell = (f'<strong style="color:{tramo_color}">{dias_atraso} días</strong> '
                             f'<span style="font-size:10px;color:{tramo_color}">{tramo_badge}</span>'
                             if dias_atraso > 0 and tramo_color != "#888" else tramo_badge)
                inv_rows += f"""
                <tr class="inv-row" id="inv-{uid}">
                  <td></td>
                  <td class="inv-cell">↳ Fac. <strong>{inv['factura']}</strong></td>
                  <td class="inv-cell">{inv['emision']}</td>
                  <td class="inv-cell">{inv['vencimiento']}</td>
                  <td class="inv-cell">{dias_cell}</td>
                  <td class="num inv-cell">{fmt_clp(inv['d1_30']) if inv['d1_30'] else '—'}</td>
                  <td class="num inv-cell">{fmt_clp(inv['d31_60']) if inv['d31_60'] else '—'}</td>
                  <td class="num inv-cell">{fmt_clp(inv['d61_90']) if inv['d61_90'] else '—'}</td>
                  <td class="num inv-cell">{fmt_clp(inv['d90plus']) if inv['d90plus'] else '—'}</td>
                  <td class="num inv-cell bold">{fmt_clp(vencido_inv)}</td>
                  <td class="inv-cell"></td>
                  <td class="inv-cell"></td>
                </tr>"""
            toggle = f"onclick=\"toggleInv('{uid}')\"" if inv_rows else ""
            cursor = "cursor:pointer" if inv_rows else ""
            arrow = f"<span id='arr-{uid}' style='margin-right:6px;font-size:10px'>▶</span>" if inv_rows else "<span style='margin-right:14px'></span>"
            html += f"""
            <tr class="client-row" style="{cursor}" {toggle}>
              <td>{arrow}{c['rut']}</td>
              <td class="client-name">{c['cliente']}</td>
              <td class="num muted">{fmt_clp(c['no_vencido'])}</td>
              <td class="num muted">{fmt_clp(c['total'])}</td>
              <td class="num">{fmt_clp(c['d1_30']) if c['d1_30'] else '—'}</td>
              <td class="num">{fmt_clp(c['d31_60']) if c['d31_60'] else '—'}</td>
              <td class="num">{fmt_clp(c['d61_90']) if c['d61_90'] else '—'}</td>
              <td class="num">{fmt_clp(c['d90plus']) if c['d90plus'] else '—'}</td>
              <td class="num bold">{fmt_clp(c['vencido'])}</td>
              <td class="num">{c['dias_calle']:.0f} días</td>
              <td>{rb}</td>
              <td class="num muted">{len(c.get('invoices',[]))} fac.</td>
            </tr>{inv_rows}"""
        return html

    # Executive cards HTML
    exec_cards_html = ""
    for e in sorted(exec_data, key=lambda x: -x["vencido"]):
        pct = e["pct_vencido"]
        color = COLORS.get(e["nombre"], "#888")
        sc = semaforo_class(pct)
        uid = e["nombre"].replace(" ", "_")
        client_rows = build_client_detail(e["clientes"], uid)

        exec_cards_html += f"""
        <div class="exec-section">
          <div class="exec-header" style="border-left: 5px solid {color};">
            <div class="exec-name">{e['nombre']}</div>
            <div class="exec-kpis">
              <div class="kpi-box {sc}">
                <div class="kpi-label">Total Cartera</div>
                <div class="kpi-value">{fmt_clp(e['total_cartera'])}</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">No Vencido</div>
                <div class="kpi-value green">{fmt_clp(e['no_vencido'])}</div>
              </div>
              <div class="kpi-box {sc}">
                <div class="kpi-label">Vencido</div>
                <div class="kpi-value">{fmt_clp(e['vencido'])}</div>
              </div>
              <div class="kpi-box {sc}">
                <div class="kpi-label">% Vencido</div>
                <div class="kpi-value">{pct:.1f}%</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">Clientes Totales</div>
                <div class="kpi-value">{e['n_clientes']}</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">Clientes en Mora</div>
                <div class="kpi-value">{e['n_clientes_mora']}</div>
              </div>
              <div class="kpi-box {'card-red' if e['dias_calle']>=60 else 'card-yellow' if e['dias_calle']>=30 else 'card-green'}">
                <div class="kpi-label">Días de Calle</div>
                <div class="kpi-value">{e['dias_calle']:.0f} días</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">1–30 días</div>
                <div class="kpi-value orange">{fmt_clp(e['d1_30'])}</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">31–60 días</div>
                <div class="kpi-value orange">{fmt_clp(e['d31_60'])}</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">61–90 días</div>
                <div class="kpi-value red">{fmt_clp(e['d61_90'])}</div>
              </div>
              <div class="kpi-box">
                <div class="kpi-label">&gt;90 días</div>
                <div class="kpi-value red">{fmt_clp(e['d90plus'])}</div>
              </div>
            </div>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar-track">
              <div class="progress-bar-fill" style="width:{min(pct,100):.1f}%; background:{color};"></div>
            </div>
            <span class="progress-label">{pct:.1f}% vencido</span>
          </div>
          <div class="client-table-wrap">
            <table class="client-table">
              <thead>
                <tr>
                  <th>RUT / Factura</th>
                  <th>Cliente</th>
                  <th>No Vencido</th>
                  <th>Total Cartera</th>
                  <th>1–30 días</th>
                  <th>31–60 días</th>
                  <th>61–90 días</th>
                  <th>&gt;90 días</th>
                  <th>Total Vencido</th>
                  <th>Días Calle</th>
                  <th>Riesgo</th>
                  <th>Facturas</th>
                </tr>
              </thead>
              <tbody>{client_rows if client_rows else '<tr><td colspan="12" class="empty-msg">Sin deuda vencida</td></tr>'}</tbody>
            </table>
          </div>
        </div>"""

    ranking_rows = ""
    for i, e in enumerate(sorted(exec_data, key=lambda x: -x["pct_vencido"]), 1):
        pct = e["pct_vencido"]
        rb = risk_badge(pct)
        color = COLORS.get(e["nombre"], "#888")
        ranking_rows += f"""
        <tr>
          <td class="rank-num">#{i}</td>
          <td><span class="dot" style="background:{color};"></span>{e['nombre']}</td>
          <td class="num">{fmt_clp(e['total_cartera'])}</td>
          <td class="num">{fmt_clp(e['vencido'])}</td>
          <td class="num">{fmt_clp(e['d1_30'])}</td>
          <td class="num">{fmt_clp(e['d31_60'])}</td>
          <td class="num">{fmt_clp(e['d61_90'])}</td>
          <td class="num">{fmt_clp(e['d90plus'])}</td>
          <td class="num bold">{pct:.1f}%</td>
          <td class="num">{e['dias_calle']:.0f} días</td>
          <td>{rb}</td>
        </tr>"""

    chart_data_json = json.dumps({
        "tramos": chart_tramos,
        "cartera": chart_cartera,
        "colors": colors,
    })

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard CxC — {report_date}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #F7F5EF; color: #222; font-size: 13px; }}

  /* HEADER */
  .header {{ background: linear-gradient(135deg, #111111 0%, #222222 100%); color: #F5C200; padding: 24px 32px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
  .header .subtitle {{ font-size: 12px; color: #999999; margin-top: 4px; }}

  /* GLOBAL KPIs */
  .global-kpis {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .gkpi {{ background: #fff; border-radius: 10px; padding: 18px 24px; flex: 1; min-width: 160px;
           box-shadow: 0 2px 8px rgba(0,0,0,.07); border-top: 4px solid #222222; }}
  .gkpi .label {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: .5px; }}
  .gkpi .value {{ font-size: 22px; font-weight: 700; margin-top: 6px; color: #111111; }}
  .gkpi.danger {{ border-top-color: #e74c3c; }}
  .gkpi.danger .value {{ color: #e74c3c; }}
  .gkpi.warning {{ border-top-color: #f39c12; }}
  .gkpi.warning .value {{ color: #f39c12; }}
  .gkpi.safe {{ border-top-color: #27ae60; }}
  .gkpi.safe .value {{ color: #27ae60; }}

  /* CHARTS */
  .charts-row {{ display: flex; gap: 16px; padding: 0 32px 20px; flex-wrap: wrap; }}
  .chart-box {{ background: #fff; border-radius: 10px; padding: 20px; flex: 1; min-width: 320px;
               box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  .chart-box h3 {{ font-size: 13px; font-weight: 600; color: #111111; margin-bottom: 14px;
                  text-transform: uppercase; letter-spacing: .5px; }}
  .chart-box canvas {{ max-height: 260px; }}

  /* RANKING TABLE */
  .ranking-wrap {{ padding: 0 32px 20px; }}
  .section-title {{ font-size: 14px; font-weight: 700; color: #111111; text-transform: uppercase;
                   letter-spacing: .5px; margin-bottom: 12px; padding-left: 8px;
                   border-left: 4px solid #222222; }}
  .rank-table {{ width: 100%; border-collapse: collapse; background: #fff;
                border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  .rank-table thead tr {{ background: #111111; color: #F5C200; }}
  .rank-table th {{ padding: 10px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: .4px;
                   font-weight: 600; }}
  .rank-table td {{ padding: 10px 12px; border-bottom: 1px solid #f0f2f5; vertical-align: middle; }}
  .rank-table tbody tr:hover {{ background: #f7f9fc; }}
  .rank-num {{ font-weight: 700; color: #222222; font-size: 14px; }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }}

  /* EXECUTIVE SECTIONS */
  .exec-sections {{ padding: 0 32px 32px; display: flex; flex-direction: column; gap: 20px; }}
  .exec-section {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }}
  .exec-header {{ padding: 18px 24px; background: #f7f9fc; }}
  .exec-name {{ font-size: 16px; font-weight: 700; color: #111111; margin-bottom: 14px; }}
  .exec-kpis {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .kpi-box {{ background: #fff; border-radius: 8px; padding: 10px 16px; min-width: 120px;
             box-shadow: 0 1px 4px rgba(0,0,0,.06); border: 1px solid #e8edf3; }}
  .kpi-box.card-red {{ border-color: #e74c3c; background: #fdf2f2; }}
  .kpi-box.card-yellow {{ border-color: #f39c12; background: #fdf7ec; }}
  .kpi-box.card-green {{ border-color: #27ae60; background: #f0faf4; }}
  .kpi-label {{ font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: .4px; }}
  .kpi-value {{ font-size: 15px; font-weight: 700; color: #111111; margin-top: 3px; }}
  .kpi-value.green {{ color: #27ae60; }}
  .kpi-value.orange {{ color: #f39c12; }}
  .kpi-value.red {{ color: #e74c3c; }}

  /* PROGRESS BAR */
  .progress-bar-container {{ padding: 10px 24px; display: flex; align-items: center; gap: 12px; }}
  .progress-bar-track {{ flex: 1; height: 8px; background: #e8edf3; border-radius: 4px; overflow: hidden; }}
  .progress-bar-fill {{ height: 100%; border-radius: 4px; transition: width .3s; }}
  .progress-label {{ font-size: 11px; color: #666; min-width: 90px; }}

  /* CLIENT TABLE */
  .client-table-wrap {{ padding: 0 24px 20px; overflow-x: auto; }}
  .client-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .client-table thead tr {{ background: #222222; color: #fff; }}
  .client-table th {{ padding: 8px 10px; text-align: left; font-weight: 600; font-size: 11px;
                     text-transform: uppercase; letter-spacing: .3px; }}
  .client-table td {{ padding: 7px 10px; border-bottom: 1px solid #f0f2f5; vertical-align: middle; }}
  .client-table tbody tr:hover {{ background: #f7f9fc; }}
  .client-name {{ font-weight: 600; color: #111111; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .bold {{ font-weight: 700; }}
  .muted {{ color: #999; }}
  .client-row {{ background: #fff; }}
  .inv-row {{ background: #f7f9fc; }}
  .inv-cell {{ font-size: 11px; color: #555; padding: 5px 10px !important; }}
  .empty-msg {{ text-align: center; padding: 20px; color: #aaa; }}
  .sin-exec-section {{ background: #fff8f0; border: 1px dashed #f39c12; border-radius:10px; margin-bottom:16px; }}

  /* BADGES */
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px;
           font-weight: 700; text-transform: uppercase; letter-spacing: .4px; }}
  .badge-red {{ background: #fde8e8; color: #c0392b; }}
  .badge-yellow {{ background: #fef3cd; color: #d35400; }}
  .badge-green {{ background: #e8f8ee; color: #1e8449; }}

  /* FOOTER */
  .footer {{ text-align: center; padding: 20px; color: #aaa; font-size: 11px; }}

  @media print {{
    body {{ background: #fff; }}
    .charts-row {{ break-inside: avoid; }}
    .exec-section {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Dashboard Cuentas por Cobrar</h1>
  <div class="subtitle">Informe al {report_date} &nbsp;|&nbsp; Empresa: Todas &nbsp;|&nbsp; División: Todas</div>
</div>

<!-- GLOBAL KPIs -->
<div class="global-kpis">
  <div class="gkpi safe">
    <div class="label">Total Cartera</div>
    <div class="value">{fmt_clp(total_global)}</div>
  </div>
  <div class="gkpi safe">
    <div class="label">No Vencido</div>
    <div class="value">{fmt_clp(total_global - vencido_global)}</div>
  </div>
  <div class="gkpi danger">
    <div class="label">Total Vencido</div>
    <div class="value">{fmt_clp(vencido_global)}</div>
  </div>
  <div class="gkpi {'danger' if pct_global >= 30 else 'warning' if pct_global >= 15 else 'safe'}">
    <div class="label">% Cartera Vencida</div>
    <div class="value">{pct_global:.1f}%</div>
  </div>
  <div class="gkpi">
    <div class="label">Ejecutivos</div>
    <div class="value">{len(exec_data)}</div>
  </div>
  <div class="gkpi warning">
    <div class="label">Días de Calle Promedio</div>
    <div class="value">{(sum(e['dias_calle'] for e in exec_data)/len(exec_data) if exec_data else 0):.0f} días</div>
  </div>
</div>

<!-- CHARTS -->
<div class="charts-row">
  <div class="chart-box">
    <h3>Cartera Vencida por Ejecutivo (Tramos de mora)</h3>
    <canvas id="chartTramos"></canvas>
  </div>
  <div class="chart-box">
    <h3>Total Cartera vs Vencido por Ejecutivo</h3>
    <canvas id="chartCartera"></canvas>
  </div>
</div>

<!-- RANKING -->
<div class="ranking-wrap">
  <div class="section-title">Ranking de Ejecutivos — Mayor a Menor % Vencido</div>
  <table class="rank-table">
    <thead>
      <tr>
        <th>#</th><th>Ejecutivo</th><th>Total Cartera</th><th>Total Vencido</th>
        <th>1–30 días</th><th>31–60 días</th><th>61–90 días</th><th>&gt;90 días</th>
        <th>% Vencido</th><th>Días Calle</th><th>Riesgo</th>
      </tr>
    </thead>
    <tbody>{ranking_rows}</tbody>
  </table>
</div>

<!-- EXECUTIVE DETAIL -->
<div class="exec-sections">
  <div class="section-title">Detalle por Ejecutivo</div>
  {exec_cards_html}
  {sin_exec_html}
</div>

<div class="footer">Generado automáticamente · Informe CxC {report_date}</div>

<script>
function toggleInv(uid) {{
  const rows = document.querySelectorAll('#inv-' + uid);
  const arr  = document.getElementById('arr-' + uid);
  const hidden = rows.length > 0 && rows[0].style.display === 'none';
  rows.forEach(r => r.style.display = hidden ? '' : 'none');
  if (arr) arr.textContent = hidden ? '▼' : '▶';
}}
// Start collapsed
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('[id^="inv-"]').forEach(r => r.style.display = 'none');
}});

const DATA = {chart_data_json};

// Chart 1: Tramos de mora por ejecutivo (barras apiladas)
new Chart(document.getElementById('chartTramos'), {{
  type: 'bar',
  data: {{
    labels: DATA.tramos.labels,
    datasets: [
      {{ label: '1–30 días',  data: DATA.tramos.d1_30,   backgroundColor: '#f39c12' }},
      {{ label: '31–60 días', data: DATA.tramos.d31_60,  backgroundColor: '#e67e22' }},
      {{ label: '61–90 días', data: DATA.tramos.d61_90,  backgroundColor: '#c0392b' }},
      {{ label: '+90 días',   data: DATA.tramos.d90plus, backgroundColor: '#7b241c' }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{
      label: ctx => ` ${{ctx.dataset.label}}: $` + Math.round(ctx.raw).toLocaleString('es-CL')
    }} }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ font: {{ size: 11 }} }} }},
      y: {{ stacked: true, ticks: {{ callback: v => '$' + (v/1000000).toFixed(1) + 'M', font: {{ size: 11 }} }} }}
    }}
  }}
}});

// Chart 2: Total vs Vencido (barras agrupadas)
new Chart(document.getElementById('chartCartera'), {{
  type: 'bar',
  data: {{
    labels: DATA.cartera.labels,
    datasets: [
      {{ label: 'Total Cartera', data: DATA.cartera.total,   backgroundColor: DATA.colors }},
      {{ label: 'Total Vencido', data: DATA.cartera.vencido, backgroundColor: '#e74c3c' }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{
      label: ctx => ` ${{ctx.dataset.label}}: $` + Math.round(ctx.raw).toLocaleString('es-CL')
    }} }} }},
    scales: {{
      x: {{ ticks: {{ font: {{ size: 11 }} }} }},
      y: {{ ticks: {{ callback: v => '$' + (v/1000000).toFixed(1) + 'M', font: {{ size: 11 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    return html


def main():
    fantasy_lookup = load_fantasy_names(BASE_MAESTRA_PATH) if BASE_MAESTRA_PATH else {}

    xls = pd.ExcelFile(EXCEL_PATH)
    exec_data = []

    available_sheets = xls.sheet_names
    for sheet in EXECUTIVE_SHEETS:
        # Handle encoding variations
        matched = next((s for s in available_sheets if s.lower().replace("ñ","n").replace("é","e") ==
                        sheet.lower().replace("ñ","n").replace("é","e")), None)
        if matched is None:
            print(f"[WARN] Hoja no encontrada: {sheet}")
            continue
        print(f"Procesando: {matched}")
        summary, rows = parse_executive_sheet(xls, matched)
        if rows:
            kpis = build_exec_kpis(summary, rows, sheet, fantasy_lookup)
            exec_data.append(kpis)

    if not exec_data:
        print("No se encontraron datos.")
        return

    html = generate_html(exec_data)
    Path(OUTPUT_PATH).write_text(html, encoding="utf-8")
    print(f"\nDashboard generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
