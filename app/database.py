from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.config import settings


def _ensure_sqlite_parent() -> None:
    if settings.resolved_database_url.startswith("sqlite:///"):
        db_path = settings.resolved_database_url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent()
engine = create_engine(settings.resolved_database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _apply_lightweight_migrations()


def get_session():
    with Session(engine) as session:
        yield session


def _apply_lightweight_migrations() -> None:
    if not settings.resolved_database_url.startswith("postgresql"):
        return
    statements = [
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS contexto_curso VARCHAR",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS ejemplo_producto VARCHAR",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS analiza_texto BOOLEAN DEFAULT TRUE",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS analiza_tablas BOOLEAN DEFAULT TRUE",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS analiza_imagenes BOOLEAN DEFAULT FALSE",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS usa_cmid_relacionado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS cmid_relacionado INTEGER",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS validar_documento BOOLEAN DEFAULT TRUE",
        "ALTER TABLE assistantconfig ADD COLUMN IF NOT EXISTS validar_similitud BOOLEAN DEFAULT TRUE",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS role INTEGER DEFAULT 0",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS cmid_relacionado INTEGER",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS related_pdf_filename VARCHAR",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS related_caracteres_extraidos INTEGER",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS similarity_score FLOAT",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS validation_reason VARCHAR",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS relevance_score FLOAT",
        "ALTER TABLE processingrun ADD COLUMN IF NOT EXISTS imagenes_analizadas INTEGER",
        "ALTER TABLE rubricevaluation ADD COLUMN IF NOT EXISTS descripcion_dimension VARCHAR",
        "ALTER TABLE rubricevaluation ADD COLUMN IF NOT EXISTS descripcion_criterio VARCHAR",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
