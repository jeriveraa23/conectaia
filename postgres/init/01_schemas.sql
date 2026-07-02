-- Extensión para datos geoespaciales (shapefiles DANE)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;


-- =====================================================================
-- BRONZE: datos crudos tal cual vienen de las fuentes
-- =====================================================================

-- Centros Digitales Rurales
CREATE TABLE IF NOT EXISTS bronze.centros_digitales (
    fecha_corte                    DATE,
    departamento                   TEXT,
    municipio                      TEXT,
    priorizacion                   TEXT,
    zona                           TEXT,
    dificultadacceso               TEXT,
    nombre_centro_poblado          TEXT,
    tipo_sitio                     TEXT,
    tipo_conectividad              TEXT,
    nombre_institucion_educativa   TEXT,
    nombre_sede_educativa          TEXT,
    estados                        TEXT,
    tipo_energia                   TEXT,
    detalle_sitio                  TEXT,
    usuarios_activos_mes           NUMERIC,
    velocidad_conexion_subida      NUMERIC,
    velocidad_conexion_bajada      NUMERIC,
    trafico_mensual_subida         NUMERIC,
    trafico_mensual_bajada         NUMERIC,
    inversion                      NUMERIC,
    meta                           TEXT,
    loaded_at                     TIMESTAMP NOT NULL DEFAULT now()
);

-- DIVIPOLA - Códigos de municipios
CREATE TABLE IF NOT EXISTS bronze.divipola (
    codigo_departamento    TEXT,
    nombre_departamento    TEXT,
    codigo_municipio       TEXT,
    nombre_municipio       TEXT,
    tipo_entidad           TEXT,
    longitud               NUMERIC,
    latitud                NUMERIC,
    loaded_at             TIMESTAMP NOT NULL DEFAULT now()
);

-- Educación MEN - Estadísticas en educación preescolar, básica y media
-- por municipio
CREATE TABLE IF NOT EXISTS bronze.educacion_men (
    anio                            INTEGER,
    codigo_municipio                TEXT,
    municipio                       TEXT,
    codigo_departamento             TEXT,
    departamento                    TEXT,
    codigo_etc                      TEXT,
    etc                              TEXT,
    poblacion_5_16                  NUMERIC,
    tasa_matriculacion_5_16         NUMERIC,
    cobertura_neta                  NUMERIC,
    cobertura_neta_transicion       NUMERIC,
    cobertura_neta_primaria         NUMERIC,
    cobertura_neta_secundaria       NUMERIC,
    cobertura_neta_media            NUMERIC,
    cobertura_bruta                 NUMERIC,
    cobertura_bruta_transicion      NUMERIC,
    cobertura_bruta_primaria        NUMERIC,
    cobertura_bruta_secundaria      NUMERIC,
    cobertura_bruta_media           NUMERIC,
    tamano_promedio_grupo           NUMERIC,
    sedes_conectadas_internet       NUMERIC,
    desercion                       NUMERIC,
    desercion_transicion            NUMERIC,
    desercion_primaria              NUMERIC,
    desercion_secundaria            NUMERIC,
    desercion_media                 NUMERIC,
    aprobacion                      NUMERIC,
    aprobacion_transicion           NUMERIC,
    aprobacion_primaria              NUMERIC,
    aprobacion_secundaria           NUMERIC,
    aprobacion_media                NUMERIC,
    reprobacion                     NUMERIC,
    reprobacion_transicion          NUMERIC,
    reprobacion_primaria            NUMERIC,
    reprobacion_secundaria          NUMERIC,
    reprobacion_media               NUMERIC,
    repitencia                      NUMERIC,
    repitencia_transicion           NUMERIC,
    repitencia_primaria             NUMERIC,
    repitencia_secundaria           NUMERIC,
    repitencia_media                NUMERIC,
    loaded_at                      TIMESTAMP NOT NULL DEFAULT now()
);


-- =====================================================================
-- SILVER: datos limpios e integrados
-- =====================================================================

-- Tabla puente: nombre estandarizado (Centros Digitales) <-> código DIVIPOLA
-- Incluye los ~30 casos de corrección manual con su justificación

CREATE TABLE IF NOT EXISTS silver.crosswalk_municipios (
    municipio_std        TEXT NOT NULL,
    departamento_std     TEXT NOT NULL,
    codigo_municipio_men TEXT,
    metodo_match         TEXT,
    observacion          TEXT,
    loaded_at            TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (municipio_std, departamento_std)
);

CREATE TABLE IF NOT EXISTS silver.dataset_integrado (
    codigo_municipio_men      TEXT NOT NULL,
    municipio                 TEXT,
    departamento              TEXT,
    anio                      INTEGER,
    tiene_centro_digital      BOOLEAN,
    n_centros_digitales       INTEGER,
    inversion_total           NUMERIC,
    usuarios_activos_prom     NUMERIC,
    velocidad_subida_prom     NUMERIC,
    velocidad_bajada_prom     NUMERIC,
    cobertura_neta            NUMERIC,
    desercion                 NUMERIC,
    aprobacion                NUMERIC,
    sedes_conectadas_internet NUMERIC,
    poblacion_5_16            NUMERIC,
    loaded_at                 TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (codigo_municipio_men, anio)
);

CREATE TABLE IF NOT EXISTS silver.features_municipio (
    codigo_municipio_men    TEXT PRIMARY KEY,
    municipio               TEXT,
    departamento            TEXT,
    desercion_pre_2020      NUMERIC,
    desercion_post_2020     NUMERIC,
    brecha_desercion        NUMERIC,
    region                  TEXT,
    indice_ruralidad        NUMERIC,
    dificultad_acceso       TEXT,
    poblacion_5_16          NUMERIC,
    loaded_at               TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS silver.municipios_clusterizados (
    codigo_municipio_men    TEXT PRIMARY KEY,
    municipio               TEXT,
    departamento            TEXT,
    cluster                 INTEGER,
    tiene_centro_digital    BOOLEAN,
    loaded_at               TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.municipios_iec (
    codigo_municipio_men        TEXT PRIMARY KEY,
    municipio                   TEXT,
    departamento                TEXT,
    region                      TEXT,
    cluster                     INTEGER,
    tiene_centro_digital        BOOLEAN,
    componente_desercion        NUMERIC,
    componente_cobertura        NUMERIC,
    componente_aprobacion       NUMERIC,
    iec                         NUMERIC,
    iec_promedio_cluster_sin_cd NUMERIC,
    diferencia_vs_cluster       NUMERIC,
    nivel_efectividad           TEXT,
    es_pdet                     BOOLEAN,
    es_outlier                  BOOLEAN DEFAULT FALSE,
    revisado_manual             BOOLEAN DEFAULT FALSE,
    loaded_at                   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.modelo_resultados (
    variable                TEXT,
    importancia             NUMERIC,
    loaded_at               TIMESTAMP NOT NULL DEFAULT now()
);