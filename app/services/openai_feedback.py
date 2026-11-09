import json
import re
from html import unescape
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import settings
from app.models import AssistantConfig
from app.schemas import AssistantDraftOut, RubricCriterion
from app.services.prompts import (
    build_assistant_draft_prompt,
    build_feedback_prompt,
    build_sentiment_prompt,
    build_validation_prompt,
)


@dataclass
class FeedbackGenerationResult:
    retroalimentacion: str
    evaluacion_rubrica: list[dict] = field(default_factory=list)
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw_content: str = ""


@dataclass
class SubmissionValidationResult:
    is_valid: bool
    reason: str
    relevance_score: float | None = None
    similarity_score: float | None = None
    model: str | None = None
    total_tokens: int | None = None


def _client() -> AzureOpenAI:
    if not settings.azure_openai_api_key:
        raise RuntimeError("Falta configurar AZURE_OPENAI_API_KEY en .env.")
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )


def generate_feedback(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    cmid: int,
    image_data_urls: list[str] | None = None,
    related_items: list[dict] | None = None,
) -> FeedbackGenerationResult:
    client = _client()

    response = client.chat.completions.create(
        model=assistant.modelo or settings.azure_openai_deployment,
        messages=build_feedback_prompt(
            assistant=assistant,
            extracted_markdown=extracted_markdown,
            student_name=student_name,
            user_id=user_id,
            course_id=course_id,
            cmid=cmid,
            image_data_urls=image_data_urls,
            related_items=related_items,
        ),
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    payload = _parse_feedback_json(content)
    usage = response.usage

    return FeedbackGenerationResult(
        retroalimentacion=_clean_feedback_text(str(payload.get("retroalimentacion") or content)),
        evaluacion_rubrica=_normalize_evaluations(payload.get("evaluacion_rubrica")),
        model=response.model,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        raw_content=content,
    )


def validate_submission(
    assistant: AssistantConfig,
    extracted_markdown: str,
    *,
    related_items: list[dict] | None = None,
) -> SubmissionValidationResult:
    client = _client()

    clipped_related_items = None
    if related_items:
        clipped_related_items = [
            {**item, "markdown": _clip(item.get("markdown") or "")} for item in related_items
        ]

    response = client.chat.completions.create(
        model=assistant.modelo or settings.azure_openai_deployment,
        messages=build_validation_prompt(
            assistant=assistant,
            extracted_markdown=_clip(extracted_markdown),
            related_items=clipped_related_items,
        ),
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    payload = _parse_feedback_json(content)
    usage = response.usage
    return SubmissionValidationResult(
        is_valid=bool(payload.get("is_valid")),
        reason=str(payload.get("reason") or "No se pudo validar el documento."),
        relevance_score=_as_float(payload.get("relevance_score")),
        similarity_score=_as_float(payload.get("similarity_score")),
        model=response.model,
        total_tokens=getattr(usage, "total_tokens", None),
    )


def generate_assistant_draft(documents: list[tuple[str, str]]) -> AssistantDraftOut:
    client = _client()

    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=build_assistant_draft_prompt(documents),
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    payload = _parse_feedback_json(content)

    rubrica: list[RubricCriterion] = []
    rubric_items_dropped = False
    for item in payload.get("rubrica") or []:
        if not isinstance(item, dict):
            rubric_items_dropped = True
            continue

        criterio = str(item.get("criterio") or "").strip()
        dimension = str(item.get("dimension") or "").strip()
        descripcion_criterio = str(item.get("descripcion_criterio") or "").strip()
        # Nunca perder un criterio solo porque el modelo no le puso nombre explicito:
        # se rellena con la mejor pista disponible antes de descartarlo.
        if not criterio:
            criterio = descripcion_criterio[:80] or dimension
        if not dimension:
            dimension = criterio

        if not criterio:
            rubric_items_dropped = True
            continue

        try:
            rubrica.append(RubricCriterion(**{**item, "criterio": criterio, "dimension": dimension}))
        except Exception:
            rubric_items_dropped = True
            continue

    perfil = [str(line).strip() for line in (payload.get("perfil_retroalimentacion") or []) if str(line).strip()]
    descripcion_producto = str(payload.get("descripcion_producto") or "").strip()
    contexto_curso = str(payload.get("contexto_curso") or "").strip()
    ejemplo_producto = str(payload.get("ejemplo_producto") or "").strip()

    valid_fields = {
        "descripcion_producto",
        "contexto_curso",
        "ejemplo_producto",
        "rubrica",
        "perfil_retroalimentacion",
    }
    campos_incompletos = {
        str(item) for item in (payload.get("campos_incompletos") or []) if str(item) in valid_fields
    }
    # Defensa adicional: si un campo quedo vacio, siempre se marca como incompleto,
    # sin depender de que el modelo lo haya reportado correctamente.
    if not descripcion_producto:
        campos_incompletos.add("descripcion_producto")
    if not contexto_curso:
        campos_incompletos.add("contexto_curso")
    if not ejemplo_producto:
        campos_incompletos.add("ejemplo_producto")
    if not rubrica or rubric_items_dropped:
        campos_incompletos.add("rubrica")
    if not perfil:
        campos_incompletos.add("perfil_retroalimentacion")

    return AssistantDraftOut(
        descripcion_producto=descripcion_producto,
        contexto_curso=contexto_curso,
        ejemplo_producto=ejemplo_producto,
        rubrica=rubrica,
        perfil_retroalimentacion=perfil,
        campos_incompletos=sorted(campos_incompletos),
    )


def analyze_sentiments(items: list[dict]) -> tuple[list[dict], str | None, int | None]:
    """Analiza el sentimiento de varias retroalimentaciones en una sola llamada.

    Devuelve (resultados normalizados, modelo usado, tokens totales).
    """
    client = _client()
    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=build_sentiment_prompt(items),
        temperature=0,
        response_format={"type": "json_object"},
    )
    payload = _parse_feedback_json(response.choices[0].message.content or "")
    usage = response.usage

    valid_run_ids = {item["run_id"] for item in items}
    results: list[dict] = []
    for raw in payload.get("resultados") or []:
        if not isinstance(raw, dict) or str(raw.get("run_id")) not in valid_run_ids:
            continue
        sentimiento = str(raw.get("sentimiento") or "").strip().lower()
        if sentimiento not in {"positivo", "neutral", "negativo"}:
            sentimiento = "neutral"
        puntaje = _as_float(raw.get("puntaje")) or 0.0
        coherencia = str(raw.get("coherencia") or "").strip().lower()
        if coherencia not in {"alineada", "indulgente", "severa"}:
            coherencia = "alineada"
        results.append(
            {
                "run_id": str(raw["run_id"]),
                "sentimiento": sentimiento,
                "puntaje": max(-1.0, min(1.0, puntaje)),
                "tono": str(raw.get("tono") or "").strip().lower() or None,
                "coherencia": coherencia,
                "coherencia_motivo": str(raw.get("coherencia_motivo") or "").strip() or None,
                "fortalezas": _clean_themes(raw.get("fortalezas")),
                "mejoras": _clean_themes(raw.get("mejoras")),
                "resumen": str(raw.get("resumen") or "").strip() or None,
            }
        )
    return results, response.model, getattr(usage, "total_tokens", None)


def _clean_themes(value) -> list[str]:
    if not isinstance(value, list):
        return []
    themes: list[str] = []
    for item in value:
        text = str(item).strip().strip(".").lower()
        if text and text not in themes:
            themes.append(text)
    return themes[:3]


def _parse_feedback_json(content: str) -> dict:
    try:
        payload = json.loads(content)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return {"retroalimentacion": content, "evaluacion_rubrica": []}


def _normalize_evaluations(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _clip(value: str) -> str:
    if len(value) <= settings.validation_max_chars:
        return value
    return value[: settings.validation_max_chars] + "\n\n[Contenido recortado para validacion]"


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_feedback_text(value: str) -> str:
    text = unescape(value)
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li\s*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
