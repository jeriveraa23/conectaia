import unicodedata
import pandas as pd

from db.connection import Database

# Casos que no hacen match automatico por diferencias de nombre, tildes
# mal codificadas o departamentos escritos distinto entre las dos fuentes.
# Se verificaron uno por uno contra bronze.divipola.
CORRECCIONES_MANUALES = {
    ("LOPEZ", "CAUCA"): "19418",
    ("MARIQUITA", "TOLIMA"): "73443",
    ("CUCUTA", "NORTE DE SANTANDER"): "54001",
    ("SAN ANDRES SOTAVENTO", "CORDOBA"): "23670",
    ("PURISIMA", "CORDOBA"): "23586",
    ("SANTAFE DE ANTIOQUIA", "ANTIOQUIA"): "05042",
    ("PROVIDENCIA", "SAN ANDRES Y PROVIDENCIA"): "88564",
    ("SAN ANDRES", "SAN ANDRES Y PROVIDENCIA"): "88001",
    ("SOTARA", "CAUCA"): "19760",
    ("PIENDAMO", "CAUCA"): "19548",
    ("MOMPOS", "BOLIVAR"): "13468",
    ("SAN JUAN DE RIO SECO", "CUNDINAMARCA"): "25662",
    ("TOLU VIEJO", "SUCRE"): "70823",
    ("CALI", "VALLE DEL CAUCA"): "76001",
    ("CARTAGENA", "BOLIVAR"): "13001",
    ("CHACHAGSI", "NARINO"): "52240",
    ("CUASPUD", "NARINO"): "52224",
    ("DON MATIAS", "ANTIOQUIA"): "05237",
    ("LEGUIZAMO", "PUTUMAYO"): "86573",
    ("BOGOTA, D.C.", "BOGOTA"): "11001",
    ("CHIBOLO", "MAGDALENA"): "47170",
    ("TOGSI", "BOYACA"): "15816",
    ("SAN VICENTE", "ANTIOQUIA"): "05674",
    ("MAGSI", "NARINO"): "52427",
    ("GSEPSA", "SANTANDER"): "68327",
    ("GSICAN", "BOYACA"): "15332",
    ("BARRANCO MINAS", "GUAINIA"): "94343",
    ("CERRO SAN ANTONIO", "MAGDALENA"): "47161",
    ("PEÐOL", "ANTIOQUIA"): "05541",
    ("MANAURE", "CESAR"): "20443",
    ("SAN PEDRO", "ANTIOQUIA"): "05664",
}
    # MAPIRIPANA (GUAINIA) no esta en DIVIPOLA como municipio independiente,
    # queda sin codigo y se revisa manualmente despues.


def estandarizar_texto(texto):
    if texto is None:
        return None
    sin_tildes = unicodedata.normalize("NFD", str(texto))
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return sin_tildes.upper().strip()


class CrosswalkBuilder:

    def __init__(self):
        self.db = Database()

    def build(self):
        cd = self.db.read("SELECT DISTINCT municipio, departamento FROM bronze.centros_digitales")
        div = self.db.read("SELECT codigo_municipio, nombre_municipio, nombre_departamento FROM bronze.divipola")

        cd["municipio_std"] = cd["municipio"].apply(estandarizar_texto)
        cd["departamento_std"] = cd["departamento"].apply(estandarizar_texto)
        div["municipio_std"] = div["nombre_municipio"].apply(estandarizar_texto)
        div["departamento_std"] = div["nombre_departamento"].apply(estandarizar_texto)

        crosswalk = cd.merge(
            div[["municipio_std", "departamento_std", "codigo_municipio"]],
            on=["municipio_std", "departamento_std"],
            how="left",
        )

        crosswalk["metodo_match"] = "automatico"
        crosswalk["observacion"] = None

        sin_match = crosswalk["codigo_municipio"].isna()
        for idx in crosswalk[sin_match].index:
            key = (crosswalk.loc[idx, "municipio_std"], crosswalk.loc[idx, "departamento_std"])
            if key in CORRECCIONES_MANUALES:
                crosswalk.loc[idx, "codigo_municipio"] = CORRECCIONES_MANUALES[key]
                crosswalk.loc[idx, "metodo_match"] = "manual"
            else:
                crosswalk.loc[idx, "metodo_match"] = "sin_resolver"
                crosswalk.loc[idx, "observacion"] = "no encontrado en divipola ni en correcciones manuales"

        resultado = crosswalk.rename(columns={"codigo_municipio": "codigo_municipio_men"})
        resultado = resultado[[
            "municipio_std", "departamento_std", "codigo_municipio_men",
            "metodo_match", "observacion"
        ]].drop_duplicates(subset=["municipio_std", "departamento_std"])

        resultado["codigo_municipio_men"] = resultado["codigo_municipio_men"].apply(
            lambda x: str(int(float(x))).zfill(5) if pd.notna(x) else None
        )

        print(resultado["metodo_match"].value_counts())

        self.db.load(resultado, schema="silver", table="crosswalk_municipios")
        return resultado