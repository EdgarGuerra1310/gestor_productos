from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import AssistantCmid, AssistantConfig, Course, Program
from app.schemas import AssistantConfigIn, AssistantConfigOut


def _assert_cmids_available(session: Session, cmids: list[int], *, exclude_assistant_id: int | None = None) -> None:
    if not cmids:
        return
    statement = select(AssistantCmid).where(AssistantCmid.cmid.in_(cmids))
    conflicts = [
        link
        for link in session.exec(statement).all()
        if exclude_assistant_id is None or link.assistant_id != exclude_assistant_id
    ]
    if conflicts:
        taken = ", ".join(str(link.cmid) for link in conflicts)
        raise HTTPException(
            status_code=409,
            detail=f"Los siguientes CMID ya estan asignados a otro asistente: {taken}.",
        )


def _resolve_dependencies(payload: AssistantConfigIn) -> dict[int, list[int]]:
    """Devuelve {cmid: [cmids preliminares]} para cada CMID del asistente.

    Usa `dependencias` (por CMID). Si no viene, aplica `cmids_relacionados` a todos los CMID,
    como hacian los clientes anteriores. Un CMID nunca depende de si mismo.
    """
    if payload.dependencias:
        source = {cmid: payload.dependencias.get(cmid, []) for cmid in payload.cmids}
    elif payload.usa_cmid_relacionado and payload.cmids_relacionados:
        source = {cmid: payload.cmids_relacionados for cmid in payload.cmids}
    else:
        source = {cmid: [] for cmid in payload.cmids}

    resolved: dict[int, list[int]] = {}
    for cmid, related in source.items():
        cleaned: list[int] = []
        for value in related:
            if value != cmid and value not in cleaned:
                cleaned.append(value)
        resolved[cmid] = cleaned
    return resolved


def _assistant_data(payload: AssistantConfigIn, dependencies: dict[int, list[int]]) -> dict:
    data = payload.model_dump(mode="json", exclude={"cmids", "dependencias"})
    union = sorted({value for related in dependencies.values() for value in related})
    data["cmids_relacionados"] = union
    data["usa_cmid_relacionado"] = bool(union)
    return data


def create_assistant(session: Session, payload: AssistantConfigIn) -> AssistantConfig:
    _assert_cmids_available(session, payload.cmids)

    dependencies = _resolve_dependencies(payload)
    assistant = AssistantConfig(**_assistant_data(payload, dependencies))
    session.add(assistant)
    session.commit()
    session.refresh(assistant)

    for cmid in payload.cmids:
        session.add(
            AssistantCmid(cmid=cmid, assistant_id=assistant.id, cmids_relacionados=dependencies[cmid])
        )
    session.commit()
    session.refresh(assistant)
    return assistant


def update_assistant(session: Session, assistant_id: int, payload: AssistantConfigIn) -> AssistantConfig:
    assistant = session.get(AssistantConfig, assistant_id)
    if assistant is None:
        raise HTTPException(status_code=404, detail=f"No existe el asistente {assistant_id}.")

    _assert_cmids_available(session, payload.cmids, exclude_assistant_id=assistant_id)

    dependencies = _resolve_dependencies(payload)
    for key, value in _assistant_data(payload, dependencies).items():
        setattr(assistant, key, value)
    assistant.updated_at = datetime.now(timezone.utc)
    session.add(assistant)

    existing_links = list(
        session.exec(select(AssistantCmid).where(AssistantCmid.assistant_id == assistant_id)).all()
    )
    existing_cmids = {link.cmid for link in existing_links}
    new_cmids = set(payload.cmids)

    for link in existing_links:
        if link.cmid not in new_cmids:
            session.delete(link)
        else:
            link.cmids_relacionados = dependencies[link.cmid]
            session.add(link)
    for cmid in new_cmids - existing_cmids:
        session.add(AssistantCmid(cmid=cmid, assistant_id=assistant_id, cmids_relacionados=dependencies[cmid]))

    session.commit()
    session.refresh(assistant)
    return assistant


def get_assistant_or_404(session: Session, assistant_id: int) -> AssistantConfig:
    assistant = session.get(AssistantConfig, assistant_id)
    if assistant is None:
        raise HTTPException(status_code=404, detail=f"No existe el asistente {assistant_id}.")
    return assistant


def get_cmids_for_assistant(session: Session, assistant_id: int) -> list[int]:
    statement = select(AssistantCmid.cmid).where(AssistantCmid.assistant_id == assistant_id)
    return sorted(session.exec(statement).all())


