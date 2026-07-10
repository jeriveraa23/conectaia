import pickle
import pandas as pd
import streamlit as st
from db.connection import cargar_importancia, cargar_dataset, get_engine
import os


@st.cache_resource
def cargar_modelo():
    ruta = os.path.join(os.path.dirname(__file__), "..", "models", "random_forest.pkl")
    with open(ruta, "rb") as f:
        return pickle.load(f)


# Descripciones en lenguaje sencillo de cada variable del modelo, para la
# tabla estática de importancia que se muestra antes de simular.
DESCRIPCIONES_VARIABLES = {
    "usuarios_activos_prom": "Qué tanto se usa realmente el Centro Digital cada mes. Es el factor más determinante: tener el centro no basta, hay que usarlo.",
    "inversion_total": "Monto total invertido en el Centro Digital.",
    "velocidad_subida_prom": "Velocidad de subida de la conexión a internet del centro.",
    "velocidad_bajada_prom": "Velocidad de bajada de la conexión a internet del centro.",
    "n_centros_digitales": "Número de sedes con Centro Digital en el municipio.",
    "cluster": "Grupo de municipios con características socioeconómicas similares al que pertenece.",
    "es_pdet": "Si el municipio está en una zona PDET. Su efecto en el modelo es marginal.",
}


def render_simulador():
    st.subheader("Simula el nivel de efectividad de un Centro Digital")
    st.markdown(
        "Este simulador usa el modelo de Random Forest entrenado con datos históricos "
        "(97.7% de accuracy) para predecir qué **nivel de efectividad** tendría un Centro "
        "Digital según sus características. Ajusta los valores de abajo y presiona "
        "**Predecir** para ver el resultado."
    )

    importancia_df = cargar_importancia()

    st.markdown("**Importancia de variables en el modelo**")
    st.caption(
        "Esto muestra qué tanto pesa cada característica en la predicción del modelo, "
        "de mayor a menor influencia."
    )
    tabla_importancia = importancia_df.copy()
    tabla_importancia["Descripción"] = tabla_importancia["variable"].map(
        lambda v: DESCRIPCIONES_VARIABLES.get(v, "")
    )
    tabla_importancia["Importancia"] = tabla_importancia["importancia"].map(lambda x: f"{x:.1%}")
    tabla_importancia = tabla_importancia.rename(columns={"variable": "Variable"})[
        ["Variable", "Importancia", "Descripción"]
    ]
    st.dataframe(tabla_importancia, hide_index=True, use_container_width=True)

    st.divider()

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
        st.caption(f"💰 ${inversion:,.0f} COP".replace(",", "."))
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

        prediccion     = modelo.predict(entrada)[0]
        probabilidades = modelo.predict_proba(entrada)[0]
        clases         = list(modelo.classes_)

        confianza = probabilidades[clases.index(prediccion)] * 100

        colores = {"Alto": "green", "Medio": "orange", "Bajo": "red"}
        color   = colores.get(prediccion, "gray")

        # --- Recomendación orientada al usuario final: qué variables ---
        # --- conviene mejorar para subir de nivel, no cómo funciona el modelo ---
        promedios = cargar_dataset().mean(numeric_only=True)
        top_vars = importancia_df["variable"].tolist()[:3]

        valores_usuario = {
            "usuarios_activos_prom": usuarios,
            "inversion_total": inversion,
            "velocidad_subida_prom": vel_subida,
            "velocidad_bajada_prom": vel_bajada,
            "n_centros_digitales": n_sedes,
        }

        nombres_legibles = {
            "usuarios_activos_prom": "el uso mensual del Centro Digital (usuarios activos)",
            "inversion_total": "la inversión total",
            "velocidad_subida_prom": "la velocidad de subida de internet",
            "velocidad_bajada_prom": "la velocidad de bajada de internet",
            "n_centros_digitales": "el número de sedes con Centro Digital",
        }

        fortalezas = []
        mejoras = []
        for var in top_vars:
            if var not in valores_usuario or var not in promedios:
                continue
            valor_usuario = valores_usuario[var]
            promedio = promedios[var]
            nombre = nombres_legibles.get(var, var)
            if valor_usuario >= promedio:
                fortalezas.append(nombre)
            else:
                mejoras.append(nombre)

        if prediccion == "Alto":
            if fortalezas:
                justificacion = (
                    "¡Buen resultado! Los valores que ingresaste en "
                    f"{', '.join(fortalezas)} están en un buen nivel, y son justamente "
                    "los factores que más influyen en la efectividad de un Centro Digital. "
                    "Mantener estos valores ayuda a sostener este nivel."
                )
            else:
                justificacion = (
                    "El modelo predice un nivel Alto para esta combinación de valores. "
                    "Mantener estas condiciones ayuda a sostener este resultado."
                )
        elif mejoras:
            justificacion = (
                "Para lograr un nivel más alto de efectividad, te recomendamos enfocar "
                f"esfuerzos en mejorar {', '.join(mejoras)}, ya que son de los factores "
                "que más influyen en el resultado y actualmente están por debajo del "
                "promedio de los Centros Digitales activos."
            )
        else:
            justificacion = (
                "Los valores ingresados ya están en línea con el promedio de los Centros "
                "Digitales activos en los factores más influyentes. Para subir de nivel, "
                "considera reforzar aún más el uso mensual del centro por parte de la "
                "comunidad, que sigue siendo el factor de mayor peso."
            )

        st.markdown(f"""
            <div style="
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
            ">
                <h2 style="color: {color}; margin: 0 0 6px 0;">
                    Predicción del nivel de efectividad: {prediccion}
                </h2>
                <p style="margin:0; font-size: 15px; color:#444;">
                    Confianza del modelo: <b>{confianza:.1f}%</b>
                </p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**Recomendación:** {justificacion}")
