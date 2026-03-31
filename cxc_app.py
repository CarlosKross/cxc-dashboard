import streamlit as st
import pandas as pd
import tempfile
import os
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from cxc_dashboard import (
    parse_executive_sheet,
    parse_sin_ejecutivo,
    parse_analisis_deuda,
    build_exec_kpis,
    generate_html,
    generate_individual_html,
    generate_email_body,
    generate_client_collection_email,
    generate_client_statement_email,
    normalize_rut,
    fmt_clp,
)

# ── Email helpers ─────────────────────────────────────────────────────────────
EMAIL_CONFIG_PATH = Path(__file__).parent / "email_config.json"

def load_email_config():
    # Primero intentar desde Streamlit Secrets (entorno cloud)
    try:
        s = st.secrets
        if "smtp" in s:
            cfg = {
                "smtp": {
                    "host":     s["smtp"].get("host", "smtp.gmail.com"),
                    "port":     int(s["smtp"].get("port", 587)),
                    "user":     s["smtp"]["user"],
                    "password": s["smtp"]["password"],
                },
                "ejecutivos": dict(s.get("ejecutivos", {})),
                "jefaturas":  list(s.get("jefaturas", {}).get("lista", [])),
            }
            return cfg
    except Exception:
        pass
    # Fallback: archivo local email_config.json
    if EMAIL_CONFIG_PATH.exists():
        return json.loads(EMAIL_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}

def send_email(cfg, to_list, subject, html_body, attachment_html=None, attachment_name=None, cc_list=None):
    msg = MIMEMultipart("mixed")
    msg["From"]    = f"Área de Cobranza Kross <{cfg['smtp']['user']}>"
    msg["To"]      = ", ".join(to_list)
    if cc_list:
        msg["Cc"]  = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if attachment_html and attachment_name:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_html.encode("utf-8"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
        msg.attach(part)

    all_recipients = to_list + (cc_list or [])
    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["smtp"]["host"], cfg["smtp"]["port"]) as server:
        server.starttls(context=context)
        server.login(cfg["smtp"]["user"], cfg["smtp"]["password"])
        server.sendmail(cfg["smtp"]["user"], all_recipients, msg.as_string())

# Sheets that are NOT executive detail sheets
NON_EXEC_SHEETS = {"resumen ejecutivo", "resumen vencido", "resumen", "parametros", "parámetros"}

# ── Base maestra source ───────────────────────────────────────────────────────
# Opción A: URL de Google Sheets publicado como CSV
# Archivo → Compartir → Publicar en la web → CSV → copiar URL aquí
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1IvZCIHk_kHkqLrHhrsfTxfTkRC9gVelk9lNgpYbFPZI/export?format=csv&gid=548843474"

# Opción B: CSV local incluido en el repo
DATA_DIR = Path(__file__).parent / "data"
BUNDLED_MAESTRA = DATA_DIR / "nombres_fantasia.csv"


def _parse_fantasy_df(df):
    rut_col  = next((c for c in df.columns if "rut"    in c.lower()), None)
    name_col = next((c for c in df.columns if "fantas" in c.lower()), None)
    if not rut_col or not name_col:
        return {}
    lookup = {}
    for _, row in df.iterrows():
        rut  = str(row[rut_col]).strip()
        name = str(row[name_col]).strip()
        if rut and name and name not in ("nan", ""):
            lookup[normalize_rut(rut)] = name
    return lookup


def _parse_exec_df(df):
    """Extrae {rut_normalizado: ejecutivo} desde el DataFrame de la base maestra."""
    rut_col  = next((c for c in df.columns if "rut"       in c.lower()), None)
    exec_col = next((c for c in df.columns if "ejecutivo" in c.lower()), None)
    if not rut_col or not exec_col:
        return {}
    lookup = {}
    for _, row in df.iterrows():
        rut  = str(row[rut_col]).strip()
        exec_name = str(row[exec_col]).strip()
        if rut and exec_name and exec_name not in ("nan", ""):
            lookup[normalize_rut(rut)] = exec_name
    return lookup


