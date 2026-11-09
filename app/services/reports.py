import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean

from sqlmodel import Session, select

from app.models import (
    AssistantCmid,
    AssistantConfig,
    Course,
    FeedbackRating,
    ProcessingEvent,
    ProcessingRun,
    ProcessingView,
    Program,
    RubricEvaluation,
    RunSentiment,
)
from app.services.openai_feedback import analyze_sentiments

LIMA = timezone(timedelta(hours=-5))
LEVELS = ("inicio", "en_proceso", "logrado", "destacado")
LEVEL_SCORE = {"inicio": 1.0, "en_proceso": 2.0, "logrado": 3.0, "destacado": 4.0}
WEEKDAYS = ("Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom")
SENTIMENT_BATCH_SIZE = 4


@dataclass
class ReportFilters:
    desde: date | None = None
    hasta: date | None = None
    assistant_id: int | None = None
    programa_id: int | None = None
    curso_id: int | None = None
    cmid: int | None = None
    rol: int | None = None
    estado: str | None = None


def _avg(values, digits: int = 2) -> float | None:
    values = [v for v in values if v is not None]
    return round(mean(values), digits) if values else None


def _to_lima(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LIMA)


def _utc_start_of_lima_day(day: date) -> datetime:
    return datetime(day.year, day.month, day.day) + timedelta(hours=5)


def _normalize_level(value: str | None) -> str:
    level = (value or "").strip().lower().replace(" ", "_")
    return level if level in LEVELS else "sin_nivel"


def _assistant_index(session: Session) -> dict[int, dict]:
    """cmid -> datos del asistente, programa y curso al que pertenece."""
    programs = {p.id: p.nombre for p in session.exec(select(Program)).all()}
    courses = {c.id: c.nombre for c in session.exec(select(Course)).all()}
    assistants = {a.id: a for a in session.exec(select(AssistantConfig)).all()}
    name_counts = Counter(a.nombre for a in assistants.values())
    index: dict[int, dict] = {}
    for link in session.exec(select(AssistantCmid)).all():
        assistant = assistants.get(link.assistant_id)
        if assistant is None:
            continue
        index[link.cmid] = {
            "assistant_id": assistant.id,
            "asistente": assistant.nombre if name_counts[assistant.nombre] == 1 else f"{assistant.nombre} (ID {assistant.id})",
            "programa_id": assistant.programa_id,
            "programa": programs.get(assistant.programa_id),
            "curso_id": assistant.curso_id,
            "curso": courses.get(assistant.curso_id),
        }
    return index


def _load_runs(session: Session, filters: ReportFilters) -> list[dict]:
    index = _assistant_index(session)

    statement = select(ProcessingRun).where(ProcessingRun.source == "moodle")
    if filters.desde:
        statement = statement.where(ProcessingRun.started_at >= _utc_start_of_lima_day(filters.desde))
    if filters.hasta:
        statement = statement.where(ProcessingRun.started_at < _utc_start_of_lima_day(filters.hasta + timedelta(days=1)))
    if filters.rol is not None:
        statement = statement.where(ProcessingRun.role == filters.rol)
    if filters.estado:
        statement = statement.where(ProcessingRun.status == filters.estado)
    if filters.cmid:
        statement = statement.where(ProcessingRun.cmid == filters.cmid)
    statement = statement.order_by(ProcessingRun.started_at.desc())

    runs: list[dict] = []
    for run in session.exec(statement).all():
        info = index.get(run.cmid) or {}
        if filters.assistant_id and info.get("assistant_id") != filters.assistant_id:
            continue
        if filters.programa_id and info.get("programa_id") != filters.programa_id:
            continue
        if filters.curso_id and info.get("curso_id") != filters.curso_id:
            continue
        runs.append(
            {
                "run": run,
                "assistant_id": info.get("assistant_id"),
                "asistente": info.get("asistente") or f"Sin asistente (CMID {run.cmid})",
                "programa": info.get("programa") or "Sin programa",
                "curso": info.get("curso") or "Sin curso",
                "started_lima": _to_lima(run.started_at),
            }
        )
    return runs


def _load_evaluations(session: Session, run_ids: list[str]) -> dict[str, list[RubricEvaluation]]:
    by_run: dict[str, list[RubricEvaluation]] = defaultdict(list)
    for start in range(0, len(run_ids), 500):
        chunk = run_ids[start : start + 500]
        for evaluation in session.exec(select(RubricEvaluation).where(RubricEvaluation.run_id.in_(chunk))).all():
            by_run[evaluation.run_id].append(evaluation)
    return by_run


