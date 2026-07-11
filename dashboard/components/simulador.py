import os
import json
import pickle
import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium
from openai import OpenAI
from db.connection import get_engine, cargar_importancia


@st.cache_resource
def cargar_modelo():
    ruta = os.path.join(os.path.dirname(__file__), "..", "models", "random_forest.pkl")
    with open(ruta, "rb") as f:
        return pickle.load(f)


@st.cache_data
def cargar_municipios():
    return pd.read_sql("""
        SELECT 
            mi.codigo_municipio_men,
            mi.municipio,
            mi.departamento,
            mi.cluster,
            mi.iec,
            mi.iec_promedio_cluster_sin_cd,
            mi.diferencia_vs_cluster,
            mi.nivel_efectividad,
            mi.region,
            AVG(di.velocidad_subida_prom) as velocidad_subida_prom,
            AVG(di.velocidad_bajada_prom) as velocidad_bajada_prom
        FROM gold.municipios_iec mi
        LEFT JOIN silver.dataset_integrado di 
            ON mi.codigo_municipio_men = di.codigo_municipio_men
        GROUP BY 
            mi.codigo_municipio_men, mi.municipio, mi.departamento,
            mi.cluster, mi.iec, mi.iec_promedio_cluster_sin_cd,
            mi.diferencia_vs_cluster, mi.nivel_efectividad, mi.region
        ORDER BY mi.municipio
    """, get_engine())


@st.cache_data
def cargar_geojson():
    ruta = os.path.join(os.path.dirname(__file__), "..", "data", "municipios.geojson")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


RANGOS_INVERSION = {
    "Baja (menos de $200M)":  100_000_000,
    "Media ($200M - $500M)":  350_000_000,
    "Alta (más de $500M)":    750_000_000,
}

RANGOS_USUARIOS = {
    "Pocos (menos de 30)":    15,
    "Moderados (30 - 100)":   65,
    "Muchos (más de 100)":    150,
}

COLORES_NIVEL = {
    "Alto":  "#1a9641",
    "Medio": "#f77f00",
    "Bajo":  "#d7191c",
}