def _parse_email_cobranza_df(df):
    """Extrae {rut_normalizado: email_cobranza} desde columna AO (índice 40) de la base maestra."""
    rut_col = next((c for c in df.columns if "rut" in c.lower()), None)
    if not rut_col:
        return {}
    cols = list(df.columns)
    # Columna AO = índice 40 (base 0)
    email_col = cols[40] if len(cols) > 40 else None
    if not email_col:
        return {}
    lookup = {}
    for _, row in df.iterrows():
        rut   = str(row[rut_col]).strip()
        email = str(row[email_col]).strip()
        if rut and email and email not in ("nan", ""):
            lookup[normalize_rut(rut)] = email
    return lookup


@st.cache_data(ttl=300)   # refresca cada 5 min
def load_fantasy_from_sheets(url):
    df = pd.read_csv(url, dtype=str)
    rut_col = next((c for c in df.columns if "rut" in c.lower()), None)
    if not rut_col:
        df = pd.read_csv(url, dtype=str, skiprows=1)
    return _parse_fantasy_df(df)


@st.cache_data(ttl=300)
def load_exec_from_sheets(url):
    """Carga {rut: ejecutivo} desde la columna 'Ejecutivo' de la base maestra."""
    try:
        df = pd.read_csv(url, dtype=str)
        rut_col = next((c for c in df.columns if "rut" in c.lower()), None)
        if not rut_col:
            df = pd.read_csv(url, dtype=str, skiprows=1)
        return _parse_exec_df(df)
    except Exception:
        return {}


@st.cache_data(ttl=300)
def load_emails_cobranza_from_sheets(url):
    """Carga {rut: email_cobranza} desde columna AO de la base maestra."""
    try:
        df = pd.read_csv(url, dtype=str)
        rut_col = next((c for c in df.columns if "rut" in c.lower()), None)
        if not rut_col:
            df = pd.read_csv(url, dtype=str, skiprows=1)
        return _parse_email_cobranza_df(df)
    except Exception:
        return {}


def load_fantasy_from_csv(path):
    df = pd.read_csv(path, dtype=str)
    return _parse_fantasy_df(df)


def load_fantasy_from_excel(file_bytes):
    try:
        df = pd.read_excel(file_bytes, usecols=["RUT", "Nombre de Fantasía"], dtype=str)
        lookup = {}
        for _, row in df.iterrows():
            rut = str(row["RUT"]).strip()
            name = str(row["Nombre de Fantasía"]).strip()
            if rut and name and name != "nan":
                lookup[normalize_rut(rut)] = name
        return lookup
    except Exception:
        return {}


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard CxC — Kross",
    page_icon="🍺",
    layout="centered",
)

