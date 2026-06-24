from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from sqlmodel import Session, desc, select

from app.models import ProcessingEvent, ProcessingRun, RubricEvaluation


def now_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def start_timer() -> float:
    return perf_counter()


def create_run(
    session: Session,
    *,
    cmid: int,
    user_id: int,
    course_id: int,
    nombre: str,
    source: str,
    request_params: dict,
) -> ProcessingRun:
    run = ProcessingRun(
        id=str(uuid4()),
        cmid=cmid,
        user_id=user_id,
        course_id=course_id,
        nombre=nombre,
        source=source,
        request_params=request_params,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    log_event(session, run.id, "started", "Solicitud recibida", details=request_params)
    return run


def log_event(
    session: Session,
    run_id: str,
    stage: str,
    message: str,
    *,
    level: str = "info",
    elapsed_ms: int | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        ProcessingEvent(
            run_id=run_id,
            level=level,
            stage=stage,
            message=message,
            elapsed_ms=elapsed_ms,
            details=details or {},
        )
    )
    session.commit()


def update_run(session: Session, run: ProcessingRun, **values) -> ProcessingRun:
    for key, value in values.items():
        setattr(run, key, value)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def finish_run(session: Session, run: ProcessingRun, *, status: str, total_ms: int, **values) -> ProcessingRun:
    values.update(
        status=status,
        stage=status,
        total_ms=total_ms,
        completed_at=datetime.now(timezone.utc),
    )
    return update_run(session, run, **values)


def save_rubric_evaluations(
    session: Session,
    run_id: str,
    evaluations: list[dict],
    rubric: list[dict],
) -> None:
    for item in evaluations:
        criterion_index = _as_int(item.get("criterion_index"), default=0)
        rubric_item = _rubric_item_for_index(rubric, criterion_index)
        session.add(
            RubricEvaluation(
                run_id=run_id,
                criterion_index=criterion_index,
                dimension=str(item.get("dimension") or rubric_item.get("dimension") or ""),
                descripcion_dimension=_safe_text(
                    item.get("descripcion_dimension") or rubric_item.get("descripcion_dimension")
                ),
                criterio=str(item.get("criterio") or rubric_item.get("criterio") or ""),
                descripcion_criterio=_safe_text(
                    item.get("descripcion_criterio") or rubric_item.get("descripcion_criterio")
                ),
                nivel_obtenido=_safe_text(item.get("nivel_obtenido")),
                score=_as_float(item.get("score")),
                evidencia=_safe_text(item.get("evidencia")),
                comentario=_safe_text(item.get("comentario")),
                recomendacion=_safe_text(item.get("recomendacion")),
                raw=item,
            )
        )
    session.commit()


def get_recent_runs(session: Session, limit: int = 50) -> list[ProcessingRun]:
    statement = select(ProcessingRun).order_by(desc(ProcessingRun.started_at)).limit(limit)
    return list(session.exec(statement).all())


def get_latest_successful_run(
    session: Session,
    *,
    cmid: int,
    user_id: int,
    course_id: int,
) -> ProcessingRun | None:
    statement = (
        select(ProcessingRun)
        .where(ProcessingRun.cmid == cmid)
        .where(ProcessingRun.user_id == user_id)
        .where(ProcessingRun.course_id == course_id)
        .where(ProcessingRun.source == "moodle")
        .where(ProcessingRun.status == "success")
        .where(ProcessingRun.retroalimentacion.is_not(None))
        .order_by(desc(ProcessingRun.completed_at), desc(ProcessingRun.started_at))
        .limit(1)
    )
    return session.exec(statement).first()


def get_rubric_evaluations(session: Session, run_id: str) -> list[RubricEvaluation]:
    statement = (
        select(RubricEvaluation)
        .where(RubricEvaluation.run_id == run_id)
        .order_by(RubricEvaluation.criterion_index)
    )
    return list(session.exec(statement).all())


def get_run_detail(session: Session, run_id: str) -> dict | None:
    run = session.get(ProcessingRun, run_id)
    if run is None:
        return None

    events = list(
        session.exec(
            select(ProcessingEvent)
            .where(ProcessingEvent.run_id == run_id)
            .order_by(ProcessingEvent.created_at)
        ).all()
    )
    rubric = get_rubric_evaluations(session, run_id)
    return {"run": run, "events": events, "rubric_evaluations": rubric}


def _rubric_item_for_index(rubric: list[dict], criterion_index: int) -> dict:
    if 1 <= criterion_index <= len(rubric):
        return rubric[criterion_index - 1]
    return {}


def _safe_text(value) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
