import pandas as pd
import numpy as np
from kmodes.kprototypes import KPrototypes
from db.connection import Database
from sklearn.preprocessing import StandardScaler

COLUMNAS_CLUSTER = ["region", "poblacion_5_16", "desercion_pre_2020"]
COLUMNAS_CATEGORICAS = ["region"]
N_CLUSTERS = 6


class ClusteringBuilder:

    def __init__(self):
        self.db = Database()

    def build(self):
        features = self.db.read("SELECT * FROM silver.features_municipio")
        dataset = self.db.read("""
            SELECT DISTINCT codigo_municipio_men, 
                   MAX(n_centros_digitales) > 0 as tiene_centro_digital
            FROM silver.dataset_integrado
            GROUP BY codigo_municipio_men
        """)

        # Tomar solo los municipios con datos completos para el clustering
        df = features[COLUMNAS_CLUSTER + ["codigo_municipio_men", "municipio", "departamento"]].copy()
        df_completo = df.dropna(subset=COLUMNAS_CLUSTER)

        print(f"Municipios para clustering: {len(df_completo)} de {len(df)} totales")
        print(f"Excluidos por nulos: {len(df) - len(df_completo)}")

        scaler = StandardScaler()
        columnas_numericas = ["poblacion_5_16", "desercion_pre_2020"]
        df_completo[columnas_numericas] = scaler.fit_transform(df_completo[columnas_numericas])

        # Preparar tipos de datos
        df_completo = df_completo.copy()
        df_completo["region"] = df_completo["region"].astype(str)
        df_completo["poblacion_5_16"] = df_completo["poblacion_5_16"].astype(float)
        df_completo["desercion_pre_2020"] = df_completo["desercion_pre_2020"].astype(float)

        # Índices de columnas categóricas
        matriz = df_completo[COLUMNAS_CLUSTER].values
        indices_categoricos = [COLUMNAS_CLUSTER.index(c) for c in COLUMNAS_CATEGORICAS]

        # Correr K-Prototypes
        kproto = KPrototypes(n_clusters=N_CLUSTERS, init="Cao", n_init=1, verbose=1)
        clusters = kproto.fit_predict(matriz, categorical=indices_categoricos)

        df_completo["cluster"] = clusters

        # Unir con tiene_centro_digital
        df_completo = df_completo.merge(dataset, on="codigo_municipio_men", how="left")

        # Seleccionar columnas finales
        resultado = df_completo[[
            "codigo_municipio_men",
            "municipio",
            "departamento",
            "cluster",
            "tiene_centro_digital",
        ]]

        print(f"\nDistribución de clusters:")
        print(resultado["cluster"].value_counts().sort_index())
        print(f"\nMunicipios con CD por cluster:")
        print(resultado.groupby("cluster")["tiene_centro_digital"].sum())
        print(f"\nMunicipios sin CD por cluster:")
        print(resultado.groupby("cluster")["tiene_centro_digital"].apply(lambda x: (~x).sum()))

        self.db.load(resultado, schema="silver", table="municipios_clusterizados")
        return resultado