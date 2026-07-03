import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)


@st.cache_data
def cargar_iec():
    return pd.read_sql("SELECT * FROM gold.municipios_iec", get_engine())


@st.cache_data
def cargar_dataset():
    return pd.read_sql("""
        SELECT 
            codigo_municipio_men,
            AVG(n_centros_digitales)    as n_centros_digitales,
            AVG(inversion_total)        as inversion_total,
            AVG(usuarios_activos_prom)  as usuarios_activos_prom,
            AVG(velocidad_subida_prom)  as velocidad_subida_prom,
            AVG(velocidad_bajada_prom)  as velocidad_bajada_prom
        FROM silver.dataset_integrado
        WHERE tiene_centro_digital = true
        GROUP BY codigo_municipio_men
    """, get_engine())


@st.cache_data
def cargar_importancia():
    return pd.read_sql(
        "SELECT * FROM gold.modelo_resultados ORDER BY importancia DESC",
        get_engine()
    )