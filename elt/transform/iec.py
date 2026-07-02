import pandas as pd
from db.connection import Database
from transform.utils import estandarizar_texto


class IECBuilder:

    def __init__(self):
        self.db = Database()

    def _normalizar(self, serie, invertir=False):
        """Normaliza una serie a escala 0-100. Si invertir=True, menor valor = mejor."""
        min_val = serie.min()
        max_val = serie.max()
        if max_val == min_val:
            return pd.Series([50.0] * len(serie), index=serie.index)
        normalizado = (serie - min_val) / (max_val - min_val) * 100
        if invertir:
            normalizado = 100 - normalizado
        return normalizado

    def build(self):
        dataset   = self.db.read("SELECT * FROM silver.dataset_integrado")
        clusters  = self.db.read("SELECT * FROM silver.municipios_clusterizados")
        cd        = self.db.read("SELECT municipio, departamento, priorizacion FROM bronze.centros_digitales WHERE estados = 'OPERACION'")
        features  = self.db.read("SELECT codigo_municipio_men, region FROM silver.features_municipio")
        crosswalk = self.db.read("SELECT municipio_std, departamento_std, codigo_municipio_men FROM silver.crosswalk_municipios")

        # --- Promedios de indicadores por municipio (todos los años disponibles) ---
        indicadores = dataset.groupby("codigo_municipio_men").agg(
            desercion_prom=("desercion", "mean"),
            cobertura_prom=("cobertura_neta", "mean"),
            aprobacion_prom=("aprobacion", "mean"),
        ).reset_index()

        # --- Normalizar componentes ---
        indicadores["componente_desercion"] = self._normalizar(indicadores["desercion_prom"], invertir=True)
        indicadores["componente_cobertura"] = self._normalizar(indicadores["cobertura_prom"], invertir=False)
        indicadores["componente_aprobacion"] = self._normalizar(indicadores["aprobacion_prom"], invertir=False)

        # --- Calcular IEC ---
        indicadores["iec"] = (
            0.40 * indicadores["componente_desercion"] +
            0.35 * indicadores["componente_cobertura"] +
            0.25 * indicadores["componente_aprobacion"]
        )

        # --- Unir con clusters ---
        df = indicadores.merge(
            clusters[["codigo_municipio_men", "cluster", "municipio", "departamento", "tiene_centro_digital"]],
            on="codigo_municipio_men", how="left"
        )
        df["tiene_centro_digital"] = df["tiene_centro_digital"].astype(bool)
        df = df.merge(features[["codigo_municipio_men", "region"]], on="codigo_municipio_men", how="left")

        # --- Promedio IEC de municipios SIN CD por cluster ---
        sin_cd = df[~df["tiene_centro_digital"]].groupby("cluster")["iec"].mean().reset_index()
        sin_cd.columns = ["cluster", "iec_promedio_cluster_sin_cd"]
        df = df.merge(sin_cd, on="cluster", how="left")

        # --- Diferencia vs cluster ---
        df["diferencia_vs_cluster"] = df["iec"] - df["iec_promedio_cluster_sin_cd"]

        # --- es_pdet ---
        cd["municipio_std"]    = cd["municipio"].apply(estandarizar_texto)
        cd["departamento_std"] = cd["departamento"].apply(estandarizar_texto)
        cd = cd.merge(crosswalk, on=["municipio_std", "departamento_std"], how="left")
        pdet = cd[cd["priorizacion"].str.contains("PDET", na=False)].groupby("codigo_municipio_men").size().reset_index()
        pdet.columns = ["codigo_municipio_men", "n_sedes_pdet"]
        pdet["es_pdet"] = True
        df = df.merge(pdet[["codigo_municipio_men", "es_pdet"]], on="codigo_municipio_men", how="left")
        df["es_pdet"] = df["es_pdet"].fillna(False)

        # --- Seleccionar columnas finales ---
        resultado = df[[
            "codigo_municipio_men",
            "municipio",
            "departamento",
            "region",
            "cluster",
            "tiene_centro_digital",
            "componente_desercion",
            "componente_cobertura",
            "componente_aprobacion",
            "iec",
            "iec_promedio_cluster_sin_cd",
            "diferencia_vs_cluster",
            "es_pdet",
        ]].dropna(subset=["codigo_municipio_men"])

        resultado["nivel_efectividad"] = None
        resultado["es_outlier"]        = False
        resultado["revisado_manual"]   = False

        print(f"IEC calculado: {len(resultado)} municipios")
        print(f"IEC promedio: {resultado['iec'].mean():.2f}")
        print(f"Con diferencia positiva vs cluster: {(resultado['diferencia_vs_cluster'] > 0).sum()}")
        print(f"PDET: {resultado['es_pdet'].sum()}")

        self.db.load(resultado, schema="gold", table="municipios_iec")
        return resultado