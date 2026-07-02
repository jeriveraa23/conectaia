import pandas as pd
from db.connection import Database
from transform.utils import estandarizar_texto

REGION_POR_DEPARTAMENTO = {
    "ANTIOQUIA": "Andina",
    "BOYACA": "Andina",
    "CALDAS": "Andina",
    "CUNDINAMARCA": "Andina",
    "HUILA": "Andina",
    "NARINO": "Andina",
    "NORTE DE SANTANDER": "Andina",
    "QUINDIO": "Andina",
    "RISARALDA": "Andina",
    "SANTANDER": "Andina",
    "TOLIMA": "Andina",
    "ATLANTICO": "Caribe",
    "BOLIVAR": "Caribe",
    "CESAR": "Caribe",
    "CORDOBA": "Caribe",
    "LA GUAJIRA": "Caribe",
    "MAGDALENA": "Caribe",
    "SUCRE": "Caribe",
    "SAN ANDRES Y PROVIDENCIA": "Caribe",
    "CHOCO": "Pacifica",
    "CAUCA": "Pacifica",
    "VALLE DEL CAUCA": "Pacifica",
    "ARAUCA": "Orinoquia",
    "CASANARE": "Orinoquia",
    "META": "Orinoquia",
    "VICHADA": "Orinoquia",
    "AMAZONAS": "Amazonia",
    "CAQUETA": "Amazonia",
    "GUAINIA": "Amazonia",
    "GUAVIARE": "Amazonia",
    "PUTUMAYO": "Amazonia",
    "VAUPES": "Amazonia",
    "BOGOTA": "Andina",
}

DIFICULTAD_ORDEN = {
    "SIN INFORMACION": 0,
    "BAJO": 1,
    "MEDIO": 2,
    "ALTO": 3,
    "MUY ALTO": 4,
}


class FeaturesBuilder:

    def __init__(self):
        self.db = Database()

    def build(self):
        dataset   = self.db.read("SELECT * FROM silver.dataset_integrado")
        cd = self.db.read("SELECT municipio, departamento, dificultadacceso, zona FROM bronze.centros_digitales WHERE estados = 'OPERACION'")
        crosswalk = self.db.read("SELECT municipio_std, departamento_std, codigo_municipio_men FROM silver.crosswalk_municipios")

        # Unir CD con crosswalk para obtener codigo_municipio_men
        cd["municipio_std"]    = cd["municipio"].apply(estandarizar_texto)
        cd["departamento_std"] = cd["departamento"].apply(estandarizar_texto)
        cd = cd.merge(crosswalk, on=["municipio_std", "departamento_std"], how="left")

        # --- Brecha de desercion pre/post 2020 ---
        pre  = dataset[dataset["anio"] < 2020].groupby("codigo_municipio_men")["desercion"].mean().rename("desercion_pre_2020")
        post = dataset[dataset["anio"] >= 2020].groupby("codigo_municipio_men")["desercion"].mean().rename("desercion_post_2020")

        features = pre.to_frame().join(post, how="outer")
        features["brecha_desercion"] = features["desercion_post_2020"] - features["desercion_pre_2020"]
        features = features.reset_index()

        # --- Municipio y departamento (del año más reciente disponible) ---
        ultimo_anio = dataset.sort_values("anio").groupby("codigo_municipio_men")[["municipio", "departamento"]].last().reset_index()
        features = features.merge(ultimo_anio, on="codigo_municipio_men", how="left")

        # --- Región ---
        features["region"] = features["departamento"].apply(
            lambda d: REGION_POR_DEPARTAMENTO.get(estandarizar_texto(d), "Desconocida")
        )

        # --- Índice de ruralidad por codigo_municipio_men ---
        cd["es_rural"] = cd["zona"].str.upper().str.strip() == "RURAL"
        ruralidad = cd.groupby("codigo_municipio_men")["es_rural"].mean().reset_index()
        ruralidad.columns = ["codigo_municipio_men", "indice_ruralidad"]
        features = features.merge(ruralidad, on="codigo_municipio_men", how="left")

        # --- Dificultad de acceso por codigo_municipio_men ---
        dificultad = cd.groupby("codigo_municipio_men")["dificultadacceso"].agg(
            lambda x: x.value_counts().index[0]
        ).reset_index()
        dificultad.columns = ["codigo_municipio_men", "dificultad_acceso"]
        features = features.merge(dificultad, on="codigo_municipio_men", how="left")

        # --- Población en edad escolar ---
        poblacion = dataset.groupby("codigo_municipio_men")["poblacion_5_16"].mean().reset_index()
        poblacion.columns = ["codigo_municipio_men", "poblacion_5_16"]
        features = features.merge(poblacion, on="codigo_municipio_men", how="left")

        # --- Seleccionar columnas finales ---
        resultado = features[[
            "codigo_municipio_men",
            "municipio",
            "departamento",
            "desercion_pre_2020",
            "desercion_post_2020",
            "brecha_desercion",
            "region",
            "indice_ruralidad",
            "dificultad_acceso",
            "poblacion_5_16",
        ]].drop_duplicates(subset=["codigo_municipio_men"])

        print(f"Features: {len(resultado)} municipios")
        print(f"Con región desconocida: {(resultado['region'] == 'Desconocida').sum()}")
        print(f"Con dificultad de acceso nula: {resultado['dificultad_acceso'].isna().sum()}")

        self.db.load(resultado, schema="silver", table="features_municipio")
        return resultado