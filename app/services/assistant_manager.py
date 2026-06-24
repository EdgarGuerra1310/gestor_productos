from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import AssistantConfig
from app.schemas import AssistantConfigIn


def create_assistant(session: Session, cmid: int, payload: AssistantConfigIn) -> AssistantConfig:
    existing = session.get(AssistantConfig, cmid)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe una configuracion para el cmid {cmid}. "
                "Carga ese CMID y editalo en lugar de crear otro."
            ),
        )

    assistant = AssistantConfig(cmid=cmid, **payload.model_dump(mode="json"))
    session.add(assistant)
    session.commit()
    session.refresh(assistant)
    return assistant


def upsert_assistant(session: Session, cmid: int, payload: AssistantConfigIn) -> AssistantConfig:
    assistant = session.get(AssistantConfig, cmid)
    data = payload.model_dump(mode="json")

    if assistant is None:
        assistant = AssistantConfig(cmid=cmid, **data)
        session.add(assistant)
    else:
        for key, value in data.items():
            setattr(assistant, key, value)
        assistant.updated_at = datetime.now(timezone.utc)

    session.commit()
    session.refresh(assistant)
    return assistant


def get_assistant_or_404(session: Session, cmid: int) -> AssistantConfig:
    assistant = session.get(AssistantConfig, cmid)
    if assistant is None or not assistant.activo:
        raise HTTPException(
            status_code=404,
            detail=f"No hay un asistente activo configurado para el cmid {cmid}.",
        )
    return assistant


def list_assistants(session: Session) -> list[AssistantConfig]:
    return list(session.exec(select(AssistantConfig).order_by(AssistantConfig.cmid)).all())