def get_dependencies_for_assistant(session: Session, assistant_id: int) -> dict[int, list[int]]:
    statement = select(AssistantCmid).where(AssistantCmid.assistant_id == assistant_id)
    return {
        link.cmid: list(link.cmids_relacionados or [])
        for link in sorted(session.exec(statement).all(), key=lambda link: link.cmid)
    }


def get_dependencies_for_cmid(session: Session, cmid: int) -> list[int]:
    link = session.get(AssistantCmid, cmid)
    return list(link.cmids_relacionados or []) if link else []


def find_assistant_by_cmid(session: Session, cmid: int) -> AssistantConfig | None:
    link = session.get(AssistantCmid, cmid)
    if link is None:
        return None
    return session.get(AssistantConfig, link.assistant_id)


def get_assistant_by_cmid_or_404(session: Session, cmid: int) -> AssistantConfig:
    assistant = find_assistant_by_cmid(session, cmid)
    if assistant is None or not assistant.activo:
        raise HTTPException(
            status_code=404,
            detail=f"No hay un asistente activo configurado para el cmid {cmid}.",
        )
    return assistant


def list_assistants(session: Session) -> list[AssistantConfigOut]:
    assistants = list(session.exec(select(AssistantConfig).order_by(AssistantConfig.id)).all())
    programs = {program.id: program.nombre for program in session.exec(select(Program)).all()}
    courses = {course.id: course.nombre for course in session.exec(select(Course)).all()}

    results: list[AssistantConfigOut] = []
    for assistant in assistants:
        cmids = get_cmids_for_assistant(session, assistant.id)
        results.append(
            AssistantConfigOut(
                id=assistant.id,
                nombre=assistant.nombre,
                cmids=cmids,
                descripcion_producto=assistant.descripcion_producto,
                contexto_curso=assistant.contexto_curso,
                ejemplo_producto=assistant.ejemplo_producto,
                analiza_texto=assistant.analiza_texto,
                analiza_tablas=assistant.analiza_tablas,
                analiza_imagenes=assistant.analiza_imagenes,
                usa_cmid_relacionado=assistant.usa_cmid_relacionado,
                cmids_relacionados=assistant.cmids_relacionados,
                dependencias=get_dependencies_for_assistant(session, assistant.id),
                validar_documento=assistant.validar_documento,
                validar_similitud=assistant.validar_similitud,
                rubrica=assistant.rubrica,
                perfil_retroalimentacion=assistant.perfil_retroalimentacion,
                modelo=assistant.modelo,
                programa_id=assistant.programa_id,
                curso_id=assistant.curso_id,
                programa_nombre=programs.get(assistant.programa_id),
                curso_nombre=courses.get(assistant.curso_id),
                activo=assistant.activo,
            )
        )
    return results


def to_assistant_out(session: Session, assistant: AssistantConfig) -> AssistantConfigOut:
    programa_nombre = None
    if assistant.programa_id is not None:
        program = session.get(Program, assistant.programa_id)
        programa_nombre = program.nombre if program else None
    curso_nombre = None
    if assistant.curso_id is not None:
        course = session.get(Course, assistant.curso_id)
        curso_nombre = course.nombre if course else None

    return AssistantConfigOut(
        id=assistant.id,
        nombre=assistant.nombre,
        cmids=get_cmids_for_assistant(session, assistant.id),
        descripcion_producto=assistant.descripcion_producto,
        contexto_curso=assistant.contexto_curso,
        ejemplo_producto=assistant.ejemplo_producto,
        analiza_texto=assistant.analiza_texto,
        analiza_tablas=assistant.analiza_tablas,
        analiza_imagenes=assistant.analiza_imagenes,
        usa_cmid_relacionado=assistant.usa_cmid_relacionado,
        cmids_relacionados=assistant.cmids_relacionados,
        dependencias=get_dependencies_for_assistant(session, assistant.id),
        validar_documento=assistant.validar_documento,
        validar_similitud=assistant.validar_similitud,
        rubrica=assistant.rubrica,
        perfil_retroalimentacion=assistant.perfil_retroalimentacion,
        modelo=assistant.modelo,
        programa_id=assistant.programa_id,
        curso_id=assistant.curso_id,
        programa_nombre=programa_nombre,
        curso_nombre=curso_nombre,
        activo=assistant.activo,
    )
