from pathlib import Path

import re
from html import escape, unescape
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.config import settings
from app.database import create_db_and_tables, get_session
from app.schemas import AssistantConfigIn, AssistantConfigOut, ProcessingResult
from app.services.analytics import (
    create_run,
    finish_run,
    get_latest_successful_run,
    get_recent_runs,
    get_run_detail,
    get_rubric_evaluations,
    log_event,
    now_ms,
    save_rubric_evaluations,
    start_timer,
    update_run,
)
from app.services.assistant_manager import create_assistant, get_assistant_or_404, list_assistants, upsert_assistant
from app.services.moodle import MoodleClient, MoodleDownloadError
from app.services.openai_feedback import generate_feedback, validate_submission
from app.services.pdf_extractor import extract_pdf_markdown
from app.services.similarity import text_similarity

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ValidationRejected(RuntimeError):
    pass


@app.on_event("startup")
def on_startup() -> None:
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()


@app.get("/")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "gestor": "/gestor", "docs": "/docs"}


@app.get("/ui", include_in_schema=False)
def user_interface():
    return FileResponse(static_dir / "index.html")


@app.get("/gestor", include_in_schema=False)
def gestor_interface():
    return FileResponse(static_dir / "index.html")


@app.get("/asistentes", response_model=list[AssistantConfigOut])
def get_asistentes(session: Session = Depends(get_session)):
    return list_assistants(session)


@app.get("/asistentes/{cmid}", response_model=AssistantConfigOut)
def get_asistente(cmid: int, session: Session = Depends(get_session)):
    return get_assistant_or_404(session, cmid)


@app.post("/asistentes/{cmid}", response_model=AssistantConfigOut, status_code=201)
def post_asistente(
    cmid: int,
    payload: AssistantConfigIn,
    session: Session = Depends(get_session),
):
    return create_assistant(session, cmid, payload)


@app.put("/asistentes/{cmid}", response_model=AssistantConfigOut)
def put_asistente(
    cmid: int,
    payload: AssistantConfigIn,
    session: Session = Depends(get_session),
):
    return upsert_assistant(session, cmid, payload)


@app.get("/analitica")
def get_analitica(
    limit: int = Query(50, ge=1, le=500),
    minutes: int = Query(5, ge=1, le=1440),
    session: Session = Depends(get_session),
):
    return get_recent_runs(session, limit=limit, minutes=minutes)


@app.get("/analitica/{run_id}")
def get_analitica_detalle(run_id: str, session: Session = Depends(get_session)):
    detail = get_run_detail(session, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="No se encontro la ejecucion solicitada.")
    return detail


