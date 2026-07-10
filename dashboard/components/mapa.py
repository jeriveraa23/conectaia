import json
import folium
import streamlit as st
from streamlit_folium import st_folium
from db.connection import cargar_iec
from utils.colores import color_por_iec
from components.preguntas import _configurar_openai, MODEL_NAME
import os


def cargar_geojson():
    ruta = os.path.join(os.path.dirname(__file__), "..", "data", "municipios.geojson")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def generar_analisis_municipio(client, datos) -> str:
    """Pide a GPT una lectura breve y NO técnica de las métricas de un
    municipio, pensada para alguien sin conocimientos de estadística o
    del proyecto."""
    prompt = f"""Eres un asistente que explica datos educativos a personas sin
formación técnica (por ejemplo, un alcalde, un docente o un ciudadano).

Datos del municipio "{datos.get('municipio')}" ({datos.get('departamento')}, región {datos.get('region')}):
- IEC (Índice de Efectividad de Conectividad, 0 a 100): {round(datos.get('iec', 0), 1)}
- Nivel de efectividad comparado con municipios similares: {datos.get('nivel_efectividad', 'N/A')}
  (diferencia de {round(datos.get('diferencia_vs_cluster', 0), 1)} puntos vs. el promedio de municipios
  parecidos que NO tienen Centro Digital)
- Retención estudiantil: {round(datos.get('componente_desercion', 0), 1)}/100
- Cobertura escolar: {round(datos.get('componente_cobertura', 0), 1)}/100
- Tasa de aprobación: {round(datos.get('componente_aprobacion', 0), 1)}/100
- ¿Tiene Centro Digital activo?: {"Sí" if datos.get('tiene_centro_digital') else "No"}
- ¿Es zona PDET?: {"Sí" if datos.get('es_pdet') else "No"}

Escribe un análisis de 3 a 5 frases, en español, SIN tecnicismos ni jerga
estadística (nada de "percentiles", "terciles", "z-score", etc.). Explica en
lenguaje cotidiano qué tan bien le va al municipio, qué significa eso en la
práctica para los estudiantes, y una idea concreta de qué se podría mejorar.
No repitas los números tal cual, intégralos de forma natural en el texto."""

    respuesta = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}],
    )
    return respuesta.choices[0].message.content.strip()


GLOSARIO = [
    ("IEC (Índice de Efectividad de Conectividad)",
     "Un puntaje de 0 a 100 que resume qué tan bien le va a un municipio en lo educativo. "
     "Se calcula combinando retención estudiantil, cobertura escolar y tasa de aprobación."),
    ("Efectividad (Alto / Medio / Bajo)",
     "Compara al municipio contra otros parecidos que NO tienen Centro Digital. Si un municipio "
     "supera bastante a esos similares, su efectividad es 'Alta' — aunque su IEC en términos "
     "absolutos no sea muy alto."),
    ("Retención estudiantil",
     "Qué tantos estudiantes se quedan en el colegio en vez de abandonarlo (lo contrario a la "
     "deserción escolar). Más alto es mejor."),
    ("Cobertura escolar",
     "Qué porcentaje de niños y jóvenes en edad escolar (5 a 16 años) están efectivamente "
     "matriculados en el grado que les corresponde."),
    ("Tasa de aprobación",
     "Qué porcentaje de estudiantes matriculados aprueba el año escolar."),
]


