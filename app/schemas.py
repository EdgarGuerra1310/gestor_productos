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
    cmids: list[int] = Field(
        description="Lista de CMID de Moodle a los que aplica esta configuracion.",
        min_length=1,
    )
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
    cmids_relacionados: list[int] = Field(
        default_factory=list,
        description=(
            "Compatibilidad: si no se envia `dependencias`, esta lista se aplica a todos los `cmids`. "
            "Al guardar se recalcula como la union de todas las dependencias."
        ),
    )
    dependencias: dict[int, list[int]] = Field(
        default_factory=dict,
        description=(
            "Dependencias por CMID: {cmid: [cmids preliminares]}. Cada CMID del asistente puede depender "
            "de CMID distintos; los que no aparecen no tienen dependencia."
        ),
    )
    validar_documento: bool = True
    validar_similitud: bool = True
    rubrica: list[RubricCriterion]
    perfil_retroalimentacion: list[str]
    modelo: str | None = None
    programa_id: int | None = None
    curso_id: int | None = None
    activo: bool = True


class AssistantConfigOut(BaseModel):
    id: int
    nombre: str
    cmids: list[int]
    descripcion_producto: str
    contexto_curso: str | None = None
    ejemplo_producto: str | None = None
    analiza_texto: bool
    analiza_tablas: bool
    analiza_imagenes: bool
    usa_cmid_relacionado: bool
    cmids_relacionados: list[int]
    dependencias: dict[int, list[int]] = {}
    validar_documento: bool
    validar_similitud: bool
    rubrica: list[RubricCriterion]
    perfil_retroalimentacion: list[str]
    modelo: str | None = None
    programa_id: int | None = None
    curso_id: int | None = None
    programa_nombre: str | None = None
    curso_nombre: str | None = None
    activo: bool


class ProgramIn(BaseModel):
    nombre: str


class ProgramOut(BaseModel):
    id: int
    nombre: str


class CourseIn(BaseModel):
    programa_id: int
    course_id: int = Field(description="El course_id (curid) real de Moodle.")


class CourseOut(BaseModel):
    id: int
    programa_id: int
    programa_nombre: str | None = None
    course_id: int
    nombre: str


class MoodleActivityOut(BaseModel):
    cmid: int
    name: str
    modname: str | None = None
    section: str | None = None


class AssistantDraftOut(BaseModel):
    descripcion_producto: str = ""
    contexto_curso: str = ""
    ejemplo_producto: str = ""
    rubrica: list[RubricCriterion] = []
    perfil_retroalimentacion: list[str] = []
    campos_incompletos: list[str] = Field(
        default_factory=list,
        description="Campos que los documentos no permitieron completar con confianza y requieren revision manual.",
    )


class RatingIn(BaseModel):
    user_id: int
    rating: int = Field(ge=1, le=5, description="Valoracion de utilidad de 1 a 5.")
    comentario: str | None = Field(default=None, max_length=1000)


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
    cmids_relacionados: list[int] = []
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
