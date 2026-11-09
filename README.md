# Asistente de Retroalimentacion para Productos Moodle

Servicio FastAPI para crear asistentes de retroalimentacion. Cada asistente tiene un ID interno propio y puede aplicar a **uno o varios `cmid`** de Moodle (por ejemplo, el mismo producto repetido en distintos cursos). Cada asistente guarda:

- uno o mas `cmid` de Moodle a los que aplica
- descripcion del producto
- contexto del curso, unidades y sesiones
- ejemplo o muestra del producto esperado
- tipo de contenido esperado: texto, tablas/cuadros, imagenes
- rubrica
- perfil/orientaciones de retroalimentacion
- configuracion opcional del modelo
- Programa y/o Curso a los que pertenece (catalogos configurables desde el gestor)

Un mismo `cmid` solo puede pertenecer a un asistente a la vez.

El endpoint principal procesa un producto desde Moodle:

```bash
GET /procesar_producto?cmid=194522&user_id=481404&course_id=2440&nombre=MARIA%20LUISA
```

Tambien incluye un endpoint tecnico opcional para depurar un PDF aislado sin Moodle:

```bash
POST /procesar_producto_pdf
```

## Requisitos

- Python 3.10+
- Token de Azure OpenAI
- Token de Moodle si usaras descarga automatica

## Instalacion

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus credenciales.

## Ejecutar

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

Abre:

```text
http://localhost:7001/docs
```

Vista del gestor:

```text
http://localhost:7001/gestor
```

## Flujo final del sistema

### 1. Gestor

El gestor entra a:

```text
http://localhost:7001/gestor
```

Desde esa vista configura previamente cada asistente:

- uno o varios `cmid` de Moodle a los que aplica (escritos a mano o agregados desde un buscador de actividades por `course_id`)
- descripcion del producto
- contexto del curso, unidades y sesiones donde se desarrolla la base conceptual del producto
- ejemplo o muestra del producto esperado
- checks de contenido esperado: texto, tablas/cuadros, imagenes
- Programa y/o Curso a los que pertenece (con sus propios catalogos, creables desde la misma vista)
- dependencia opcional de uno o varios `cmid` preliminares/relacionados (tambien con buscador de Moodle)
- validacion previa del documento y similitud con cada entrega relacionada
- rubrica (se puede generar un borrador con IA a partir de documentos de evidencia en PDF o Word)
- perfil de retroalimentacion
- deployment de Azure OpenAI opcional

Sin esa configuracion previa, el usuario no podra procesar su producto porque el sistema no sabra que rubrica aplicar.

### 2. Usuario

El usuario no configura nada. Solo accede a un enlace como este:

```text
http://161.132.50.205:7001/procesar_producto?cmid=194522&user_id=481404&course_id=2440&nombre=MARIA%20LUISA
```

Con esos parametros, el sistema:

1. Busca en la base de datos la configuracion del `cmid`.
2. Revisa si ya existe una retroalimentacion exitosa para `cmid`, `user_id` y `course_id`.
3. Si existe, muestra la retroalimentacion guardada sin volver a consultar Moodle ni GPT.
4. Si no existe, consulta Moodle con `course_id` y `cmid`.
5. Ubica la entrega PDF del `user_id`.
6. Descarga el PDF temporalmente.
7. Extrae texto, tablas o imagenes segun la configuracion.
8. Genera la retroalimentacion con Azure OpenAI.
9. Elimina el PDF temporal.
10. Guarda y muestra la retroalimentacion.

### Rol del enlace

El enlace acepta `role`:

```text
role=0
```

Usuario normal. Si ya tiene retroalimentacion exitosa para `cmid`, `user_id` y `course_id`, se muestra la guardada.

```text
role=1
```

Validador. Siempre regenera la retroalimentacion, aunque ya exista una anterior.

Si no se envia `role`, se asume `role=0`.

Para forzar una regeneracion manual:

```text
&force_refresh=true
```

### Dependencia de uno o varios CMID relacionados

Cada asistente puede marcar:

```json
{
  "usa_cmid_relacionado": true,
  "cmids_relacionados": [100, 101],
  "validar_similitud": true
}
```

Cuando esta activo, el sistema descarga tambien la entrega de cada `cmid` en `cmids_relacionados` para el mismo `user_id` y `course_id`. Luego, para cada una:

