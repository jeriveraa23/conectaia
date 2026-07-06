import json
import folium
import streamlit as st
from streamlit_folium import st_folium
from db.connection import cargar_iec
from utils.colores import color_por_iec, color_por_nivel
import os


def cargar_geojson():
    ruta = os.path.join(os.path.dirname(__file__), "..", "data", "municipios.geojson")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def construir_popup(datos):
    iec = datos.get('iec', 0)
    nivel = datos.get('nivel_efectividad', 'N/A')
    diferencia = datos.get('diferencia_vs_cluster', 0)

    color_nivel = {"Alto": "#1a9641", "Medio": "#f77f00", "Bajo": "#d7191c"}.get(nivel, "#666")
    signo = "+" if diferencia > 0 else ""

    return f"""
        <div style="font-family: Arial; min-width: 220px; max-width: 280px;">
            <h4 style="margin:0 0 2px 0; color:#222;">{datos.get('municipio', 'N/A')}</h4>
            <p style="margin:0 0 8px 0; color:#888; font-size:12px;">
                {datos.get('departamento', '')} · {datos.get('region', '')}
            </p>

            <div style="
                background:{color_nivel}22;
                border-left: 4px solid {color_nivel};
                padding: 6px 10px;
                border-radius: 4px;
                margin-bottom: 8px;
            ">
                <b style="color:{color_nivel};">Efectividad {nivel}</b><br>
                <span style="font-size:13px;">IEC: <b>{round(iec, 1)}</b> / 100</span>
            </div>

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
                vs municipios similares: <b style="color:{color_nivel};">{signo}{round(diferencia, 1)} pts</b><br>
                {'✅ Centro Digital activo' if datos.get('tiene_centro_digital') else '❌ Sin Centro Digital'}
                {'· 🏔️ Zona PDET' if datos.get('es_pdet') else ''}
            </p>
        </div>
    """


def construir_mapa(iec_df, geojson, modo_color):
    mapa = folium.Map(
        location=[4.5, -74.0],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    iec_dict = iec_df.set_index("codigo_municipio_men").to_dict("index")

    def color_de(datos):
        """Usa umbrales FIJOS (los mismos de la leyenda y las tarjetas),
        nunca cuantiles relativos al conjunto filtrado."""
        if datos is None:
            return "#eeeeee"
        if modo_color == "IEC":
            return color_por_iec(datos.get("iec"))
        return color_por_nivel(datos.get("nivel_efectividad"))

    def style_function(feature):
        codigo = feature["properties"].get("MPIO_CCNCT")
        datos = iec_dict.get(codigo)
        return {
            "fillColor": color_de(datos),
            "fillOpacity": 0.75 if datos else 0.4,
            "color": "#ffffff",
            "weight": 0.6,
        }

    def highlight_function(feature):
        return {
            "fillOpacity": 0.9,
            "color": "#333333",
            "weight": 2,
        }

    for feature in geojson["features"]:
        codigo = feature["properties"].get("MPIO_CCNCT")
        datos = iec_dict.get(codigo)

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
            tooltip=feature["properties"].get("MPIO_CNMBR", ""),
            popup=popup,
        ).add_to(mapa)

    return mapa


def render_mapa():
    if st.button("🔄 Recargar datos"):
        st.cache_data.clear()

    iec_df  = cargar_iec()
    geojson = cargar_geojson()

    with st.expander("⚙️ Filtros", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            modo_color = st.radio("Colorear por:", ["IEC (Índice de Efectividad de Conectividad)", "Nivel de efectividad"])
        with col2:
            regiones   = ["Todas"] + sorted(iec_df["region"].dropna().unique().tolist())
            region_sel = st.selectbox("Región", regiones)
        with col3:
            nivel_sel  = st.selectbox("Nivel", ["Todos", "Alto", "Medio", "Bajo"])
        with col4:
            solo_pdet  = st.checkbox("Solo PDET (Programas de Desarrollo con Enfoque Territorial)")
            solo_cd    = st.checkbox("Solo con Centro Digital activo")

    if modo_color == "IEC":
        st.markdown("**Leyenda (IEC)**: 🟢 75-100 · 🟡 60-74 · 🟠 45-59 · 🔴 0-44")
    else:
        st.markdown("**Leyenda (Nivel de efectividad)**: 🟢 Alto · 🟠 Medio · 🔴 Bajo")

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

    mapa = construir_mapa(df_filtrado, geojson, modo_color)

    contenedor = st.container()
    with contenedor:
        st_folium(
            mapa,
            use_container_width=True,
            height=650,
            returned_objects=[],
            key="mapa_principal"
        )