def explicar_con_openai(municipio, departamento, region, cluster, iec, iec_promedio_cluster,
                         diferencia, nivel_predicho, n_sedes, inversion_sel, usuarios_sel, es_pdet):
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    prompt = f"""
Eres un analista de datos educativos de Colombia. Explica en 3 párrafos cortos y en lenguaje claro 
para un alcalde o funcionario público (no técnico) por qué el municipio de {municipio} ({departamento}) 
obtuvo un nivel de efectividad "{nivel_predicho}" en el simulador de Centros Digitales Rurales.

Datos del municipio:
- Región: {region}
- IEC actual: {iec:.1f} sobre 100
- IEC promedio de municipios similares (grupo territorial {cluster}): {iec_promedio_cluster:.1f}
- Diferencia vs grupo: {diferencia:+.1f} puntos
- Número de sedes simuladas: {n_sedes}
- Inversión estimada: {inversion_sel}
- Usuarios esperados por mes: {usuarios_sel}
- Zona PDET: {"Sí" if es_pdet else "No"}

En el primer párrafo explica qué significa el nivel "{nivel_predicho}" y cómo se compara el municipio 
con otros de su grupo territorial. En el segundo párrafo explica qué factores del Centro Digital 
influyen más en este resultado. En el tercer párrafo da una recomendación práctica para mejorar 
o mantener la efectividad. Sé directo, evita tecnicismos y usa máximo 150 palabras en total.
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].message.content


def construir_mapa_simulacion(geojson, codigo_municipio, municipio, iec_real,
                               iec_promedio_cluster, nivel_predicho, diferencia):
    mapa = folium.Map(location=[4.5, -74.0], zoom_start=5, tiles="CartoDB positron")
    color_pred = COLORES_NIVEL.get(nivel_predicho, "#666")
    signo = "+" if diferencia > 0 else ""

    for feature in geojson["features"]:
        codigo = feature["properties"].get("MPIO_CCNCT")

        if codigo == codigo_municipio:
            popup_html = f"""
                <div style="font-family:Arial; min-width:220px;">
                    <h4 style="margin:0; color:#222;">{municipio}</h4>
                    <div style="
                        background:{color_pred}22;
                        border-left:4px solid {color_pred};
                        padding:6px 10px;
                        border-radius:4px;
                        margin:8px 0;
                    ">
                        <b style="color:{color_pred};">Efectividad simulada: {nivel_predicho}</b>
                    </div>
                    <table style="width:100%; font-size:12px;">
                        <tr>
                            <td style="color:#555;">IEC actual</td>
                            <td style="text-align:right;"><b>{iec_real:.1f}</b>/100</td>
                        </tr>
                        <tr>
                            <td style="color:#555;">IEC promedio del grupo</td>
                            <td style="text-align:right;"><b>{iec_promedio_cluster:.1f}</b>/100</td>
                        </tr>
                        <tr>
                            <td style="color:#555;">Diferencia vs grupo</td>
                            <td style="text-align:right; color:{color_pred};"><b>{signo}{diferencia:.1f} pts</b></td>
                        </tr>
                    </table>
                </div>
            """
            folium.GeoJson(
                feature,
                style_function=lambda x, c=color_pred: {
                    "fillColor": c,
                    "color": "#333",
                    "weight": 2,
                    "fillOpacity": 0.8,
                },
                tooltip=municipio,
                popup=folium.Popup(popup_html, max_width=280),
            ).add_to(mapa)
        else:
            folium.GeoJson(
                feature,
                style_function=lambda x: {
                    "fillColor": "#dddddd",
                    "color": "#ffffff",
                    "weight": 0.3,
                    "fillOpacity": 0.5,
                },
            ).add_to(mapa)

    return mapa


def render_simulador():
    st.subheader("🧪 Simulador de impacto de un Centro Digital")
    st.markdown(
        "Selecciona las características del municipio y del Centro Digital para predecir "
        "su nivel de efectividad esperado según el modelo entrenado con datos reales."
    )

    municipios_df = cargar_municipios()
    geojson = cargar_geojson()
    modelo = cargar_modelo()

    # ── Formulario ────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        opciones_municipio = municipios_df["municipio"] + " — " + municipios_df["departamento"]
        seleccion = st.selectbox(
            "Municipio",
            opciones_municipio,
            help="Selecciona el municipio donde se instalará o planea instalar el Centro Digital."
        )

        n_sedes = st.number_input(
            "Número de sedes con Centro Digital",
            min_value=1, max_value=100, value=5,
            help="¿En cuántas instituciones educativas del municipio estará disponible el Centro Digital?"
        )

        inversion_sel = st.selectbox(
            "Inversión estimada",
            list(RANGOS_INVERSION.keys()),
            help="Monto aproximado destinado a la instalación y operación del Centro Digital en este municipio."
        )

    with col2:
        usuarios_sel = st.selectbox(
            "Usuarios esperados por mes",
            list(RANGOS_USUARIOS.keys()),
            help="Número aproximado de personas que usarán activamente el Centro Digital cada mes."
        )

        es_pdet = st.checkbox(
            "¿Es zona PDET?",
            help=(
                "Las zonas PDET son territorios priorizados por el gobierno "
                "para la construcción de paz y el desarrollo rural en Colombia."
            )
        )

    # ── Datos del municipio seleccionado ─────────────────────────────────────
    idx = opciones_municipio[opciones_municipio == seleccion].index[0]
    mun = municipios_df.loc[idx]

    cluster = int(mun["cluster"]) if pd.notna(mun["cluster"]) else 0
    vel_subida = float(mun["velocidad_subida_prom"]) if pd.notna(mun["velocidad_subida_prom"]) else 3.5
    vel_bajada = float(mun["velocidad_bajada_prom"]) if pd.notna(mun["velocidad_bajada_prom"]) else 14.0

    # Perfil del grupo territorial
    regiones_cluster = pd.read_sql(f"""
        SELECT fm.region, COUNT(*) as n
        FROM silver.municipios_clusterizados mc
        JOIN silver.features_municipio fm 
            ON mc.codigo_municipio_men = fm.codigo_municipio_men
        WHERE mc.cluster = {cluster}
        GROUP BY fm.region
        ORDER BY n DESC
    """, get_engine())

    n_total_cluster = regiones_cluster["n"].sum()
    iec_promedio_cluster = float(mun["iec_promedio_cluster_sin_cd"]) if pd.notna(mun["iec_promedio_cluster_sin_cd"]) else 0.0

    with st.expander("📊 Ver perfil del Grupo territorial de este municipio", expanded=False):
        st.markdown(f"""
            **¿Qué es el Grupo territorial?**
            Es la categoría a la que pertenece cada municipio según su región natural,
            tamaño de población escolar y situación educativa histórica antes de 2020.
            Permite comparar municipios de forma justa — solo contra otros con perfil similar.

            **Lo que determina el grupo:**
            - 🌎 **Región natural** — Andina, Caribe, Pacífica, Orinoquía o Amazonía
            - 👶 **Población escolar** — cuántos niños entre 5 y 16 años tiene el municipio
            - 📉 **Deserción histórica** — cómo venía el municipio antes de 2020
        """)

        col_a, col_b = st.columns(2)
        col_a.metric("Municipios en este grupo", int(n_total_cluster))
        col_a.metric("IEC promedio del grupo", f"{iec_promedio_cluster:.1f}")

        with col_b:
            st.markdown("**Composición por región:**")
            for _, row in regiones_cluster.iterrows():
                pct = row["n"] / n_total_cluster * 100
                st.markdown(f"- {row['region']}: **{int(row['n'])}** municipios ({pct:.0f}%)")

    st.divider()

    # ── Predicción ────────────────────────────────────────────────────────────
    if st.button("🔮 Predecir nivel de efectividad", use_container_width=True):
        entrada = pd.DataFrame([{
            "inversion_total":       RANGOS_INVERSION[inversion_sel],
            "usuarios_activos_prom": RANGOS_USUARIOS[usuarios_sel],
            "velocidad_subida_prom": vel_subida,
            "velocidad_bajada_prom": vel_bajada,
            "n_centros_digitales":   n_sedes,
            "cluster":               cluster,
            "es_pdet":               int(es_pdet),
        }])

        prediccion     = modelo.predict(entrada)[0]
        probabilidades = modelo.predict_proba(entrada)[0]
        clases         = modelo.classes_
        color          = COLORES_NIVEL.get(prediccion, "#666")
        diferencia     = float(mun["diferencia_vs_cluster"]) if pd.notna(mun["diferencia_vs_cluster"]) else 0.0
        iec_real       = float(mun["iec"]) if pd.notna(mun["iec"]) else 0.0

        # Resultado principal
        st.markdown(f"""
            <div style="
                background:{color}18;
                border:2px solid {color};
                border-radius:12px;
                padding:20px;
                text-align:center;
                margin:16px 0;
            ">
                <h2 style="color:{color}; margin:0;">
                    Efectividad esperada: {prediccion}
                </h2>
                <p style="color:#555; margin:6px 0 0 0;">
                    para {mun['municipio']} ({mun['departamento']})
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Métricas comparativas
        col1, col2, col3 = st.columns(3)
        col1.metric("IEC actual del municipio", f"{iec_real:.1f}")
        col2.metric("IEC promedio del grupo territorial", f"{iec_promedio_cluster:.1f}")
        col3.metric(
            "Diferencia vs grupo",
            f"{diferencia:+.1f} pts",
            delta=f"{diferencia:+.1f}",
        )

        # Probabilidades
        st.markdown("**Probabilidad por nivel:**")
        prob_df = pd.DataFrame({
            "Nivel":        clases,
            "Probabilidad": [f"{p:.1%}" for p in probabilidades]
        })
        st.dataframe(prob_df, hide_index=True, use_container_width=True)

        # Importancia de variables
        st.markdown("**¿Qué factores influyen más en la efectividad?**")
        importancia_df = cargar_importancia()
        importancia_df["variable"] = importancia_df["variable"].replace({
            "usuarios_activos_prom":  "Usuarios activos mensuales",
            "inversion_total":        "Inversión total",
            "velocidad_bajada_prom":  "Velocidad de bajada",
            "velocidad_subida_prom":  "Velocidad de subida",
            "n_centros_digitales":    "Número de sedes",
            "cluster":                "Grupo territorial",
            "es_pdet":                "Zona PDET",
        })
        st.bar_chart(importancia_df.set_index("variable")["importancia"])

        # Explicación con OpenAI
        st.markdown("### 💡 ¿Por qué este resultado?")
        with st.spinner("Generando análisis..."):
            explicacion = explicar_con_openai(
                municipio=mun["municipio"],
                departamento=mun["departamento"],
                region=mun["region"],
                cluster=cluster,
                iec=iec_real,
                iec_promedio_cluster=iec_promedio_cluster,
                diferencia=diferencia,
                nivel_predicho=prediccion,
                n_sedes=n_sedes,
                inversion_sel=inversion_sel,
                usuarios_sel=usuarios_sel,
                es_pdet=es_pdet,
            )
        st.markdown(explicacion)

        # Mapa de simulación
        st.markdown("### 🗺️ Municipio simulado en el mapa")
        mapa_sim = construir_mapa_simulacion(
            geojson=geojson,
            codigo_municipio=mun["codigo_municipio_men"],
            municipio=mun["municipio"],
            iec_real=iec_real,
            iec_promedio_cluster=iec_promedio_cluster,
            nivel_predicho=prediccion,
            diferencia=diferencia,
        )
        st_folium(mapa_sim, use_container_width=True, height=500, returned_objects=[], key="mapa_simulacion")