@app.get("/procesar_producto")
async def procesar_producto(
    cmid: int = Query(...),
    user_id: int = Query(...),
    course_id: int = Query(...),
    nombre: str = Query(...),
    role: int = Query(0, ge=0, le=1),
    formato: str = Query("html", pattern="^(html|json)$"),
    force_refresh: bool = Query(False),
    session: Session = Depends(get_session),
):
    force_refresh = force_refresh or role == 1
    if formato == "html":
        return HTMLResponse(_loading_to_html(cmid, user_id, course_id, nombre, force_refresh, role))

    if not force_refresh and role == 0:
        cached_run = get_latest_successful_run(
            session,
            cmid=cmid,
            user_id=user_id,
            course_id=course_id,
        )
        if cached_run is not None:
            return _processing_result_from_cache(session, cached_run, nombre)

    total_timer = start_timer()
    run = create_run(
        session,
        cmid=cmid,
        user_id=user_id,
        course_id=course_id,
        nombre=nombre,
        source="moodle",
        request_params={
            "cmid": cmid,
            "user_id": user_id,
            "course_id": course_id,
            "nombre": nombre,
            "role": role,
            "formato": formato,
            "force_refresh": force_refresh,
        },
        role=role,
    )
    pdf_path: Path | None = None
    related_pdf_path: Path | None = None

    try:
        update_run(session, run, stage="assistant_lookup")
        assistant = get_assistant_or_404(session, cmid)
        log_event(session, run.id, "assistant_lookup", "Configuracion CMID encontrada")

        moodle_client = MoodleClient()
        update_run(session, run, stage="moodle_download", moodle_service_url=moodle_client.service_url)
        moodle_timer = start_timer()
        pdf_path = await moodle_client.download_submission_pdf(
            cmid=cmid,
            user_id=user_id,
            course_id=course_id,
            target_dir=settings.temp_dir,
        )
        moodle_ms = now_ms(moodle_timer)
        log_event(
            session,
            run.id,
            "moodle_download",
            "PDF descargado desde Moodle",
            elapsed_ms=moodle_ms,
            details={"pdf_filename": pdf_path.name},
        )
        update_run(
            session,
            run,
            moodle_ms=moodle_ms,
            pdf_filename=pdf_path.name,
            pdf_size_bytes=pdf_path.stat().st_size,
            cmid_relacionado=assistant.cmid_relacionado if assistant.usa_cmid_relacionado else None,
        )

        if assistant.usa_cmid_relacionado and not assistant.cmid_relacionado:
            raise RuntimeError("El CMID esta configurado como dependiente, pero no tiene cmid_relacionado.")

        if assistant.usa_cmid_relacionado and assistant.cmid_relacionado:
            related_timer = start_timer()
            update_run(session, run, stage="related_moodle_download")
            related_pdf_path = await moodle_client.download_submission_pdf(
                cmid=assistant.cmid_relacionado,
                user_id=user_id,
                course_id=course_id,
                target_dir=settings.temp_dir,
            )
            log_event(
                session,
                run.id,
                "related_moodle_download",
                "PDF relacionado descargado desde Moodle",
                elapsed_ms=now_ms(related_timer),
                details={"cmid_relacionado": assistant.cmid_relacionado, "pdf_filename": related_pdf_path.name},
            )
            update_run(session, run, related_pdf_filename=related_pdf_path.name)

        result = _process_pdf_path(
            session,
            run,
            pdf_path,
            assistant,
            cmid,
            user_id,
            course_id,
            nombre,
            related_pdf_path=related_pdf_path,
            total_timer=total_timer,
        )

        cleanup_ms = _cleanup_pdf(pdf_path)
        total_ms = now_ms(total_timer)
        finish_run(session, run, status="success", total_ms=total_ms, cleanup_ms=cleanup_ms)
        result.total_ms = total_ms

        if formato == "json":
            return result
        return HTMLResponse(_result_to_html(result))
    except HTTPException as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc.detail))
        if formato == "json":
            raise HTTPException(status_code=exc.status_code, detail={"run_id": run.id, "error": exc.detail}) from exc
        return HTMLResponse(_error_to_html(exc.detail, cmid, user_id, course_id, nombre, run.id), status_code=exc.status_code)
    except MoodleDownloadError as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc))
        if formato == "json":
            raise HTTPException(status_code=502, detail={"run_id": run.id, "error": str(exc)}) from exc
        return HTMLResponse(_error_to_html(str(exc), cmid, user_id, course_id, nombre, run.id), status_code=502)
    except ValidationRejected as exc:
        if formato == "json":
            raise HTTPException(status_code=422, detail={"run_id": run.id, "error": str(exc)}) from exc
        return HTMLResponse(_error_to_html(str(exc), cmid, user_id, course_id, nombre, run.id), status_code=422)
    except RuntimeError as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc))
        if formato == "json":
            raise HTTPException(status_code=500, detail={"run_id": run.id, "error": str(exc)}) from exc
        return HTMLResponse(_error_to_html(str(exc), cmid, user_id, course_id, nombre, run.id), status_code=500)
    except Exception as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc))
        if formato == "json":
            raise HTTPException(status_code=500, detail={"run_id": run.id, "error": str(exc)}) from exc
        return HTMLResponse(_error_to_html(str(exc), cmid, user_id, course_id, nombre, run.id), status_code=500)
    finally:
        _cleanup_pdf(pdf_path)
        _cleanup_pdf(related_pdf_path)