def _load_sentiments(session: Session, run_ids: list[str]) -> dict[str, RunSentiment]:
    result: dict[str, RunSentiment] = {}
    for start in range(0, len(run_ids), 500):
        chunk = run_ids[start : start + 500]
        for item in session.exec(select(RunSentiment).where(RunSentiment.run_id.in_(chunk))).all():
            result[item.run_id] = item
    return result


def _load_ratings(session: Session, run_ids: list[str]) -> dict[str, FeedbackRating]:
    result: dict[str, FeedbackRating] = {}
    for start in range(0, len(run_ids), 500):
        chunk = run_ids[start : start + 500]
        for item in session.exec(select(FeedbackRating).where(FeedbackRating.run_id.in_(chunk))).all():
            result[item.run_id] = item
    return result


def _needs_analysis(sentiment: RunSentiment | None) -> bool:
    return sentiment is None or sentiment.coherencia is None


def _evaluation_score(evaluation: RubricEvaluation) -> float | None:
    if evaluation.score is not None:
        return float(evaluation.score)
    return LEVEL_SCORE.get(_normalize_level(evaluation.nivel_obtenido))


def _run_score(evaluations: list[RubricEvaluation]) -> float | None:
    return _avg([_evaluation_score(e) for e in evaluations])


def _predominant_level(evaluations: list[RubricEvaluation]) -> str | None:
    counter = Counter(_normalize_level(e.nivel_obtenido) for e in evaluations)
    counter.pop("sin_nivel", None)
    return counter.most_common(1)[0][0] if counter else None


def _load_views(session: Session, filters: ReportFilters, cmids: set[int] | None) -> list[ProcessingView]:
    statement = select(ProcessingView)
    if filters.desde:
        statement = statement.where(ProcessingView.viewed_at >= _utc_start_of_lima_day(filters.desde))
    if filters.hasta:
        statement = statement.where(ProcessingView.viewed_at < _utc_start_of_lima_day(filters.hasta + timedelta(days=1)))
    if filters.cmid:
        statement = statement.where(ProcessingView.cmid == filters.cmid)
    views = list(session.exec(statement).all())
    if cmids is not None:
        views = [v for v in views if v.cmid in cmids]
    return views


def _bucket_key(day: date, monthly: bool) -> str:
    return day.strftime("%Y-%m") if monthly else day.isoformat()


def _timeline_keys(first: date, last: date, monthly: bool) -> list[str]:
    keys: list[str] = []
    if monthly:
        year, month = first.year, first.month
        while (year, month) <= (last.year, last.month):
            keys.append(f"{year:04d}-{month:02d}")
            month += 1
            if month > 12:
                year, month = year + 1, 1
    else:
        day = first
        while day <= last:
            keys.append(day.isoformat())
            day += timedelta(days=1)
    return keys