st.markdown("""
<style>
    /* ── Kross Brand Colors ── fondo claro, acento amarillo ── */
    :root {
        --kross-yellow: #F5C200;
        --kross-dark:   #111111;
        --kross-bg:     #F7F5EF;
    }

    /* Fondo general beige/blanco */
    .stApp { background-color: #F7F5EF; }
    .block-container { max-width: 780px; padding-top: 0 !important; }

    /* Header de marca: amarillo con texto negro bold */
    .kross-header {
        background: #F5C200;
        padding: 18px 32px 14px;
        margin: -1rem -1rem 1.5rem -1rem;
        display: flex;
        align-items: center;
        gap: 16px;
        border-bottom: 3px solid #d4a800;
    }
    .kross-header h1 {
        color: #111111 !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        letter-spacing: 1px;
        margin: 0;
        text-transform: uppercase;
    }
    .kross-header .sub {
        color: #444;
        font-size: 12px;
        margin-top: 2px;
        font-weight: 600;
    }

    /* Títulos y texto */
    h1, h2, h3 { color: #111111 !important; }
    h2, h3 { border-left: 4px solid #F5C200; padding-left: 10px; }
    p, label, .stMarkdown { color: #333333 !important; }

    /* Botón primario → amarillo Kross */
    .stButton > button[kind="primary"] {
        background: #F5C200 !important;
        color: #111 !important;
        font-weight: 800 !important;
        border: none !important;
        border-radius: 6px !important;
        text-transform: uppercase;
        letter-spacing: .5px;
    }
    .stButton > button[kind="primary"]:hover {
        background: #d4a800 !important;
    }

    /* Botón secundario */
    .stButton > button {
        background: #fff !important;
        color: #111 !important;
        border: 1px solid #ccc !important;
        border-radius: 6px !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border: 2px dashed #F5C200 !important;
        border-radius: 8px !important;
        background: #fff !important;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        background: #fff !important;
        color: #111 !important;
        border: 1px solid #ddd !important;
        border-radius: 6px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #F5C200 !important;
        box-shadow: 0 0 0 2px rgba(245,194,0,.2) !important;
    }

    /* Métricas */
    [data-testid="stMetric"] {
        background: #fff;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #F5C200;
        box-shadow: 0 1px 4px rgba(0,0,0,.08);
    }
    [data-testid="stMetricLabel"] { color: #777 !important; }
    [data-testid="stMetricValue"] { color: #111 !important; font-weight: 800 !important; }

    /* Alertas */
    .stSuccess { background: #f0faf4 !important; border-color: #2ecc71 !important; color: #1a6b3a !important; }
    .stWarning { background: #fffbea !important; border-color: #F5C200 !important; color: #7a5f00 !important; }
    .stError   { background: #fff0f0 !important; border-color: #e74c3c !important; color: #8b1a1a !important; }

    /* Expander */
    [data-testid="stExpander"] {
        background: #fff !important;
        border: 1px solid #e8e4d8 !important;
        border-radius: 8px !important;
    }

    /* Divider */
    hr { border-color: #e8e4d8 !important; }

    /* Caption */
    .stCaption { color: #999 !important; }

    /* Checkbox */
    .stCheckbox label { color: #333 !important; }

    /* Subheader */
    .stSubheader { color: #111 !important; }

    /* Download button */
    [data-testid="stDownloadButton"] > button {
        background: #F5C200 !important;
        color: #111 !important;
        font-weight: 800 !important;
        border: none !important;
        border-radius: 6px !important;
        text-transform: uppercase;
    }
</style>

<div class="kross-header">
  <div>
    <h1>🍺 Dashboard Cuentas por Cobrar</h1>
    <div class="sub">Cervecería Kross · Gestión de Cobranza</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Upload CxC file ───────────────────────────────────────────────────────────
cxc_file = st.file_uploader(
    "Archivo CxC (Excel)",
    type=["xlsx", "xls"],
    help="Informe CxC con hojas por ejecutivo",
)

# Guardar bytes en session_state para que persistan al clic del botón
if cxc_file is not None:
    st.session_state["cxc_bytes"] = cxc_file.read()
    st.session_state["cxc_name"]  = cxc_file.name

report_date = st.text_input("Fecha del informe", value="", placeholder="dd/mm/aaaa", max_chars=12)

# ── Base maestra (optional override) ─────────────────────────────────────────
with st.expander("⚙️ Opciones avanzadas — Base Maestra"):
    st.markdown(
        "La app incluye una base maestra con **Nombres de Fantasía** actualizada. "
        "Si quieres usar una versión más reciente, súbela aquí."
    )
    maestra_file = st.file_uploader(
        "Base Maestra actualizada (opcional)",
        type=["xlsx"],
        key="maestra",
        help="Archivo con columnas RUT y Nombre de Fantasía",
    )

# ── Generate ──────────────────────────────────────────────────────────────────
if st.button("🚀 Generar Dashboard", type="primary",
             disabled="cxc_bytes" not in st.session_state):

    with st.spinner("Procesando…"):

        # Load fantasy lookup: archivo subido > Google Sheets > CSV local
        if maestra_file is not None:
            fantasy_lookup = load_fantasy_from_excel(maestra_file)
            st.caption(f"Base maestra: {len(fantasy_lookup)} clientes (archivo subido)")
        elif GOOGLE_SHEET_URL:
            try:
                fantasy_lookup = load_fantasy_from_sheets(GOOGLE_SHEET_URL)
                st.caption(f"Base maestra: {len(fantasy_lookup)} clientes (Google Sheets)")
            except Exception:
                fantasy_lookup = load_fantasy_from_csv(BUNDLED_MAESTRA) if BUNDLED_MAESTRA.exists() else {}
                st.caption(f"Base maestra: {len(fantasy_lookup)} clientes (CSV local — Sheets no disponible)")
        elif BUNDLED_MAESTRA.exists():
            fantasy_lookup = load_fantasy_from_csv(BUNDLED_MAESTRA)
            st.caption(f"Base maestra: {len(fantasy_lookup)} clientes (CSV local)")
        else:
            fantasy_lookup = {}

        cxc_bytes = st.session_state["cxc_bytes"]
        cxc_name  = st.session_state["cxc_name"]
        ext = ".xls" if cxc_name.lower().endswith(".xls") else ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(cxc_bytes)
            cxc_tmp = tmp.name

        try:
            xls = pd.ExcelFile(cxc_tmp)
            available_sheets = xls.sheet_names
            exec_data = []
            warnings  = []
            sin_exec_rows = []

            import unicodedata
            def norm_sheet(s):
                s = unicodedata.normalize("NFD", str(s).strip().lower())
                return "".join(c for c in s if unicodedata.category(c) != "Mn")

            is_analisis = any(
                "analisis" in norm_sheet(s) or "deuda" in norm_sheet(s)
                for s in available_sheets
            )

            if is_analisis:
                exec_lookup = load_exec_from_sheets(GOOGLE_SHEET_URL) if GOOGLE_SHEET_URL else {}
                if len(exec_lookup) == 0:
                    st.warning(
                        "⚠️ No se encontró columna **Ejecutivo** en la base maestra. "
                        "Agrega la columna 'Ejecutivo' al Google Sheet para asignar clientes a ejecutivos. "
                        "Por ahora todos los clientes aparecerán en 'Sin Ejecutivo'."
                    )
                parsed = parse_analisis_deuda(xls, exec_lookup, fantasy_lookup)
                for exec_name, (summary, rows) in parsed.items():
                    if exec_name == "Sin Ejecutivo":
                        sin_exec_rows = rows
                    elif rows:
                        kpis = build_exec_kpis(summary, rows, exec_name, fantasy_lookup)
                        exec_data.append(kpis)
            else:
                candidates = [
                    s for s in available_sheets
                    if norm_sheet(s) not in NON_EXEC_SHEETS
                    and not norm_sheet(s).startswith("resumen")
                ]
                for sheet in candidates:
                    summary, rows = parse_executive_sheet(xls, sheet)
                    if rows:
                        kpis = build_exec_kpis(summary, rows, sheet, fantasy_lookup)
                        exec_data.append(kpis)
                    else:
                        warnings.append(f"Sin datos en hoja: **{sheet}**")
                sin_exec_rows = parse_sin_ejecutivo(xls)

            xls.close()

            if not exec_data:
                st.error(f"No se encontraron hojas de ejecutivos. Hojas disponibles: {available_sheets}")
            else:
                for w in warnings:
                    st.warning(w)

                fecha = report_date.strip() or "s/f"
                html  = generate_html(exec_data, fecha, sin_exec_rows=sin_exec_rows or None)
                filename = f"CXC_Dashboard_{fecha.replace('/', '-')}.html"

                # Cargar emails de cobranza desde base maestra
                emails_cobranza = load_emails_cobranza_from_sheets(GOOGLE_SHEET_URL) if GOOGLE_SHEET_URL else {}
                st.session_state["emails_cobranza"] = emails_cobranza

                # Guardar en session_state para que persista al hacer clic en Enviar
                st.session_state["exec_data"]     = exec_data
                st.session_state["sin_exec_rows"] = sin_exec_rows
                st.session_state["html"]          = html
                st.session_state["filename"]      = filename
                st.session_state["fecha"]         = fecha

        finally:
            try:
                os.unlink(cxc_tmp)
            except Exception:
                pass

# ── Mostrar resultados y correos (persiste entre reruns) ──────────────────────
if "exec_data" in st.session_state:
    exec_data     = st.session_state["exec_data"]
    sin_exec_rows = st.session_state["sin_exec_rows"]
    html          = st.session_state["html"]
    filename      = st.session_state["filename"]
    fecha         = st.session_state["fecha"]

    total_cartera = sum(e["total_cartera"] for e in exec_data)
    total_vencido = sum(e["vencido"] for e in exec_data)
    pct = total_vencido / total_cartera * 100 if total_cartera else 0

    st.success(f"✅ {len(exec_data)} ejecutivos procesados")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Cartera", f"${total_cartera/1_000_000:.1f}M")
    col2.metric("Total Vencido", f"${total_vencido/1_000_000:.1f}M")
    col3.metric("% Vencido",     f"{pct:.1f}%")

    st.download_button(
        label="⬇️ Descargar Dashboard HTML",
        data=html.encode("utf-8"),
        file_name=filename,
        mime="text/html",
        type="primary",
    )

    # ── Envío de correos ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📧 Enviar Informes por Correo")

    email_cfg   = load_email_config()
    exec_emails = email_cfg.get("ejecutivos", {})
    jefaturas   = email_cfg.get("jefaturas", [])
    smtp_cfg    = email_cfg.get("smtp", {})
    smtp_ok     = bool(smtp_cfg.get("user") and smtp_cfg.get("password")
                       and "xxxx" not in smtp_cfg.get("password", ""))

    if not smtp_ok:
        st.warning(
            "**El envío de correos no está configurado.**  \n"
            "Para habilitarlo, ve a tu app en **share.streamlit.io → Settings → Secrets** "
            "y agrega las credenciales SMTP. Contacta al administrador del sistema."
        )
    else:
        col_a, col_b = st.columns(2)
        send_exec  = col_a.checkbox("Informe individual a cada ejecutivo", value=True)
        send_jefes = col_b.checkbox("Informe general a jefaturas", value=True)

        with st.expander("Ver / editar destinatarios"):
            st.markdown("**Ejecutivos**")
            edited_exec = {}
            for e in exec_data:
                default = exec_emails.get(e["nombre"], "")
                edited_exec[e["nombre"]] = st.text_input(
                    e["nombre"], value=default, key=f"mail_{e['nombre']}"
                )
            st.markdown("**Jefaturas**")
            jefaturas_str = st.text_area(
                "Un correo por línea", value="\n".join(jefaturas), height=80
            )

        if st.button("📤 Enviar ahora", type="primary"):
            jefes_list = [j.strip() for j in jefaturas_str.splitlines() if j.strip()]
            errors = []
            sent   = []

            with st.spinner("Enviando correos…"):
                if send_exec:
                    for e in exec_data:
                        to = edited_exec.get(e["nombre"], "").strip()
                        if not to:
                            errors.append(f"Sin email para {e['nombre']}")
                            continue
                        try:
                            email_body = generate_email_body(e, fecha)
                            ind_html   = generate_individual_html(e, fecha)
                            send_email(
                                email_cfg, [to],
                                f"Informe CxC — {e['nombre']} — {fecha}",
                                email_body,
                                ind_html,
                                f"CxC_{e['nombre'].replace(' ','_')}_{fecha.replace('/','_')}.html",
                            )
                            sent.append(f"{e['nombre']} → {to}")
                        except Exception as ex:
                            errors.append(f"{e['nombre']}: {ex}")

                if send_jefes and jefes_list:
                    try:
                        body = (
                            f"<p>Adjunto el informe general de Cuentas por Cobrar al {fecha}.</p>"
                            f"<p>Saludos,<br>Cervecería Kross</p>"
                        )
                        send_email(
                            email_cfg, jefes_list,
                            f"Dashboard CxC General — {fecha}",
                            body,
                            html,
                            filename,
                        )
                        sent += [f"Jefaturas → {j}" for j in jefes_list]
                    except Exception as ex:
                        errors.append(f"Jefaturas: {ex}")

            if sent:
                st.success("✅ Correos enviados:\n" + "\n".join(f"- {s}" for s in sent))
            for err in errors:
                st.error(err)

# ── Envío de cobranza a clientes ─────────────────────────────────────────────
if "exec_data" in st.session_state:
    exec_data       = st.session_state["exec_data"]
    fecha           = st.session_state["fecha"]
    emails_cobranza = st.session_state.get("emails_cobranza", {})
    email_cfg       = load_email_config()
    smtp_cfg        = email_cfg.get("smtp", {})
    smtp_ok         = bool(smtp_cfg.get("user") and smtp_cfg.get("password")
                           and "xxxx" not in smtp_cfg.get("password", ""))

    st.divider()
    st.subheader("📬 Enviar Cobranza a Clientes")
    st.markdown("Envía un aviso de deuda vencida directamente al contacto de pago de cada cliente.")

    if not smtp_ok:
        st.warning("Configura las credenciales SMTP para habilitar el envío.")
    else:
        # Recopilar todos los clientes con deuda vencida de todos los ejecutivos
        all_clients = []
        for e in exec_data:
            for c in e["clientes"]:
                if c["vencido"] > 0 and c.get("invoices"):
                    all_clients.append({
                        "ejecutivo": e["nombre"],
                        "rut":       c["rut"],
                        "cliente":   c["cliente"],
                        "vencido":   c["vencido"],
                        "invoices":  c["invoices"],
                    })

        if not all_clients:
            st.info("No hay clientes con deuda vencida.")
        else:
            n_con_email = sum(1 for c in all_clients if emails_cobranza.get(c["rut"]))
            n_sin_email = len(all_clients) - n_con_email
            col1, col2 = st.columns(2)
            col1.metric("Clientes con email registrado", n_con_email)
            col2.metric("Sin email (requiere ingreso manual)", n_sin_email)

            with st.expander(f"📋 Ver y editar destinatarios ({len(all_clients)} clientes con deuda)"):
                st.markdown("Completa los correos que falten. Deja vacío para omitir el cliente.")
                client_emails = {}
                for c in all_clients:
                    default = emails_cobranza.get(c["rut"], "")
                    cols = st.columns([3, 2, 2])
                    cols[0].markdown(f"**{c['cliente']}**  \n<small>{c['rut']} · {c['ejecutivo']}</small>",
                                     unsafe_allow_html=True)
                    cols[1].markdown(f"<div style='padding-top:8px;color:#c0392b;font-weight:700'>"
                                     f"{fmt_clp(c['vencido'])}</div>", unsafe_allow_html=True)
                    client_emails[c["rut"]] = cols[2].text_input(
                        "Email contacto pago", value=default,
                        key=f"cemail_{c['rut']}", label_visibility="collapsed",
                        placeholder="email@cliente.cl"
                    )

            if st.button("📤 Enviar avisos de cobranza", type="primary"):
                errors, sent = [], []
                with st.spinner("Enviando avisos…"):
                    for c in all_clients:
                        # Leer directo desde session_state para garantizar el valor actual
                        to = st.session_state.get(f"cemail_{c['rut']}", "").strip()
                        if not to:
                            continue
                        try:
                            body = generate_client_collection_email(
                                cliente=c["cliente"],
                                rut=c["rut"],
                                ejecutivo=c["ejecutivo"],
                                facturas=c["invoices"],
                                total_vencido=c["vencido"],
                                report_date=fecha,
                            )
                            # CC: ejecutivo a cargo + gestor (remitente)
                            exec_email = exec_emails.get(c["ejecutivo"], "")
                            gestor_email = cfg_smtp_user = email_cfg.get("smtp", {}).get("user", "")
                            cc = [e for e in [exec_email, gestor_email] if e and e != to]
                            send_email(
                                email_cfg, [to],
                                f"Aviso Saldo Pendiente — Cervecería Kross — {fecha}",
                                body,
                                cc_list=cc or None,
                            )
                            sent.append(f"{c['cliente']} → {to}")
                        except Exception as ex:
                            errors.append(f"{c['cliente']}: {ex}")

                if sent:
                    st.success(f"✅ Avisos enviados a {len(sent)} clientes:\n" +
                               "\n".join(f"- {s}" for s in sent))
                if errors:
                    for err in errors:
                        st.error(err)
                if not sent and not errors:
                    st.warning("Ningún cliente tenía email registrado. Completa los correos en la tabla.")

# ── Estado de Cuenta completo (todos los clientes) ───────────────────────────
if "exec_data" in st.session_state:
    exec_data       = st.session_state["exec_data"]
    fecha           = st.session_state["fecha"]
    emails_cobranza = st.session_state.get("emails_cobranza", {})
    email_cfg       = load_email_config()
    smtp_cfg        = email_cfg.get("smtp", {})
    smtp_ok         = bool(smtp_cfg.get("user") and smtp_cfg.get("password")
                           and "xxxx" not in smtp_cfg.get("password", ""))

    st.divider()
    st.subheader("📋 Enviar Estado de Cuenta a Clientes")
    st.markdown(
        "Envía el estado de cuenta a clientes **sin deuda vencida**. "
        "Los clientes con mora ya reciben el aviso de cobranza. "
        "Recomendado enviar cada **lunes** al subir el archivo."
    )

    import datetime as _dt
    hoy = _dt.date.today()
    if hoy.weekday() == 0:
        st.success("✅ Hoy es lunes — momento ideal para enviar el estado de cuenta semanal.")

    if not smtp_ok:
        st.warning("Configura las credenciales SMTP para habilitar el envío.")
    else:
        # RUTs que ya reciben aviso de cobranza (tienen deuda vencida)
        ruts_morosos = {
            c["rut"]
            for e in exec_data
            for c in e["clientes"]
            if c["vencido"] > 0
        }

        # Solo clientes SIN deuda vencida (los morosos ya reciben aviso de cobranza)
        all_clients_stmt = []
        for e in exec_data:
            for c in e["clientes"]:
                if c["rut"] in ruts_morosos:
                    continue
                all_invoices = c.get("all_invoices") or c.get("invoices", [])
                if all_invoices:
                    all_clients_stmt.append({
                        "ejecutivo":    e["nombre"],
                        "rut":          c["rut"],
                        "cliente":      c["cliente"],
                        "total":        c["total"],
                        "vencido":      c["vencido"],
                        "all_invoices": all_invoices,
                    })

        n_con = sum(1 for c in all_clients_stmt if emails_cobranza.get(c["rut"]))
        n_sin = len(all_clients_stmt) - n_con
        col1, col2 = st.columns(2)
        col1.metric("Clientes con email registrado", n_con)
        col2.metric("Sin email", n_sin)

        with st.expander(f"📋 Ver destinatarios ({len(all_clients_stmt)} clientes)"):
            stmt_emails = {}
            for c in all_clients_stmt:
                default = emails_cobranza.get(c["rut"], "")
                cols = st.columns([3, 2, 2])
                estado_txt = f"🔴 {fmt_clp(c['vencido'])} vencido" if c["vencido"] > 0 else "🟢 Al día"
                cols[0].markdown(f"**{c['cliente']}**  \n<small>{c['rut']} · {c['ejecutivo']}</small>",
                                 unsafe_allow_html=True)
                cols[1].markdown(f"<div style='padding-top:8px;font-size:13px'>{estado_txt}</div>",
                                 unsafe_allow_html=True)
                stmt_emails[c["rut"]] = cols[2].text_input(
                    "Email", value=default, key=f"semail_{c['rut']}",
                    label_visibility="collapsed", placeholder="email@cliente.cl"
                )

        if st.button("📤 Enviar estado de cuenta a todos", type="primary"):
            errors, sent = [], []
            with st.spinner("Enviando estados de cuenta…"):
                for c in all_clients_stmt:
                    to = stmt_emails.get(c["rut"], "").strip()
                    if not to:
                        continue
                    try:
                        body = generate_client_statement_email(
                            cliente=c["cliente"],
                            rut=c["rut"],
                            ejecutivo=c["ejecutivo"],
                            all_invoices=c["all_invoices"],
                            report_date=fecha,
                        )
                        # CC: ejecutivo a cargo + gestor
                        exec_email_cc = exec_emails.get(c["ejecutivo"], "")
                        gestor_cc     = email_cfg.get("smtp", {}).get("user", "")
                        cc = [e for e in [exec_email_cc, gestor_cc] if e and e != to]
                        send_email(
                            email_cfg, [to],
                            f"Tu Estado de Cuenta Semanal — Cervecería Kross — {fecha}",
                            body,
                            cc_list=cc or None,
                        )
                        sent.append(f"{c['cliente']} → {to}")
                    except Exception as ex:
                        errors.append(f"{c['cliente']}: {ex}")

            if sent:
                st.success(f"✅ Estados de cuenta enviados a {len(sent)} clientes:\n" +
                           "\n".join(f"- {s}" for s in sent))
            if errors:
                for err in errors:
                    st.error(err)
            if not sent and not errors:
                st.warning("Ningún cliente tenía email registrado.")

st.divider()
st.caption("Cervecería Kross · Dashboard CxC")