@app.post("/procesar_producto_pdf", response_model=ProcessingResult)
async def procesar_producto_pdf(
    cmid: int = Form(...),
    user_id: int = Form(...),
    course_id: int = Form(...),
    nombre: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    total_timer = start_timer()
    run = create_run(
        session,
        cmid=cmid,
        user_id=user_id,
        course_id=course_id,
        nombre=nombre,
        source="upload_debug",
        request_params={"cmid": cmid, "user_id": user_id, "course_id": course_id, "nombre": nombre},
    )
    pdf_path = settings.temp_dir / f"upload_{cmid}_{user_id}.pdf"

    try:
        assistant = get_assistant_or_404(session, cmid)
        content = await file.read()
        _validate_pdf_upload(file.filename or "", content)
        pdf_path.write_bytes(content)
        update_run(session, run, pdf_filename=file.filename, pdf_size_bytes=len(content))
        result = _process_pdf_path(session, run, pdf_path, assistant, cmid, user_id, course_id, nombre, total_timer=total_timer)
        cleanup_ms = _cleanup_pdf(pdf_path)
        total_ms = now_ms(total_timer)
        finish_run(session, run, status="success", total_ms=total_ms, cleanup_ms=cleanup_ms)
        result.total_ms = total_ms
        return result
    except HTTPException as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc.detail))
        raise HTTPException(status_code=exc.status_code, detail={"run_id": run.id, "error": exc.detail}) from exc
    except ValidationRejected as exc:
        raise HTTPException(status_code=422, detail={"run_id": run.id, "error": str(exc)}) from exc
    except RuntimeError as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc))
        raise HTTPException(status_code=500, detail={"run_id": run.id, "error": str(exc)}) from exc
    finally:
        _cleanup_pdf(pdf_path)


