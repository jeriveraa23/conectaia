import os
import re
import pandas as pd
import streamlit as st
from openai import OpenAI
from db.connection import get_engine

# ---------------------------------------------------------------------------
# Configuración del modelo
# ---------------------------------------------------------------------------
# gpt-4o-mini es, al momento de escribir esto, el modelo más económico de la
# familia GPT-4o de OpenAI — más que suficiente para generar SQL simple y
# resúmenes cortos. Verifica el nombre y precio vigentes en
# https://openai.com/api/pricing antes de desplegar a producción, por si
# OpenAI lo reemplazó por uno más nuevo.
MODEL_NAME = "gpt-4o-mini"

MAX_PREGUNTAS_SESION = 3

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
    componente_aprobacion NUMERIC,
    iec NUMERIC,                        -- IEC = Índice de Efectividad de Conectividad (escala 0-100): mide el impacto educativo del Centro Digital combinando deserción (40%), cobertura (35%) y aprobación (25%)
    iec_promedio_cluster_sin_cd NUMERIC, -- IEC promedio de municipios similares SIN Centro Digital en el mismo grupo territorial
    diferencia_vs_cluster NUMERIC,      -- diferencia entre el IEC del municipio y el promedio de su grupo (positivo = mejor que sus pares)
    nivel_efectividad TEXT ('Alto'|'Medio'|'Bajo'), es_pdet BOOLEAN,
    es_outlier BOOLEAN, revisado_manual BOOLEAN

gold.modelo_resultados (grano: variable del modelo Random Forest)
    variable TEXT, importancia NUMERIC
"""

PALABRAS_PROHIBIDAS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "--", "/*", ";", "copy", "call",
]


def _configurar_openai() -> OpenAI | None:
    """Busca la API key primero en st.secrets (Streamlit Cloud) y, si no
    existe, en las variables de entorno (uso local con .env)."""
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        st.error(
            "Falta la variable OPENAI_API_KEY. Agrégala en Streamlit Cloud "
            "en Settings → Secrets, o en tu .env local."
        )
        return None

    return OpenAI(api_key=api_key)


def _extraer_sql(texto_respuesta: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", texto_respuesta, re.DOTALL | re.IGNORECASE)
    sql = match.group(1) if match else texto_respuesta
    return sql.strip().rstrip(";").strip()


def _es_query_segura(sql: str) -> tuple[bool, str]:
    sql_lower = sql.lower()
    if not sql_lower.strip().startswith("select"):
        return False, "Esa pregunta generó una consulta que no es de solo lectura, así que no se ejecuta."
    for palabra in PALABRAS_PROHIBIDAS:
        if palabra in sql_lower:
            return False, f"La consulta generada contiene un término no permitido ('{palabra}')."
    return True, ""


def _generar_sql(client: OpenAI, pregunta: str) -> str:
    system_prompt = f"""Eres un asistente que traduce preguntas en español a consultas SQL
de PostgreSQL, usando EXCLUSIVAMENTE el siguiente esquema:

{ESQUEMA_DESCRIPCION}

Glosario importante:
- IEC = Índice de Efectividad de Conectividad: puntaje de 0 a 100 que mide el impacto
  educativo de los Centros Digitales Rurales en un municipio. Se calcula combinando
  deserción escolar (40%), cobertura neta (35%) y tasa de aprobación (25%).
  Un IEC más alto significa mejor desempeño educativo.

Reglas:
- Responde ÚNICAMENTE con la consulta SQL, sin explicación, sin markdown.
- Solo genera consultas SELECT (nunca INSERT/UPDATE/DELETE/DDL).
- Usa nombres de columnas y tablas exactamente como aparecen arriba, con su esquema (ej. gold.municipios_iec).
- Si la pregunta pide un "top N" o un listado, agrega siempre LIMIT 50 como máximo.
- Si la pregunta no se puede responder con este esquema, responde exactamente: NO_DISPONIBLE"""

    respuesta = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta},
        ],
    )
    return _extraer_sql(respuesta.choices[0].message.content)


def _generar_respuesta_natural(client: OpenAI, pregunta: str, df: pd.DataFrame) -> str:
    tabla_muestra = df.head(20).to_markdown(index=False)
    prompt = f"""El usuario preguntó: "{pregunta}"

Estos son los resultados de la consulta a la base de datos (máximo 20 filas mostradas):

{tabla_muestra}

Responde en español, en un párrafo breve y claro, la pregunta original
basándote SOLO en estos datos. Si es útil, menciona cifras concretas.
No inventes datos que no estén en la tabla."""

    respuesta = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    return respuesta.choices[0].message.content.strip()


def _procesar_pregunta(client: OpenAI, pregunta: str) -> str:
    try:
        sql = _generar_sql(client, pregunta)
    except Exception as e:
        return f"No pude conectarme con el modelo: {e}"

    if sql.strip().upper() == "NO_DISPONIBLE":
        return (
            "No puedo responder esa pregunta con los datos disponibles del proyecto "
            "(municipios, IEC —Índice de Efectividad de Conectividad—, grupos territoriales, Centros Digitales)."
        )

    segura, motivo = _es_query_segura(sql)
    if not segura:
        return motivo

    try:
        df = pd.read_sql(sql, get_engine())
    except Exception as e:
        return f"Hubo un error consultando la base de datos: {e}"

    try:
        return _generar_respuesta_natural(client, pregunta, df)
    except Exception:
        if df.empty:
            return "La consulta no arrojó resultados para esa pregunta."
        return f"Encontré estos resultados, pero no pude redactar el resumen:\n\n{df.head(20).to_markdown(index=False)}"


def render_chat_flotante():
    """Botón de chat flotante (abajo a la derecha), visible en toda la app."""

    if "chat_historial" not in st.session_state:
        st.session_state.chat_historial = []
    if "preguntas_usadas" not in st.session_state:
        st.session_state.preguntas_usadas = 0

    with st.container(key="chat_flotante"):
        with st.popover("💬 ¿Dudas? Pregúntame", help="Pregúntale a los datos"):
            st.markdown("**💬 Pregúntale a los datos**")

            restantes = MAX_PREGUNTAS_SESION - st.session_state.preguntas_usadas
            st.caption(f"{max(restantes, 0)} de {MAX_PREGUNTAS_SESION} preguntas disponibles en esta sesión.")

            for rol, contenido in st.session_state.chat_historial:
                with st.chat_message(rol):
                    st.markdown(contenido)

            if restantes <= 0:
                st.info(
                    "Alcanzaste el límite de preguntas de esta sesión. "
                    "Recarga la página para reiniciar."
                )
                return

            client = _configurar_openai()
            if client is None:
                return

            pregunta = st.chat_input("Escribe tu pregunta...")
            if pregunta:
                st.session_state.chat_historial.append(("user", pregunta))
                st.session_state.preguntas_usadas += 1
                with st.spinner("Consultando los datos..."):
                    respuesta = _procesar_pregunta(client, pregunta)
                st.session_state.chat_historial.append(("assistant", respuesta))
                st.rerun()
