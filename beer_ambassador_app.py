import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Beer Ambassador · Kross",
    page_icon="🍺",
    layout="wide",
)

DATA_PATH = Path(__file__).parent / "data" / "beer_ambassador_visitas.csv"

COLUMNAS = [
    "fecha", "pdv", "tipo_visita", "ambassador",
    # Ejecución Comercial
    "portafolio_activo", "quiebre_stock", "lineas_conectadas", "rotacion_lenta",
    "temperatura_correcta", "espuma_adecuada", "vasos_correctos", "recomendacion_activa", "equipo_capacitado",
    "visible_en_carta", "descripcion_atractiva", "destacada_campana", "marca_bien_escrita",
    "notas_ejecucion",
    # Identidad y Branding
    "material_pop_vigente", "material_limpio", "lineamiento_marca",
    "competencia_visual", "posicion_correcta", "transmite_calidad",
    "notas_branding",
    # Experiencia de Marca
    "staff_describe_variedades", "saben_mas_premiada", "recomiendan_maridaje",
    "hay_degustacion", "incentivo_staff", "venta_cruzada",
    "storytelling", "menciona_chilena_premiada",
    "propuesta_maridaje", "propuesta_cocteleria",
    "notas_experiencia",
    # Data & Métricas
    "participacion_categoria", "precio_vs_competencia", "competidor_activando", "cambio_administrador",
    "notas_data",
    # Prospección (cuenta nueva)
    "es_prospecto",
    "tipo_local", "ticket_promedio", "perfil_publico",
    "capacidad_pax", "volumen_potencial",
    "tipo_cocina", "enfoque_maridaje", "eventos_musica",
    "tiene_schop", "num_lineas", "marcas_conectadas",
    "precio_competencia_schop", "espacio_nueva_linea",
    "condiciones_comerciales",
    "notas_prospeccion",
    # Score
    "score_pct",
]

DIAS = {0: ("Lunes", "📋 Planificación", "Reunión comercial + contacto y filtro de prospectos"),
        1: ("Martes", "🚶 Gestión", "Visita y ruta de nuevos prospectos + cápsulas por variedad"),
        2: ("Miércoles", "🤝 Conversión", "Cierre técnico nuevos prospectos + prospección en frío"),
        3: ("Jueves", "🎓 Capacitación", "Capacitación PDV (Staff) + Auditoría Técnica (Check List)"),
        4: ("Viernes", "🎉 Activaciones", "Implementación de activaciones/sampling + Cata VIP o Beer Dinners"),
        5: ("Sábado", "📊 Revisión", "Revisar KPIs de la semana"),
        6: ("Domingo", "☀️ Descanso", "Preparar agenda de la semana siguiente")}

METAS = {"Prospección y Cierres": (5, 0.40),
         "Implementación Promos": (5, 0.20),
         "Capacitación PDV": (10, 0.20),
         "Auditorías Calidad": (20, 0.20)}


# ── Persistencia ──────────────────────────────────────────────────────────────
def load_visitas():
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
        for col in COLUMNAS:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=COLUMNAS)


def save_visita(row: dict):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = load_visitas()
    new_row = {col: row.get(col, None) for col in COLUMNAS}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DATA_PATH, index=False)


# ── Cálculo KPIs ──────────────────────────────────────────────────────────────
def calc_kpis(df: pd.DataFrame, mes: int, anio: int):
    if df.empty:
        return {"Prospección y Cierres": 0, "Implementación Promos": 0,
                "Capacitación PDV": 0, "Auditorías Calidad": 0}
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    mask = (df["fecha"].dt.month == mes) & (df["fecha"].dt.year == anio)
    mes_df = df[mask]
    return {
        "Prospección y Cierres": int(mes_df[mes_df["es_prospecto"] == True].shape[0]),
        "Implementación Promos": int(mes_df[mes_df["hay_degustacion"] == True].shape[0]),
        "Capacitación PDV": int(mes_df[mes_df["staff_describe_variedades"] == True].shape[0]),
        "Auditorías Calidad": int(mes_df[mes_df["tipo_visita"] == "Auditoría"].shape[0]),
    }


# ── UI helpers ────────────────────────────────────────────────────────────────
def pregunta(label, key, default=False):
    return st.checkbox(label, value=default, key=key)