- compara la entrega anterior con la actual
- calcula similitud
- valida que la nueva entrega no sea una repeticion de ninguna de ellas
- orienta la retroalimentacion como continuidad o mejora respecto a esas entregas preliminares

La similitud maxima entre todas las relacionadas es la que se usa para la validacion global.

### Validacion previa

Antes de retroalimentar, el sistema puede validar:

- que el PDF no este en blanco o casi vacio
- que tenga relacion con el producto esperado
- que no sea un documento ajeno a la actividad
- que no repita la entrega de un `cmid` relacionado

Si no pasa la validacion, no se genera retroalimentacion y se muestra el motivo.

Si necesitas respuesta JSON para integraciones tecnicas, agrega:

```text
&formato=json
```

Ejemplo:

```text
http://161.132.50.205:7001/procesar_producto?cmid=194522&user_id=481404&course_id=2440&nombre=MARIA%20LUISA&formato=json
```

## Primer uso desde la vista del gestor

1. Ejecuta el servidor.
2. Entra a `http://localhost:7001/gestor`.
3. Presiona `Cargar ejemplo`.
4. Revisa o cambia el `CMID`.
5. Presiona `Guardar cambios`.
6. En la seccion `Probar desde Moodle`, coloca `cmid`, `user_id`, `course_id` y `nombre`.
7. Presiona `Traer PDF de Moodle y evaluar`.

Si el `CMID` ya existe, el gestor carga esa configuracion para editarla. No se crea un segundo asistente con el mismo `cmid`.

## Primer uso desde script

Tambien puedes cargar el asistente de ejemplo por consola:

```bash
python scripts/seed_demo.py
```

Luego prueba:

```text
http://localhost:7001/asistentes/por-cmid/194522
```

## Como crear tu primer asistente real

Para cada actividad de Moodle necesitas un asistente por `cmid`.

### 1. Define el CMID

Ejemplo:

```text
194522
```

Ese numero es la llave que usara el endpoint:

```text
/procesar_producto?cmid=194522&user_id=481404&course_id=2440&nombre=MARIA%20LUISA
```

### 2. Escribe la descripcion del producto

Describe que debe entregar el docente, para que sirve el producto, que elementos debe contener y que enfoque pedagogico debe respetar.

### 3. Escribe la rubrica

Antes de la rubrica, puedes agregar:

- `contexto_curso`: informacion de unidades, sesiones, contenidos base o lecturas del curso que sustentan el producto.
- `ejemplo_producto`: una muestra, modelo o estructura esperada del producto para orientar mejor la evaluacion.

La rubrica se pega como JSON. Cada criterio debe tener esta forma:

```json
{
  "dimension": "Estructura y organizacion del calendario comunal",
  "descripcion_dimension": "Evalua si el producto presenta una estructura clara y completa.",
  "criterio": "Presencia de las cinco columnas estructurales",
  "descripcion_criterio": "Verifica que el calendario incluya las columnas esperadas y que cada una tenga contenido pertinente.",
  "niveles": {
    "inicio": "Descripcion del nivel inicio.",
    "en_proceso": "Descripcion del nivel en proceso.",
    "logrado": "Descripcion del nivel logrado.",
    "destacado": "Descripcion del nivel destacado."
  }
}
```

### 4. Escribe el perfil de retroalimentacion

En la vista, coloca una orientacion por linea. Ejemplo:

```text
Iniciar reconociendo aciertos.
Senalar omisiones de manera especifica.
Nunca emitir juicios de valor sobre la cultura de la comunidad.
Proponer preguntas reflexivas.
```

### 5. Guarda y prueba

Primero prueba desde la vista del gestor con `Probar desde Moodle`. Esa prueba usa el mismo endpoint real `/procesar_producto`, descarga el PDF desde Moodle y aplica la rubrica configurada para el `cmid`.

## Endpoints principales

### Crear asistente

```http
POST /asistentes
Content-Type: application/json
```

El asistente recibe un `id` autogenerado. Si alguno de los `cmids` (o `cmids_relacionados`) ya esta asignado a otro asistente, devuelve `409 Conflict`.

### Editar asistente

```http
PUT /asistentes/{id}
Content-Type: application/json
```

