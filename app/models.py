from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class AssistantConfig(SQLModel, table=True):
    cmid: int = Field(primary_key=True, index=True)
    nombre: str
    descripcion_producto: str
    contexto_curso: str | None = None
    ejemplo_producto: str | None = None
    analiza_texto: bool = True
    analiza_tablas: bool = True
    analiza_imagenes: bool = False
    usa_cmid_relacionado: bool = False
    cmid_relacionado: int | None = Field(default=None, index=True)
    validar_documento: bool = True
    validar_similitud: bool = True
    rubrica: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    perfil_retroalimentacion: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    modelo: str | None = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProcessingRun(SQLModel, table=True):
    id: str = Field(primary_key=True)
    cmid: int = Field(index=True)
    user_id: int = Field(index=True)
    course_id: int = Field(index=True)
    nombre: str
    role: int = Field(default=0, index=True)
    source: str = Field(default="moodle", index=True)
    status: str = Field(default="started", index=True)
    stage: str = Field(default="started", index=True)

    request_params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    moodle_service_url: str | None = None
    pdf_filename: str | None = None
    pdf_size_bytes: int | None = None
    paginas_detectadas: int | None = None
    tablas_detectadas: int | None = None
    imagenes_analizadas: int | None = None
    caracteres_extraidos: int | None = None
    cmid_relacionado: int | None = Field(default=None, index=True)
    related_pdf_filename: str | None = None
    related_caracteres_extraidos: int | None = None
    similarity_score: float | None = None
    validation_passed: bool | None = None
    validation_reason: str | None = None
    relevance_score: float | None = None

    modelo: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    retroalimentacion: str | None = None

    moodle_ms: int | None = None
    extraction_ms: int | None = None
    gpt_ms: int | None = None
    cleanup_ms: int | None = None
    total_ms: int | None = None

    error_type: str | None = None
    error_message: str | None = None
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    completed_at: datetime | None = None


class ProcessingEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="processingrun.id")
    level: str = Field(default="info", index=True)
    stage: str = Field(index=True)
    message: str
    elapsed_ms: int | None = None
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class RubricEvaluation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="processingrun.id")
    criterion_index: int = Field(index=True)
    dimension: str
    descripcion_dimension: str | None = None
    criterio: str
    descripcion_criterio: str | None = None
    nivel_obtenido: str | None = Field(default=None, index=True)
    score: float | None = None
    evidencia: str | None = None
    comentario: str | None = None
    recomendacion: str | None = None
    raw: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