def construir_popup(datos):
    iec = datos.get('iec', 0)
    nivel = datos.get('nivel_efectividad', 'N/A')
    diferencia = datos.get('diferencia_vs_cluster', 0)

    # El color principal de la tarjeta lo determina el IEC (KPI principal),
    # con los mismos umbrales fijos que el resto del dashboard.
    color_iec = color_por_iec(iec)
    # La efectividad relativa a municipios similares es información
    # secundaria: se muestra, pero con un color propio y discreto que NO
    # afecta el color general de la tarjeta.
    color_nivel_secundario = {"Alto": "#1a9641", "Medio": "#e08e00", "Bajo": "#d7191c"}.get(nivel, "#888")
    signo = "+" if diferencia > 0 else ""

    return f"""
        <div style="font-family: Arial; min-width: 220px; max-width: 280px;">
            <h4 style="margin:0 0 2px 0; color:#222;">{datos.get('municipio', 'N/A')}</h4>
            <p style="margin:0 0 8px 0; color:#888; font-size:12px;">
                {datos.get('departamento', '')} · {datos.get('region', '')}
            </p>

            <div style="
                background:{color_iec}22;
                border-left: 4px solid {color_iec};
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 8px;
            ">
                <span style="font-size:11px; color:#666;">IEC (Índice de Efectividad de Conectividad)</span><br>
                <span style="font-size:26px; font-weight:700; color:{color_iec};">{round(iec, 1)}</span>
                <span style="font-size:13px; color:#888;"> / 100</span>
            </div>

            <p style="margin:0 0 8px 0; font-size:12px; color:#666;">
                Efectividad <b style="color:{color_nivel_secundario};">{nivel}</b> vs. municipios similares
                ({signo}{round(diferencia, 1)} pts)
            </p>

            <table style="width:100%; font-size:12px; border-collapse:collapse;">
                <tr>
                    <td style="padding:3px 0; color:#555;">Retención estudiantil</td>
                    <td style="text-align:right;"><b>{round(datos.get('componente_desercion', 0), 1)}</b>/100</td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#555;">Cobertura escolar</td>
                    <td style="text-align:right;"><b>{round(datos.get('componente_cobertura', 0), 1)}</b>/100</td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#555;">Tasa de aprobación</td>
                    <td style="text-align:right;"><b>{round(datos.get('componente_aprobacion', 0), 1)}</b>/100</td>
                </tr>
            </table>

            <hr style="margin:8px 0; border-color:#eee;">
            <p style="margin:0; font-size:11px; color:#666;">
                {'✅ Centro Digital activo' if datos.get('tiene_centro_digital') else '❌ Sin Centro Digital'}
                {'· 🏔️ Zona PDET' if datos.get('es_pdet') else ''}
            </p>
        </div>
    """


# Bounding box real de Colombia (calculado a partir de data/municipios.geojson),
# con un pequeño margen. Se usa para que el mapa arranque centrado en el país
# y no se pueda alejar hasta ver el mundo completo.
COLOMBIA_BOUNDS = [[-5.2, -83.0], [14.2, -65.8]]  # [[sur, oeste], [norte, este]]

# Gris más oscuro para municipios sin dato de IEC (antes casi invisible sobre
# el fondo claro del mapa base).
COLOR_SIN_DATO = "#8a8a8a"


def construir_mapa(iec_df, geojson):
    mapa = folium.Map(
        location=[4.5, -74.0],
        zoom_start=5,
        tiles="CartoDB positron",
        min_zoom=5,
        max_bounds=True,
    )
    mapa.fit_bounds(COLOMBIA_BOUNDS)
    # Evita que el usuario arrastre el mapa muy lejos de Colombia.
    mapa.options["maxBounds"] = COLOMBIA_BOUNDS
    mapa.options["maxBoundsViscosity"] = 1.0

    iec_dict = iec_df.set_index("codigo_municipio_men").to_dict("index")

    def color_de(datos):
        """Usa umbrales FIJOS (los mismos de la leyenda y las tarjetas),
        nunca cuantiles relativos al conjunto filtrado."""
        if datos is None:
            return COLOR_SIN_DATO
        return color_por_iec(datos.get("iec"))

    def style_function(feature):
        codigo = feature["properties"].get("MPIO_CCNCT")
        datos = iec_dict.get(codigo)
        return {
            "fillColor": color_de(datos),
            "fillOpacity": 0.75,
            "color": "#ffffff",
            "weight": 0.6,
        }

    def highlight_function(feature):
        return {
            "fillOpacity": 0.9,
            "color": "#333333",
            "weight": 2,
        }

    tooltip_style = (
        "font-size:14px; font-weight:600; color:#222; "
        "background-color:#ffffff; padding:6px 10px; "
        "border:1px solid #999; border-radius:4px;"
    )

    for feature in geojson["features"]:
        codigo = feature["properties"].get("MPIO_CCNCT")
        datos = iec_dict.get(codigo)
        # Nombre visible en el tooltip, sin importar si tiene datos o no.
        feature["properties"]["_nombre_tooltip"] = feature["properties"].get("MPIO_CNMBR", "Desconocido")

        if datos:
            popup_html = construir_popup(datos)
            popup = folium.Popup(popup_html, max_width=300)
        else:
            nombre = feature["properties"].get("MPIO_CNMBR", "Desconocido")
            popup = folium.Popup(f"<b>{nombre}</b><br>Sin datos en el análisis", max_width=200)

        folium.GeoJson(
            feature,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["_nombre_tooltip"],
                aliases=["Municipio:"],
                style=tooltip_style,
                sticky=True,
            ),
            popup=popup,
        ).add_to(mapa)

    return mapa