```json
{
  "nombre": "Calendario comunal EIB",
  "cmids": [194522, 194600],
  "descripcion_producto": "El calendario comunal es una herramienta pedagogica...",
  "contexto_curso": "Unidad 1, sesion 2: se desarrolla el calendario comunal...",
  "ejemplo_producto": "Ejemplo de referencia: calendario organizado por epocas...",
  "analiza_texto": true,
  "analiza_tablas": true,
  "analiza_imagenes": false,
  "usa_cmid_relacionado": false,
  "cmids_relacionados": [],
  "programa_id": 1,
  "curso_id": 3,
  "rubrica": [
    {
      "dimension": "Estructura y organizacion del calendario comunal",
      "descripcion_dimension": "Evalua la organizacion general del calendario comunal.",
      "criterio": "Presencia de las cinco columnas estructurales",
      "descripcion_criterio": "Verifica que esten presentes las columnas esperadas y que se usen de forma pertinente.",
      "niveles": {
        "inicio": "El calendario carece de mas de dos columnas...",
        "en_proceso": "El calendario tiene columnas basicas...",
        "logrado": "Las cinco columnas estan presentes...",
        "destacado": "Las cinco columnas estan completas..."
      }
    }
  ],
  "perfil_retroalimentacion": [
    "Iniciar reconociendo los aciertos.",
    "Senalar omisiones de manera especifica.",
    "Nunca emitir juicios de valor sobre la cultura."
  ]
}
```

### Buscar asistente por CMID

```http
GET /asistentes/por-cmid/{cmid}
```

Util para cargar en el gestor el asistente que ya incluye ese `cmid`, sin conocer su `id`.

### Generar borrador de configuracion con IA

```http
POST /asistentes/generar-borrador
Content-Type: multipart/form-data
```

Recibe uno o varios archivos PDF o Word (`.doc` / `.docx`) (`files`) con evidencia (rubricas, ejemplos, guias) y devuelve un borrador JSON con `descripcion_producto`, `contexto_curso`, `ejemplo_producto`, `rubrica`, `perfil_retroalimentacion` y `campos_incompletos` (los campos que los documentos no permitieron completar) para revisar y ajustar antes de guardar. No guarda nada por si solo.

Los `.docx` se leen directamente. Los `.doc` antiguos se convierten con Microsoft Word instalado en el servidor (via COM); si el servidor no tiene Word disponible, se devuelve un error pidiendo subir el archivo como `.docx` o `.pdf`.

### Buscar actividades de un curso en Moodle

```http
GET /moodle/cursos/{course_id}/actividades?q=texto
```

Lista las actividades (`cmid`, nombre, tipo) del curso indicado, para elegir cuales agregar como `cmids` o `cmids_relacionados` de un asistente.

### Programas y cursos

```http
GET /programas
POST /programas            { "nombre": "..." }
GET /cursos?programa_id=1
POST /cursos                { "programa_id": 1, "course_id": 2440 }
```

Al crear un curso solo se envia el `course_id` (curid) de Moodle; el `nombre` se obtiene automaticamente desde Moodle y se guarda.

### Procesar desde Moodle

```http
GET /procesar_producto?cmid=194522&user_id=481404&course_id=2440&nombre=MARIA%20LUISA
```

El servicio intentara encontrar la actividad por `cmid`, descargar el PDF entregado por `user_id`, extraer texto y tablas, enviar todo a Azure OpenAI y eliminar el archivo temporal.

Cada procesamiento genera un `run_id` y queda guardado para analitica.

### Modulos del gestor y reporteria

El gestor (`/gestor`) esta organizado en tres modulos:

- **Asistentes**: listado lateral con buscador y editor de configuracion (CMID, rubrica, IA, programa/curso, dependencias).
- **Pruebas**: simula el enlace que recibe el usuario final.
- **Reporteria**: tablero con filtros (fechas, asistente, programa, curso, rol, estado) y cuatro secciones:
  - *Resumen de uso*: ejecuciones, tasa de exito, usuarios unicos y recurrentes, consultas guardadas (reaperturas de una retroalimentacion ya generada), tiempos, tokens, uso por dia/hora/dia de semana, por asistente/programa/curso y motivos de error o rechazo.
  - *Retroalimentaciones*: tabla paginada con buscador y detalle completo (texto entregado, evaluacion por criterio, validacion, eventos, sentimiento). Se puede exportar a CSV.
  - *Desempeno por rubrica*: niveles obtenidos, puntaje por dimension y criterios con menor desempeno.
  - *Tono y coherencia*: el boton "Analizar pendientes" usa Azure OpenAI para clasificar el sentimiento y el tono de cada retroalimentacion, extraer fortalezas y oportunidades de mejora recurrentes y, sobre todo, comparar el texto con los niveles reales de la rubrica: **alineada**, **indulgente** (elogia mas de lo que el desempeno justifica) o **severa**. Las indulgentes y severas aparecen como alertas con su motivo. El resultado se guarda en `runsentiment`, por lo que cada retroalimentacion se analiza una sola vez.
  - *Valoraciones de docentes*: en la pagina de la retroalimentacion el docente puede responder "¿Te fue util?" (1 a 5 estrellas y comentario opcional; una valoracion por retroalimentacion, editable). La reporteria muestra promedio, distribucion, tasa de respuesta, valoracion por asistente y los comentarios recientes. No aparece para el rol Validador. Endpoints: `GET/PUT /retroalimentaciones/{run_id}/valoracion` (el `user_id` debe coincidir con el de la ejecucion). Tabla: `feedbackrating`.

