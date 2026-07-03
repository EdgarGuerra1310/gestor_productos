from pydantic import BaseModel, Field


class RubricCriterion(BaseModel):
    dimension: str
    descripcion_dimension: str | None = Field(
        default=None,
        description="Explica que aspecto general evalua esta dimension.",
    )
    criterio: str
    descripcion_criterio: str | None = Field(
        default=None,
        description="Explica que se espera observar para este criterio.",
    )
    niveles: dict[str, str] = Field(
        description="Claves esperadas: inicio, en_proceso, logrado, destacado."
    )


class AssistantConfigIn(BaseModel):
    nombre: str
    descripcion_producto: str
    contexto_curso: str | None = Field(
        default=None,
        description="Informacion de unidades, sesiones y contenidos base del curso relacionados con el producto.",
    )
    ejemplo_producto: str | None = Field(
        default=None,
        description="Ejemplo o muestra del producto esperado para orientar la retroalimentacion.",
    )
    analiza_texto: bool = True
    analiza_tablas: bool = True
    analiza_imagenes: bool = False
    usa_cmid_relacionado: bool = False
    cmid_relacionado: int | None = None
    validar_documento: bool = True
    validar_similitud: bool = True
    rubrica: list[RubricCriterion]
    perfil_retroalimentacion: list[str]
    modelo: str | None = None
    activo: bool = True


class AssistantConfigOut(AssistantConfigIn):
    cmid: int


class RubricEvaluationOut(BaseModel):
    criterion_index: int
    dimension: str
    descripcion_dimension: str | None = None
    criterio: str
    descripcion_criterio: str | None = None
    nivel_obtenido: str | None = None
    score: float | None = None
    evidencia: str | None = None
    comentario: str | None = None
    recomendacion: str | None = None


class ProcessingResult(BaseModel):
    run_id: str
    desde_cache: bool = False
    cmid: int
    user_id: int
    course_id: int
    nombre: str
    role: int = 0
    paginas_detectadas: int
    tablas_detectadas: int
    imagenes_analizadas: int = 0
    caracteres_extraidos: int
    cmid_relacionado: int | None = None
    similarity_score: float | None = None
    validation_passed: bool | None = None
    validation_reason: str | None = None
    relevance_score: float | None = None
    total_ms: int | None = None
    moodle_ms: int | None = None
    extraction_ms: int | None = None
    gpt_ms: int | None = None
    modelo: str | None = None
    total_tokens: int | None = None
    retroalimentacion: str
    evaluacion_rubrica: list[RubricEvaluationOut] = []


class ProcessingRunSummary(BaseModel):
    id: str
    cmid: int
    user_id: int
    course_id: int
    nombre: str
    source: str
    status: str
    stage: str
    paginas_detectadas: int | None = None
    tablas_detectadas: int | None = None
    total_ms: int | None = None
    error_message: str | None = None
