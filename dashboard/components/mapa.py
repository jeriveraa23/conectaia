import os
import json
import folium
import streamlit as st
from streamlit_folium import st_folium
from openai import OpenAI
from db.connection import cargar_iec
from utils.colores import color_por_iec


@st.cache_data(show_spinner=False)
def cargar_geojson():
    ruta = os.path.join(os.path.dirname(__file__), "..", "data", "municipios.geojson")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


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


def _cliente_openai():
    """Busca la API key en st.secrets (Streamlit Cloud) o en variables de entorno (.env local)."""
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def analizar_municipio_con_ia(datos):
    """Genera un análisis en lenguaje natural del municipio, con el mismo
    estilo del simulador (3 párrafos, para funcionario público no técnico)."""
    client = _cliente_openai()
    if client is None:
        return "⚠️ Falta configurar OPENAI_API_KEY para generar el análisis."

    iec = datos.get("iec", 0)
    nivel = datos.get("nivel_efectividad", "N/A")
    diferencia = datos.get("diferencia_vs_cluster", 0)
    tiene_cd = datos.get("tiene_centro_digital", False)

    prompt = f"""
Eres un analista de datos educativos de Colombia. Explica en 3 párrafos cortos y en lenguaje claro
para un alcalde o funcionario público (no técnico) la situación del municipio de {datos.get('municipio', 'N/A')}
({datos.get('departamento', '')}) en cuanto al impacto de los Centros Digitales Rurales en la educación.

Contexto: el IEC (Índice de Efectividad de Conectividad) es un puntaje de 0 a 100 que mide
el impacto educativo de los Centros Digitales Rurales. Se construye combinando tres indicadores
educativos: menor deserción escolar (peso 40%), mayor cobertura neta (peso 35%) y mayor tasa de
aprobación (peso 25%). Un IEC más alto significa un mejor impacto educativo.

Datos del municipio:
- Región: {datos.get('region', 'N/A')}
- IEC actual (Índice de Efectividad de Conectividad): {iec:.1f} sobre 100
- Nivel de efectividad vs municipios similares: {nivel}
- Diferencia vs su grupo territorial: {diferencia:+.1f} puntos
- Retención estudiantil: {datos.get('componente_desercion', 0):.1f}/100
- Cobertura escolar: {datos.get('componente_cobertura', 0):.1f}/100
- Tasa de aprobación: {datos.get('componente_aprobacion', 0):.1f}/100
- {'Tiene Centro Digital activo' if tiene_cd else 'No tiene Centro Digital'}
- {'Es zona PDET' if datos.get('es_pdet') else 'No es zona PDET'}

En el primer párrafo explica cómo está el municipio en términos de IEC y qué significa su nivel
de efectividad "{nivel}" comparado con municipios similares. En el segundo párrafo analiza sus tres
componentes (retención, cobertura, aprobación) e identifica cuál es su punto más fuerte y cuál el
más débil. En el tercer párrafo da una recomendación práctica. Sé directo, evita tecnicismos y usa
máximo 160 palabras en total.
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=320,
        temperature=0.7,
    )
    return response.choices[0].message.content


def construir_popup(datos):
    iec = datos.get('iec', 0)
    nivel = datos.get('nivel_efectividad', 'N/A')
    diferencia = datos.get('diferencia_vs_cluster', 0)

    color_iec = color_por_iec(iec)
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
            <p style="margin:8px 0 0 0; font-size:11px; color:#2b6cb0; font-style:italic;">
                👉 Cierra este cuadro y usa el botón de análisis con IA debajo del mapa.
            </p>
        </div>
    """


COLOMBIA_BOUNDS = [[-5.2, -83.0], [14.2, -65.8]]
COLOR_SIN_DATO = "#a0a0a0"  # mismo gris que utils/colores.py — antes eran dos grises distintos
COLOR_ATENUADO = "#d9d9d9"


@st.cache_data(show_spinner=False)
def _popups_por_codigo(_iec_df_full):
    """Genera una sola vez el HTML de cada popup y lo cachea, indexado por
    código de municipio. A diferencia de un folium.Map, un string es
    inmutable y seguro de cachear/reutilizar entre reruns."""
    popups = {}
    for _, fila in _iec_df_full.iterrows():
        popups[fila["codigo_municipio_men"]] = construir_popup(fila.to_dict())
    return popups


