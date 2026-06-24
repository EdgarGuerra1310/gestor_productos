from app.models import AssistantConfig


def build_feedback_prompt(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    image_data_urls: list[str] | None = None,
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
