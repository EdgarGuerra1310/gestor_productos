from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Course, Program
from app.schemas import CourseOut
from app.services.moodle import MoodleClient, MoodleDownloadError


def create_program(session: Session, nombre: str) -> Program:
    program = Program(nombre=nombre.strip())
    session.add(program)
    session.commit()
    session.refresh(program)
    return program


def list_programs(session: Session) -> list[Program]:
    return list(session.exec(select(Program).order_by(Program.nombre)).all())


def get_program_or_404(session: Session, programa_id: int) -> Program:
    program = session.get(Program, programa_id)
    if program is None:
        raise HTTPException(status_code=404, detail=f"No existe el programa {programa_id}.")
    return program


async def create_course(session: Session, programa_id: int, course_id: int) -> Course:
    program = get_program_or_404(session, programa_id)

    existing = session.exec(select(Course).where(Course.course_id == course_id)).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"El course_id {course_id} ya esta registrado como '{existing.nombre}'.",
        )

    try:
        nombre = await MoodleClient().get_course_name(course_id)
    except MoodleDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    course = Course(programa_id=program.id, course_id=course_id, nombre=nombre)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def list_courses(session: Session, programa_id: int | None = None) -> list[CourseOut]:
    statement = select(Course)
    if programa_id is not None:
        statement = statement.where(Course.programa_id == programa_id)
    courses = list(session.exec(statement.order_by(Course.nombre)).all())

    programs = {program.id: program.nombre for program in session.exec(select(Program)).all()}
    return [
        CourseOut(
            id=course.id,
            programa_id=course.programa_id,
            programa_nombre=programs.get(course.programa_id),
            course_id=course.course_id,
            nombre=course.nombre,
        )
        for course in courses
    ]
