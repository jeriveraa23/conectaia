import os
import re
import pandas as pd
import streamlit as st
import google.generativeai as genai
from db.connection import get_engine

# ---------------------------------------------------------------------------
# Configuración del modelo
# ---------------------------------------------------------------------------
# Usamos un modelo Flash: es el que tiene el free tier más generoso en
# Google AI Studio y es más que suficiente para generar SQL + resúmenes.
# Verifica el nombre de modelo vigente y las cuotas actuales en
# https://ai.google.dev/pricing antes de desplegar a producción.
MODEL_NAME = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Esquema disponible para el agente (solo silver/gold: son las capas
# analíticas ya limpias; no exponemos bronze para evitar respuestas basadas
# en datos crudos sin procesar).
# ---------------------------------------------------------------------------
ESQUEMA_DESCRIPCION = """
silver.dataset_integrado (grano: municipio-año)
    codigo_municipio_men TEXT, municipio TEXT, departamento TEXT, anio INTEGER,
    tiene_centro_digital BOOLEAN, n_centros_digitales INTEGER,
    inversion_total NUMERIC, usuarios_activos_prom NUMERIC,
    velocidad_subida_prom NUMERIC, velocidad_bajada_prom NUMERIC,
    cobertura_neta NUMERIC, desercion NUMERIC, aprobacion NUMERIC,
    sedes_conectadas_internet NUMERIC, poblacion_5_16 NUMERIC

silver.features_municipio (grano: municipio)
    codigo_municipio_men TEXT, municipio TEXT, departamento TEXT,
    desercion_pre_2020 NUMERIC, desercion_post_2020 NUMERIC,
    brecha_desercion NUMERIC, region TEXT, indice_ruralidad NUMERIC,
    dificultad_acceso TEXT, poblacion_5_16 NUMERIC

silver.municipios_clusterizados (grano: municipio)
    codigo_municipio_men TEXT, municipio TEXT, departamento TEXT,
    cluster INTEGER, tiene_centro_digital BOOLEAN

gold.municipios_iec (grano: municipio) -- tabla principal para preguntas de impacto
    codigo_municipio_men TEXT, municipio TEXT, departamento TEXT, region TEXT,
    cluster INTEGER, tiene_centro_digital BOOLEAN,
    componente_desercion NUMERIC, componente_cobertura NUMERIC,
    componente_aprobacion NUMERIC, iec NUMERIC,
    iec_promedio_cluster_sin_cd NUMERIC, diferencia_vs_cluster NUMERIC,
    nivel_efectividad TEXT ('Alto'|'Medio'|'Bajo'), es_pdet BOOLEAN,
    es_outlier BOOLEAN, revisado_manual BOOLEAN

gold.modelo_resultados (grano: variable del modelo Random Forest)
    variable TEXT, importancia NUMERIC
"""

PALABRAS_PROHIBIDAS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "--", "/*", ";", "copy", "call",
]

EJEMPLOS_PREGUNTAS = [
    "¿Cuáles son los 5 municipios con mayor IEC que tienen centro digital?",
    "¿Cuál es el IEC promedio por región?",
    "¿Qué municipios en zona PDET tienen nivel de efectividad Alto?",
    "¿Cuántos municipios por cluster no tienen centro digital?",
]


def _configurar_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error(
            "Falta la variable de entorno GEMINI_API_KEY. "
            "Consíguela gratis en https://aistudio.google.com/apikey "
            "y agrégala a tu .env"
        )
        return False
    genai.configure(api_key=api_key)
    return True


def _extraer_sql(texto_respuesta: str) -> str:
    """Limpia bloques de markdown (```sql ... ```) que el modelo pueda incluir."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", texto_respuesta, re.DOTALL | re.IGNORECASE)
    sql = match.group(1) if match else texto_respuesta
    return sql.strip().rstrip(";").strip()


def _es_query_segura(sql: str) -> tuple[bool, str]:
    sql_lower = sql.lower()
    if not sql_lower.strip().startswith("select"):
        return False, "La consulta generada no es un SELECT. Por seguridad no se ejecuta."
    for palabra in PALABRAS_PROHIBIDAS:
        if palabra in sql_lower:
            return False, f"La consulta contiene un término no permitido ('{palabra}')."
    return True, ""


def _generar_sql(modelo, pregunta: str) -> str:
    prompt = f"""Eres un asistente que traduce preguntas en español a consultas SQL