def build_summary(session: Session, filters: ReportFilters) -> dict:
    runs = _load_runs(session, filters)
    run_ids = [item["run"].id for item in runs]
    evaluations = _load_evaluations(session, run_ids)
    sentiments = _load_sentiments(session, run_ids)
    ratings = _load_ratings(session, run_ids)

    cmids_in_scope = {item["run"].cmid for item in runs}
    restrict_views = bool(filters.assistant_id or filters.programa_id or filters.curso_id)
    views = _load_views(session, filters, cmids_in_scope if restrict_views else None)

    success = [r for r in runs if r["run"].status == "success"]
    status_counter = Counter(r["run"].status for r in runs)
    user_counter = Counter(r["run"].user_id for r in runs)

    run_scores = {r["run"].id: _run_score(evaluations.get(r["run"].id, [])) for r in success}
    level_counter: Counter = Counter()
    for r in success:
        for evaluation in evaluations.get(r["run"].id, []):
            level_counter[_normalize_level(evaluation.nivel_obtenido)] += 1

    analyzed = [sentiments[r["run"].id] for r in success if r["run"].id in sentiments]

    kpis = {
        "ejecuciones": len(runs),
        "exitosas": status_counter.get("success", 0),
        "fallidas": status_counter.get("failed", 0),
        "rechazadas": status_counter.get("validation_failed", 0),
        "en_curso": len(runs) - sum(status_counter.get(s, 0) for s in ("success", "failed", "validation_failed")),
        "tasa_exito": round(status_counter.get("success", 0) / len(runs), 4) if runs else None,
        "usuarios_unicos": len(user_counter),
        "usuarios_recurrentes": sum(1 for count in user_counter.values() if count > 1),
        "consultas_guardadas": len(views),
        "tiempo_prom_ms": _avg([r["run"].total_ms for r in success], 0),
        "moodle_prom_ms": _avg([r["run"].moodle_ms for r in success], 0),
        "gpt_prom_ms": _avg([r["run"].gpt_ms for r in success], 0),
        "tokens_total": sum(r["run"].total_tokens or 0 for r in success),
        "tokens_prom": _avg([r["run"].total_tokens for r in success], 0),
        "puntaje_promedio": _avg(list(run_scores.values())),
        "similitud_promedio": _avg([r["run"].similarity_score for r in runs if r["run"].similarity_score is not None]),
        "sentimiento_promedio": _avg([s.puntaje for s in analyzed]),
        "sentimiento_analizadas": len(analyzed),
        "sentimiento_pendientes": sum(
            1
            for r in success
            if _needs_analysis(sentiments.get(r["run"].id)) and (r["run"].retroalimentacion or "").strip()
        ),
        "valoraciones": len(ratings),
        "valoracion_promedio": _avg([rating.rating for rating in ratings.values()]),
        "tasa_valoracion": (
            round(len(ratings) / len([r for r in success if r["run"].role == 0]), 4)
            if [r for r in success if r["run"].role == 0]
            else None
        ),
    }

    # --- linea de tiempo -------------------------------------------------
    dated = [r["started_lima"].date() for r in runs] + [_to_lima(v.viewed_at).date() for v in views]
    timeline: list[dict] = []
    granularity = "dia"
    if dated:
        first = filters.desde or min(dated)
        last = filters.hasta or max(dated)
        if last < first:
            last = first
        monthly = (last - first).days > 92
        granularity = "mes" if monthly else "dia"
        buckets = {
            key: {"fecha": key, "ejecuciones": 0, "exitosas": 0, "fallidas": 0, "consultas": 0, "_sent": []}
            for key in _timeline_keys(first, last, monthly)
        }
        for r in runs:
            bucket = buckets.get(_bucket_key(r["started_lima"].date(), monthly))
            if bucket is None:
                continue
            bucket["ejecuciones"] += 1
            if r["run"].status == "success":
                bucket["exitosas"] += 1
                if r["run"].id in sentiments:
                    bucket["_sent"].append(sentiments[r["run"].id].puntaje)
            elif r["run"].status in ("failed", "validation_failed"):
                bucket["fallidas"] += 1
        for view in views:
            bucket = buckets.get(_bucket_key(_to_lima(view.viewed_at).date(), monthly))
            if bucket is not None:
                bucket["consultas"] += 1
        for bucket in buckets.values():
            bucket["sentimiento"] = _avg(bucket.pop("_sent"))
            timeline.append(bucket)

    by_hour = [0] * 24
    by_weekday = [0] * 7
    for r in runs:
        by_hour[r["started_lima"].hour] += 1
        by_weekday[r["started_lima"].weekday()] += 1

    # --- agrupaciones ----------------------------------------------------
    def group_runs(key_name: str) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in runs:
            groups[r[key_name]].append(r)
        rows = []
        for name, items in groups.items():
            ok = [i for i in items if i["run"].status == "success"]
            scores = [run_scores.get(i["run"].id) for i in ok]
            sent = [sentiments[i["run"].id].puntaje for i in ok if i["run"].id in sentiments]
            rows.append(
                {
                    "nombre": name,
                    "ejecuciones": len(items),
                    "exitosas": len(ok),
                    "fallidas": sum(1 for i in items if i["run"].status in ("failed", "validation_failed")),
                    "usuarios": len({i["run"].user_id for i in items}),
                    "puntaje_prom": _avg(scores),
                    "tiempo_prom_ms": _avg([i["run"].total_ms for i in ok], 0),
                    "sentimiento_prom": _avg(sent),
                }
            )
        return sorted(rows, key=lambda row: row["ejecuciones"], reverse=True)

    # --- desempeno por criterio -----------------------------------------
    criteria: dict[tuple, dict] = {}
    dimensions: dict[str, list[float]] = defaultdict(list)
    for r in success:
        for evaluation in evaluations.get(r["run"].id, []):
            key = (r["asistente"], evaluation.dimension, evaluation.criterio)
            entry = criteria.setdefault(
                key,
                {
                    "asistente": r["asistente"],
                    "dimension": evaluation.dimension,
                    "criterio": evaluation.criterio,
                    "evaluaciones": 0,
                    "_scores": [],
                    "niveles": {level: 0 for level in LEVELS},
                },
            )
            entry["evaluaciones"] += 1
            score = _evaluation_score(evaluation)
            if score is not None:
                entry["_scores"].append(score)
                dimensions[evaluation.dimension].append(score)
            level = _normalize_level(evaluation.nivel_obtenido)
            if level in entry["niveles"]:
                entry["niveles"][level] += 1
    criteria_rows = []
    for entry in criteria.values():
        entry["puntaje_prom"] = _avg(entry.pop("_scores"))
        total_levels = sum(entry["niveles"].values())
        low = entry["niveles"]["inicio"] + entry["niveles"]["en_proceso"]
        entry["pct_bajo"] = round(low / total_levels, 4) if total_levels else None
        criteria_rows.append(entry)
    criteria_rows.sort(key=lambda row: (row["puntaje_prom"] is None, row["puntaje_prom"] or 0))

    # --- errores ----------------------------------------------------------
    error_counter: Counter = Counter()
    for r in runs:
        run = r["run"]
        if run.status == "failed" and run.error_message:
            error_counter[("Error", run.error_message[:140])] += 1
        elif run.status == "validation_failed":
            reason = run.validation_reason or run.error_message or "Documento rechazado en la validacion"
            error_counter[("Validacion", reason[:140])] += 1

    # --- sentimiento ------------------------------------------------------
    strengths: Counter = Counter()
    improvements: Counter = Counter()
    tone_counter: Counter = Counter()
    for item in analyzed:
        strengths.update(item.fortalezas or [])
        improvements.update(item.mejoras or [])
        if item.tono:
            tone_counter[item.tono] += 1

    sentiment = {
        "distribucion": {
            label: sum(1 for item in analyzed if item.sentimiento == label)
            for label in ("positivo", "neutral", "negativo")
        },
        "promedio": kpis["sentimiento_promedio"],
        "tonos": [{"tono": tone, "total": count} for tone, count in tone_counter.most_common()],
        "temas_fortalezas": [{"tema": t, "total": c} for t, c in strengths.most_common(12)],
        "temas_mejora": [{"tema": t, "total": c} for t, c in improvements.most_common(12)],
        "analizadas": len(analyzed),
        "pendientes": kpis["sentimiento_pendientes"],
    }

    run_info = {r["run"].id: r for r in runs}
    coherence_labels = ("alineada", "indulgente", "severa")
    coherence = {
        "distribucion": {
            label: sum(1 for item in analyzed if item.coherencia == label) for label in coherence_labels
        },
        "alertas": [
            {
                "run_id": item.run_id,
                "fecha": run_info[item.run_id]["started_lima"].isoformat(),
                "nombre": run_info[item.run_id]["run"].nombre,
                "asistente": run_info[item.run_id]["asistente"],
                "puntaje_rubrica": run_scores.get(item.run_id),
                "sentimiento": item.puntaje,
                "coherencia": item.coherencia,
                "motivo": item.coherencia_motivo,
            }
            for item in analyzed
            if item.coherencia in ("indulgente", "severa") and item.run_id in run_info
        ][:15],
        "evaluadas": sum(1 for item in analyzed if item.coherencia),
    }

    rating_values = list(ratings.values())
    ratings_by_assistant: dict[str, list[int]] = defaultdict(list)
    for rating in rating_values:
        if rating.run_id in run_info:
            ratings_by_assistant[run_info[rating.run_id]["asistente"]].append(rating.rating)
    valoraciones = {
        "total": len(rating_values),
        "promedio": kpis["valoracion_promedio"],
        "tasa_valoracion": kpis["tasa_valoracion"],
        "distribucion": {str(star): sum(1 for r in rating_values if r.rating == star) for star in range(1, 6)},
        "por_asistente": sorted(
            (
                {"nombre": name, "total": len(values), "promedio": _avg(values)}
                for name, values in ratings_by_assistant.items()
            ),
            key=lambda row: row["total"],
            reverse=True,
        ),
        "comentarios": [
            {
                "run_id": rating.run_id,
                "fecha": _to_lima(rating.updated_at or rating.created_at).isoformat(),
                "nombre": run_info[rating.run_id]["run"].nombre,
                "asistente": run_info[rating.run_id]["asistente"],
                "rating": rating.rating,
                "comentario": rating.comentario,
            }
            for rating in sorted(rating_values, key=lambda r: r.updated_at or r.created_at, reverse=True)
            if rating.comentario and rating.run_id in run_info
        ][:15],
    }

    return {
        "kpis": kpis,
        "coherencia": coherence,
        "valoraciones": valoraciones,
        "granularidad": granularity,
        "serie": timeline,
        "por_hora": by_hour,
        "por_dia_semana": [{"dia": WEEKDAYS[i], "total": by_weekday[i]} for i in range(7)],
        "por_estado": [{"estado": status, "total": count} for status, count in status_counter.most_common()],
        "niveles": {level: level_counter.get(level, 0) for level in LEVELS},
        "por_asistente": group_runs("asistente"),
        "por_programa": group_runs("programa"),
        "por_curso": group_runs("curso"),
        "criterios": criteria_rows,
        "dimensiones": sorted(
            (
                {"dimension": name, "puntaje_prom": _avg(values), "evaluaciones": len(values)}
                for name, values in dimensions.items()
            ),
            key=lambda row: row["puntaje_prom"] or 0,
        ),
        "errores": [
            {"tipo": kind, "mensaje": message, "total": count} for (kind, message), count in error_counter.most_common(8)
        ],
        "sentimiento": sentiment,
    }


