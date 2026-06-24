import json
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import settings
from app.models import AssistantConfig
from app.services.prompts import build_feedback_prompt


@dataclass
class FeedbackGenerationResult:
    retroalimentacion: str
    evaluacion_rubrica: list[dict] = field(default_factory=list)
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw_content: str = ""


def generate_feedback(
    assistant: AssistantConfig,
    extracted_markdown: str,
    student_name: str,
    user_id: int,
    course_id: int,
    image_data_urls: list[str] | None = None,
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
        ),
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or ""
    payload = _parse_feedback_json(content)
    usage = response.usage

    return FeedbackGenerationResult(
        retroalimentacion=str(payload.get("retroalimentacion") or content),
        evaluacion_rubrica=_normalize_evaluations(payload.get("evaluacion_rubrica")),
        model=response.model,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        raw_content=content,
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
