from extract.extract import Extractor
from transform.crosswalk import CrosswalkBuilder
from transform.integracion import Integrador
from transform.features import FeaturesBuilder
from transform.clustering import ClusteringBuilder
from transform.iec import IECBuilder
from transform.random_forest import RandomForestBuilder


def main():
    extractor = Extractor()
    extractor.extract_divipola()
    extractor.extract_centros_digitales()
    extractor.extract_educacion_men()

    crosswalk_builder = CrosswalkBuilder()
    crosswalk_builder.build()

    integrador = Integrador()
    integrador.build()

    features_builder = FeaturesBuilder()
    features_builder.build()

    clustering_builder = ClusteringBuilder()
    clustering_builder.build()

    iec_builder = IECBuilder()
    iec_builder.build()

    rf_builder = RandomForestBuilder()
    rf_builder.build()

if __name__ == "__main__":
    main()