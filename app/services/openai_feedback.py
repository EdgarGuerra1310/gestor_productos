import json
import re
from html import unescape
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import settings
from app.models import AssistantConfig
from app.services.prompts import build_feedback_prompt, build_validation_prompt


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


def generate_feedback(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    image_data_urls: list[str] | None = None,
    related_markdown: str | None = None,
    similarity_score: float | None = None,
) -> FeedbackGenerationResult:
    if not settings.azure_openai_api_key:
        raise RuntimeError("Falta configurar AZURE_OPENAI_API_KEY en .env.")

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )

    response = client.chat.completions.create(
        model=assistant.modelo or settings.azure_openai_deployment,
        messages=build_feedback_prompt(
            assistant=assistant,
            extracted_markdown=extracted_markdown,
            student_name=student_name,
            user_id=user_id,
            course_id=course_id,
            image_data_urls=image_data_urls,
            related_markdown=related_markdown,
            similarity_score=similarity_score,
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
    related_markdown: str | None = None,
    similarity_score: float | None = None,
) -> SubmissionValidationResult:
    if not settings.azure_openai_api_key:
        raise RuntimeError("Falta configurar AZURE_OPENAI_API_KEY en .env.")

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )

    response = client.chat.completions.create(
        model=assistant.modelo or settings.azure_openai_deployment,
        messages=build_validation_prompt(
            assistant=assistant,
            extracted_markdown=_clip(extracted_markdown),
            related_markdown=_clip(related_markdown or "") if related_markdown else None,
            similarity_score=similarity_score,
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
        similarity_score=_as_float(payload.get("similarity_score") or similarity_score),
        model=response.model,
        total_tokens=getattr(usage, "total_tokens", None),
    )


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