def _process_pdf_path(
    session: Session,
    run,
    pdf_path: Path,
    assistant,
    cmid: int,
    user_id: int,
    course_id: int,
    nombre: str,
    related_pdf_path: Path | None = None,
    total_timer: float | None = None,
) -> ProcessingResult:
    update_run(session, run, stage="pdf_extraction")
    extraction_timer = start_timer()
    include_text = assistant.analiza_texto is not False
    include_tables = assistant.analiza_tablas is not False
    include_images = assistant.analiza_imagenes is True
    extracted = extract_pdf_markdown(
        pdf_path,
        include_text=include_text,
        include_tables=include_tables,
        include_images=include_images,
    )
    extraction_ms = now_ms(extraction_timer)
    if not extracted.markdown.strip() and not extracted.image_data_urls:
        raise RuntimeError(
            "No se pudo extraer contenido del PDF. Si es escaneado, activa imagenes o OCR."
        )

    related_markdown = None
    similarity_score = None
    if related_pdf_path is not None:
        related_extracted = extract_pdf_markdown(
            related_pdf_path,
            include_text=include_text,
            include_tables=include_tables,
            include_images=False,
        )
        related_markdown = related_extracted.markdown
        similarity_score = text_similarity(extracted.markdown, related_markdown)
        update_run(
            session,
            run,
            related_caracteres_extraidos=len(related_markdown),
            similarity_score=similarity_score,
        )
        log_event(
            session,
            run.id,
            "related_pdf_extraction",
            "Entrega relacionada extraida y comparada",
            details={
                "cmid_relacionado": assistant.cmid_relacionado,
                "related_caracteres_extraidos": len(related_markdown),
                "similarity_score": similarity_score,
            },
        )

    log_event(
        session,
        run.id,
        "pdf_extraction",
        "Texto y tablas extraidos del PDF",
        elapsed_ms=extraction_ms,
        details={
            "paginas_detectadas": extracted.pages,
            "tablas_detectadas": extracted.tables,
            "imagenes_analizadas": len(extracted.image_data_urls),
            "caracteres_extraidos": len(extracted.markdown),
            "modo": {
                "texto": include_text,
                "tablas": include_tables,
                "imagenes": include_images,
            },
        },
    )
    update_run(
        session,
        run,
        extraction_ms=extraction_ms,
        paginas_detectadas=extracted.pages,
        tablas_detectadas=extracted.tables,
        imagenes_analizadas=len(extracted.image_data_urls),
        caracteres_extraidos=len(extracted.markdown),
        extra={
            **(run.extra or {}),
            "modo_analisis": {
                "texto": include_text,
                "tablas": include_tables,
                "imagenes": include_images,
            },
        },
    )

    _validate_before_feedback(
        session=session,
        run=run,
        assistant=assistant,
        extracted_markdown=extracted.markdown,
        related_markdown=related_markdown,
        similarity_score=similarity_score,
        total_timer=total_timer,
    )

    update_run(session, run, stage="openai_feedback", modelo=assistant.modelo or settings.azure_openai_deployment)
    gpt_timer = start_timer()
    feedback = generate_feedback(
        assistant=assistant,
        extracted_markdown=extracted.markdown,
        student_name=nombre,
        user_id=user_id,
        course_id=course_id,
        image_data_urls=extracted.image_data_urls,
        related_markdown=related_markdown,
        similarity_score=similarity_score,
    )
    gpt_ms = now_ms(gpt_timer)

    log_event(
        session,
        run.id,
        "openai_feedback",
        "Retroalimentacion generada por Azure OpenAI",
        elapsed_ms=gpt_ms,
        details={
            "modelo": feedback.model,
            "total_tokens": feedback.total_tokens,
            "rubric_items": len(feedback.evaluacion_rubrica),
            "imagenes_analizadas": len(extracted.image_data_urls),
        },
    )
    update_run(
        session,
        run,
        gpt_ms=gpt_ms,
        modelo=feedback.model,
        prompt_tokens=feedback.prompt_tokens,
        completion_tokens=feedback.completion_tokens,
        total_tokens=feedback.total_tokens,
        retroalimentacion=feedback.retroalimentacion,
    )
    save_rubric_evaluations(session, run.id, feedback.evaluacion_rubrica, assistant.rubrica)

    return ProcessingResult(
        run_id=run.id,
        cmid=cmid,
        user_id=user_id,
        course_id=course_id,
        nombre=nombre,
        role=run.role,
        paginas_detectadas=extracted.pages,
        tablas_detectadas=extracted.tables,
        imagenes_analizadas=len(extracted.image_data_urls),
        caracteres_extraidos=len(extracted.markdown),
        cmid_relacionado=assistant.cmid_relacionado if assistant.usa_cmid_relacionado else None,
        similarity_score=similarity_score,
        validation_passed=True,
        validation_reason=run.validation_reason,
        relevance_score=run.relevance_score,
        moodle_ms=run.moodle_ms,
        extraction_ms=extraction_ms,
        gpt_ms=gpt_ms,
        modelo=feedback.model,
        total_tokens=feedback.total_tokens,
        retroalimentacion=feedback.retroalimentacion,
        evaluacion_rubrica=feedback.evaluacion_rubrica,
    )


def _validate_pdf_upload(filename: str, content: bytes) -> None:
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extension .pdf.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no parece ser un PDF valido.")
    max_bytes = settings.max_pdf_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"El PDF supera {settings.max_pdf_mb} MB.")


