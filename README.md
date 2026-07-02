# ConectaIA — Análisis del Impacto de los Centros Digitales Rurales en Colombia

## Descripción General

ConectaIA es un proyecto de ingeniería de datos e inteligencia artificial desarrollado como propuesta para la competencia de datos abiertos. El objetivo es medir y clasificar el impacto educativo de los centros digitales rurales en los municipios de Colombia, utilizando datos abiertos del Ministerio de Educación Nacional (MEN) y del Ministerio de Tecnologías de la Información y las Comunicaciones (MinTIC).

La pregunta central que responde el proyecto es: **¿los Centros Digitales Rurales están asociados a mejores resultados educativos en los municipios donde operan, en comparación con municipios de perfil territorial similar que no los tienen?**

---

## Arquitectura

El proyecto implementa una arquitectura de datos medallones (Bronze → Silver → Gold) sobre PostgreSQL con PostGIS, orquestada mediante un pipeline ELT en Python. Todo el entorno corre en contenedores Docker.

```
bronze/     → datos crudos tal cual vienen de las fuentes (Socrata API)
silver/     → datos limpios, integrados y con campos calculadas
gold/       → productos analíticos finales: IEC(Índeice de efectividad de conectividad), clustering, modelo Random Forest (Clasificación)
```

### Stack tecnológico

- **Orquestación**: Python 3.11, Docker Compose
- **Base de datos**: PostgreSQL 16 + PostGIS
- **Procesamiento**: pandas, scikit-learn, kmodes
- **Fuentes de datos**: API Socrata (datos.gov.co)

---

## Fuentes de Datos

| Dataset | Fuente | Filas | Descripción |
|---|---|---|---|
| Centros Digitales Rurales | MinTIC / Socrata `fybg-535s` | 14,057 | Una fila por sede educativa con centro digital |
| DIVIPOLA | DANE / Socrata `gdxc-w37w` | 1,122 | Códigos y nombres oficiales de municipios |
| Estadísticas Educación MEN | MEN / Socrata `nudc-7mev` | 15,707 | Indicadores educativos por municipio y año (2011-2024) |

---

## Pipeline ELT — Hitos

### Hito 1 — Extracción a Bronze

Se extrajeron los tres datasets desde la API Socrata de datos.gov.co usando paginación estable con el parámetro `$order=:id`, que garantiza que no haya solapamiento entre páginas consecutivas (problema que causaba registros duplicados sin este ordenamiento). Cada dataset se cargó en su tabla bronze correspondiente, respetando los nombres de columna definidos en el esquema SQL — no los nombres que devuelve Socrata internamente. Se implementó un mecanismo de reintentos automáticos para manejar la inestabilidad ocasional de la API. Los números con formato de coma decimal (`"3,75"`) y separador de miles (`"1,174,274"`) se normalizaron automáticamente antes de la carga.

**Tablas creadas**: `bronze.centros_digitales`, `bronze.divipola`, `bronze.educacion_men`

---

### Hito 2 — Crosswalk de Municipios (Silver)

El principal desafío de integración fue que las tres fuentes usan nombres de municipio distintos para referirse al mismo lugar. Centros Digitales usa nombres abreviados (`"CUCUTA"`, `"CALI"`, `"MOMPOS"`), mientras que DIVIPOLA usa los nombres oficiales (`"SAN JOSE DE CUCUTA"`, `"SANTIAGO DE CALI"`, `"SANTA CRUZ DE MOMPOX"`). Adicionalmente, algunos nombres en centros digitales tienen caracteres mal codificados por problemas de encoding en el origen (`"CHACHAGsI"` en vez de `"CHACHAGÜÍ"`, `"MAGsI"` en vez de `"MAGÜÍ"`).

Se construyó una tabla puente que resuelve este problema en dos pasos: primero un match automático por texto estandarizado (sin tildes, en mayúsculas) que resolvió 1,072 de los 1,104 municipios únicos, y luego 31 correcciones manuales verificadas una por una contra el listado oficial de DIVIPOLA. Solo 1 municipio quedó sin resolver (Mapiripana, Guainía — que no existe como municipio independiente en DIVIPOLA).

