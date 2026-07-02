import os
import requests
import pandas as pd

from db.connection import Database

class Extractor:

    BASE_URL = "https://www.datos.gov.co/resource"

    def __init__(self):
        self.db = Database()
        self.app_token = os.environ.get("SOCRATA_APP_TOKEN", "")

    def _headers(self):
        """Incluye token de Socrata en la petición para evitar límites de tasa."""
        headers = {}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        return headers

    def _paginate(self, dataset_id, page_size=1000):
        """Descarga todas las filas de un dataset en bloques de page_size."""
        url = f"{self.BASE_URL}/{dataset_id}.json"
        all_rows = []
        offset = 0

        while True:
            params = {"$limit": page_size, "$offset": offset, "$order": ":id"}
            resp = requests.get(url, params=params, headers=self._headers())
            resp.raise_for_status()
            rows = resp.json()

            if not rows:
                break

            all_rows.extend(rows)
            offset += page_size

        return pd.DataFrame(all_rows)

    def extract_divipola(self):
        """Extrae DIVIPOLA y renombra columnas al esquema definido en el SQL."""
        df = self._paginate("gdxc-w37w")
        df = df.rename(columns={
            "cod_dpto":        "codigo_departamento",
            "dpto":            "nombre_departamento",
            "cod_mpio":        "codigo_municipio",
            "nom_mpio":        "nombre_municipio",
            "tipo_municipio":  "tipo_entidad",
            "longitud":        "longitud",
            "latitud":         "latitud",
        })
        print(f"DIVIPOLA: {len(df)} filas extraídas")
        self.db.load(df, schema="bronze", table="divipola")
        return df

    def extract_centros_digitales(self):
        """Extrae Centros Digitales y renombra columnas al esquema definido en el SQL."""
        df = self._paginate("fybg-535s")
        df = df.rename(columns={
            "fecha_corte":                   "fecha_corte",
            "departamento":                  "departamento",
            "municipio":                     "municipio",
            "priorizacion":                  "priorizacion",
            "zona":                          "zona",
            "dificultadacceso":              "dificultadacceso",
            "nombre_centro_poblado":         "nombre_centro_poblado",
            "tipo_sitio":                    "tipo_sitio",
            "tipo_conectividad":             "tipo_conectividad",
            "nombre_institucion_educativa":  "nombre_institucion_educativa",
            "nombre_sede_educativa":         "nombre_sede_educativa",
            "estados":                       "estados",
            "tipo_energia":                  "tipo_energia",
            "detalle_sitio":                 "detalle_sitio",
            "usuarios_activos_mes":          "usuarios_activos_mes",
            "velocidad_conexion_subida":     "velocidad_conexion_subida",
            "velocidad_conexion_bajada":     "velocidad_conexion_bajada",
            "trafico_mensual_subida":        "trafico_mensual_subida",
            "trafico_mensual_bajada":        "trafico_mensual_bajada",
            "inversion":                     "inversion",
            "meta":                          "meta",
        })
        print(f"Centros Digitales: {len(df)} filas extraídas")
        self.db.load(df, schema="bronze", table="centros_digitales")
        return df

    def extract_educacion_men(self):
        """Extrae Educación MEN y renombra columnas al esquema definido en el SQL."""
        df = self._paginate("nudc-7mev")
        df = df.rename(columns={
            "a_o":                          "anio",
            "c_digo_municipio":             "codigo_municipio",
            "municipio":                    "municipio",
            "c_digo_departamento":          "codigo_departamento",
            "departamento":                 "departamento",
            "c_digo_etc":                   "codigo_etc",
            "etc":                          "etc",
            "poblaci_n_5_16":               "poblacion_5_16",
            "tasa_matriculaci_n_5_16":      "tasa_matriculacion_5_16",
            "cobertura_neta":               "cobertura_neta",
            "cobertura_neta_transici_n":    "cobertura_neta_transicion",
            "cobertura_neta_primaria":      "cobertura_neta_primaria",
            "cobertura_neta_secundaria":    "cobertura_neta_secundaria",
            "cobertura_neta_media":         "cobertura_neta_media",
            "cobertura_bruta":              "cobertura_bruta",
            "cobertura_bruta_transici_n":   "cobertura_bruta_transicion",
            "cobertura_bruta_primaria":     "cobertura_bruta_primaria",
            "cobertura_bruta_secundaria":   "cobertura_bruta_secundaria",
            "cobertura_bruta_media":        "cobertura_bruta_media",
            "tama_o_promedio_de_grupo":     "tamano_promedio_grupo",
            "sedes_conectadas_a_internet":  "sedes_conectadas_internet",
            "deserci_n":                    "desercion",
            "deserci_n_transici_n":         "desercion_transicion",
            "deserci_n_primaria":           "desercion_primaria",
            "deserci_n_secundaria":         "desercion_secundaria",
            "deserci_n_media":              "desercion_media",
            "aprobaci_n":                   "aprobacion",
            "aprobaci_n_transici_n":        "aprobacion_transicion",
            "aprobaci_n_primaria":          "aprobacion_primaria",
            "aprobaci_n_secundaria":        "aprobacion_secundaria",
            "aprobaci_n_media":             "aprobacion_media",
            "reprobaci_n":                  "reprobacion",
            "reprobaci_n_transici_n":       "reprobacion_transicion",
            "reprobaci_n_primaria":         "reprobacion_primaria",
            "reprobaci_n_secundaria":       "reprobacion_secundaria",
            "reprobaci_n_media":            "reprobacion_media",
            "repitencia":                   "repitencia",
            "repitencia_transici_n":        "repitencia_transicion",
            "repitencia_primaria":          "repitencia_primaria",
            "repitencia_secundaria":        "repitencia_secundaria",
            "repitencia_media":             "repitencia_media",
        })
        print(f"Educación MEN: {len(df)} filas extraídas")
        self.db.load(df, schema="bronze", table="educacion_men")
        return df