def construir_mapa(iec_df, geojson, codigo_seleccionado=None, popups_html=None):
    mapa = folium.Map(
        location=[4.5, -74.0],
        zoom_start=5,
        tiles="CartoDB positron",
        min_zoom=5,
        max_bounds=True,
    )
    mapa.fit_bounds(COLOMBIA_BOUNDS)
    mapa.options["maxBounds"] = COLOMBIA_BOUNDS
    mapa.options["maxBoundsViscosity"] = 1.0

    iec_dict = iec_df.set_index("codigo_municipio_men").to_dict("index")

    hay_seleccion = bool(codigo_seleccionado)

    def color_de(datos):
        if datos is None:
            return COLOR_SIN_DATO
        return color_por_iec(datos.get("iec"))

    def style_function(feature):
        codigo = feature["properties"].get("MPIO_CCNCT")
        datos = iec_dict.get(codigo)

        if not hay_seleccion:
            return {
                "fillColor": color_de(datos),
                "fillOpacity": 0.75,
                "color": "#ffffff",
                "weight": 0.6,
            }

        if codigo == codigo_seleccionado:
            # Municipio seleccionado: resaltado con su color real de IEC y borde grueso
            return {
                "fillColor": color_de(datos),
                "fillOpacity": 0.9,
                "color": "#222222",
                "weight": 3,
            }

        # Resto del mapa: atenuado mientras hay una selección activa
        return {
            "fillColor": COLOR_ATENUADO,
            "fillOpacity": 0.35,
            "color": "#ffffff",
            "weight": 0.4,
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
        feature["properties"]["_nombre_tooltip"] = feature["properties"].get("MPIO_CNMBR", "Desconocido")

        if datos:
            popup_html = (popups_html or {}).get(codigo) or construir_popup(datos)
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


def _filtrar_iec(iec_df, region_sel, nivel_sel, solo_pdet, solo_cd):
    df = iec_df.copy()
    if region_sel != "Todas":
        df = df[df["region"] == region_sel]
    if nivel_sel != "Todos":
        df = df[df["nivel_efectividad"] == nivel_sel]
    if solo_pdet:
        df = df[df["es_pdet"] == True]
    if solo_cd:
        df = df[df["tiene_centro_digital"] == True]
    return df


def _construir_mapa_con_filtros(iec_df_full, region_sel, nivel_sel, solo_pdet, solo_cd, codigo_sel):
    """Arma un folium.Map NUEVO en cada llamada (los objetos Map no se pueden
    cachear/reutilizar: se mutan internamente cada vez que st_folium los
    renderiza, y reusar el mismo objeto entre reruns causa
    'OrderedDict mutated during iteration'). Lo que sí reutilizamos de caché
    es el trabajo pesado que es seguro cachear: el geojson leído de disco y
    el HTML de los popups (ambos son datos inmutables, no objetos con estado)."""
    geojson = cargar_geojson()
    popups_html = _popups_por_codigo(iec_df_full)
    df_filtrado = _filtrar_iec(iec_df_full, region_sel, nivel_sel, solo_pdet, solo_cd)
    return construir_mapa(df_filtrado, geojson, codigo_seleccionado=codigo_sel, popups_html=popups_html)


def render_mapa():
    st.markdown(
        "Este mapa muestra el **IEC (Índice de Efectividad de Conectividad)** de cada "
        "municipio colombiano, en una escala de 0 a 100. Usa los filtros para acotar por "
        "región, nivel de efectividad, zona PDET o presencia de Centro Digital. "
        "Haz clic sobre un municipio para ver el detalle completo de sus componentes."
    )

    if st.button("🔄 Recargar datos"):
        st.cache_data.clear()
        st.cache_resource.clear()

    iec_df = cargar_iec()

    with st.expander("⚙️ Filtros", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            regiones   = ["Todas"] + sorted(iec_df["region"].dropna().unique().tolist())
            region_sel = st.selectbox("Región", regiones)
        with col2:
            nivel_sel  = st.selectbox("Nivel de efectividad", ["Todos", "Alto", "Medio", "Bajo"])
        with col3:
            solo_pdet  = st.checkbox("Solo PDET")
            solo_cd    = st.checkbox("Solo con CD activo")
        with col4:
            municipios_tabla = (
                iec_df[["municipio", "codigo_municipio_men"]]
                .dropna()
                .drop_duplicates()
                .sort_values("municipio")
            )
            municipio_sel = st.selectbox("Municipio", ["Todos"] + municipios_tabla["municipio"].tolist())
            codigo_sel = None
            if municipio_sel != "Todos":
                coincidencias = municipios_tabla.loc[municipios_tabla["municipio"] == municipio_sel, "codigo_municipio_men"]
                codigo_sel = coincidencias.iloc[0] if not coincidencias.empty else None

    _leyenda_iec = [
        ("#1a9641", "75-100"),
        ("#a6d96a", "60-74"),
        ("#fdae61", "45-59"),
        ("#d7191c", "0-44"),
        (COLOR_SIN_DATO, "Sin dato"),
    ]
    _swatches = "".join(
        f'<span style="display:inline-flex; align-items:center; margin-right:14px;">'
        f'<span style="width:12px; height:12px; background:{color}; border-radius:3px; '
        f'display:inline-block; margin-right:5px;"></span>'
        f'<span style="font-size:13px; color:#444;">{etiqueta}</span></span>'
        for color, etiqueta in _leyenda_iec
    )
    st.markdown(
        f'<div style="margin-bottom:6px;"><b style="font-size:13px;">Leyenda (IEC):</b> {_swatches}</div>',
        unsafe_allow_html=True,
    )
    if municipio_sel != "Todos":
        st.caption(f"🔎 Resaltando **{municipio_sel}** — el resto del mapa se muestra atenuado.")

    df_filtrado = _filtrar_iec(iec_df, region_sel, nivel_sel, solo_pdet, solo_cd)
    st.markdown(f"**{len(df_filtrado)} municipios** seleccionados")

    mapa = _construir_mapa_con_filtros(iec_df, region_sel, nivel_sel, solo_pdet, solo_cd, codigo_sel)

    # OJO: ya NO pasamos returned_objects=[]; necesitamos que st_folium
    # devuelva el municipio sobre el que el usuario hizo clic.
    #
    # El "key" tiene que cambiar cuando cambian los filtros. Si se deja fijo,
    # streamlit-folium intenta reutilizar el mismo contenedor Leaflet y
    # "parchar" el mapa anterior con el nuevo en vez de recrearlo desde cero,
    # lo cual rompe con "Map container is already initialized" y variables
    # geo_json_XXXX no definidas cuando la estructura del mapa cambia mucho
    # (como al resaltar un municipio distinto). Con un key dinámico, cada
    # combinación de filtros obtiene su propio contenedor limpio.
    key_mapa = f"mapa_principal_{region_sel}_{nivel_sel}_{solo_pdet}_{solo_cd}_{codigo_sel}"
    salida = st_folium(
        mapa,
        use_container_width=True,
        height=650,
        returned_objects=["last_active_drawing"],
        key=key_mapa,
    )

    # --- Panel de análisis con IA del municipio seleccionado -----------
    _render_panel_analisis(salida, iec_df)

    # --- Glosario -------------------------------------------------------
    st.divider()
    st.markdown("#### 📖 Glosario de términos")
    for termino, definicion in GLOSARIO:
        with st.expander(termino):
            st.markdown(definicion)


def _municipio_desde_click(salida, iec_df):
    """A partir de la salida de st_folium intenta identificar el municipio
    clickeado. Folium no nos da el código directamente, así que ubicamos el
    municipio cuyo polígono contiene el punto donde se hizo clic usando el
    nombre del tooltip activo, con respaldo en las coordenadas."""
    if not salida:
        return None

    # 1) Vía tooltip / objeto activo (nombre del municipio)
    nombre = None
    obj = salida.get("last_active_drawing") or salida.get("last_object_clicked_tooltip")
    if isinstance(obj, dict):
        props = obj.get("properties", {})
        nombre = props.get("_nombre_tooltip") or props.get("MPIO_CNMBR")
    elif isinstance(obj, str):
        nombre = obj

    if nombre:
        coincidencias = iec_df[iec_df["municipio"].str.upper() == str(nombre).upper()]
        if not coincidencias.empty:
            return coincidencias.iloc[0].to_dict()

    return None


def _render_panel_analisis(salida, iec_df):
    st.divider()
    st.markdown("### 🤖 Análisis del municipio con IA")

    datos = _municipio_desde_click(salida, iec_df)

    if datos is None:
        st.info(
            "Haz clic en un municipio del mapa para seleccionarlo y luego genera "
            "un análisis detallado con inteligencia artificial."
        )
        return

    # Guardamos el municipio seleccionado en la sesión para que el análisis
    # persista aunque Streamlit se recargue.
    st.markdown(
        f"Municipio seleccionado: **{datos.get('municipio')}** "
        f"({datos.get('departamento')}) · IEC {datos.get('iec', 0):.1f}"
    )

    if st.button("✨ Generar análisis del municipio", use_container_width=True, key="btn_analisis_municipio"):
        with st.spinner("Generando análisis con IA..."):
            analisis = analizar_municipio_con_ia(datos)
        st.session_state["analisis_municipio"] = {
            "codigo": datos.get("codigo_municipio_men"),
            "texto": analisis,
        }

    # Mostrar el último análisis generado, si corresponde a este municipio.
    guardado = st.session_state.get("analisis_municipio")
    if guardado and guardado.get("codigo") == datos.get("codigo_municipio_men"):
        st.markdown(guardado["texto"])