Todos los códigos de municipio se estandarizaron al formato de 5 dígitos con ceros a la izquierda (ej. `"05001"`) para garantizar consistencia en los joins posteriores.

**Tablas creadas**: `silver.crosswalk_municipios`

---

### Hito 3 — Dataset Integrado (Silver)

Se construyó la tabla central de trabajo combinando las tres fuentes. El proceso tuvo tres pasos principales: 
primero se agregaron las sedes de Centros Digitales por municipio. pero **solo las sedes en estado OPERACION** (8,601 de 14,057), excluyendo las que están en INSTALACION o PLANEACION porque no han tenido impacto educativo aún. Esto definió qué municipios realmente tienen un centro digital activo. Luego se usó el crosswalk para obtener el código de municipio de cada centro digital, y finalmente se hizo un join con educación MEN, que tiene una fila por municipio y año (2011-2024). Las variables de centros digitales (inversión, usuarios, velocidad) se repiten iguales en todos los años del mismo municipio, porque son un snapshot o fecha de corte de 2023.

El resultado es una tabla con granularidad municipio-año: 15,704 filas, 1,037 municipios únicos, donde cada fila combina los indicadores educativos de ese año con las características del CD del municipio.

**Tablas creadas**: `silver.dataset_integrado`

---

### Hito 4 — Features por Municipio (Silver)

Se calcularon las variables de perfil territorial de cada municipio, algunas necesarias para el clustering. Las variables calculadas fueron:

- **Deserción pre/post 2020**: promedio de la tasa de deserción escolar en los periodos 2011-2019 y 2020-2024, y la brecha entre ambos periodos
- **Región**: mapeo de departamento a región (Andina, Caribe, Pacífica, Orinoquía, Amazonía)
- **Índice de ruralidad**: sedes del municipio ubicadas en zona rural, calculado a partir de centros digitales y mapeado al municipio via crosswalk por código (no por nombre, para evitar problemas de encoding)
- **Dificultad de acceso**: valor más frecuente de dificultad de acceso reportado entre las sedes del municipio
- **Población en edad escolar**: promedio de la población entre 5 y 16 años

Los 248 municipios sin CD no tienen índice de ruralidad ni dificultad de acceso (esas variables solo existen en el dataset de Centros Digitales). Se dejaron en NULL de forma intencional — eliminar o inventar valores distorsionaría el análisis posterior.

**Tablas creadas**: `silver.features_municipio`

---

### Hito 5 — Clustering de Municipios (Silver)

Para poder comparar municipios de forma justa, se agruparon en clusters de perfil territorial similar usando el algoritmo **K-Prototypes** (versión de K-Means que maneja variables mixtas, numéricas y categóricas). Las variables de clustering seleccionadas fueron las tres disponibles para todos los municipios (con y sin centro digital):

- `region` — variable categórica
- `poblacion_5_16` — variable numérica, normalizada con StandardScaler
- `desercion_pre_2020` — variable numérica, normalizada con StandardScaler

Se usaron 6 clusters. El resultado fue una distribución con municipios con centro digital y sin centro digital en cada cluster, lo que permite la comparación dentro de cada grupo. Los clusters 1 y 4 tienen pocos municipios sin CD (4 y 1 respectivamente), lo que limita la robustez de la comparación en esos grupos específicos.

**Tablas creadas**: `silver.municipios_clusterizados`

---

### Hito 6 — Índice de Efectividad de Conectividad (IEC) (Gold)

El IEC es el indicador central del proyecto, es un número de 0 a 100 que resume la situación educativa de cada municipio. Se calcula como una suma ponderada de tres componentes normalizados al rango 0-100:

```
IEC = 0.40 × componente_desercion + 0.35 × componente_cobertura + 0.25 × componente_aprobacion
```

- **Componente deserción** (40%): Tasa de deserciónj escolar de cada municipio. El dato se toma invertido.
    Menor deserción produce un componente más alto
