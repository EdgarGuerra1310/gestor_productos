from pathlib import Path

from html import escape
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
from app.services.openai_feedback import generate_feedback
from app.services.pdf_extractor import extract_pdf_markdown

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


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
def get_analitica(limit: int = Query(50, ge=1, le=500), session: Session = Depends(get_session)):
    return get_recent_runs(session, limit=limit)


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
    formato: str = Query("html", pattern="^(html|json)$"),
    force_refresh: bool = Query(False),
    session: Session = Depends(get_session),
):
    if formato == "html":
        return HTMLResponse(_loading_to_html(cmid, user_id, course_id, nombre, force_refresh))

    if not force_refresh:
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
            "formato": formato,
            "force_refresh": force_refresh,
        },
    )
    pdf_path: Path | None = None

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
        )

        result = _process_pdf_path(session, run, pdf_path, assistant, cmid, user_id, course_id, nombre)

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
        result = _process_pdf_path(session, run, pdf_path, assistant, cmid, user_id, course_id, nombre)
        cleanup_ms = _cleanup_pdf(pdf_path)
        total_ms = now_ms(total_timer)
        finish_run(session, run, status="success", total_ms=total_ms, cleanup_ms=cleanup_ms)
        result.total_ms = total_ms
        return result
    except RuntimeError as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc))
        raise HTTPException(status_code=500, detail={"run_id": run.id, "error": str(exc)}) from exc
    except HTTPException as exc:
        _record_failure(session, run, total_timer, exc.__class__.__name__, str(exc.detail))
        raise HTTPException(status_code=exc.status_code, detail={"run_id": run.id, "error": exc.detail}) from exc
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

    update_run(session, run, stage="openai_feedback", modelo=assistant.modelo or settings.azure_openai_deployment)
    gpt_timer = start_timer()
    feedback = generate_feedback(
        assistant=assistant,
        extracted_markdown=extracted.markdown,
        student_name=nombre,
        user_id=user_id,
        course_id=course_id,
        image_data_urls=extracted.image_data_urls,
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
        paginas_detectadas=extracted.pages,
        tablas_detectadas=extracted.tables,
        imagenes_analizadas=len(extracted.image_data_urls),
        caracteres_extraidos=len(extracted.markdown),
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
        paginas_detectadas=run.paginas_detectadas or 0,
        tablas_detectadas=run.tablas_detectadas or 0,
        imagenes_analizadas=run.imagenes_analizadas or 0,
        caracteres_extraidos=run.caracteres_extraidos or 0,
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
) -> str:
    api_url = "/procesar_producto?" + urlencode(
        {
            "cmid": cmid,
            "user_id": user_id,
            "course_id": course_id,
            "nombre": nombre,
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
        <p>CMID {cmid} · Usuario {user_id} · Curso {course_id}</p>
      </div>
    </header>
    <main class="single-page">
      <section id="loading-panel" class="panel loading-panel user-result-panel">
        <div class="spinner" aria-hidden="true"></div>
        <h2>Estamos generando tu retroalimentacion</h2>
        <p class="meta-line">Descargando el PDF de Moodle, leyendo el contenido y aplicando la rubrica configurada.</p>
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
          <p class="meta-line">ID de ejecucion: ${{escapeHtml(data.run_id)}}</p>
          ${{cacheLine}}
          <p class="meta-line">Paginas: ${{escapeHtml(data.paginas_detectadas)}} · Tablas: ${{escapeHtml(data.tablas_detectadas)}} · Imagenes: ${{escapeHtml(data.imagenes_analizadas || 0)}} · Tiempo: ${{escapeHtml(data.total_ms || "-")}} ms</p>
          <pre class="feedback-output">${{escapeHtml(data.retroalimentacion)}}</pre>
          ${{rows ? `
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
          ` : ""}}
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
    feedback = escape(result.retroalimentacion)
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
        <p>CMID {result.cmid} · Usuario {result.user_id} · Curso {result.course_id}</p>
      </div>
      <a class="docs-link" href="/gestor">Gestor</a>
    </header>
    <main class="single-page">
      <section class="panel user-result-panel">
        <h2>{escape(result.nombre)}</h2>
        <p class="meta-line">ID de ejecucion: {result.run_id}</p>
        {cache_line}
        <p class="meta-line">Tiempo total: {result.total_ms or 0} ms</p>
        <p class="meta-line">Imagenes analizadas: {result.imagenes_analizadas}</p>
        <p class="meta-line">Paginas detectadas: {result.paginas_detectadas} · Tablas detectadas: {result.tablas_detectadas}</p>
        <pre class="feedback-output">{feedback}</pre>
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
        <p>CMID {cmid} · Usuario {user_id} · Curso {course_id}</p>
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
