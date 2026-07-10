import os
import pickle
import pandas as pd
import streamlit as st
from db.connection import get_engine, cargar_iec, cargar_importancia


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
def cargar_perfil_clusters():
    return pd.read_sql("""
        SELECT 
            mc.cluster,
            COUNT(*) as n_municipios,
            AVG(fm.desercion_pre_2020) as desercion_promedio,
            AVG(fm.poblacion_5_16) as poblacion_promedio,
            MODE() WITHIN GROUP (ORDER BY fm.region) as region_predominante,
            AVG(mi.iec) as iec_promedio
        FROM silver.municipios_clusterizados mc
        JOIN silver.features_municipio fm 
            ON mc.codigo_municipio_men = fm.codigo_municipio_men
        JOIN gold.municipios_iec mi 
            ON mc.codigo_municipio_men = mi.codigo_municipio_men
        GROUP BY mc.cluster
        ORDER BY mc.cluster
    """, get_engine())


RANGOS_INVERSION = {
    "Baja (menos de $200M)":      100_000_000,
    "Media ($200M - $500M)":      350_000_000,
    "Alta (más de $500M)":        750_000_000,
}

RANGOS_USUARIOS = {
    "Pocos (menos de 30)":        15,
    "Moderados (30 - 100)":       65,
    "Muchos (más de 100)":        150,
}

COLORES_NIVEL = {
    "Alto":  "#1a9641",
    "Medio": "#f77f00",
    "Bajo":  "#d7191c",
}


def render_simulador():
    st.subheader("🧪 Simulador de impacto de un Centro Digital")
    st.markdown(
        "Selecciona las características del municipio y del Centro Digital para predecir "
        "su nivel de efectividad esperado según el modelo entrenado con datos reales."
    )

    municipios_df = cargar_municipios()
    perfil_clusters = cargar_perfil_clusters()
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
            min_value=1,
            max_value=100,
            value=5,
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
                "Las zonas PDET (Programas de Desarrollo con Enfoque Territorial) son territorios "
                "priorizados por el gobierno para la construcción de paz y el desarrollo rural en Colombia."
            )
        )

    # ── Datos del municipio seleccionado ─────────────────────────────────────
    idx = opciones_municipio[opciones_municipio == seleccion].index[0]
    mun = municipios_df.loc[idx]

    cluster = int(mun["cluster"]) if pd.notna(mun["cluster"]) else 0
    vel_subida = float(mun["velocidad_subida_prom"]) if pd.notna(mun["velocidad_subida_prom"]) else 3.5
    vel_bajada = float(mun["velocidad_bajada_prom"]) if pd.notna(mun["velocidad_bajada_prom"]) else 14.0

    # Info del grupo territorial
    perfil = perfil_clusters[perfil_clusters["cluster"] == cluster]

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

        if not perfil.empty:
            p = perfil.iloc[0]
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Municipios en este grupo", int(p["n_municipios"]))
            col_b.metric("Región predominante", p["region_predominante"])
            col_c.metric("IEC promedio del grupo", f"{p['iec_promedio']:.1f}")
            col_d.metric("Deserción promedio histórica", f"{p['desercion_promedio']:.1f}%")

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
        col1.metric(
            "IEC actual del municipio",
            f"{mun['iec']:.1f}" if pd.notna(mun['iec']) else "Sin datos",
        )
        col2.metric(
            "IEC promedio del grupo territorial",
            f"{mun['iec_promedio_cluster_sin_cd']:.1f}" if pd.notna(mun['iec_promedio_cluster_sin_cd']) else "Sin datos",
        )
        col3.metric(
            "Diferencia vs grupo",
            f"{mun['diferencia_vs_cluster']:+.1f} pts" if pd.notna(mun['diferencia_vs_cluster']) else "Sin datos",
            delta=f"{mun['diferencia_vs_cluster']:+.1f}" if pd.notna(mun['diferencia_vs_cluster']) else None,
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