- **Componente cobertura neta** (35%): Porcentaje de niños entre 5 y 16 años que están matriculados en el grado que corresponde a su edad. 
    Se toma mayor cobertura que produce un componente más alto
- **Componente aprobación** (25%): Tasa de aprobación escolar.
    El mayor tasa de aprobación produce un componente más alto

El IEC se calcula para los 1,037 municipios usando el promedio de todos los años disponibles. Para la comparación, se calculó el promedio del IEC de los municipios sin centro digital dentro de cada cluster (`iec_promedio_cluster_sin_cd`), y la diferencia de cada municipio con centro digital respecto a ese promedio (`diferencia_vs_cluster`).

El IEC promedio nacional resultó en 64.63 sobre 100. El 62% de los municipios con centro digital tienen un IEC superior al promedio de municipios sin CD de su mismo cluster, lo que sugiere una asociación positiva entre los centros digitales y los resultados educativos.

**Tablas creadas**: `gold.municipios_iec`

---

### Hito 7 — Clasificación con Random Forest (Gold)

Se entrenó un modelo de clasificación Random Forest para dos propósitos: clasificar cada municipio con centro digital en nivel de efectividad Alto, Medio o Bajo, y entender qué características del centro digital predicen esa efectividad.

La variable objetivo (`nivel_efectividad`) se definió por terciles de `diferencia_vs_cluster`: el tercio superior de municipios que más superaron a su cluster en IEC se clasificó como Alto, el tercio inferior como Bajo, y el resto como Medio. Las variables predictoras fueron las características del centro digital: inversión total, usuarios activos mensuales, velocidades de conexión (subida y bajada), número de sedes, cluster territorial y si el municipio es zona PDET.

El modelo alcanzó un 97.71% de accuracy sobre los datos de entrenamiento. Los resultados de importancia de variables revelan que el uso activo del centro digital (`usuarios_activos_prom`) es el factor más determinante de la efectividad (34%), seguido por la inversión total (16%). Las velocidades de conexión y el número de sedes tienen importancia similar entre sí (~12% cada uno). Ser zona PDET tiene un efecto marginal en el modelo (1.3%).

El modelo entrenado se serializó como archivo `.pkl` para su uso en el simulador interactivo del dashboard.

**Tablas creadas**: `gold.modelo_resultados`

---

## Estructura del Proyecto

```
ConectaIA/
├── docker-compose.yml
├── docker/
│   └── elt.Dockerfile
├── postgres/
│   └── init/
│       └── 01_schemas.sql
├── elt/
│   ├── requirements.txt
│   ├── wait-for-it.sh
│   ├── run_pipeline.py
│   ├── db/
│   │   └── connection.py
│   ├── extract/
│   │   └── extract.py
│   └── transform/
│       ├── utils.py
│       ├── crosswalk.py
│       ├── integracion.py
│       ├── features.py
│       ├── clustering.py
│       ├── iec.py
│       └── random_forest.py
└── README.md
```

---

## Cómo ejecutar el proyecto

### Requisitos
- Docker Desktop instalado y corriendo

### Pasos

```bash
# Clonar el repositorio
git clone https://github.com/jeriveraa23/conectaia.git
cd conectaia

# Levantar el entorno completo
docker compose up --build
```

El pipeline corre automáticamente al levantar los contenedores. Postgres inicializa el esquema y el contenedor ELT extrae, transforma y carga los datos en secuencia. El proceso completo tarda aproximadamente 5 minutos dependiendo de la disponibilidad de la API de datos.gov.co.

---

## Hallazgos Principales

- El 62% de los municipios con Centros Digitales en operación tienen un IEC superior al promedio de municipios sin CD de su mismo cluster territorial
- El factor más determinante de la efectividad del CD es el uso activo (usuarios activos mensuales), no la inversión ni la velocidad de conexión
- Los Centros Digitales con mayor efectividad tienden a estar en municipios con mayor inversión acumulada y mejores velocidades de conexión
- Las zonas PDET no muestran un efecto diferencial significativo en el modelo, lo que sugiere que el impacto del CD es relativamente uniforme independientemente de la priorización de política pública

---