def _validate_before_feedback(
    *,
    session: Session,
    run,
    assistant,
    extracted_markdown: str,
    related_markdown: str | None,
    similarity_score: float | None,
    total_timer: float | None = None,
) -> None:
    update_run(session, run, stage="validation")

    if len(extracted_markdown.strip()) < settings.min_extracted_chars:
        _reject_validation(
            session,
            run,
            "El documento no contiene suficiente informacion legible para validar el producto. No se dara retroalimentacion.",
            total_timer,
            relevance_score=0,
            similarity_score=similarity_score,
        )

    if (
        assistant.usa_cmid_relacionado
        and assistant.validar_similitud
        and similarity_score is not None
        and similarity_score >= settings.similarity_threshold
    ):
        _reject_validation(
            session,
            run,
            (
                "La entrega actual es demasiado similar a la entrega relacionada. "
                "No se dara retroalimentacion porque parece una repeticion de una subida anterior."
            ),
            total_timer,
            relevance_score=None,
            similarity_score=similarity_score,
        )

    if assistant.validar_documento is False:
        update_run(
            session,
            run,
            validation_passed=True,
            validation_reason="Validacion documental desactivada en la configuracion del CMID.",
            similarity_score=similarity_score,
        )
        return

    validation = validate_submission(
        assistant,
        extracted_markdown,
        related_markdown=related_markdown,
        similarity_score=similarity_score,
    )
    update_run(
        session,
        run,
        validation_passed=validation.is_valid,
        validation_reason=validation.reason,
        relevance_score=validation.relevance_score,
        similarity_score=validation.similarity_score or similarity_score,
        extra={
            **(run.extra or {}),
            "validation": {
                "model": validation.model,
                "total_tokens": validation.total_tokens,
            },
        },
    )
    log_event(
        session,
        run.id,
        "validation",
        "Validacion previa completada",
        details={
            "is_valid": validation.is_valid,
            "reason": validation.reason,
            "relevance_score": validation.relevance_score,
            "similarity_score": validation.similarity_score or similarity_score,
        },
    )
    if not validation.is_valid:
        _reject_validation(
            session,
            run,
            f"No se dara retroalimentacion: {validation.reason}",
            total_timer,
            relevance_score=validation.relevance_score,
            similarity_score=validation.similarity_score or similarity_score,
        )


def _reject_validation(
    session: Session,
    run,
    reason: str,
    total_timer: float | None,
    *,
    relevance_score: float | None,
    similarity_score: float | None,
) -> None:
    total_ms = now_ms(total_timer) if total_timer is not None else 0
    log_event(
        session,
        run.id,
        "validation",
        reason,
        level="warning",
        elapsed_ms=total_ms,
        details={"relevance_score": relevance_score, "similarity_score": similarity_score},
    )
    finish_run(
        session,
        run,
        status="validation_failed",
        total_ms=total_ms,
        validation_passed=False,
        validation_reason=reason,
        relevance_score=relevance_score,
        similarity_score=similarity_score,
    )
    raise ValidationRejected(reason)


def _record_failure(session: Session, run, total_timer: float, error_type: str, error_message: str) -> None:
    total_ms = now_ms(total_timer)
    log_event(
        session,
        run.id,
        run.stage or "error",
        error_message,
        level="error",
        elapsed_ms=total_ms,
        details={"error_type": error_type},
    )
    finish_run(
        session,
        run,
        status="failed",
        total_ms=total_ms,
        error_type=error_type,
        error_message=error_message,
    )


def _cleanup_pdf(pdf_path: Path | None) -> int:
    cleanup_timer = start_timer()
    if pdf_path and pdf_path.exists():
        pdf_path.unlink()
    return now_ms(cleanup_timer)


def _processing_result_from_cache(session: Session, run, nombre: str) -> ProcessingResult:
    evaluations = [
        {
            "criterion_index": item.criterion_index,
            "dimension": item.dimension,
            "descripcion_dimension": item.descripcion_dimension,
            "criterio": item.criterio,
            "descripcion_criterio": item.descripcion_criterio,
            "nivel_obtenido": item.nivel_obtenido,
            "score": item.score,
            "evidencia": item.evidencia,
            "comentario": item.comentario,
            "recomendacion": item.recomendacion,
        }
        for item in get_rubric_evaluations(session, run.id)
    ]
    return ProcessingResult(
        run_id=run.id,
        desde_cache=True,
        cmid=run.cmid,
        user_id=run.user_id,
        course_id=run.course_id,
        nombre=run.nombre or nombre,
        role=run.role,
        paginas_detectadas=run.paginas_detectadas or 0,
        tablas_detectadas=run.tablas_detectadas or 0,
        imagenes_analizadas=run.imagenes_analizadas or 0,
        caracteres_extraidos=run.caracteres_extraidos or 0,
        cmid_relacionado=run.cmid_relacionado,
        similarity_score=run.similarity_score,
        validation_passed=run.validation_passed,
        validation_reason=run.validation_reason,
        relevance_score=run.relevance_score,
        total_ms=run.total_ms,
        moodle_ms=run.moodle_ms,
        extraction_ms=run.extraction_ms,
        gpt_ms=run.gpt_ms,
        modelo=run.modelo,
        total_tokens=run.total_tokens,
        retroalimentacion=run.retroalimentacion or "",
        evaluacion_rubrica=evaluations,
    )


