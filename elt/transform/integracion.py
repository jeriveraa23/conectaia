import pandas as pd
from db.connection import Database
from transform.utils import estandarizar_texto

class Integrador:
    def __init__(self):
        self.db = Database()

    def build(self):
        cd        = self.db.read("SELECT * FROM bronze.centros_digitales")
        crosswalk = self.db.read("SELECT * FROM silver.crosswalk_municipios")
        men       = self.db.read("SELECT * FROM bronze.educacion_men")

        men = men[men["municipio"].apply(estandarizar_texto) != "NACIONAL"]

        # Paso 1: Solo sedes en OPERACION — las en INSTALACION y PLANEACION
        # no tienen impacto educativo aún
        cd_operacion = cd[cd["estados"] == "OPERACION"]

        cd_agg = cd_operacion.groupby(["municipio", "departamento"]).agg(
            n_centros_digitales=("municipio", "count"),
            inversion_total=("inversion", "sum"),
            usuarios_activos_prom=("usuarios_activos_mes", "mean"),
            velocidad_subida_prom=("velocidad_conexion_subida", "mean"),
            velocidad_bajada_prom=("velocidad_conexion_bajada", "mean"),
        ).reset_index()

        # Paso 2: Estandarizar texto y unir con crosswalk para obtener códigos
        cd_agg["municipio_std"]    = cd_agg["municipio"].apply(estandarizar_texto)
        cd_agg["departamento_std"] = cd_agg["departamento"].apply(estandarizar_texto)

        cd_con_codigo = cd_agg.merge(
            crosswalk[["municipio_std", "departamento_std", "codigo_municipio_men"]],
            on=["municipio_std", "departamento_std"],
            how="left",
        )

        # Paso 3: Unir con Educacion MEN por código de municipio y año
        men = men.rename(columns={"codigo_municipio": "codigo_municipio_men"})
        men["codigo_municipio_men"] = men["codigo_municipio_men"].apply(
            lambda x: str(int(float(x))).zfill(5) if pd.notna(x) else None
        )

        dataset = men.merge(
            cd_con_codigo[[
                "codigo_municipio_men", "n_centros_digitales", "inversion_total",
                "usuarios_activos_prom", "velocidad_subida_prom", "velocidad_bajada_prom"
            ]],
            on="codigo_municipio_men",
            how="left"
        )

        # Paso 4: Columnas derivadas
        dataset["tiene_centro_digital"] = dataset["n_centros_digitales"].notna()
        dataset["n_centros_digitales"]  = dataset["n_centros_digitales"].fillna(0).astype(int)

        # Paso 5: Seleccionar columnas
        resultado = dataset[[
            "codigo_municipio_men",
            "municipio",
            "departamento",
            "anio",
            "tiene_centro_digital",
            "n_centros_digitales",
            "inversion_total",
            "usuarios_activos_prom",
            "velocidad_subida_prom",
            "velocidad_bajada_prom",
            "cobertura_neta",
            "desercion",
            "aprobacion",
            "sedes_conectadas_internet",
            "poblacion_5_16",
        ]]

        print(f"Dataset integrado: {len(resultado)} filas")
        print(f"Municipios únicos: {resultado['codigo_municipio_men'].nunique()}")
        print(f"Con CD: {resultado['tiene_centro_digital'].sum()} filas")

        self.db.load(resultado, schema="silver", table="dataset_integrado")
        return resultado