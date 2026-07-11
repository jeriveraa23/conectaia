# ConectaIA — ¿Los Centros Digitales Rurales mejoran la educación en Colombia?

  > **Una plataforma de inteligencia de datos que mide, compara y simula el impacto educativo de los Centros Digitales Rurales en los municipios colombianos.**

  ---

  ## ¿De qué trata este proyecto?

  Colombia ha invertido en instalar **Centros Digitales Rurales (CD)** en municipios de todo el país: espacios con conectividad a internet, computadores y personal de apoyo, pensados para reducir la brecha
  digital en zonas alejadas. Pero surge una pregunta natural: **¿realmente están funcionando?**

  ConectaIA responde esa pregunta usando datos oficiales del Gobierno Nacional, inteligencia artificial y visualizaciones interactivas. El resultado es una plataforma que cualquier persona, funcionario
  público, investigador, periodista o ciudadano interesado, puede usar para entender qué está pasando en cada municipio, compararlo con sus pares, y simular qué pasaría si se cambian las condiciones del centro
   digital.

  La pregunta que guía todo el proyecto es:

  > **¿Los municipios que tienen un Centro Digital activo muestran mejores resultados educativos que municipios similares que no lo tienen?**

  ---

  ## ¿De dónde vienen los datos?

  ConectaIA no inventa información. Todo parte de **datos abiertos publicados por el Gobierno colombiano** en el portal [datos.gov.co](https://datos.gov.co), específicamente tres fuentes oficiales:

  ### 1. Centros Digitales Rurales, MinTIC
  Publicado por el Ministerio de Tecnologías de la Información y las Comunicaciones. Contiene información de cada sede con centro digital en el país: cuánto se invirtió, cuántos usuarios activos tiene al mes,
  a qué velocidades sube y baja datos, si está en zona rural, y cuál es su estado (en operación, en instalación o en planeación). Esta fuente tiene **14.057 registros** de sedes individuales a lo largo del
  territorio nacional.

  ### 2. DIVIPOLA, DANE
  El listado oficial de municipios de Colombia con sus nombres y códigos únicos. Es la referencia que permite conectar información de distintas fuentes bajo un mismo identificador. Contiene los **1.122
  municipios** del país.

  ### 3. Estadísticas Educativas, Ministerio de Educación Nacional (MEN)
  Indicadores educativos por municipio y año, desde 2011 hasta 2024. Incluye tres métricas clave: **tasa de deserción escolar** (cuántos niños abandonan el colegio), **cobertura neta** (qué porcentaje de niños
   en edad escolar están matriculados en el grado correcto), y **tasa de aprobación** (cuántos estudiantes pasan el año). Esta fuente tiene **15.707 registros** históricos.

  ---

  ## ¿Cómo se cruza y organiza la información?

  Los datos llegan en formatos distintos, con nombres de municipios diferentes y estructuras incompatibles entre sí. ConectaIA los transforma en una base de datos organizada en **tres capas**, como si fuera
  una fábrica de datos:

  ```
  Datos crudos  →  Datos limpios  →  Resultados finales
    (Bronce)          (Plata)             (Oro)
  ```

  ### Capa Bronce: los datos tal como llegan
  Los tres conjuntos de datos se descargan directamente desde la API oficial y se guardan sin modificar. Esta capa existe como respaldo fiel de la fuente original.

  ### Capa Plata: datos limpios e integrados
  Aquí ocurre el trabajo de preparación. El principal reto es que cada fuente llama diferente a los mismos municipios. Por ejemplo:

  - MinTIC dice **"CUCUTA"**
  - El DANE dice **"SAN JOSE DE CUCUTA"**
  - Algunos registros tienen problemas de caracteres: **"CHACHAGsI"** en lugar de **"CHACHAGÜÍ"**

  Para resolver esto, se construyó una **tabla puente** que empareja los nombres de cada fuente con el código oficial del municipio. Este proceso fue en dos pasos: primero se hizo automáticamente con texto
  estandarizado (sin tildes, en mayúsculas), resolviendo 1.072 de los 1.104 municipios. Los 31 restantes se corrigieron manualmente, uno por uno, verificando contra el listado oficial del DANE.

  Con los nombres resueltos, se construye la **tabla integrada**: una fila por municipio y año que combina los indicadores educativos con las características del centro digital (si existe). Solo se incluyen
  centros en **estado OPERACIÓN**, los que están en instalación o planeación no se cuentan porque todavía no han tenido impacto real.

  ### Capa Oro: los productos finales de análisis
  Con los datos limpios y unidos, se calculan los indicadores clave: el IEC, los grupos territoriales y las predicciones del modelo. Esta capa es lo que alimenta el tablero interactivo.

  ---

  ## ¿Cómo se crean características adicionales por municipio?

  Para poder comparar municipios de forma justa, primero hay que entender bien a cada uno. Por eso se calculan **variables de perfil territorial** que no vienen directamente en los datos originales sino que se
   construyen a partir de ellos:

  - **Deserción histórica y reciente**: Se separa el promedio de deserción antes y después de 2020 para detectar el impacto de la pandemia en cada municipio, y se calcula la brecha entre ambos períodos.
  - **Región geográfica**: Se clasifica cada municipio en una de las cinco grandes regiones de Colombia (Andina, Caribe, Pacífica, Orinoquía, Amazonía), basándose en su departamento.
  - **Índice de ruralidad**: Qué proporción de las sedes del municipio están en zona rural (solo disponible para municipios con CD).
  - **Dificultad de acceso**: Qué tan difícil es llegar físicamente al municipio, medido por el nivel de dificultad reportado en las sedes del centro digital.
  - **Población en edad escolar**: El promedio de niños y jóvenes entre 5 y 16 años, que es la población objetivo del sistema educativo.

  ---

  ## ¿Cómo se agrupan los municipios en grupos similares?

  No tiene sentido comparar un municipio pequeño y aislado de la Amazonía con una ciudad intermedia del Eje Cafetero. Para que la comparación sea justa, ConectaIA agrupa los municipios en **6 grupos
  territoriales** usando un algoritmo de inteligencia artificial llamado **K-Prototypes**, que trabaja con datos mixtos (numéricos y de categorías al mismo tiempo).

  Los tres criterios de agrupación son:
  1. **Región geográfica**, para que los municipios comparados estén en contextos similares
  2. **Tamaño de población escolar**, para no comparar municipios de tamaños muy distintos
  3. **Nivel histórico de deserción escolar**, para que los puntos de partida educativos sean parecidos

  Cada grupo reúne municipios con y sin centro digital de perfil similar. Esto es clave: cuando se evalúa si un CD mejoró algo, la comparación se hace contra municipios del **mismo grupo que no tienen CD**, no
   contra el promedio nacional.

  ---

  ## ¿Qué es el IEC y cómo se calcula?

  El **IEC (Índice de Efectividad de Conectividad)** es el corazón del proyecto. Es un **número de 0 a 100** que resume la situación educativa de un municipio en un solo valor. Cuanto más alto, mejor.

  Se construye combinando tres indicadores educativos con diferentes pesos según su importancia:

  | Componente | Peso | ¿Qué mide? |
  |---|---|---|
  | Tasa de deserción escolar | **40%** | Cuántos niños abandonan el colegio (invertido: menos deserción = mejor puntaje) |
  | Cobertura neta | **35%** | Qué porcentaje de niños en edad escolar están matriculados en el grado correcto |
  | Tasa de aprobación | **25%** | Qué proporción de estudiantes pasan el año |

  Cada componente se normaliza a una escala de 0 a 100 antes de combinarse, para que sean comparables entre sí.

  El IEC se calcula para los **1.037 municipios** con datos disponibles, usando el promedio de todos los años (2011-2024). El **promedio nacional es de 64.63 sobre 100**.

  ### ¿Cómo se compara un municipio con su grupo?

  Una vez calculado el IEC de cada municipio, se calcula también el **IEC promedio de los municipios sin centro digital dentro del mismo grupo territorial**. La diferencia entre estos dos valores indica si el
  municipio está por encima o por debajo de lo que cabría esperar para su perfil.

  El hallazgo principal: **el 62% de los municipios con Centros Digitales en operación tienen un IEC superior al promedio de municipios similares sin CD**, lo que sugiere una asociación positiva entre los
  centros digitales y los resultados educativos.

  ---

  ## ¿Cómo funciona el modelo de inteligencia artificial?

  ConectaIA entrena un modelo de **Random Forest**, un algoritmo de aprendizaje automático que aprende patrones a partir de ejemplos reales, para clasificar cada municipio con CD en tres niveles de
  efectividad: **Alto, Medio o Bajo**.

  ### ¿Qué aprende el modelo?

  El modelo aprende a predecir el nivel de efectividad a partir de las características del centro digital:

  - Inversión total en el centro
  - Promedio de usuarios activos por mes
  - Velocidades de conexión (subida y bajada)
  - Número de sedes en el municipio
  - Grupo territorial al que pertenece
  - Si es zona PDET (municipios priorizados por el proceso de paz)

  ### ¿Qué factores importan más?

  Uno de los resultados más valiosos es entender **qué hace que un CD sea efectivo**. El modelo reveló el peso de cada factor:

  | Factor | Importancia |
  |---|---|
  | Usuarios activos mensuales | **34%**, el más importante |
  | Inversión total | **16%** |
  | Velocidad de descarga | **12%** |
  | Velocidad de subida | **12%** |
  | Número de sedes | **11%** |
  | Grupo territorial | **3%** |
  | Zona PDET | **1.3%**, efecto mínimo |

  La conclusión es clara: **lo que más predice la efectividad no es cuánto se invirtió ni la velocidad del internet, sino cuántas personas realmente usan el centro digital activamente**. Un CD con muchos
  usuarios tiene mucha más probabilidad de mostrar impacto educativo positivo que uno bien equipado pero poco utilizado.

  ---

  ## ¿Qué muestra el tablero interactivo?

  El tablero es la cara visible del proyecto. Está diseñado para que cualquier persona pueda explorar los resultados sin necesidad de conocimientos técnicos. Tiene tres módulos principales:

  ---

  ### Módulo 1: Mapa de Municipios

  Un mapa interactivo de Colombia donde cada municipio aparece coloreado según su nivel de efectividad:

  - **Verde**: IEC alto (75–100), resultados educativos muy buenos
  - **Amarillo**: IEC medio-alto (60–74), resultados por encima del promedio
  - **Naranja**: IEC medio-bajo (45–59), resultados por mejorar
  - **Rojo**: IEC bajo (0–44), situación educativa crítica

  **Filtros disponibles**: Se puede filtrar el mapa por región del país, nivel de efectividad, si el municipio es zona PDET, y si tiene o no un centro digital activo.

  **Detalle por municipio**: Al hacer clic en cualquier municipio del mapa, aparece una ventana emergente con información detallada: el IEC total, el desglose por componente (deserción, cobertura, aprobación),
   el nivel de efectividad y la comparación con el promedio de su grupo territorial.

  **Polígonos geográficos**: El mapa carga los contornos de cada municipio en formato GeoJSON para dibujar sus fronteras con precisión y permitir una visualización territorial correcta.

  ---

  ### Módulo 2: Simulador de Impacto

  El simulador permite hacerse una pregunta práctica: **"¿Qué IEC tendría este municipio si cambiamos las condiciones del centro digital?"**

  El usuario selecciona un municipio y ajusta los parámetros del centro digital que quiere simular:

  - **Nivel de inversión** (desde $100 millones hasta $750 millones)
  - **Usuarios activos esperados por mes** (desde 15 hasta 150 usuarios)
  - **Número de sedes** en el municipio
  - **Si es zona PDET** o no

  Al presionar **Simular**, el modelo de inteligencia artificial calcula el nivel de efectividad predicho y muestra cuatro resultados:

  1. **El nivel de efectividad simulado**, Alto, Medio o Bajo, con las probabilidades de cada clasificación.
  2. **Comparación con el grupo territorial**: El IEC simulado se contrasta con el promedio real de municipios similares, para entender si el resultado estaría por encima o por debajo de lo esperado para ese
  perfil.
  3. **Explicación en lenguaje natural generada por IA**: Un texto claro en español que explica por qué el municipio obtuvo ese puntaje, qué significa la diferencia respecto a su grupo, y qué factores están
  impulsando o limitando el resultado.
  4. **Mapa simulado**: Un mapa actualizado resalta el municipio seleccionado, mostrando visualmente dónde queda su IEC simulado en el contexto del territorio nacional.

  ---

  ### Módulo 3: Asistente de Preguntas con IA

  Un chatbot integrado en el tablero que permite hacer **hasta 3 preguntas** sobre los datos del proyecto en lenguaje cotidiano, sin necesidad de conocer ningún lenguaje de programación ni bases de datos.

  Ejemplos de preguntas que se pueden hacer:
  - *"¿Cuáles son los 5 municipios con mayor IEC en la región Caribe?"*
  - *"¿Cuántos municipios tienen nivel de efectividad Alto en Antioquia?"*
  - *"¿Qué municipios PDET tienen un IEC por encima del promedio nacional?"*

  El asistente traduce la pregunta a una consulta sobre los datos reales, obtiene los resultados y los devuelve en una respuesta clara en español.

  ---

  ## Tecnología utilizada

  | Componente | Tecnología |
  |---|---|
  | **Tablero interactivo** | Streamlit, framework de Python para aplicaciones web de datos |
  | **Base de datos** | Supabase, base de datos en la nube que almacena todos los datos procesados y los resultados del modelo |
  | **Mapas** | Folium, librería de mapas interactivos |
  | **Modelos de IA** | scikit-learn (Random Forest), K-Prototypes (agrupamiento) |
  | **Asistente de lenguaje** | GPT-3.5 / GPT-4o-mini (OpenAI) para explicaciones y chatbot |
  | **Pipeline de datos** | Python, pandas |
  | **Fuente de datos** | API Socrata de datos.gov.co |

  ---

  ## Hallazgos principales

  - El **62%** de los municipios con Centros Digitales en operación tienen mejores resultados educativos que municipios similares sin CD.
  - El factor que más predice la efectividad de un CD es el **uso activo** (usuarios al mes), no la inversión ni la velocidad de internet.
  - El **IEC promedio nacional** es de **64.63 sobre 100**.
  - Ser zona PDET no garantiza mayor efectividad educativa por sí solo; lo que importa es si el centro está siendo realmente utilizado.
  - Los CDs con mayor inversión y mejores velocidades tienden también a tener más usuarios, lo que crea un círculo virtuoso de impacto.

  ---

  *ConectaIA fue desarrollado como propuesta para la competencia de datos abiertos, usando exclusivamente fuentes oficiales del Gobierno colombiano.*