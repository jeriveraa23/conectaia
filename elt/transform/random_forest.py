import os
import pickle
import pandas as pd
from sqlalchemy import text
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from db.connection import Database


class RandomForestBuilder:

    def __init__(self):
        self.db = Database()

    def build(self):
        iec = self.db.read("SELECT * FROM gold.municipios_iec")
        dataset = self.db.read("""
            SELECT 
                codigo_municipio_men,
                AVG(n_centros_digitales) as n_centros_digitales,
                AVG(inversion_total) as inversion_total,
                AVG(usuarios_activos_prom) as usuarios_activos_prom,
                AVG(velocidad_subida_prom) as velocidad_subida_prom,
                AVG(velocidad_bajada_prom) as velocidad_bajada_prom
            FROM silver.dataset_integrado
            WHERE tiene_centro_digital = true
            GROUP BY codigo_municipio_men
        """)

        # --- Solo municipios con CD ---
        df = iec[iec["tiene_centro_digital"] == True].copy()
        df = df.merge(dataset, on="codigo_municipio_men", how="left")

        # --- Definir nivel_efectividad por terciles de diferencia_vs_cluster ---
        df = df.dropna(subset=["diferencia_vs_cluster"])
        terciles = df["diferencia_vs_cluster"].quantile([0.33, 0.66])
        
        def clasificar(x):
            if x <= terciles[0.33]:
                return "Bajo"
            elif x <= terciles[0.66]:
                return "Medio"
            else:
                return "Alto"

        df["nivel_efectividad"] = df["diferencia_vs_cluster"].apply(clasificar)

        # --- Variables predictoras ---
        columnas_x = [
            "inversion_total",
            "usuarios_activos_prom", 
            "velocidad_subida_prom",
            "velocidad_bajada_prom",
            "n_centros_digitales",
            "cluster",
            "es_pdet",
        ]

        df_modelo = df[columnas_x + ["nivel_efectividad"]].dropna()

        X = df_modelo[columnas_x].copy()
        X["es_pdet"] = X["es_pdet"].astype(int)
        X["cluster"] = X["cluster"].astype(int)
        y = df_modelo["nivel_efectividad"]

        # --- Entrenar Random Forest ---
        modelo = RandomForestClassifier(n_estimators=100, random_state=42)
        modelo.fit(X, y)

        # --- Predicciones ---
        df_modelo["nivel_efectividad_pred"] = modelo.predict(X)

        accuracy = (df_modelo["nivel_efectividad"] == df_modelo["nivel_efectividad_pred"]).mean()
        print(f"Accuracy en entrenamiento: {accuracy:.2%}")
        print(f"Distribución nivel_efectividad:")
        print(df["nivel_efectividad"].value_counts())

        # --- Importancia de variables ---
        importancia = pd.DataFrame({
            "variable": columnas_x,
            "importancia": modelo.feature_importances_
        }).sort_values("importancia", ascending=False)

        print(f"\nImportancia de variables:")
        print(importancia.to_string(index=False))

        # --- Actualizar nivel_efectividad en gold.municipios_iec ---
        with self.db.engine.begin() as conn:
            for _, row in df[["codigo_municipio_men", "nivel_efectividad"]].iterrows():
                conn.execute(text(
                    "UPDATE gold.municipios_iec SET nivel_efectividad = :nivel "
                    "WHERE codigo_municipio_men = :codigo"
                ), {"nivel": row["nivel_efectividad"], "codigo": row["codigo_municipio_men"]})

        # --- Guardar importancia en gold.modelo_resultados ---
        self.db.load(importancia, schema="gold", table="modelo_resultados")

        # --- Guardar modelo como archivo ---
        os.makedirs("/app/models", exist_ok=True)
        with open("/app/models/random_forest.pkl", "wb") as f:
            pickle.dump(modelo, f)

        print(f"\nModelo guardado en /app/models/random_forest.pkl")
        return modelo