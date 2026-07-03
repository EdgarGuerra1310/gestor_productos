from app.models import AssistantConfig


def build_feedback_prompt(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    image_data_urls: list[str] | None = None,
    related_markdown: str | None = None,
    similarity_score: float | None = None,
) -> list[dict]:
    rubric_text = _rubric_to_text(assistant.rubrica)
    profile_text = "\n".join(f"- {item}" for item in assistant.perfil_retroalimentacion)

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
- cmid: {assistant.cmid}

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

ENTREGA RELACIONADA O ANTERIOR
{"Esta actividad depende de un CMID previo. Contrasta la entrega actual con la anterior y orienta la retroalimentacion como continuidad del proceso." if related_markdown else "No se proporciono entrega relacionada."}
{related_markdown or ""}

SIMILITUD CON ENTREGA RELACIONADA
{similarity_score if similarity_score is not None else "No calculada"}

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
- Si existe entrega relacionada, explica avances, continuidad, mejoras o repeticiones respecto a la entrega anterior.
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
    related_markdown: str | None = None,
    similarity_score: float | None = None,
) -> list[dict[str, str]]:
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

ENTREGA RELACIONADA O ANTERIOR
{related_markdown or "No se proporciono entrega relacionada."}

SIMILITUD CALCULADA CON ENTREGA RELACIONADA
{similarity_score if similarity_score is not None else "No calculada"}

INSTRUCCIONES
Valida estrictamente:
1. Que el documento no este en blanco o casi vacio.
2. Que el contenido tenga relacion clara con el producto esperado.
3. Que no sea un documento cualquiera, ajeno al curso o ajeno a la actividad.
4. Si existe entrega relacionada, que la entrega actual no sea una repeticion de la anterior.

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
- Si la entrega actual parece repeticion de la relacionada, is_valid debe ser false.
""".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


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