def _run_row(
    item: dict,
    evaluations: list[RubricEvaluation],
    sentiment: RunSentiment | None,
    rating: FeedbackRating | None = None,
) -> dict:
    run: ProcessingRun = item["run"]
    return {
        "run_id": run.id,
        "fecha": item["started_lima"].isoformat() if item["started_lima"] else None,
        "cmid": run.cmid,
        "asistente": item["asistente"],
        "programa": item["programa"],
        "curso": item["curso"],
        "user_id": run.user_id,
        "course_id": run.course_id,
        "nombre": run.nombre,
        "rol": run.role,
        "estado": run.status,
        "etapa": run.stage,
        "puntaje": _run_score(evaluations),
        "nivel": _predominant_level(evaluations),
        "criterios": len(evaluations),
        "sentimiento": sentiment.sentimiento if sentiment else None,
        "sentimiento_puntaje": sentiment.puntaje if sentiment else None,
        "coherencia": sentiment.coherencia if sentiment else None,
        "valoracion": rating.rating if rating else None,
        "total_ms": run.total_ms,
        "tokens": run.total_tokens,
        "paginas": run.paginas_detectadas,
        "similitud": run.similarity_score,
        "error": run.error_message or (run.validation_reason if run.status == "validation_failed" else None),
    }


def list_runs(
    session: Session,
    filters: ReportFilters,
    *,
    search: str | None = None,
    sentimiento: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    runs = _load_runs(session, filters)
    run_ids = [item["run"].id for item in runs]
    evaluations = _load_evaluations(session, run_ids)
    sentiments = _load_sentiments(session, run_ids)
    ratings = _load_ratings(session, run_ids)

    rows = [
        _run_row(item, evaluations.get(item["run"].id, []), sentiments.get(item["run"].id), ratings.get(item["run"].id))
        for item in runs
    ]
    if search:
        needle = search.strip().lower()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                str(row[key]) for key in ("nombre", "user_id", "cmid", "asistente", "curso", "programa", "run_id")
            ).lower()
        ]
    if sentimiento:
        rows = [row for row in rows if row["sentimiento"] == sentimiento]

    return {"total": len(rows), "items": rows[offset : offset + limit]}