def render_mapa():
    st.markdown(
        "Este mapa muestra el **IEC (Índice de Efectividad de Conectividad)** de cada "
        "municipio colombiano, en una escala de 0 a 100. Usa los filtros para acotar por "
        "región, nivel de efectividad, zona PDET o presencia de Centro Digital. "
        "Haz clic sobre un municipio para ver el detalle completo de sus componentes."
    )

    if st.button("🔄 Recargar datos"):
        st.cache_data.clear()

    iec_df  = cargar_iec()
    geojson = cargar_geojson()

    with st.expander("⚙️ Filtros", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            regiones   = ["Todas"] + sorted(iec_df["region"].dropna().unique().tolist())
            region_sel = st.selectbox("Región", regiones)
        with col2:
            nivel_sel  = st.selectbox("Nivel de efectividad", ["Todos", "Alto", "Medio", "Bajo"])
        with col3:
            solo_pdet  = st.checkbox("Solo PDET")
            solo_cd    = st.checkbox("Solo con CD activo")

    st.markdown("**Leyenda (IEC)**: 🟢 75-100 · 🟡 60-74 · 🟠 45-59 · 🔴 0-44 · ⬛ Sin dato")

    df_filtrado = iec_df.copy()
    if region_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado["region"] == region_sel]
    if nivel_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["nivel_efectividad"] == nivel_sel]
    if solo_pdet:
        df_filtrado = df_filtrado[df_filtrado["es_pdet"] == True]
    if solo_cd:
        df_filtrado = df_filtrado[df_filtrado["tiene_centro_digital"] == True]

    st.markdown(f"**{len(df_filtrado)} municipios** seleccionados")

    mapa = construir_mapa(df_filtrado, geojson)

    contenedor = st.container()
    with contenedor:
        resultado_click = st_folium(
            mapa,
            use_container_width=True,
            height=650,
            returned_objects=["last_active_drawing"],
            key="mapa_principal"
        )

    # --- Panel del municipio seleccionado (clic en el mapa) -----------------
    if resultado_click and resultado_click.get("last_active_drawing"):
        propiedades = resultado_click["last_active_drawing"].get("properties", {})
        codigo_click = propiedades.get("MPIO_CCNCT")
        if codigo_click:
            st.session_state["municipio_seleccionado"] = codigo_click

    iec_dict_completo = iec_df.set_index("codigo_municipio_men").to_dict("index")
    codigo_sel = st.session_state.get("municipio_seleccionado")
    datos_sel = iec_dict_completo.get(codigo_sel) if codigo_sel else None

    if "analisis_municipios" not in st.session_state:
        st.session_state.analisis_municipios = {}

    if datos_sel:
        with st.container(border=True):
            st.markdown(f"### 📍 {datos_sel['municipio']} · {datos_sel['departamento']}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("IEC", f"{datos_sel['iec']:.1f}")
            c2.metric("Efectividad", datos_sel.get("nivel_efectividad", "N/A"))
            c3.metric("Retención", f"{datos_sel.get('componente_desercion', 0):.1f}")
            c4.metric("Cobertura", f"{datos_sel.get('componente_cobertura', 0):.1f}")
            c5.metric("Aprobación", f"{datos_sel.get('componente_aprobacion', 0):.1f}")

            if st.button("🧠 Generar análisis", key=f"btn_analisis_{codigo_sel}"):
                client = _configurar_openai()
                if client:
                    with st.spinner("Generando análisis..."):
                        texto = generar_analisis_municipio(client, datos_sel)
                    st.session_state.analisis_municipios[codigo_sel] = texto

            if codigo_sel in st.session_state.analisis_municipios:
                st.info(st.session_state.analisis_municipios[codigo_sel])
    else:
        st.caption("👆 Haz clic sobre un municipio en el mapa para ver su detalle y generar un análisis con IA.")

    # --- Glosario -------------------------------------------------------
    st.divider()
    st.markdown("#### 📖 Glosario de términos")
    for termino, definicion in GLOSARIO:
        with st.expander(termino):
            st.markdown(definicion)
