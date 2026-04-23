import streamlit as st
import pandas as pd
import json
import shutil
from datetime import date
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Beer Ambassador · Kross", page_icon="🍺", layout="wide")

# ── CSS Responsivo ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Fuente base más grande para móvil ── */
html, body, [class*="css"] { font-size: 16px; }

/* ── Sidebar compacto ── */
[data-testid="stSidebar"] { min-width: 220px !important; }

/* ── Inputs y botones táctiles ── */
input, textarea, select,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    font-size: 16px !important;   /* evita zoom en iOS */
    min-height: 44px;
    border-radius: 8px !important;
}

/* ── Checkboxes más grandes ── */
[data-testid="stCheckbox"] > label {
    font-size: 15px !important;
    padding: 8px 4px;
    cursor: pointer;
}
[data-testid="stCheckbox"] input[type="checkbox"] {
    width: 20px; height: 20px;
}

/* ── Botón principal prominente ── */
[data-testid="stButton"] > button[kind="primary"] {
    height: 52px;
    font-size: 17px !important;
    font-weight: 700;
    border-radius: 10px !important;
    width: 100%;
}

/* ── Sliders táctiles ── */
[data-testid="stSlider"] > div > div > div { height: 8px; }
[data-testid="stSlider"] [role="slider"]   { width: 28px !important; height: 28px !important; }

/* ── Métricas legibles ── */
[data-testid="stMetricValue"] { font-size: 28px !important; }

/* ── En pantallas pequeñas: columnas en una sola fila vertical ── */
@media (max-width: 768px) {
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    /* Sidebar colapsado por defecto en móvil (comportamiento nativo Streamlit) */
    section[data-testid="stSidebar"] { width: 0 !important; }
    /* Secciones más separadas */
    .block-container { padding: 1rem 0.75rem !important; }
}

/* ── Separadores de sección ── */
hr { margin: 1.5rem 0 !important; }

