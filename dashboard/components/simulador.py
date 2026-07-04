import pickle
import pandas as pd
import streamlit as st
from db.connection import cargar_importancia, get_engine
import os


@st.cache_resource
def cargar_modelo():
    ruta = os.path.join(os.path.dirname(__file__), "..", "models", "random_forest.pkl")
    with open(ruta, "rb") as f:
        return pickle.load(f)


def render_simulador():
    st.subheader("Simula el nivel de efectividad de un Centro Digital")
    st.markdown("Ingresa las características del Centro Digital y el modelo predecirá su nivel de efectividad esperado.")

    col1, col2 = st.columns(2)

    with col1:
        inversion = st.number_input(
            "Inversión total (COP)",
            min_value=0,
            max_value=10_000_000_000,
            value=500_000_000,
            step=50_000_000,
            format="%d"
        )
        usuarios = st.number_input(
            "Usuarios activos mensuales (promedio)",
            min_value=0,
            max_value=500,
            value=50
        )
        vel_subida = st.number_input(
            "Velocidad de subida (Mbps)",
            min_value=0.0,
            max_value=100.0,
            value=3.5,
            step=0.5
        )

    with col2:
        vel_bajada = st.number_input(
            "Velocidad de bajada (Mbps)",
            min_value=0.0,
            max_value=100.0,
            value=14.0,
            step=0.5
        )
        n_sedes = st.number_input(
            "Número de sedes con CD",
            min_value=1,
            max_value=100,
            value=5
        )
        cluster = st.selectbox(
            "Cluster territorial",
            options=[0, 1, 2, 3, 4, 5],
            format_func=lambda x: f"Cluster {x}"
        )
        es_pdet = st.checkbox("¿Es zona PDET?")

    if st.button("🔮 Predecir nivel de efectividad", use_container_width=True):
        modelo = cargar_modelo()

        entrada = pd.DataFrame([{
            "inversion_total":        inversion,
            "usuarios_activos_prom":  usuarios,
            "velocidad_subida_prom":  vel_subida,
            "velocidad_bajada_prom":  vel_bajada,
            "n_centros_digitales":    n_sedes,
            "cluster":                cluster,
            "es_pdet":                int(es_pdet),
        }])

        prediccion    = modelo.predict(entrada)[0]
        probabilidades = modelo.predict_proba(entrada)[0]
        clases        = modelo.classes_

        colores = {"Alto": "green", "Medio": "orange", "Bajo": "red"}
        color   = colores.get(prediccion, "gray")

        st.markdown(f"""
            <div style="
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
            ">
                <h2 style="color: {color}; margin: 0;">
                    Nivel de efectividad predicho: {prediccion}
                </h2>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("**Probabilidades por clase:**")
        prob_df = pd.DataFrame({
            "Nivel":        clases,
            "Probabilidad": [f"{p:.1%}" for p in probabilidades]
        })
        st.dataframe(prob_df, hide_index=True, use_container_width=True)

        st.markdown("**Importancia de variables del modelo:**")
        importancia_df = cargar_importancia()
        st.bar_chart(importancia_df.set_index("variable")["importancia"])