def _loading_to_html(
    cmid: int,
    user_id: int,
    course_id: int,
    nombre: str,
    force_refresh: bool = False,
    role: int = 0,
) -> str:
    api_url = "/procesar_producto?" + urlencode(
        {
            "cmid": cmid,
            "user_id": user_id,
            "course_id": course_id,
            "nombre": nombre,
            "role": role,
            "formato": "json",
            "force_refresh": str(force_refresh).lower(),
        }
    )
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Procesando producto</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar user-topbar">
      <div>
        <h1>Procesando producto</h1>
        <p>CMID {cmid} &middot; Usuario {user_id} &middot; Curso {course_id} &middot; Rol {role}</p>
      </div>
    </header>
    <main class="single-page">
      <section id="loading-panel" class="panel loading-panel user-result-panel">
        <div class="spinner" aria-hidden="true"></div>
        <h2>Estamos generando tu retroalimentacion</h2>
        <p class="meta-line">Espera unos minutos, ya casi terminamos</p>
      </section>
      <section id="result-panel" class="panel user-result-panel hidden"></section>
    </main>
    <script>
      const apiUrl = {api_url!r};
      const loadingPanel = document.querySelector("#loading-panel");
      const resultPanel = document.querySelector("#result-panel");

      function escapeHtml(value) {{
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }}

      function cleanDisplayText(value) {{
        return String(value ?? "")
          .replaceAll("\\\\r\\\\n", "\\n")
          .replaceAll("\\\\n", "\\n")
          .replaceAll("\\\\t", " ")
          .replace(/<\\s*br\\s*\\/?\\s*>/gi, "\\n")
          .replace(/<\\s*\\/\\s*(p|div|li|h[1-6])\\s*>/gi, "\\n")
          .replace(/<\\s*li\\s*>/gi, "- ")
          .replace(/<[^>]+>/g, "")
          .replace(/[ \\t]+/g, " ")
          .replace(/\\b(Aciertos|Aspectos por mejorar|Recomendaciones|Preguntas reflexivas|Cierre):/gi, "\\n\\n$1:\\n")
          .replace(/\\n{{3,}}/g, "\\n\\n")
          .trim();
      }}

      function feedbackToHtml(value) {{
        const text = cleanDisplayText(value);
        if (!text) return '<p>No se recibio retroalimentacion textual.</p>';
        const headings = /^(Aciertos|Aspectos por mejorar|Recomendaciones|Preguntas reflexivas|Cierre):$/i;
        const lines = text.split("\\n").map((line) => line.trim()).filter(Boolean);
        const html = [];
        let paragraph = [];
        let list = [];

        function flushParagraph() {{
          if (paragraph.length) {{
            html.push(`<p>${{escapeHtml(paragraph.join(" "))}}</p>`);
            paragraph = [];
          }}
        }}

        function flushList() {{
          if (list.length) {{
            html.push(`<ul>${{list.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>`);
            list = [];
          }}
        }}

        for (const rawLine of lines) {{
          const line = rawLine.replace(/^\\*\\*(.+)\\*\\*$/, "$1").trim();
          if (headings.test(line)) {{
            flushParagraph();
            flushList();
            html.push(`<h3 class="feedback-heading">${{escapeHtml(line)}}</h3>`);
            continue;
          }}

          if (/^([-*•]|\\d+[.)])\\s+/.test(line)) {{
            flushParagraph();
            list.push(line.replace(/^([-*•]|\\d+[.)])\\s+/, ""));
            continue;
          }}

          flushList();
          paragraph.push(line);
        }}

        flushParagraph();
        flushList();
        return html.join("");
      }}

      function renderResult(data) {{
        const cacheLine = data.desde_cache ? '<p class="cache-note">Retroalimentacion recuperada de una ejecucion anterior</p>' : "";
        const rows = (data.evaluacion_rubrica || []).map((item) => `
          <tr>
            <td>${{escapeHtml(item.criterion_index)}}</td>
            <td>${{escapeHtml(item.dimension)}}</td>
            <td>${{escapeHtml(item.criterio)}}</td>
            <td>${{escapeHtml(item.nivel_obtenido || "")}}</td>
            <td>${{escapeHtml(item.comentario || "")}}</td>
          </tr>
        `).join("");

        resultPanel.innerHTML = `
          <h2>{escape(nombre)}</h2>
          <!-- <p class="meta-line">ID de ejecucion: ${{escapeHtml(data.run_id)}}</p> -->
          ${{cacheLine}}
          <!--<p class="meta-line">Rol: ${{data.role === 1 ? "Validador" : "Usuario"}} &middot; Validacion: ${{data.validation_passed === false ? "rechazada" : "aprobada"}} ${{data.similarity_score != null ? "&middot; Similitud: " + escapeHtml(data.similarity_score) : ""}}</p>-->
          <p class="meta-line">Paginas: ${{escapeHtml(data.paginas_detectadas)}} &middot; Tablas: ${{escapeHtml(data.tablas_detectadas)}} &middot; Imagenes: ${{escapeHtml(data.imagenes_analizadas || 0)}} &middot; Tiempo: ${{escapeHtml(data.total_ms || "-")}} ms</p>
          <div class="feedback-output">${{feedbackToHtml(data.retroalimentacion)}}</div>
          <!--${{rows ? `
            <h3>Evaluacion por criterio</h3>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Dimension</th>
                    <th>Criterio</th>
                    <th>Nivel</th>
                    <th>Comentario</th>
                  </tr>
                </thead>
                <tbody>${{rows}}</tbody>
              </table>
            </div>
          ` : ""}} -->
        `;
      }}

      function renderError(message, runId) {{
        resultPanel.innerHTML = `
          <h2>{escape(nombre)}</h2>
          ${{runId ? `<p class="meta-line">ID de ejecucion: ${{escapeHtml(runId)}}</p>` : ""}}
          <p class="error-text">${{escapeHtml(message)}}</p>
        `;
      }}

      async function processProduct() {{
        try {{
          const response = await fetch(apiUrl);
          const data = await response.json();
          if (!response.ok) {{
            const detail = data.detail || {{}};
            renderError(detail.error || detail || `Error HTTP ${{response.status}}`, detail.run_id);
          }} else {{
            renderResult(data);
          }}
        }} catch (error) {{
          renderError(error.message);
        }} finally {{
          loadingPanel.classList.add("hidden");
          resultPanel.classList.remove("hidden");
        }}
      }}

      processProduct();
    </script>
  </body>
