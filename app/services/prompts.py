from app.models import AssistantConfig


def build_feedback_prompt(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    cmid: int,
    image_data_urls: list[dict] | None = None,
    related_items: list[dict] | None = None,
) -> list[dict]:
    rubric_text = _rubric_to_text(assistant.rubrica)
    profile_text = "\n".join(f"- {item}" for item in assistant.perfil_retroalimentacion)
    related_items = related_items or []

    system = (
        "Eres un asistente pedagogico especializado en retroalimentacion formativa para docentes. "
        "Evalua productos educativos con respeto intercultural, usando solo la rubrica y el contexto dados. "
        "Reconoce aciertos, identifica omisiones concretas y propone mejoras accionables. "
        "No inventes datos que no aparezcan en el producto; cuando algo no se observe, dilo con claridad. "
        "Responde exclusivamente con un objeto JSON valido."
    )

    user = f"""
DATOS DEL ENVIO
- Docente: {student_name}
- user_id: {user_id}
- course_id: {course_id}
- cmid: {cmid}

PRODUCTO A EVALUAR
{assistant.descripcion_producto}

BASE DEL CURSO, UNIDADES Y SESIONES
{assistant.contexto_curso or "No se proporciono contexto especifico de unidades o sesiones."}

EJEMPLO O MUESTRA DEL PRODUCTO ESPERADO
Usa esta muestra solo como referencia pedagogica. No exijas una copia literal si el contexto del docente justifica adaptaciones.
{assistant.ejemplo_producto or "No se proporciono ejemplo del producto esperado."}

RUBRICA
{rubric_text}

PERFIL DE RETROALIMENTACION
{profile_text}

TRANSCRIPCION DEL PDF
El contenido puede mezclar parrafos y tablas representadas en Markdown.

{extracted_markdown}

ENTREGAS RELACIONADAS O PRELIMINARES
{"Esta actividad depende de uno o mas CMID previos (productos preliminares). Contrasta la entrega actual con cada una de ellas y orienta la retroalimentacion como continuidad del proceso." if related_items else "No se proporcionaron entregas relacionadas."}
{_related_items_to_text(related_items)}

IMAGENES DEL PDF
{"Se adjuntan paginas renderizadas del PDF para analisis visual." if image_data_urls else "No se adjuntaron imagenes para este procesamiento."}

INSTRUCCIONES DE RESPUESTA
Devuelve exclusivamente un JSON valido con esta forma:

{{
  "retroalimentacion": "Texto completo en espanol con saludo, aciertos, aspectos por mejorar, niveles estimados, recomendaciones, preguntas reflexivas y cierre.",
  "evaluacion_rubrica": [
    {{
      "criterion_index": 1,
      "dimension": "Dimension evaluada",
      "descripcion_dimension": "Descripcion de la dimension evaluada",
      "criterio": "Criterio evaluado",
      "descripcion_criterio": "Descripcion del criterio evaluado",
      "nivel_obtenido": "inicio | en_proceso | logrado | destacado",
      "score": 0.0,
      "evidencia": "Evidencia textual o descripcion observada en el PDF.",
      "comentario": "Justificacion breve del nivel asignado.",
      "recomendacion": "Accion concreta para mejorar este criterio."
    }}
  ]
}}

Reglas:
- Incluye un item en evaluacion_rubrica por cada criterio de la rubrica, respetando el mismo orden.
- Usa criterion_index empezando en 1.
- score debe estar entre 0 y 4: inicio=1, en_proceso=2, logrado=3, destacado=4. Usa 0 si no hay evidencia.
- Si algo no se observa en el PDF, indicarlo en evidencia y asignar el nivel correspondiente.
- Mantente especifico, formativo y respetuoso.
- Si existen entregas relacionadas, la retroalimentacion debe centrarse en comprobar si la version final corrigio las brechas solicitadas en cada una de ellas.
- Para cada brecha anterior relevante, indica si esta corregida, parcialmente corregida o pendiente, citando evidencia de la version final.
- Si la version final ya no guarda relacion con las entregas relacionadas, indicalo con claridad y no inventes continuidad.
- Es esperable que una version final conserve similitud con una entrega preliminar; no penalices la similitud por si sola, penaliza la repeticion sin mejoras o la falta de relacion.
- Respeta estrictamente la estructura, encabezados y orden indicados en el perfil de retroalimentacion del gestor.
- En retroalimentacion escribe texto plano. No uses etiquetas HTML, Markdown tecnico ni secuencias literales como \\n.
""".strip()

    user_content: str | list[dict] = user
    if image_data_urls:
        user_content = [{"type": "text", "text": user}]
        user_content.extend(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
            for data_url in image_data_urls
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_validation_prompt(
    assistant: AssistantConfig,
    extracted_markdown: str,
    *,
    related_items: list[dict] | None = None,
) -> list[dict[str, str]]:
    related_items = related_items or []
    system = (
        "Eres un validador estricto de productos educativos. "
        "Debes decidir si corresponde dar retroalimentacion o rechazar el documento. "
        "Responde exclusivamente con JSON valido."
    )
    user = f"""
PRODUCTO ESPERADO
{assistant.descripcion_producto}

BASE DEL CURSO, UNIDADES Y SESIONES
{assistant.contexto_curso or "No se proporciono contexto especifico."}

EJEMPLO O MUESTRA DEL PRODUCTO ESPERADO
{assistant.ejemplo_producto or "No se proporciono ejemplo."}

RUBRICA
{_rubric_to_text(assistant.rubrica)}

DOCUMENTO LEIDO
{extracted_markdown}

ENTREGAS RELACIONADAS O PRELIMINARES
{_related_items_to_text(related_items) if related_items else "No se proporcionaron entregas relacionadas."}

INSTRUCCIONES
Valida estrictamente:
1. Que el documento no este en blanco o casi vacio.
2. Que el contenido tenga relacion clara con el producto esperado.
3. Que no sea un documento cualquiera, ajeno al curso o ajeno a la actividad.
4. Si existen entregas relacionadas, que la entrega actual tenga continuidad logica con cada una de ellas.
5. Si existen entregas relacionadas, que la entrega actual parezca una version final o mejorada de esos productos preliminares, no otro producto distinto.
6. Si existe retroalimentacion anterior guardada para alguna entrega relacionada, que la entrega actual pueda evaluarse frente a esas brechas.
7. Si existen entregas relacionadas, que no sea una repeticion sin mejoras de ninguna de ellas.

Devuelve este JSON:
{{
  "is_valid": true,
  "reason": "Motivo claro y especifico.",
  "relevance_score": 0.0,
  "similarity_score": 0.0
}}

Reglas:
- relevance_score va de 0 a 1.
- Si el documento no corresponde, is_valid debe ser false y reason debe explicar estrictamente por que no se dara retroalimentacion.
- En una version final se espera cierta similitud con una entrega preliminar; no rechaces por similitud alta si observas mejoras, ampliaciones o correcciones.
- Si la entrega actual parece repeticion sin mejoras de cualquiera de las relacionadas, is_valid debe ser false.
- Si la entrega actual no guarda relacion clara con ninguna entrega relacionada cuando el CMID depende de ellas, is_valid debe ser false.
""".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_assistant_draft_prompt(documents: list[tuple[str, str]]) -> list[dict]:
    system = (
        "Eres un asistente que ayuda a un gestor pedagogico a redactar la configuracion de un asistente de "
        "retroalimentacion, a partir de documentos de evidencia (rubricas, ejemplos, guias de la actividad). "
        "Analiza cuidadosamente todo el contenido (incluida la rubrica, si existe) para redactar descripciones "
        "completas: puedes sintetizar y resumir lo que los documentos evidencian, pero no inventes hechos, "
        "unidades, sesiones o ejemplos que no esten sustentados en ellos. Responde exclusivamente con un objeto "
        "JSON valido."
    )

    documents_text = "\n\n".join(
        f"### Documento: {filename}\n{content}" for filename, content in documents
    ) or "No se recibieron documentos."

    user = f"""
DOCUMENTOS DE EVIDENCIA SUBIDOS
{documents_text}

INSTRUCCIONES
A partir de los documentos anteriores, redacta un borrador de configuracion con esta forma exacta de JSON:

{{
  "descripcion_producto": "Descripcion clara de que debe entregar el docente, para que sirve el producto y que enfoque pedagogico respeta.",
  "contexto_curso": "Informacion de unidades, sesiones o contenidos base del curso que sustentan el producto, si se puede inferir de los documentos.",
  "ejemplo_producto": "Descripcion de una muestra o estructura esperada del producto, si algun documento la contiene.",
  "rubrica": [
    {{
      "dimension": "Nombre de la dimension",
      "descripcion_dimension": "Que evalua esta dimension en general.",
      "criterio": "Nombre del criterio",
      "descripcion_criterio": "Que se espera observar para este criterio.",
      "niveles": {{
        "inicio": "Descripcion del nivel inicio.",
        "en_proceso": "Descripcion del nivel en proceso.",
        "logrado": "Descripcion del nivel logrado.",
        "destacado": "Descripcion del nivel destacado."
      }}
    }}
  ],
  "perfil_retroalimentacion": [
    "Orientacion 1 para dar la retroalimentacion",
    "Orientacion 2 para dar la retroalimentacion"
  ],
  "campos_incompletos": ["nombre_del_campo_que_no_pudiste_completar_con_confianza"]
}}

Este borrador se usara luego para que otro asistente de IA evalue entregas reales de docentes, asi que cada
campo que completes debe quedar bien explicado y con el detalle suficiente para que ese asistente entienda
todo lo que necesita, no frases sueltas de una linea.

Reglas por campo:
- "descripcion_producto": si los documentos dan algun indicio del producto esperado, redacta 3 a 5 oraciones
  que cubran que debe entregar el docente, para que sirve el producto, que elementos o estructura debe tener
  segun la rubrica u otros documentos, y que enfoque pedagogico respeta. Si hay una rubrica, sintetiza la
  descripcion a partir de sus dimensiones y criterios (eso es resumir, no inventar). Solo dejala vacia si los
  documentos no permiten deducir absolutamente nada sobre el producto.
- "contexto_curso": si los documentos mencionan (aunque sea de forma indirecta) unidades, sesiones o
  contenidos del curso, redacta 2 a 4 oraciones explicando esa base curricular. Si no hay ninguna pista real,
  dejala como cadena vacia; no inventes unidades o sesiones que no aparezcan en los documentos.
- "ejemplo_producto": si algun documento incluye una muestra, modelo o estructura de referencia real,
  descríbela con suficiente detalle (secciones, partes, que debe contener) para orientar la evaluacion. Si no
  hay ninguna, dejala como cadena vacia.
- "rubrica": transcribe fielmente toda tabla o matriz de rubrica que encuentres, respetando dimensiones,
  criterios y los cuatro niveles (inicio, en_proceso, logrado, destacado). Cada item DEBE incluir un
  "criterio" (nombre corto y especifico, nunca vacio) y una "dimension" (tambien no vacia); si el documento
  no nombra explicitamente un criterio, redacta tu un nombre breve y claro a partir de lo que describe, pero
  nunca omitas el nombre. No dejes fuera ningun criterio de la rubrica original por no tener claro su nombre:
  siempre nombralo. Si no hay ninguna rubrica reconocible en los documentos, deja el arreglo vacio.
- "perfil_retroalimentacion": redacta entre 4 y 6 orientaciones concretas y accionables (una por linea) para
  dar la retroalimentacion, basadas en el tono, enfoque o advertencias que sugieran los documentos (por
  ejemplo: como iniciar, que evitar, como tratar errores, que reforzar). Si no hay ninguna pista de tono en
  los documentos, deja la lista vacia en vez de inventar un estilo.
- "campos_incompletos" debe listar, usando exactamente estos nombres (descripcion_producto, contexto_curso,
  ejemplo_producto, rubrica, perfil_retroalimentacion), cualquier campo que hayas dejado vacio (o
  incompleto) por falta de informacion suficiente en los documentos, para que el gestor sepa que debe
  completarlo a mano. Si todos los campos quedaron bien sustentados, devuelve una lista vacia. No repitas
  ahi un campo que sí lograste completar con informacion real de los documentos.
- Responde solo con el JSON, sin texto adicional.
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_sentiment_prompt(items: list[dict]) -> list[dict]:
    system = (
        "Eres un analista de datos educativos. Analizas retroalimentaciones formativas ya emitidas a docentes "
        "y estimas su sentimiento y los temas que contienen. Responde exclusivamente con un objeto JSON valido."
    )

    blocks: list[str] = []
    for item in items:
        evaluations = "\n".join(
            f"  - {ev.get('criterio', '')}: nivel {ev.get('nivel') or 'sin nivel'}"
            + (f" | {ev.get('comentario')}" if ev.get("comentario") else "")
            for ev in item.get("evaluaciones", [])
        )
        blocks.append(
            f"### run_id: {item['run_id']}\n"
            f"Puntaje de rubrica del docente (escala 1 a 4): {item.get('puntaje_rubrica') if item.get('puntaje_rubrica') is not None else 'no disponible'}\n"
            f"Retroalimentacion:\n{item.get('retroalimentacion') or '(vacia)'}\n"
            f"Evaluacion por criterio:\n{evaluations or '  (sin evaluacion por criterio)'}"
        )

    user = f"""
RETROALIMENTACIONES A ANALIZAR
{chr(10).join(blocks)}

INSTRUCCIONES
Para cada retroalimentacion devuelve este JSON exacto (un item por run_id, sin omitir ninguno):

{{
  "resultados": [
    {{
      "run_id": "id recibido",
      "sentimiento": "positivo | neutral | negativo",
      "puntaje": 0.0,
      "tono": "motivador | neutro | exigente | critico",
      "coherencia": "alineada | indulgente | severa",
      "coherencia_motivo": "Una frase que explica por que el tono es coherente o no con los niveles de la rubrica.",
      "fortalezas": ["tema breve", "tema breve"],
      "mejoras": ["tema breve", "tema breve"],
      "resumen": "Una frase que resume el resultado del docente."
    }}
  ]
}}

Reglas:
- "sentimiento" describe la valoracion global del producto del docente que transmite la retroalimentacion: positivo si predominan logros y aciertos, negativo si predominan carencias importantes, neutral si esta equilibrado.
- "puntaje" va de -1 (muy negativo) a 1 (muy positivo).
- "coherencia" compara el tono del texto con los niveles reales de la rubrica: "alineada" si el texto refleja con fidelidad el desempeno (ni exagera ni minimiza), "indulgente" si el texto elogia mas de lo que los niveles justifican (por ejemplo, elogios generales con muchos criterios en inicio o en proceso), "severa" si el texto critica mas de lo que los niveles justifican.
- "fortalezas" y "mejoras": maximo 3 temas cada una, frases nominales cortas (2 a 5 palabras) en minusculas y sin punto final, reutilizando las mismas expresiones para temas equivalentes (por ejemplo "organizacion temporal", "uso de la lengua originaria").
- No inventes informacion que no este en el texto.
- Responde solo con el JSON.
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _related_items_to_text(related_items: list[dict]) -> str:
    if not related_items:
        return ""
    chunks: list[str] = []
    for item in related_items:
        chunks.append(f"\n--- Entrega relacionada (cmid {item.get('cmid')}) ---")
        similarity_score = item.get("similarity_score")
        chunks.append(f"Similitud calculada con esta entrega: {similarity_score if similarity_score is not None else 'No calculada'}")
        previous_feedback_context = item.get("previous_feedback_context")
        if previous_feedback_context:
            chunks.append(
                "Usa estas brechas como foco principal de la retroalimentacion final. Verifica si fueron "
                "corregidas, parcialmente corregidas o si siguen pendientes."
            )
            chunks.append(previous_feedback_context)
        else:
            chunks.append(
                "No se encontro retroalimentacion anterior guardada para esta entrega relacionada. "
                "Infiere brechas comparando la entrega actual con esta entrega y con la rubrica."
            )
        markdown = item.get("markdown") or ""
        if markdown:
            chunks.append("Contenido de la entrega relacionada:")
            chunks.append(markdown)
    return "\n".join(chunks)


def _rubric_to_text(rubric: list[dict]) -> str:
    chunks: list[str] = []
    for index, item in enumerate(rubric, start=1):
        chunks.append(f"{index}. Dimension: {item.get('dimension', '')}")
        if item.get("descripcion_dimension"):
            chunks.append(f"   Descripcion de la dimension: {item.get('descripcion_dimension')}")
        chunks.append(f"   Criterio: {item.get('criterio', '')}")
        if item.get("descripcion_criterio"):
            chunks.append(f"   Descripcion del criterio: {item.get('descripcion_criterio')}")
        niveles = item.get("niveles", {})
        for level in ("inicio", "en_proceso", "logrado", "destacado"):
            if level in niveles:
                chunks.append(f"   - {level}: {niveles[level]}")
    return "\n".join(chunks)