def seccion(titulo, emoji):
    st.markdown(f"### {emoji} {titulo}")
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
            st.metric(label=nombre, value=f"{actual}/{meta}",
                      delta=f"{pct*100:.0f}% ({int(pond*100)}% pond.)")
            st.progress(pct)
            st.caption(f"{color} Meta: {meta} · Pond. {int(pond*100)}%")

    st.markdown("---")
    st.subheader("📅 Calendario semanal")
    cal_cols = st.columns(5)
    for i, (dia_n, (dia_nombre, foco, desc)) in enumerate(list(DIAS.items())[:5]):
        with cal_cols[i]:
            activo = hoy.weekday() == dia_n
            st.markdown(f"{'**' if activo else ''}{dia_nombre}{'**' if activo else ''}")
            st.caption(foco)
            if activo:
                st.success(desc)
            else:
                st.text(desc[:40] + "…")


def pagina_checklist():
    st.title("✅ Check List de Visita PDV")
    df = load_visitas()

    with st.form("visita_form", clear_on_submit=True):
        # Cabecera
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fecha = st.date_input("Fecha", value=date.today())
        with col2:
            pdv = st.text_input("Nombre del PDV *", placeholder="Ej: Bar La Canela")
        with col3:
            tipo_visita = st.selectbox("Tipo de visita", ["Auditoría", "Capacitación", "Activación", "Prospección"])
        with col4:
            ambassador = st.text_input("Beer Ambassador", placeholder="Tu nombre")

        st.markdown("---")

        # ── 1. Ejecución Comercial ────────────────────────────────────────────
        seccion("1. Ejecución Comercial", "🛒")
        st.markdown("**Disponibilidad**")
        c1, c2 = st.columns(2)
        with c1:
            portafolio_activo   = pregunta("¿Todo el portafolio acordado activo?", "portafolio_activo")
            quiebre_stock       = pregunta("¿Hay quiebres de stock?", "quiebre_stock")
        with c2:
            lineas_conectadas   = pregunta("¿Líneas comprometidas conectadas?", "lineas_conectadas")
            rotacion_lenta      = pregunta("¿Hay rotación lenta en algún SKU?", "rotacion_lenta")

        st.markdown("**Calidad de Servicio**")
        c1, c2, c3 = st.columns(3)
        with c1:
            temperatura_correcta = pregunta("¿Temperatura correcta?", "temperatura_correcta")
            espuma_adecuada      = pregunta("¿Espuma adecuada?", "espuma_adecuada")
        with c2:
            vasos_correctos      = pregunta("¿Vasos correctos (marca visible)?", "vasos_correctos")
            recomendacion_activa = pregunta("¿Se ofrece recomendación activa?", "recomendacion_activa")
        with c3:
            equipo_capacitado    = pregunta("¿Equipo capacitado?", "equipo_capacitado")

        st.markdown("**Carta y Visibilidad**")
        c1, c2 = st.columns(2)
        with c1:
            visible_en_carta    = pregunta("¿Kross visible en carta?", "visible_en_carta")
            descripcion_atractiva = pregunta("¿Tiene descripción atractiva?", "descripcion_atractiva")
        with c2:
            destacada_campana   = pregunta("¿Destacada Maibock/Golden (campaña vigente)?", "destacada_campana")
            marca_bien_escrita  = pregunta("¿Marca correctamente escrita?", "marca_bien_escrita")

        notas_ejecucion = st.text_area("Notas Ejecución Comercial", key="notas_ejecucion", height=70)

        # ── 2. Identidad y Branding ───────────────────────────────────────────
        seccion("2. Identidad y Branding", "🎨")
        st.markdown("**Material POP**")
        c1, c2, c3 = st.columns(3)
        with c1:
            material_pop_vigente = pregunta("¿Hay material vigente?", "material_pop_vigente")
        with c2:
            material_limpio      = pregunta("¿Limpio y en buen estado?", "material_limpio")
        with c3:
            lineamiento_marca    = pregunta("¿Se respeta lineamiento de marca?", "lineamiento_marca")

        st.markdown("**Territorio Visual**")
        c1, c2, c3 = st.columns(3)
        with c1:
            competencia_visual   = pregunta("¿La marca compite visualmente con otras?", "competencia_visual")
        with c2:
            posicion_correcta    = pregunta("¿Bien posicionada?", "posicion_correcta")
        with c3:
            transmite_calidad    = pregunta("¿El punto transmite calidad Kross?", "transmite_calidad")

        notas_branding = st.text_area("Notas Identidad y Branding", key="notas_branding", height=70)

        # ── 3. Experiencia de Marca ───────────────────────────────────────────
        seccion("3. Experiencia de Marca", "⭐")
        st.markdown("**Capacitación**")
        c1, c2, c3 = st.columns(3)
        with c1:
            staff_describe_variedades = pregunta("¿Staff describe cada variedad?", "staff_describe_variedades")
        with c2:
            saben_mas_premiada        = pregunta("¿Saben cuál es la más premiada?", "saben_mas_premiada")
        with c3:
            recomiendan_maridaje      = pregunta("¿Recomiendan maridajes?", "recomiendan_maridaje")

        st.markdown("**Activación y Storytelling**")
        c1, c2 = st.columns(2)
        with c1:
            hay_degustacion   = pregunta("¿Hay degustación activa?", "hay_degustacion")
            incentivo_staff   = pregunta("¿Hay incentivo al staff?", "incentivo_staff")
            venta_cruzada     = pregunta("¿Se empuja venta cruzada (tabla, merch)?", "venta_cruzada")
        with c2:
            storytelling          = pregunta("¿Se cuenta la historia de la marca?", "storytelling")
            menciona_chilena_premiada = pregunta("¿Se menciona que es chilena y premiada?", "menciona_chilena_premiada")

        st.markdown("**Propuestas**")
        propuesta_maridaje    = st.text_input("Maridaje propuesto según carta", key="propuesta_maridaje")
        propuesta_cocteleria  = st.text_input("Propuesta de coctelería (tracción de volumen)", key="propuesta_cocteleria")
        notas_experiencia     = st.text_area("Notas Experiencia de Marca", key="notas_experiencia", height=70)

        # ── 4. Data & Métricas ────────────────────────────────────────────────
        seccion("4. Data & Métricas", "📊")
        c1, c2 = st.columns(2)
        with c1:
            participacion_categoria  = st.text_input("Participación Kross en la categoría", key="participacion_categoria", placeholder="Ej: 2 de 5 marcas schop")
            precio_vs_competencia    = st.text_input("Precio vs competencia", key="precio_vs_competencia", placeholder="Ej: +$500 sobre la media")
        with c2:
            competidor_activando     = st.text_input("Competidor activando fuerte", key="competidor_activando", placeholder="Ej: Kunstmann con promotor")
            cambio_administrador     = st.text_input("Cambio de administrador / dueño", key="cambio_administrador", placeholder="Ej: Nuevo dueño desde mayo")
        notas_data = st.text_area("Notas Data & Métricas", key="notas_data", height=70)

        # ── 5. Prospección ────────────────────────────────────────────────────
        seccion("5. Prospección (solo cuenta nueva)", "🔍")
        es_prospecto = st.checkbox("¿Es un prospecto nuevo?", key="es_prospecto")

        tipo_local = ticket_promedio = perfil_publico = ""
        capacidad_pax = volumen_potencial = ""
        tipo_cocina = enfoque_maridaje = eventos_musica = ""
        tiene_schop = False
        num_lineas = marcas_conectadas = precio_competencia_schop = ""
        espacio_nueva_linea = False
        condiciones_comerciales = notas_prospeccion = ""

        if es_prospecto:
            st.markdown("**Posicionamiento**")
            c1, c2, c3 = st.columns(3)
            with c1:
                tipo_local       = st.selectbox("Tipo de local", ["Premium", "Masivo", "Craft especializado", "Otro"], key="tipo_local")
                ticket_promedio  = st.text_input("Ticket promedio estimado", key="ticket_promedio", placeholder="Ej: $18.000")
            with c2:
                perfil_publico   = st.text_input("Público predominante", key="perfil_publico", placeholder="Ej: 25-40, NSE medio-alto")
                capacidad_pax    = st.text_input("Capacidad máx. (pax)", key="capacidad_pax", placeholder="Ej: 80 pax")
            with c3:
                volumen_potencial = st.text_input("Volumen potencial (barriles/mes)", key="volumen_potencial", placeholder="Ej: 2 barriles/mes")

            st.markdown("**Concepto Gastronómico**")
            c1, c2, c3 = st.columns(3)
            with c1:
                tipo_cocina      = st.text_input("Tipo de cocina", key="tipo_cocina", placeholder="Ej: Americana, Mediterránea")
            with c2:
                enfoque_maridaje = st.text_input("Enfoque maridaje", key="enfoque_maridaje", placeholder="Ej: Tapas y tabla de quesos")
            with c3:
                eventos_musica   = st.text_input("Eventos / música", key="eventos_musica", placeholder="Ej: DJ viernes, trivia martes")

            st.markdown("**Infraestructura Cervecera**")
            c1, c2 = st.columns(2)
            with c1:
                tiene_schop          = pregunta("¿Tiene schop?", "tiene_schop_pros")
                num_lineas           = st.text_input("¿Cuántas líneas?", key="num_lineas", placeholder="Ej: 4 líneas")
                marcas_conectadas    = st.text_input("Marcas conectadas actualmente", key="marcas_conectadas", placeholder="Ej: Heineken, Corona")
            with c2:
                precio_competencia_schop = st.text_input("Precio pinta competencia", key="precio_competencia_schop", placeholder="Ej: $3.500")
                espacio_nueva_linea  = pregunta("¿Hay espacio para nueva línea?", "espacio_nueva_linea")
            condiciones_comerciales = st.text_area("Condiciones comerciales actuales (aporte, rappel, trademarketing)", key="condiciones_comerciales", height=70)
            notas_prospeccion       = st.text_area("Notas Prospección", key="notas_prospeccion", height=70)

        # ── Score ─────────────────────────────────────────────────────────────
        st.markdown("---")
        checks_binarios = [
            portafolio_activo, lineas_conectadas, temperatura_correcta, espuma_adecuada,
            vasos_correctos, recomendacion_activa, equipo_capacitado, visible_en_carta,
            descripcion_atractiva, destacada_campana, marca_bien_escrita,
            material_pop_vigente, material_limpio, lineamiento_marca,
            posicion_correcta, transmite_calidad,
            staff_describe_variedades, saben_mas_premiada, recomiendan_maridaje,
            hay_degustacion, storytelling, menciona_chilena_premiada,
        ]
        score_pct = round(sum(1 for c in checks_binarios if c) / len(checks_binarios) * 100, 1)
        col_score, _ = st.columns([1, 3])
        with col_score:
            color = "🟢" if score_pct >= 85 else ("🟡" if score_pct >= 70 else "🔴")
            st.metric("Score PDV", f"{score_pct}%", delta=None)
            st.caption(f"{color} {'Excelente' if score_pct >= 85 else ('Aceptable' if score_pct >= 70 else 'Requiere atención')}")

        submitted = st.form_submit_button("💾 Guardar visita", use_container_width=True, type="primary")

    if submitted:
        if not pdv.strip():
            st.error("El campo 'Nombre del PDV' es obligatorio.")
            return
        row = dict(
            fecha=str(fecha), pdv=pdv.strip(), tipo_visita=tipo_visita, ambassador=ambassador,
            portafolio_activo=portafolio_activo, quiebre_stock=quiebre_stock,
            lineas_conectadas=lineas_conectadas, rotacion_lenta=rotacion_lenta,
            temperatura_correcta=temperatura_correcta, espuma_adecuada=espuma_adecuada,
            vasos_correctos=vasos_correctos, recomendacion_activa=recomendacion_activa,
            equipo_capacitado=equipo_capacitado, visible_en_carta=visible_en_carta,
            descripcion_atractiva=descripcion_atractiva, destacada_campana=destacada_campana,
            marca_bien_escrita=marca_bien_escrita, notas_ejecucion=notas_ejecucion,
            material_pop_vigente=material_pop_vigente, material_limpio=material_limpio,
            lineamiento_marca=lineamiento_marca, competencia_visual=competencia_visual,
            posicion_correcta=posicion_correcta, transmite_calidad=transmite_calidad,
            notas_branding=notas_branding,
            staff_describe_variedades=staff_describe_variedades,
            saben_mas_premiada=saben_mas_premiada, recomiendan_maridaje=recomiendan_maridaje,
            hay_degustacion=hay_degustacion, incentivo_staff=incentivo_staff,
            venta_cruzada=venta_cruzada, storytelling=storytelling,
            menciona_chilena_premiada=menciona_chilena_premiada,
            propuesta_maridaje=propuesta_maridaje, propuesta_cocteleria=propuesta_cocteleria,
            notas_experiencia=notas_experiencia,
            participacion_categoria=participacion_categoria,
            precio_vs_competencia=precio_vs_competencia,
            competidor_activando=competidor_activando, cambio_administrador=cambio_administrador,
            notas_data=notas_data,
            es_prospecto=es_prospecto, tipo_local=tipo_local,
            ticket_promedio=ticket_promedio, perfil_publico=perfil_publico,
            capacidad_pax=capacidad_pax, volumen_potencial=volumen_potencial,
            tipo_cocina=tipo_cocina, enfoque_maridaje=enfoque_maridaje,
            eventos_musica=eventos_musica, tiene_schop=tiene_schop,
            num_lineas=num_lineas, marcas_conectadas=marcas_conectadas,
            precio_competencia_schop=precio_competencia_schop,
            espacio_nueva_linea=espacio_nueva_linea,
            condiciones_comerciales=condiciones_comerciales,
            notas_prospeccion=notas_prospeccion,
            score_pct=score_pct,
        )
        save_visita(row)
        st.success(f"✅ Visita a **{pdv}** guardada. Score: {score_pct}%")
        st.balloons()