de PostgreSQL, usando EXCLUSIVAMENTE el siguiente esquema:

{ESQUEMA_DESCRIPCION}

Reglas:
- Responde ÚNICAMENTE con la consulta SQL, sin explicación, sin markdown.
- Solo genera consultas SELECT (nunca INSERT/UPDATE/DELETE/DDL).
- Usa nombres de columnas y tablas exactamente como aparecen arriba, con su esquema (ej. gold.municipios_iec).
- Si la pregunta pide un "top N" o un listado, agrega siempre LIMIT 50 como máximo.
- Si la pregunta no se puede responder con este esquema, responde exactamente: NO_DISPONIBLE

Pregunta: {pregunta}

SQL:"""
    respuesta = modelo.generate_content(prompt)
    return _extraer_sql(respuesta.text)


def _generar_respuesta_natural(modelo, pregunta: str, df: pd.DataFrame) -> str:
    tabla_muestra = df.head(20).to_markdown(index=False)
    prompt = f"""El usuario preguntó: "{pregunta}"

Estos son los resultados de la consulta a la base de datos (máximo 20 filas mostradas):

{tabla_muestra}

Responde en español, en un párrafo breve y claro, la pregunta original
basándote SOLO en estos datos. Si es útil, menciona cifras concretas.
No inventes datos que no estén en la tabla."""
    respuesta = modelo.generate_content(prompt)
    return respuesta.text.strip()


def render_preguntas():
    st.subheader("💬 Pregúntale a los datos")
    st.markdown(
        "Escribe una pregunta en lenguaje natural sobre los municipios, "
        "el IEC o los Centros Digitales. El asistente genera y ejecuta "
        "una consulta SQL de solo lectura sobre las capas `silver`/`gold`."
    )

    with st.expander("Ejemplos de preguntas"):
        for ej in EJEMPLOS_PREGUNTAS:
            st.markdown(f"- {ej}")

    if not _configurar_gemini():
        return

    pregunta = st.text_input(
        "Tu pregunta",
        placeholder="Ej: ¿Cuáles son los 5 municipios con mayor IEC que tienen centro digital?",
    )

    if st.button("🔎 Preguntar", use_container_width=True) and pregunta:
        modelo = genai.GenerativeModel(MODEL_NAME)

        with st.spinner("Generando consulta SQL..."):
            try:
                sql = _generar_sql(modelo, pregunta)
            except Exception as e:
                st.error(f"Error llamando a Gemini: {e}")
                return

        if sql.strip().upper() == "NO_DISPONIBLE":
            st.warning(
                "No puedo responder esa pregunta con los datos disponibles "
                "en el esquema silver/gold del proyecto."
            )
            return

        segura, motivo = _es_query_segura(sql)
        if not segura:
            st.error(motivo)
            with st.expander("Ver consulta generada (rechazada)"):
                st.code(sql, language="sql")
            return

        with st.spinner("Consultando la base de datos..."):
            try:
                df = pd.read_sql(sql, get_engine())
            except Exception as e:
                st.error(f"Error ejecutando la consulta: {e}")
                with st.expander("Ver consulta generada"):
                    st.code(sql, language="sql")
                return

        with st.spinner("Redactando respuesta..."):
            try:
                respuesta_texto = _generar_respuesta_natural(modelo, pregunta, df)
                st.markdown(respuesta_texto)
            except Exception as e:
                st.warning(f"No se pudo redactar el resumen ({e}), pero aquí están los datos:")

        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Ver consulta SQL generada"):
            st.code(sql, language="sql")
