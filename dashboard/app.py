import streamlit as st
from components.mapa import render_mapa
from components.simulador import render_simulador
from components.preguntas import render_preguntas

st.set_page_config(
    page_title="ConectaIA — Centros Digitales Rurales",
    page_icon="🌐",
    layout="wide"
)

st.markdown("""
    <style>
        iframe {
            height: 700px !important;
            width: 100% !important;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
        }

        /* Indicador de carga: Streamlit ya muestra automáticamente un ícono
           de "Running..." cada vez que cambias un filtro/control y la app
           se recalcula. Aquí lo agrandamos y le damos color para que sea
           evidente que el dashboard está procesando el cambio. */
        [data-testid="stStatusWidget"] {
            transform: scale(1.6);
            transform-origin: top right;
            background-color: #62A7B4;
            border-radius: 8px;
            padding: 4px 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        }
        [data-testid="stStatusWidget"] * {
            color: #ffffff !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 ConectaIA — Impacto de los Centros Digitales Rurales")
st.markdown("Análisis del impacto educativo de los Centros Digitales Rurales en Colombia · EPM & Julius AI")

tab_mapa, tab_simulador, tab_preguntas = st.tabs(["Mapa de municipios", "Simulador de impacto", "Preguntas en lenguaje natural"])

with tab_mapa:
    render_mapa()

with tab_simulador:
    render_simulador()

with tab_preguntas:
    render_preguntas()