Endpoints: `GET /reportes/resumen`, `GET /reportes/ejecuciones`, `GET /reportes/ejecuciones/{run_id}`, `GET /reportes/ejecuciones.csv` y `POST /reportes/sentimiento/analizar` (todos aceptan `desde`, `hasta`, `assistant_id`, `programa_id`, `curso_id`, `cmid`, `rol`, `estado`). Las fechas se agrupan en hora de Lima y solo se consideran ejecuciones originadas desde Moodle. Tablas nuevas: `runsentiment` y `processingview`.

### Analitica y logs

Ultimas ejecuciones:

```http
GET /analitica?limit=50
```

Detalle completo de una ejecucion:

```http
GET /analitica/{run_id}
```

Se guardan estos datos:

- parametros de entrada: `cmid`, `user_id`, `course_id`, `nombre`
- estado: `started`, `success` o `failed`
- etapa alcanzada: configuracion, Moodle, extraccion PDF, OpenAI, error
- tiempos: Moodle, extraccion, GPT, limpieza y total
- metricas PDF: paginas, tablas, caracteres extraidos, tamano del archivo
- modelo usado y tokens consumidos
- retroalimentacion final
- evaluacion por cada criterio de rubrica: dimension, criterio, nivel obtenido, score, evidencia, comentario y recomendacion
- eventos/logs por etapa con mensajes y detalles

Tablas creadas:

- `processingrun`: una fila por procesamiento
- `processingevent`: eventos y logs por procesamiento
- `rubricevaluation`: resultado por cada item de rubrica

### Procesar PDF directo para depuracion

```http
POST /procesar_producto_pdf
```

Campos de formulario:

- `cmid`
- `user_id`
- `course_id`
- `nombre`
- `file`

Este endpoint queda solo como apoyo tecnico si necesitas probar un PDF aislado. La vista del gestor usa Moodle directamente.

## Notas sobre tablas y PDF

El extractor usa `pdfplumber`, que conserva texto y extrae tablas como Markdown. Esto ayuda a que GPT reciba una representacion clara de matrices, columnas y criterios. Si el PDF es escaneado como imagen, instala OCR aparte y activa:

```env
ENABLE_OCR=true
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

OCR requiere instalar Tesseract en Windows.

## Modos de analisis del PDF

Cada configuracion por `cmid` permite marcar que contenido tendra el producto:

```json
{
  "analiza_texto": true,
  "analiza_tablas": true,
  "analiza_imagenes": false
}
```

- `analiza_texto`: extrae parrafos y texto plano del PDF.
- `analiza_tablas`: extrae tablas/cuadros y los convierte a Markdown.
- `analiza_imagenes`: renderiza paginas del PDF y las envia al modelo con vision.

Recomendacion:

- Solo texto: activa solo `analiza_texto`.
- Matrices, calendarios, planificaciones o rubricas: activa `analiza_texto` y `analiza_tablas`.
- Capturas, diagramas, mapas, organizadores visuales o cuadros que no se leen bien como tabla: activa tambien `analiza_imagenes`.

Para controlar costo y tiempo de vision:

```env
VISION_MAX_PAGES=3
VISION_DPI=144
```

## Variables de entorno

Ver `.env.example`.

## PostgreSQL

La app usa estas variables para conectarse a PostgreSQL:

```env
DB_NAME=gestor_pdf
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432
DATABASE_URL=
```

Si la base aun no existe, creala en PostgreSQL:

```sql
CREATE DATABASE gestor_pdf;
```

Al iniciar FastAPI, las tablas se crean automaticamente.