</html>"""


def _result_to_html(result: ProcessingResult) -> str:
    feedback = _feedback_to_html(result.retroalimentacion)
    cache_line = (
        '<p class="cache-note">Retroalimentacion recuperada de una ejecucion anterior</p>'
        if result.desde_cache
        else ""
    )
    rubric_rows = "\n".join(
        f"""<tr>
          <td>{item.criterion_index}</td>
          <td>{escape(item.dimension)}</td>
          <td>{escape(item.criterio)}</td>
          <td>{escape(item.nivel_obtenido or "")}</td>
          <td>{escape(item.comentario or "")}</td>
        </tr>"""
        for item in result.evaluacion_rubrica
    )
    rubric_table = (
        f"""<h3>Evaluacion por criterio</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Dimension</th>
                <th>Criterio</th>
                <th>Nivel</th>
                <th>Comentario</th>
              </tr>
            </thead>
            <tbody>{rubric_rows}</tbody>
          </table>
        </div>"""
        if rubric_rows
        else ""
    )
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Retroalimentacion del producto</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar user-topbar">
      <div>
        <h1>Retroalimentacion del producto</h1>
        <p>CMID {result.cmid} &middot; Usuario {result.user_id} &middot; Curso {result.course_id}</p>
      </div>
      <a class="docs-link" href="/gestor">Gestor</a>
    </header>
    <main class="single-page">
      <section class="panel user-result-panel">
        <h2>{escape(result.nombre)}</h2>
        <p class="meta-line">ID de ejecucion: {result.run_id}</p>
        {cache_line}
        <p class="meta-line">Rol: {"Validador" if result.role == 1 else "Usuario"} &middot; Validacion: {"rechazada" if result.validation_passed is False else "aprobada"}{f" &middot; Similitud: {result.similarity_score}" if result.similarity_score is not None else ""}</p>
        <p class="meta-line">Tiempo total: {result.total_ms or 0} ms</p>
        <p class="meta-line">Imagenes analizadas: {result.imagenes_analizadas}</p>
        <p class="meta-line">Paginas detectadas: {result.paginas_detectadas} &middot; Tablas detectadas: {result.tablas_detectadas}</p>
        <div class="feedback-output">{feedback}</div>
        {rubric_table}
      </section>
    </main>
  </body>
</html>"""