def pagina_historial():
    st.title("📋 Historial de Visitas")
    df = load_visitas()

    if df.empty:
        st.info("Aún no hay visitas registradas. ¡Ve a Check List para registrar la primera!")
        return

    hoy = date.today()
    kpis = calc_kpis(df, hoy.month, hoy.year)

    # KPI resumen
    st.subheader(f"KPIs — {hoy.strftime('%B %Y').capitalize()}")
    cols = st.columns(4)
    for i, (nombre, (meta, pond)) in enumerate(METAS.items()):
        actual = kpis.get(nombre, 0)
        pct = min(actual / meta, 1.0)
        pct_cumpl = round(pct * 100)
        band = ("100%" if pct_cumpl >= 100 else
                "90-99%" if pct_cumpl >= 90 else
                "85-89%" if pct_cumpl >= 85 else
                "80-84%" if pct_cumpl >= 80 else
                "75-79%" if pct_cumpl >= 75 else "<75%")
        with cols[i]:
            st.metric(nombre, f"{actual}/{meta}", delta=f"{pct_cumpl}%")
            st.progress(pct)
            st.caption(f"Rango: {band}")

    st.markdown("---")

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        ambas = sorted(df["ambassador"].dropna().unique().tolist())
        filtro_amb = st.multiselect("Filtrar por Ambassador", ambas)
    with col2:
        tipos = sorted(df["tipo_visita"].dropna().unique().tolist())
        filtro_tipo = st.multiselect("Filtrar por Tipo de visita", tipos)
    with col3:
        if st.button("🗑️ Exportar a Excel", use_container_width=True):
            excel_path = DATA_PATH.parent / "beer_ambassador_export.xlsx"
            df.to_excel(excel_path, index=False)
            st.success(f"Exportado: {excel_path}")

    df_show = df.copy()
    if filtro_amb:
        df_show = df_show[df_show["ambassador"].isin(filtro_amb)]
    if filtro_tipo:
        df_show = df_show[df_show["tipo_visita"].isin(filtro_tipo)]

    # Tabla simplificada
    cols_tabla = ["fecha", "pdv", "tipo_visita", "ambassador", "score_pct",
                  "notas_ejecucion", "notas_branding", "notas_experiencia"]
    cols_tabla = [c for c in cols_tabla if c in df_show.columns]
    df_show["fecha"] = pd.to_datetime(df_show["fecha"], errors="coerce")
    df_show = df_show.sort_values("fecha", ascending=False)
    st.dataframe(df_show[cols_tabla], use_container_width=True, hide_index=True)

    st.caption(f"Total visitas: {len(df_show)}")


# ── Navegación ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("kross_logo.png.png", use_container_width=True)
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