def runs_to_csv(session: Session, filters: ReportFilters) -> str:
    rows = list_runs(session, filters, limit=100000)["items"]
    columns = [
        "fecha", "run_id", "asistente", "programa", "curso", "cmid", "course_id", "user_id", "nombre", "rol",
        "estado", "puntaje", "nivel", "criterios", "sentimiento", "sentimiento_puntaje", "coherencia", "valoracion",
        "total_ms", "tokens",
        "paginas", "similitud", "error",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def get_run_report(session: Session, run_id: str) -> dict | None:
    run = session.get(ProcessingRun, run_id)
    if run is None:
        return None
    index = _assistant_index(session)
    info = index.get(run.cmid) or {}
    item = {
        "run": run,
        "asistente": info.get("asistente") or f"Sin asistente (CMID {run.cmid})",
        "programa": info.get("programa") or "Sin programa",
        "curso": info.get("curso") or "Sin curso",
        "started_lima": _to_lima(run.started_at),
    }
    evaluations = _load_evaluations(session, [run_id]).get(run_id, [])
    sentiment = session.get(RunSentiment, run_id)
    rating = session.get(FeedbackRating, run_id)
    events = session.exec(
        select(ProcessingEvent).where(ProcessingEvent.run_id == run_id).order_by(ProcessingEvent.created_at)
    ).all()

    return {
        **_run_row(item, evaluations, sentiment, rating),
        "valoracion_detalle": (
            {"rating": rating.rating, "comentario": rating.comentario, "fecha": _to_lima(rating.updated_at).isoformat()}
            if rating
            else None
        ),
        "retroalimentacion": run.retroalimentacion,
        "modelo": run.modelo,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "moodle_ms": run.moodle_ms,
        "extraction_ms": run.extraction_ms,
        "gpt_ms": run.gpt_ms,
        "pdf_filename": run.pdf_filename,
        "relevancia": run.relevance_score,
        "validacion_aprobada": run.validation_passed,
        "validacion_motivo": run.validation_reason,
        "cmids_relacionados": run.cmids_relacionados or [],
        "relacionados": run.related_details or [],
        "evaluacion": [
            {
                "indice": e.criterion_index,
                "dimension": e.dimension,
                "criterio": e.criterio,
                "nivel": _normalize_level(e.nivel_obtenido),
                "score": _evaluation_score(e),
                "evidencia": e.evidencia,
                "comentario": e.comentario,
                "recomendacion": e.recomendacion,
            }
            for e in sorted(evaluations, key=lambda e: e.criterion_index)
        ],
        "sentimiento_detalle": (
            {
                "sentimiento": sentiment.sentimiento,
                "puntaje": sentiment.puntaje,
                "tono": sentiment.tono,
                "coherencia": sentiment.coherencia,
                "coherencia_motivo": sentiment.coherencia_motivo,
                "fortalezas": sentiment.fortalezas or [],
                "mejoras": sentiment.mejoras or [],
                "resumen": sentiment.resumen,
            }
            if sentiment
            else None
        ),
        "eventos": [
            {
                "etapa": event.stage,
                "nivel": event.level,
                "mensaje": event.message,
                "ms": event.elapsed_ms,
                "fecha": _to_lima(event.created_at).isoformat() if event.created_at else None,
            }
            for event in events
        ],
    }


def analyze_pending_sentiments(session: Session, filters: ReportFilters, *, limit: int = 12) -> dict:
    """Analiza el sentimiento de las retroalimentaciones exitosas que aun no se analizaron."""
    runs = [
        r
        for r in _load_runs(session, filters)
        if r["run"].status == "success" and (r["run"].retroalimentacion or "").strip()
    ]
    sentiments = _load_sentiments(session, [r["run"].id for r in runs])
    pending = [r for r in runs if _needs_analysis(sentiments.get(r["run"].id))]
    batch = pending[:limit]
    evaluations = _load_evaluations(session, [r["run"].id for r in batch])

    processed = 0
    for start in range(0, len(batch), SENTIMENT_BATCH_SIZE):
        chunk = batch[start : start + SENTIMENT_BATCH_SIZE]
        items = [
            {
                "run_id": r["run"].id,
                "retroalimentacion": (r["run"].retroalimentacion or "")[:6000],
                "puntaje_rubrica": _run_score(evaluations.get(r["run"].id, [])),
                "evaluaciones": [
                    {
                        "criterio": e.criterio,
                        "nivel": _normalize_level(e.nivel_obtenido),
                        "comentario": (e.comentario or "")[:240],
                    }
                    for e in sorted(evaluations.get(r["run"].id, []), key=lambda e: e.criterion_index)
                ],
            }
            for r in chunk
        ]
        results, model, tokens = analyze_sentiments(items)
        per_item_tokens = (tokens // len(results)) if tokens and results else None
        for result in results:
            session.merge(
                RunSentiment(
                    run_id=result["run_id"],
                    sentimiento=result["sentimiento"],
                    puntaje=result["puntaje"],
                    tono=result["tono"],
                    coherencia=result["coherencia"],
                    coherencia_motivo=result["coherencia_motivo"],
                    fortalezas=result["fortalezas"],
                    mejoras=result["mejoras"],
                    resumen=result["resumen"],
                    modelo=model,
                    total_tokens=per_item_tokens,
                )
            )
            processed += 1
        session.commit()

    return {"procesadas": processed, "pendientes": max(len(pending) - processed, 0)}