def _error_to_html(
    detail: object,
    cmid: int,
    user_id: int,
    course_id: int,
    nombre: str,
    run_id: str | None = None,
) -> str:
    run_line = f'<p class="meta-line">ID de ejecucion: {escape(run_id)}</p>' if run_id else ""
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>No se pudo procesar el producto</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar user-topbar">
      <div>
        <h1>No se pudo procesar el producto</h1>
        <p>CMID {cmid} &middot; Usuario {user_id} &middot; Curso {course_id}</p>
      </div>
      <a class="docs-link" href="/gestor">Gestor</a>
    </header>
    <main class="single-page">
      <section class="panel user-result-panel">
        <h2>{escape(nombre)}</h2>
        {run_line}
        <p class="error-text">{escape(str(detail))}</p>
      </section>
    </main>
  </body>
</html>"""


def _feedback_to_html(value: str) -> str:
    text = _clean_display_text(value)
    if not text:
        return "<p>No se recibio retroalimentacion textual.</p>"

    chunks: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            chunks.append(f"<p>{escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_items() -> None:
        if items:
            rendered_items = "".join(f"<li>{escape(item)}</li>" for item in items)
            chunks.append(f"<ul>{rendered_items}</ul>")
            items.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_items()
            continue

        line = re.sub(r"^\*\*(.+)\*\*$", r"\1", line).strip()
        if _is_feedback_heading(line):
            flush_paragraph()
            flush_items()
            chunks.append(f'<h3 class="feedback-heading">{escape(line)}</h3>')
            continue

        if re.match(r"^([-*•]|\d+[.)])\s+", line):
            flush_paragraph()
            items.append(re.sub(r"^([-*•]|\d+[.)])\s+", "", line))
            continue

        flush_items()
        paragraph.append(line)

    flush_paragraph()
    flush_items()
    return "\n".join(chunks)


def _clean_display_text(value: str) -> str:
    text = unescape(str(value or ""))
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li\s*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(
        r"(?i)\b(Aciertos|Aspectos por mejorar|Recomendaciones|Preguntas reflexivas|Cierre):",
        r"\n\n\1:\n",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_feedback_heading(value: str) -> bool:
    return bool(
        re.match(
            r"(?i)^(Aciertos|Aspectos por mejorar|Recomendaciones|Preguntas reflexivas|Cierre):$",
            value.strip(),
        )
    )