/* ── File uploader área más grande ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #e0a800 !important;
    border-radius: 10px !important;
    padding: 12px !important;
}
</style>
""", unsafe_allow_html=True)

DATA_PATH   = Path(__file__).parent / "data" / "beer_ambassador_visitas.csv"
FOTOS_PATH  = Path(__file__).parent / "data" / "fotos"
CRM_PATH    = Path(__file__).parent / "data" / "CRM_Comercial.xlsx"
SHEET_ID    = "1OrV3TVFvR52VQrmqWOGxqRk9lbtYNWdTbxS34Gn_AGU"
SHEET_NAME  = "Visitas"
CRM_SHEET_ID = "1IvZCIHk_kHkqLrHhrsfTxfTkRC9gVelk9lNgpYbFPZI"
SCOPES      = ["https://spreadsheets.google.com/feeds",
               "https://www.googleapis.com/auth/drive"]

EJECUTIVOS_VALIDOS = [
    "Armiro Perez", "Carlos Echeverria", "Carol Ibaceta",
    "Francisco Carreño", "Gerson Astudillo",
]
VARIEDADES_BASE = [
    "Golden", "Pils", "Maibock", "Stout", "K5",
    "Hoppy", "Berries", "Hazy Lager", "Ipa", "Ipa Pomelo",
]

DIAS = {
    0: ("Lunes",     "📋 Planificación", "Reunión comercial + contacto y filtro de prospectos"),
    1: ("Martes",    "🚶 Gestión",        "Visita y ruta de nuevos prospectos + cápsulas por variedad"),
    2: ("Miércoles", "🤝 Conversión",     "Cierre técnico nuevos prospectos + prospección en frío"),
    3: ("Jueves",    "🎓 Capacitación",   "Capacitación PDV (Staff) + Auditoría Técnica (Check List)"),
    4: ("Viernes",   "🎉 Activaciones",   "Implementación de activaciones/sampling + Cata VIP o Beer Dinners"),
    5: ("Sábado",    "📊 Revisión",       "Revisar KPIs de la semana"),
    6: ("Domingo",   "☀️ Descanso",       "Preparar agenda de la semana siguiente"),
}

METAS = {
    "Prospección y Cierres":  (5,  0.40),
    "Implementación Promos":  (5,  0.20),
    "Capacitación PDV":       (10, 0.20),
    "Auditorías Calidad":     (20, 0.20),
}

VARIEDADES_KROSS = [
    "Golden Ale", "Maibock", "Stout", "IPA", "Weizen",
    "Pale Ale", "Red Ale", "Pilsner", "Porter", "Otra",
]

# ── CRM Comercial ─────────────────────────────────────────────────────────────

def _procesar_crm(df_maestra, df_ventas):
    """Transforma DataFrames de Base Maestra + Base Ventas en estructura CRM."""
    import re
    from datetime import date as _date
    hoy = _date.today()

    # ── Base Maestra ──────────────────────────────────────────────────────────
    df = df_maestra.copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    col_nombre = next((c for c in df.columns if "Fantas" in c), None)
    col_ejec   = next((c for c in df.columns if "Ejecutivo" in c), None)
    col_activo = next((c for c in df.columns if "Activos" in c), None)
    col_cat    = next((c for c in df.columns if "Categor" in c), None)
    if not all([col_nombre, col_ejec, col_activo]):
        return None

    df = df[df[col_activo].str.lower().isin(["si", "sí"])]
    df = df[df[col_ejec].isin(EJECUTIVOS_VALIDOS)]

    clientes = {}
    for _, row in df.iterrows():
        nombre = row[col_nombre]
        if not nombre or nombre == "nan":
            continue
        vars_c = [v for v in VARIEDADES_BASE
                  if row.get(v, "").upper() in ("TRUE", "1", "SI", "SÍ")]
        clientes[nombre] = {
            "ejecutivo":  row[col_ejec],
            "variedades": vars_c,
            "comuna":     row.get("Comuna", ""),
            "categoria":  row.get(col_cat, "") if col_cat else "",
            "volumenes":  {},
            "ventas_mes": {},
        }

    # ── Base Ventas ───────────────────────────────────────────────────────────
    df_v = df_ventas.copy()
    for col in df_v.select_dtypes(include="object").columns:
        df_v[col] = df_v[col].astype(str).str.strip()

    col_desc   = next((c for c in df_v.columns if "Descrip" in c), None)
    col_dest   = next((c for c in df_v.columns if "Destino" in c), None)
    col_litros = next((c for c in df_v.columns if "Litro" in c), None)
    col_mes    = next((c for c in df_v.columns if c.strip().lower() == "mes"), None)
    col_anio   = next((c for c in df_v.columns
                       if c.strip().lower() in ("año", "ano", "year")
                       or (c.strip().lower().startswith("a") and c.strip().lower().endswith("o") and len(c.strip()) <= 5)), None)

    if col_desc and col_dest and col_litros:
        df_v["variedad"]  = df_v[col_desc].str.extract(r"KROSS\s+([\w\s]+?)\s+\d+", flags=re.IGNORECASE)
        df_v["cliente_n"] = df_v[col_dest].str.split(" ; ").str[0].str.strip()
        # Litros: formato chileno usa "." como miles → quitar antes de parsear
        df_v["_litros"] = pd.to_numeric(
            df_v[col_litros].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            errors="coerce"
        ).fillna(0)

        # Historial completo
        vol = df_v.groupby(["cliente_n", "variedad"])["_litros"].sum().reset_index()
        for _, r in vol.iterrows():
            n = r["cliente_n"]
            if n in clientes and pd.notna(r["variedad"]) and r["variedad"] not in ("nan", ""):
                clientes[n]["volumenes"][r["variedad"].strip()] = round(r["_litros"], 1)

        # Ventas del mes en curso
        if col_mes and col_anio:
            df_mes = df_v[
                (df_v[col_mes].str.strip() == str(hoy.month)) &
                (df_v[col_anio].str.strip() == str(hoy.year))
            ]
        else:
            col_fecha = next((c for c in df_v.columns if c.lower() == "fecha"), None)
            df_v["_fecha"] = pd.to_datetime(df_v[col_fecha], dayfirst=True, errors="coerce") if col_fecha else pd.NaT
            df_mes = df_v[(df_v["_fecha"].dt.month == hoy.month) & (df_v["_fecha"].dt.year == hoy.year)]

        if not df_mes.empty:
            vol_mes = df_mes.groupby(["cliente_n", "variedad"])["_litros"].sum().reset_index()
            for _, r in vol_mes.iterrows():
                n = r["cliente_n"]
                if n in clientes and pd.notna(r["variedad"]) and r["variedad"] not in ("nan", ""):
                    clientes[n]["ventas_mes"][r["variedad"].strip()] = round(r["_litros"], 1)

    # ── Agrupar por ejecutivo ─────────────────────────────────────────────────
    by_ej = {}
    for nombre, data in clientes.items():
        ej = data["ejecutivo"]
        by_ej.setdefault(ej, []).append(nombre)
    for ej in by_ej:
        by_ej[ej] = sorted(by_ej[ej])

    return {"clientes": clientes, "by_ejecutivo": by_ej}


@st.cache_data(ttl=1800, show_spinner="Cargando CRM...")
def load_crm(file_bytes: bytes = None):
    """CRM desde Google Sheets (cloud), archivo subido, o Excel local."""
    try:
        import io
        if file_bytes:
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            return _procesar_crm(
                xl.parse("Base Maestra", skiprows=1, header=0),
                xl.parse("Base Ventas 26"),
            )
        if _usar_gsheets():
            return _load_crm_gsheets()
        if CRM_PATH.exists():
            xl = pd.ExcelFile(CRM_PATH)
            return _procesar_crm(
                xl.parse("Base Maestra", skiprows=1, header=0),
                xl.parse("Base Ventas 26"),
            )
        return None
    except Exception as e:
        st.warning(f"⚠️ Error cargando CRM: {e}")
        return None


@st.cache_data(ttl=1800, show_spinner="Cargando CRM desde Google Sheets...")
def _load_crm_gsheets():
    """Lee Base Maestra + Base Ventas 26 directamente desde el CRM en Google Sheets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        gc  = gspread.authorize(creds)
        sh  = gc.open_by_key(CRM_SHEET_ID)

        # Base Maestra: fila 0 = subtotales, fila 1 = encabezados, fila 2+ = datos
        raw_m = sh.worksheet("Base Maestra").get_all_values()
        if len(raw_m) < 3:
            return None
        df_maestra = pd.DataFrame(raw_m[2:], columns=raw_m[1])

        # Base Ventas 26: fila 0 = encabezados, fila 1+ = datos
        raw_v = sh.worksheet("Base Ventas 26").get_all_values()
        if len(raw_v) < 2:
            return None
        df_ventas = pd.DataFrame(raw_v[1:], columns=raw_v[0])

        return _procesar_crm(df_maestra, df_ventas)
    except gspread.SpreadsheetNotFound:
        st.error("❌ CRM no accesible. Comparte la hoja con: beer-ambassador-bot@beer-ambassador.iam.gserviceaccount.com")
        return None
    except Exception as e:
        st.warning(f"⚠️ Error leyendo CRM: {e}")
        return None


def panel_cliente_crm(crm, pdv):
    """Muestra tarjeta con info del cliente seleccionado del CRM."""
    if not crm or not pdv:
        return
    info = crm["clientes"].get(pdv, {})
    if not info:
        return

    from datetime import date as _date
    mes_txt = _date.today().strftime("%B %Y").capitalize()

    with st.container():
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**🏪 Categoría:** {info.get('categoria','—')}")
            st.markdown(f"**📍 Comuna:** {info.get('comuna','—')}")
            vars_txt = ", ".join(info.get("variedades", [])) or "Sin registro"
            st.markdown(f"**🍺 Variedades:** {vars_txt}")
        with c2:
            ventas_mes = info.get("ventas_mes", {})
            total_mes  = sum(ventas_mes.values())
            st.markdown(f"**📅 Ventas {mes_txt}**")
            if ventas_mes:
                st.metric("Total mes", f"{total_mes:.0f} L")
                for var, lts in sorted(ventas_mes.items(), key=lambda x: -x[1]):
                    st.caption(f"• {var}: {lts:.0f} L")
            else:
                st.caption("Sin ventas registradas este mes")
        with c3:
            vols = info.get("volumenes", {})
            if vols:
                st.markdown("**📦 Histórico top 5**")
                for var, lts in sorted(vols.items(), key=lambda x: -x[1])[:5]:
                    st.caption(f"• {var}: {lts:.0f} L")
        st.markdown("---")


# ── Google Sheets ─────────────────────────────────────────────────────────────

def _usar_gsheets():
    """True si hay credenciales de Google en los Secrets de Streamlit."""
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


@st.cache_resource(ttl=60)
def _get_worksheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=5000, cols=80)
    return ws


# ── Helpers de datos ──────────────────────────────────────────────────────────

def load_visitas() -> pd.DataFrame:
    if _usar_gsheets():
        try:
            ws = _get_worksheet()
            # get_all_values() evita el error de cabeceras duplicadas
            data = ws.get_all_values()
            if not data or len(data) < 2:
                return pd.DataFrame()
            headers = data[0]
            rows    = data[1:]
            # Filtrar filas completamente vacías
            rows = [r for r in rows if any(c.strip() for c in r)]
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows, columns=headers)
        except Exception as e:
            st.warning(f"⚠️ No se pudo leer Google Sheets: {e}")
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)
    return pd.DataFrame()


def save_visita(row: dict, fotos: dict):
    # Fotos → solo en modo local (en cloud se omiten)
    if not _usar_gsheets():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        slug = f"{row['fecha']}_{row['pdv'].replace(' ', '_')[:20]}"
        fotos_paths = {}
        for seccion, archivos in fotos.items():
            if archivos:
                carpeta = FOTOS_PATH / slug / seccion
                carpeta.mkdir(parents=True, exist_ok=True)
                rutas = []
                for f in archivos:
                    dest = carpeta / f.name
                    dest.write_bytes(f.getbuffer())
                    rutas.append(str(dest))
                fotos_paths[seccion] = rutas
        row["fotos_json"] = json.dumps(fotos_paths, ensure_ascii=False)
        df = load_visitas()
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(DATA_PATH, index=False)
    else:
        # Modo cloud → guardar en Google Sheets
        try:
            ws = _get_worksheet()
            # Verificar si A1 tiene un encabezado válido (no es TRUE/FALSE ni vacío)
            a1 = ws.acell("A1").value or ""
            if a1.strip() in ("", "TRUE", "FALSE") :
                ws.clear()
                ws.append_row(list(row.keys()))
            ws.append_row(list(row.values()))
            # Invalidar caché para que load_visitas lea lo nuevo
            _get_worksheet.clear()
        except Exception as e:
            st.error(f"❌ Error al guardar en Google Sheets: {e}")


def calc_kpis(df, mes, anio):
    ceros = {k: 0 for k in METAS}
    if df.empty or "fecha" not in df.columns:
        return ceros
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    m = (df["fecha"].dt.month == mes) & (df["fecha"].dt.year == anio)
    d = df[m]
    return {
        "Prospección y Cierres": int((d.get("tipo_visita", pd.Series()) == "Prospección").sum()),
        "Implementación Promos": int((d.get("tiene_activacion", pd.Series()) == True).sum()),
        "Capacitación PDV":      int((d.get("tipo_visita", pd.Series()) == "Capacitación").sum()),
        "Auditorías Calidad":    int((d.get("tipo_visita", pd.Series()) == "Auditoría").sum()),
    }


def save_fotos_uploader(label, key, seccion_dict, seccion_key):
    archivos = st.file_uploader(
        label, type=["jpg", "jpeg", "png", "webp", "heic"],
        accept_multiple_files=True, key=key,
    )
    if archivos:
        seccion_dict[seccion_key] = archivos
        st.caption(f"📎 {len(archivos)} foto(s) adjunta(s)")


def rating(label, key, ayuda=""):
    cols = st.columns([3, 2])
    with cols[0]:
        st.markdown(f"**{label}**")
        if ayuda:
            st.caption(ayuda)
    with cols[1]:
        return st.select_slider("", options=[1, 2, 3, 4, 5],
                                 value=3, key=key,
                                 label_visibility="collapsed",
                                 format_func=lambda x: {1:"⭐ Pésimo", 2:"⭐⭐ Malo",
                                                          3:"⭐⭐⭐ Regular", 4:"⭐⭐⭐⭐ Bueno",
                                                          5:"⭐⭐⭐⭐⭐ Excelente"}[x])


def seccion_header(titulo, emoji, descripcion=""):
    st.markdown(f"### {emoji} {titulo}")
    if descripcion:
        st.caption(descripcion)
    st.markdown("---")


# ── PÁGINAS ───────────────────────────────────────────────────────────────────

def pagina_dashboard():
    st.title("🍺 Beer Ambassador · Kross")
    hoy = date.today()
    dia_info = DIAS[hoy.weekday()]
    st.markdown(f"**Hoy es {dia_info[0]} {hoy.strftime('%d/%m/%Y')}** — {dia_info[1]}")
    st.info(f"📌 {dia_info[2]}")
    st.markdown("---")

    df = load_visitas()
    kpis = calc_kpis(df, hoy.month, hoy.year)

    st.subheader(f"📊 KPIs del mes — {hoy.strftime('%B %Y').capitalize()}")
    cols = st.columns(4)
    for i, (nombre, (meta, pond)) in enumerate(METAS.items()):
        actual = kpis.get(nombre, 0)
        pct = min(actual / meta, 1.0)
        color = "🟢" if pct >= 1.0 else ("🟡" if pct >= 0.75 else "🔴")
        with cols[i]:
            st.metric(nombre, f"{actual}/{meta}", delta=f"{int(pct*100)}%")
            st.progress(pct)
            st.caption(f"{color} Pond. {int(pond*100)}%")

    st.markdown("---")
    st.subheader("📅 Calendario semanal")
    cal = st.columns(5)
    for i, (dn, (nombre, foco, desc)) in enumerate(list(DIAS.items())[:5]):
        with cal[i]:
            activo = hoy.weekday() == dn
            st.markdown(f"{'**' if activo else ''}{nombre}{'**' if activo else ''}")
            st.caption(foco)
            if activo:
                st.success(desc)
            else:
                st.text(desc[:45] + "…")


# ── AUDITORÍA ─────────────────────────────────────────────────────────────────

def form_auditoria(base, fotos):

    # 1. Ejecución Comercial
    seccion_header("1. Ejecución Comercial", "🛒", "Disponibilidad, carta y visibilidad en el punto")

    st.markdown("**Disponibilidad**")
    c1, c2 = st.columns(2)
    with c1:
        base["portafolio_activo"] = st.checkbox("¿Todo el portafolio acordado activo?", key="pa")
        base["quiebre_stock"]     = st.checkbox("¿Hay quiebres de stock?", key="qs")
    with c2:
        base["lineas_conectadas"] = st.checkbox("¿Líneas comprometidas conectadas?", key="lc")
        base["rotacion_lenta"]    = st.checkbox("¿Algún SKU con rotación lenta?", key="rl")

    st.markdown("**Carta y Visibilidad**")
    c1, c2 = st.columns(2)
    with c1:
        base["visible_carta"]        = st.checkbox("¿Kross visible en carta?", key="vc")
        base["descripcion_atractiva"] = st.checkbox("¿Descripción atractiva?", key="da")
    with c2:
        base["destacada_campana"]    = st.checkbox("¿Maibock/Golden destacada (campaña vigente)?", key="dc")
        base["marca_bien_escrita"]   = st.checkbox("¿Marca correctamente escrita?", key="mbe")

    save_fotos_uploader("📷 Fotos de carta / visibilidad", "fotos_carta", fotos, "carta")
    base["notas_ejecucion"] = st.text_area("Observaciones ejecución comercial",
                                            placeholder="Ej: quiebre en Golden, carta desactualizada…", key="ne")

    st.markdown("---")

    # 2. Prueba de variedades en barra
    seccion_header("2. Prueba de Variedades en Barra", "🍺",
                   "El Beer Ambassador prueba cada variedad conectada y evalúa temperatura, espuma, sabor y servicio")

    if "variedades" not in st.session_state:
        st.session_state.variedades = []

    col_add, col_clear = st.columns([2, 1])
    with col_add:
        nueva = st.selectbox("Seleccionar variedad conectada", [""] + VARIEDADES_KROSS, key="nueva_variedad")
    with col_clear:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Agregar variedad", use_container_width=True):
            if nueva and nueva not in [v["nombre"] for v in st.session_state.variedades]:
                st.session_state.variedades.append({
                    "nombre": nueva, "temp": 3, "espuma": 3, "sabor": 3,
                    "vaso_correcto": True, "obs": ""
                })

    for idx, v in enumerate(st.session_state.variedades):
        with st.expander(f"🍺 {v['nombre']}", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                v["temp"]   = st.select_slider("Temperatura", [1,2,3,4,5], value=v["temp"],
                                                key=f"temp_{idx}",
                                                format_func=lambda x: {1:"Muy caliente",2:"Caliente",
                                                3:"Aceptable",4:"Fría",5:"Perfecta"}[x])
            with c2:
                v["espuma"] = st.select_slider("Espuma", [1,2,3,4,5], value=v["espuma"],
                                                key=f"espuma_{idx}",
                                                format_func=lambda x: {1:"Excesiva",2:"Mucha",
                                                3:"Aceptable",4:"Buena",5:"Perfecta"}[x])
            with c3:
                v["sabor"]  = st.select_slider("Sabor / Calidad", [1,2,3,4,5], value=v["sabor"],
                                                key=f"sabor_{idx}",
                                                format_func=lambda x: {1:"Deficiente",2:"Malo",
                                                3:"Regular",4:"Bueno",5:"Excelente"}[x])
            v["vaso_correcto"] = st.checkbox("¿Vaso correcto con marca visible?", value=v["vaso_correcto"], key=f"vaso_{idx}")
            v["obs"] = st.text_input("Observación de esta variedad", value=v["obs"],
                                      placeholder="Ej: línea con sabor a jabón, temperatura alta", key=f"obs_{idx}")
            save_fotos_uploader(f"📷 Foto del vaso — {v['nombre']}", f"foto_var_{idx}", fotos, f"variedad_{v['nombre']}")
            if st.button(f"🗑️ Quitar {v['nombre']}", key=f"del_{idx}"):
                st.session_state.variedades.pop(idx)
                st.rerun()

    base["variedades_json"] = json.dumps(st.session_state.variedades, ensure_ascii=False)
    prom_sabor = (sum(v["sabor"] for v in st.session_state.variedades) /
                  max(len(st.session_state.variedades), 1))
    base["score_variedades"] = round(prom_sabor / 5 * 100, 1)

    if st.session_state.variedades:
        st.caption(f"Promedio calidad barra: **{prom_sabor:.1f}/5** ({base['score_variedades']}%)")

    st.markdown("---")

    # 3. Identidad y Branding
    seccion_header("3. Identidad y Branding", "🎨")
    c1, c2, c3 = st.columns(3)
    with c1:
        base["pop_vigente"]       = st.checkbox("¿Material POP vigente?", key="pv")
        base["pop_limpio"]        = st.checkbox("¿POP limpio y en buen estado?", key="pl")
    with c2:
        base["lineamiento_marca"] = st.checkbox("¿Respeta lineamiento de marca?", key="lm")
        base["posicion_correcta"] = st.checkbox("¿Bien posicionada vs competencia?", key="pc")
    with c3:
        base["transmite_calidad"] = st.checkbox("¿El punto transmite calidad Kross?", key="tc")
    save_fotos_uploader("📷 Fotos de POP y branding", "fotos_pop", fotos, "branding")
    base["notas_branding"] = st.text_area("Observaciones branding",
                                           placeholder="Ej: cartel sucio, mal posicionado junto a competencia", key="nb")

    st.markdown("---")

    # 4. Data & Métricas
    seccion_header("4. Data & Métricas", "📊", "Contexto competitivo y alertas del punto")
    c1, c2 = st.columns(2)
    with c1:
        base["participacion"]         = st.text_input("Participación Kross en categoría",
                                                       placeholder="Ej: 2 de 6 líneas schop", key="part")
        base["precio_vs_competencia"] = st.text_input("Precio Kross vs competencia",
                                                       placeholder="Ej: +$500 sobre Heineken", key="pvc")
    with c2:
        base["competidor_fuerte"]     = st.text_input("Competidor activando fuerte",
                                                       placeholder="Ej: Kunstmann con promotora los viernes", key="cf")
        base["cambio_administrador"]  = st.text_input("Cambio de administrador / dueño",
                                                       placeholder="Ej: nuevo dueño desde abril", key="ca")
    base["notas_data"] = st.text_area("Observaciones data & métricas", key="nd")


# ── CAPACITACIÓN ──────────────────────────────────────────────────────────────

def form_capacitacion(base, fotos):

    seccion_header("1. Diagnóstico Previo del Staff", "🔍",
                   "Evalúa el nivel de conocimiento ANTES de la capacitación (1=No sabe, 5=Experto)")
    c1, c2 = st.columns(2)
    with c1:
        base["diag_variedades"]  = rating("Conoce las variedades Kross", "dv",
                                           "¿Sabe nombrar y describir cada estilo?")
        base["diag_premiada"]    = rating("Sabe cuál es la más premiada", "dp",
                                           "La cervecería chilena más premiada del mundo")
    with c2:
        base["diag_maridaje"]    = rating("Recomienda maridajes", "dm",
                                           "¿Orienta al cliente según la comida?")
        base["diag_servicio"]    = rating("Servicio técnico", "ds",
                                           "Temperatura, espuma, vaso correcto")

    st.markdown("---")
    seccion_header("2. Temas Capacitados", "📚", "Marca todo lo que se cubrió en esta visita")
    temas = [
        "Historia y origen de Kross",
        "Variedades y estilos (descripción en palabras simples)",
        "La cervecería chilena más premiada del mundo",
        "Servicio técnico (temperatura, espuma, vaso)",
        "Maridajes según carta del local",
        "Up-selling y venta activa",
        "Coctelería con Kross",
        "Storytelling para recomendar al cliente",
        "Activaciones y degustaciones",
    ]
    temas_sel = []
    c1, c2 = st.columns(2)
    for i, tema in enumerate(temas):
        col = c1 if i % 2 == 0 else c2
        with col:
            if st.checkbox(tema, key=f"tema_{i}"):
                temas_sel.append(tema)
    base["temas_capacitados"] = ", ".join(temas_sel)

    st.markdown("---")
    seccion_header("3. Evaluación Post-Capacitación", "✅",
                   "Nivel del staff AL TERMINAR la capacitación")
    c1, c2 = st.columns(2)
    with c1:
        base["post_variedades"] = rating("Describe variedades correctamente", "pv2")
        base["post_premiada"]   = rating("Menciona la más premiada", "pp2")
    with c2:
        base["post_maridaje"]   = rating("Recomienda maridaje", "pm2")
        base["post_servicio"]   = rating("Servicio técnico", "ps2")

    mejora = ((base.get("post_variedades",3) + base.get("post_maridaje",3) +
               base.get("post_servicio",3)) -
              (base.get("diag_variedades",3) + base.get("diag_maridaje",3) +
               base.get("diag_servicio",3)))
    base["mejora_capacitacion"] = mejora
    if mejora > 0:
        st.success(f"📈 Mejora neta de la sesión: +{mejora} puntos")
    elif mejora == 0:
        st.info("Sin cambio medible en esta sesión")
    else:
        st.warning(f"⚠️ Puntuación bajó {mejora} (revisar metodología)")

    st.markdown("---")
    seccion_header("4. Compromisos y Seguimiento", "📝")
    base["compromisos"]      = st.text_area("Compromisos adquiridos por el staff / administrador",
                                             placeholder="Ej: van a recomendar maridaje con el menú de temporada", key="comp")
    base["proxima_accion"]   = st.text_input("Próxima acción de seguimiento",
                                              placeholder="Ej: revisitar en 2 semanas para evaluar", key="prox")
    base["personas_capacitadas"] = st.number_input("N° de personas capacitadas", min_value=1, value=2, key="npax")
    save_fotos_uploader("📷 Fotos de la capacitación", "fotos_cap", fotos, "capacitacion")
    base["notas_capacitacion"] = st.text_area("Notas generales", key="ncap")


# ── ACTIVACIÓN ────────────────────────────────────────────────────────────────

def form_activacion(base, fotos):

    seccion_header("1. Tipo de Activación", "🎉")
    tipos_act = st.multiselect("¿Qué tipo(s) de activación se realizó?",
                                ["Degustación / Sampling", "Cata guiada", "Beer Dinner",
                                 "Maridaje con menú", "Coctelería Kross", "Trivia cervecera",
                                 "Happy Hour Kross", "Lanzamiento de variedad", "Otra"],
                                key="tipos_act")
    base["tipos_activacion"] = ", ".join(tipos_act)
    base["tiene_activacion"] = len(tipos_act) > 0

    st.markdown("---")
    seccion_header("2. Variedades Activadas", "🍺")
    vars_act = st.multiselect("Variedades que se sirvieron / destacaron", VARIEDADES_KROSS, key="vars_act")
    base["variedades_activadas"] = ", ".join(vars_act)
    base["material_pop_usado"]   = st.checkbox("¿Se usó material POP de Kross?", key="mpu")
    base["incentivo_staff"]      = st.checkbox("¿Hubo incentivo al staff?", key="is_act")
    base["venta_cruzada"]        = st.checkbox("¿Se empujó venta cruzada (tabla, merch, etc.)?", key="vc_act")

    st.markdown("---")
    seccion_header("3. Resultados", "📊")
    c1, c2, c3 = st.columns(3)
    with c1:
        base["asistentes_estimados"] = st.number_input("Asistentes estimados", min_value=0, value=0, key="asist")
    with c2:
        base["pintas_vendidas"]      = st.number_input("Pintas / jarras vendidas (aprox.)", min_value=0, value=0, key="pintas")
    with c3:
        base["rating_activacion"]    = st.select_slider("Éxito de la activación", [1,2,3,4,5], value=3,
                                                          key="rat_act",
                                                          format_func=lambda x: {1:"Muy baja",2:"Baja",
                                                          3:"Regular",4:"Buena",5:"Excelente"}[x])
    base["storytelling_ok"]  = st.checkbox("¿Se contó la historia de la marca?", key="story_act")
    base["menciona_premiada"] = st.checkbox("¿Se mencionó que es chilena y más premiada del mundo?", key="mp_act")
    base["propuesta_maridaje"]   = st.text_input("Maridaje propuesto / destacado",
                                                   placeholder="Ej: Stout + tabla de quesos", key="pm_act")
    base["propuesta_cocteleria"] = st.text_input("Coctelería destacada",
                                                   placeholder="Ej: Shandy con Maibock", key="pc_act")

    st.markdown("---")
    save_fotos_uploader("📷 Fotos de la activación (ambiente, producto, gente)", "fotos_act", fotos, "activacion")
    base["notas_activacion"] = st.text_area("Observaciones de la activación", key="nact")


# ── PROSPECCIÓN ───────────────────────────────────────────────────────────────

def form_prospeccion(base, fotos):

    seccion_header("1. Perfil del Local", "🗺️")
    c1, c2, c3 = st.columns(3)
    with c1:
        base["tipo_local"]        = st.selectbox("Posicionamiento", ["Premium", "Masivo", "Craft especializado", "Otro"], key="tl")
        base["ticket_promedio"]   = st.text_input("Ticket promedio estimado", placeholder="Ej: $18.000", key="tp")
    with c2:
        base["perfil_publico"]    = st.text_input("Público predominante", placeholder="Ej: 25-40, NSE medio-alto", key="pp")
        base["capacidad_pax"]     = st.text_input("Capacidad máx. (pax)", placeholder="Ej: 80 pax", key="cpax")
    with c3:
        base["volumen_potencial"] = st.text_input("Volumen potencial (barriles/mes)", placeholder="Ej: 2 barriles", key="vp")
        base["potencial_rating"]  = st.select_slider("Potencial del local", [1,2,3,4,5], value=3, key="pot_r",
                                                       format_func=lambda x: {1:"Muy bajo",2:"Bajo",
                                                       3:"Medio",4:"Alto",5:"Muy alto"}[x])

    st.markdown("---")
    seccion_header("2. Concepto Gastronómico", "🍽️")
    c1, c2, c3 = st.columns(3)
    with c1:
        base["tipo_cocina"]      = st.text_input("Tipo de cocina", placeholder="Ej: Americana, Mediterránea", key="tcocina")
    with c2:
        base["enfoque_maridaje"] = st.text_input("Enfoque maridaje", placeholder="Ej: Tapas, tabla quesos", key="em")
    with c3:
        base["eventos_musica"]   = st.text_input("Eventos / música", placeholder="Ej: DJ viernes, trivia martes", key="evm")

    st.markdown("---")
    seccion_header("3. Infraestructura Cervecera", "🔧")
    c1, c2 = st.columns(2)
    with c1:
        base["tiene_schop"]          = st.checkbox("¿Tiene schop?", key="tschop")
        base["num_lineas"]           = st.text_input("¿Cuántas líneas?", placeholder="Ej: 4 líneas", key="nl")
        base["marcas_conectadas"]    = st.text_input("Marcas conectadas actualmente", placeholder="Ej: Heineken, Corona", key="mc")
    with c2:
        base["precio_competencia"]   = st.text_input("Precio pinta competencia", placeholder="Ej: $3.500", key="pcomp")
        base["espacio_nueva_linea"]  = st.checkbox("¿Hay espacio para nueva línea Kross?", key="enl")
        base["condiciones_actuales"] = st.text_area("Condiciones comerciales actuales (aporte, rappel, trademarketing)",
                                                     height=80, key="cond")

    st.markdown("---")
    seccion_header("4. Próximos Pasos", "🎯")
    base["decision_maker"]   = st.text_input("Nombre del tomador de decisión (dueño / admin)",
                                              placeholder="Ej: Pedro Soto, administrador", key="dm")
    base["contacto"]         = st.text_input("Teléfono / email de contacto", key="cont")
    base["proxima_reunion"]  = st.text_input("Próxima reunión pactada", placeholder="Ej: Lunes 25 a las 11:00", key="pr")
    base["temperatura_lead"] = st.select_slider("Temperatura del lead", [1,2,3,4,5], value=3, key="tl2",
                                                 format_func=lambda x: {1:"Frío",2:"Tibio",
                                                 3:"Interesado",4:"Caliente",5:"Cierre inminente"}[x])
    save_fotos_uploader("📷 Fotos del local (fachada, interior, barra)", "fotos_pros", fotos, "prospeccion")
    base["notas_prospeccion"] = st.text_area("Observaciones generales del prospecto", key="np")


# ── CHECK LIST PAGE ───────────────────────────────────────────────────────────

def pagina_checklist():
    st.title("✅ Check List de Visita PDV")

    # ── Cargar CRM ────────────────────────────────────────────────
    crm = load_crm()
    if crm is None and not _usar_gsheets():
        st.warning("⚠️ CRM no encontrado localmente. Sube el archivo para habilitar el selector de clientes.")
        crm_file = st.file_uploader("📂 Cargar CRM Comercial (.xlsx)", type=["xlsx"], key="crm_upload")
        if crm_file:
            crm = load_crm(file_bytes=crm_file.read())
    elif crm is None and _usar_gsheets():
        st.error("❌ No se pudo cargar el CRM desde Google Sheets. Verifica que la hoja esté compartida con la cuenta de servicio.")

    # ── Cabecera ──────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        fecha = st.date_input("Fecha", value=date.today())
    with c2:
        tipo_visita = st.selectbox("Tipo de visita *",
                                   ["Auditoría", "Capacitación", "Activación", "Prospección"])

    ambassador = "Francisco Rodriguez"
    if crm:
        ejecutivos = sorted(crm["by_ejecutivo"].keys())
        ejecutivo = st.selectbox("Ejecutivo de la cuenta *", ["— Selecciona —"] + ejecutivos)
    else:
        ejecutivo = st.text_input("Ejecutivo de la cuenta", placeholder="Nombre del ejecutivo")

    # ── Selector PDV filtrado por ejecutivo ───────────────────────
    if crm and ejecutivo and ejecutivo != "— Selecciona —":
        clientes_ej = crm["by_ejecutivo"].get(ejecutivo, [])
        if tipo_visita == "Prospección":
            pdv = st.text_input("Nombre del Prospecto *", placeholder="Nombre del local nuevo")
        else:
            pdv_sel = st.selectbox(
                f"📋 Cartera de {ejecutivo} ({len(clientes_ej)} clientes activos)",
                ["— Selecciona cliente —"] + clientes_ej,
            )
            pdv = pdv_sel if pdv_sel != "— Selecciona cliente —" else ""
            # Tarjeta informativa del cliente
            if pdv:
                panel_cliente_crm(crm, pdv)
    else:
        pdv = st.text_input("Nombre del PDV *", placeholder="Ej: Bar La Canela")

    # Guardar también ejecutivo en base
    st.markdown("---")
    base  = {
        "fecha": str(fecha), "pdv": pdv, "tipo_visita": tipo_visita,
        "ambassador": ambassador, "ejecutivo": ejecutivo,
    }
    fotos = {}

    # Pre-cargar variedades del cliente en session_state para Auditoría
    if (crm and pdv and tipo_visita == "Auditoría"
            and "variedades" not in st.session_state):
        info = crm["clientes"].get(pdv, {})
        vars_crm = info.get("variedades", [])
        if vars_crm:
            st.session_state.variedades = [
                {"nombre": v, "temp": 3, "espuma": 3, "sabor": 3,
                 "vaso_correcto": True, "obs": ""}
                for v in vars_crm
            ]

    if tipo_visita == "Auditoría":
        form_auditoria(base, fotos)
    elif tipo_visita == "Capacitación":
        form_capacitacion(base, fotos)
    elif tipo_visita == "Activación":
        form_activacion(base, fotos)
    elif tipo_visita == "Prospección":
        form_prospeccion(base, fotos)

    # Compromisos / próximos pasos (común a todos excepto capacitación que ya los tiene)
    if tipo_visita in ("Auditoría", "Activación"):
        st.markdown("---")
        seccion_header("Compromisos y Próximos Pasos", "📝")
        base["compromisos"]    = st.text_area("Compromisos pactados con el punto",
                                               placeholder="Ej: van a actualizar la carta la semana que viene", key="comp_gen")
        base["proxima_accion"] = st.text_input("Próxima acción de seguimiento",
                                                placeholder="Ej: revisitar el jueves próximo", key="prox_gen")

    st.markdown("---")
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        guardar = st.button("💾 Guardar visita", use_container_width=True, type="primary")
    with col_info:
        n_fotos = sum(len(v) for v in fotos.values() if v)
        st.caption(f"📎 {n_fotos} foto(s) adjunta(s) en total")

    if guardar:
        if not pdv.strip():
            st.error("El campo 'Nombre del PDV' es obligatorio.")
            return
        save_visita(base, fotos)
        if tipo_visita == "Auditoría":
            st.session_state.variedades = []
        st.success(f"✅ Visita **{tipo_visita}** en **{pdv}** guardada correctamente.")
        st.balloons()


# ── HISTORIAL ─────────────────────────────────────────────────────────────────

def pagina_historial():
    st.title("📋 Historial de Visitas")
    df = load_visitas()

    if df.empty:
        st.info("Sin visitas aún. ¡Registra la primera en Check List PDV!")
        return

    hoy = date.today()
    kpis = calc_kpis(df, hoy.month, hoy.year)
    st.subheader(f"KPIs — {hoy.strftime('%B %Y').capitalize()}")
    cols = st.columns(4)
    for i, (nombre, (meta, pond)) in enumerate(METAS.items()):
        actual = kpis.get(nombre, 0)
        pct = min(actual / meta, 1.0)
        color = "🟢" if pct >= 1.0 else ("🟡" if pct >= 0.75 else "🔴")
        with cols[i]:
            st.metric(nombre, f"{actual}/{meta}", delta=f"{int(pct*100)}%")
            st.progress(pct)
            st.caption(f"{color} Pond. {int(pond*100)}%")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        tipos = sorted(df["tipo_visita"].dropna().unique()) if "tipo_visita" in df.columns else []
        filtro_tipo = st.multiselect("Tipo de visita", tipos)
    with c2:
        ambs = sorted(df["ambassador"].dropna().unique()) if "ambassador" in df.columns else []
        filtro_amb = st.multiselect("Ambassador", ambs)
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📥 Exportar a Excel", use_container_width=True):
            p = DATA_PATH.parent / "beer_ambassador_export.xlsx"
            df.to_excel(p, index=False)
            st.success(f"Guardado en: {p}")

    df_show = df.copy()
    if filtro_tipo:
        df_show = df_show[df_show["tipo_visita"].isin(filtro_tipo)]
    if filtro_amb:
        df_show = df_show[df_show["ambassador"].isin(filtro_amb)]

    df_show["fecha"] = pd.to_datetime(df_show["fecha"], errors="coerce")
    df_show = df_show.sort_values("fecha", ascending=False)

    cols_base = ["fecha", "pdv", "tipo_visita", "ambassador"]
    cols_show = [c for c in cols_base if c in df_show.columns]
    st.dataframe(df_show[cols_show], use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(df_show)} visitas")

    # Detalle individual
    st.markdown("---")
    st.subheader("🔍 Ver detalle de una visita")
    if "pdv" in df_show.columns and len(df_show):
        opciones = df_show.apply(lambda r: f"{r['fecha'].date() if pd.notna(r['fecha']) else '?'} | {r.get('pdv','?')} | {r.get('tipo_visita','?')}", axis=1).tolist()
        sel = st.selectbox("Selecciona una visita", opciones, key="detalle_sel")
        idx = opciones.index(sel)
        row = df_show.iloc[idx]
        st.json(row.dropna().to_dict())

        # Mostrar fotos si existen
        if "fotos_json" in row and pd.notna(row["fotos_json"]):
            try:
                fotos_dict = json.loads(row["fotos_json"])
                for sec, rutas in fotos_dict.items():
                    st.markdown(f"**📷 {sec}**")
                    cols_img = st.columns(min(len(rutas), 4))
                    for i, ruta in enumerate(rutas):
                        if Path(ruta).exists():
                            with cols_img[i % 4]:
                                st.image(ruta, use_container_width=True)
            except Exception:
                pass


# ── NAV ───────────────────────────────────────────────────────────────────────

logo = Path(__file__).parent / "kross_logo.png.png"
with st.sidebar:
    if logo.exists():
        st.image(str(logo), use_container_width=True)
    st.markdown("## 🍺 Beer Ambassador")
    st.markdown("---")
    pagina = st.radio("Navegación", ["🏠 Dashboard", "✅ Check List PDV", "📋 Historial"])
    st.markdown("---")
    hoy = date.today()
    dia_info = DIAS[hoy.weekday()]
    st.markdown(f"**Hoy:** {dia_info[0]}")
    st.markdown(f"**Foco:** {dia_info[1]}")

if pagina == "🏠 Dashboard":
    pagina_dashboard()
elif pagina == "✅ Check List PDV":
    pagina_checklist()
elif pagina == "📋 Historial":
    pagina_historial()
