(function () {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const STATUS_LABELS = {
    success: "Exitosa",
    failed: "Fallida",
    validation_failed: "Rechazada",
    started: "En curso",
  };
  const LEVEL_LABELS = { inicio: "Inicio", en_proceso: "En proceso", logrado: "Logrado", destacado: "Destacado", sin_nivel: "Sin nivel" };
  const SENT_LABELS = { positivo: "Positivo", neutral: "Neutral", negativo: "Negativo" };
  const COH_LABELS = { alineada: "Alineada", indulgente: "Indulgente", severa: "Severa" };
  const PAGE_SIZE = 20;

  const state = { tab: "resumen", offset: 0, summary: null, loaded: false, courses: [], assistants: [] };

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  const fmtInt = (value) => (value == null ? "-" : Number(value).toLocaleString("es-PE"));
  const fmtNum = (value, digits = 2) => (value == null ? "-" : Number(value).toLocaleString("es-PE", { minimumFractionDigits: digits, maximumFractionDigits: digits }));
  const fmtPct = (value) => (value == null ? "-" : `${(value * 100).toFixed(0)}%`);
  const fmtMs = (value) => {
    if (value == null) return "-";
    return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
  };
  const fmtDate = (iso) => {
    if (!iso) return "-";
    const [day, time] = iso.split("T");
    return `${day.split("-").reverse().join("/")} ${time ? time.slice(0, 5) : ""}`;
  };

  async function api(path, options) {
    const response = await fetch(path, options);
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      throw new Error(detail || `Error HTTP ${response.status}`);
    }
    return data;
  }

  // ---------------------------------------------------------------- filtros
  function toISO(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function filterParams(extra = {}) {
    const params = new URLSearchParams();
    const map = {
      desde: $("#rp-desde").value,
      hasta: $("#rp-hasta").value,
      assistant_id: $("#rp-asistente").value,
      programa_id: $("#rp-programa").value,
      curso_id: $("#rp-curso").value,
      rol: $("#rp-rol").value,
      estado: $("#rp-estado").value,
      ...extra,
    };
    Object.entries(map).forEach(([key, value]) => {
      if (value !== "" && value != null) params.set(key, value);
    });
    return params;
  }

  function applyPreset(range) {
    $$("#rp-presets button").forEach((button) => button.classList.toggle("active", button.dataset.range === range));
    const today = new Date();
    if (range === "todo") {
      $("#rp-desde").value = "";
      $("#rp-hasta").value = "";
    } else if (range === "hoy") {
      $("#rp-desde").value = toISO(today);
      $("#rp-hasta").value = toISO(today);
    } else {
      const from = new Date();
      from.setDate(today.getDate() - (Number(range) - 1));
      $("#rp-desde").value = toISO(from);
      $("#rp-hasta").value = toISO(today);
    }
  }

  async function loadFilterOptions() {
    try {
      const [assistants, programs, courses] = await Promise.all([api("/asistentes"), api("/programas"), api("/cursos")]);
      state.assistants = assistants;
      state.courses = courses;
      $("#rp-asistente").innerHTML =
        '<option value="">Todos</option>' +
        assistants.map((a) => `<option value="${a.id}">${esc(a.nombre)} (ID ${a.id})</option>`).join("");
      $("#rp-programa").innerHTML =
        '<option value="">Todos</option>' + programs.map((p) => `<option value="${p.id}">${esc(p.nombre)}</option>`).join("");
      renderCourseOptions();
    } catch (error) {
      window.notify && window.notify(`No se pudieron cargar los filtros: ${error.message}`, "error");
    }
  }

  function renderCourseOptions() {
    const programId = $("#rp-programa").value;
    const courses = programId ? state.courses.filter((c) => String(c.programa_id) === programId) : state.courses;
    $("#rp-curso").innerHTML =
      '<option value="">Todos</option>' + courses.map((c) => `<option value="${c.id}">${esc(c.nombre)}</option>`).join("");
  }

  // ---------------------------------------------------------------- graficos
  function emptyState(message = "Sin datos para los filtros seleccionados.") {
    return `<p class="empty-note">${esc(message)}</p>`;
  }

  function lineChart(target, labels, series) {
    const el = $(target);
    const max = Math.max(1, ...series.flatMap((s) => s.values.map((v) => v || 0)));
    if (!labels.length || series.every((s) => s.values.every((v) => !v))) {
      el.innerHTML = emptyState();
      return;
    }
    const width = 760;
    const height = 220;
    const pad = { left: 34, right: 12, top: 12, bottom: 26 };
    const innerW = width - pad.left - pad.right;
    const innerH = height - pad.top - pad.bottom;
    const x = (i) => pad.left + (labels.length === 1 ? innerW / 2 : (i / (labels.length - 1)) * innerW);
    const y = (v) => pad.top + innerH - (v / max) * innerH;

    const grid = [0, 0.5, 1]
      .map((f) => {
        const value = Math.round(max * f);
        const yy = y(max * f);
        return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" class="grid-line"/><text x="${pad.left - 6}" y="${yy + 4}" class="axis" text-anchor="end">${value}</text>`;
      })
      .join("");

    const step = Math.max(1, Math.ceil(labels.length / 8));
    const xLabels = labels
      .map((label, i) =>
        i % step === 0
          ? `<text x="${x(i)}" y="${height - 6}" class="axis" text-anchor="middle">${esc(label.length > 7 ? label.slice(5) : label)}</text>`
          : ""
      )
      .join("");

    const paths = series
      .map((s) => {
        const points = s.values.map((v, i) => `${x(i).toFixed(1)},${y(v || 0).toFixed(1)}`).join(" ");
        const dots = s.values
          .map((v, i) =>
            v
              ? `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3.2" fill="${s.color}"><title>${esc(labels[i])}: ${v} ${esc(s.name)}</title></circle>`
              : ""
          )
          .join("");
        return `<polyline points="${points}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linejoin="round"/>${dots}`;
      })
      .join("");

    el.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" preserveAspectRatio="xMidYMid meet">${grid}${xLabels}${paths}</svg>`;
  }

  function columnChart(target, labels, values, color = "var(--accent)") {
    const el = $(target);
    const max = Math.max(1, ...values);
    if (!values.some((v) => v > 0)) {
      el.innerHTML = emptyState();
      return;
    }
    el.innerHTML = `<div class="columns">${values
      .map(
        (v, i) => `<div class="col" title="${esc(labels[i])}: ${v}">
          <span class="col-val">${v || ""}</span>
          <span class="col-bar" style="height:${Math.max(2, (v / max) * 100)}%;background:${color}"></span>
          <span class="col-lab">${esc(labels[i])}</span></div>`
      )
      .join("")}</div>`;
  }

  function hBars(target, rows, { color = "var(--accent)", format = fmtInt, max } = {}) {
    const el = $(target);
    if (!rows.length) {
      el.innerHTML = emptyState();
      return;
    }
    const top = max ?? Math.max(...rows.map((r) => r.value || 0), 1);
    el.innerHTML = rows
      .map(
        (r) => `<div class="hbar">
          <div class="hbar-label" title="${esc(r.label)}">${esc(r.label)}</div>
          <div class="hbar-track"><div class="hbar-fill" style="width:${Math.max(1.5, ((r.value || 0) / top) * 100)}%;background:${r.color || color}"></div></div>
          <div class="hbar-value">${format(r.value)}</div></div>`
      )
      .join("");
  }

  function stacked(target, segments) {
    const el = $(target);
    const total = segments.reduce((sum, s) => sum + s.value, 0);
    if (!total) {
      el.innerHTML = emptyState();
      return;
    }
    el.innerHTML = `<div class="stack">${segments
      .map((s) => `<span style="width:${(s.value / total) * 100}%;background:${s.color}" title="${esc(s.label)}: ${s.value}"></span>`)
      .join("")}</div>
      <ul class="stack-legend">${segments
        .map(
          (s) => `<li><i style="background:${s.color}"></i>${esc(s.label)}<b>${fmtInt(s.value)}</b><small>${fmtPct(s.value / total)}</small></li>`
        )
        .join("")}</ul>`;
  }

  function donut(target, segments) {
    const el = $(target);
    const total = segments.reduce((sum, s) => sum + s.value, 0);
    if (!total) {
      el.innerHTML = emptyState();
      return;
    }
    let acc = 0;
    const stops = segments
      .map((s) => {
        const from = (acc / total) * 100;
        acc += s.value;
        return `${s.color} ${from}% ${(acc / total) * 100}%`;
      })
      .join(", ");
    el.innerHTML = `<div class="donut-wrap"><div class="donut" style="background:conic-gradient(${stops})"><span>${fmtInt(total)}</span></div>
      <ul class="stack-legend">${segments
        .map((s) => `<li><i style="background:${s.color}"></i>${esc(s.label)}<b>${fmtInt(s.value)}</b><small>${fmtPct(s.value / total)}</small></li>`)
        .join("")}</ul></div>`;
  }

  function starsInline(value) {
    if (!value) return "-";
    return `<span class="stars-inline" title="${value} de 5">${"&#9733;".repeat(value)}<span class="off">${"&#9733;".repeat(5 - value)}</span></span>`;
  }

  const COLORS = {
    alineada: "#16a34a",
    indulgente: "#f59e0b",
    severa: "#dc2626",
    success: "#0f766e",
    failed: "#b42318",
    validation_failed: "#d97706",
    started: "#2563eb",
    inicio: "#dc2626",
    en_proceso: "#f59e0b",
    logrado: "#16a34a",
    destacado: "#0f766e",
    positivo: "#16a34a",
    neutral: "#94a3b8",
    negativo: "#dc2626",
  };

  // ---------------------------------------------------------------- tablas
  function usageTable(target, rows, firstColumn) {
    const el = $(target);
    if (!rows.length) {
      el.innerHTML = `<tbody><tr><td>${emptyState()}</td></tr></tbody>`;
      return;
    }
    el.innerHTML = `<thead><tr><th>${firstColumn}</th><th>Ejecuciones</th><th>Exitosas</th><th>Fallidas / rechazadas</th><th>Usuarios</th><th>Puntaje prom.</th><th>Tiempo prom.</th><th>Sentimiento</th></tr></thead>
      <tbody>${rows
        .map(
          (r) => `<tr><td><strong>${esc(r.nombre)}</strong></td><td>${fmtInt(r.ejecuciones)}</td><td>${fmtInt(r.exitosas)}</td><td>${fmtInt(r.fallidas)}</td><td>${fmtInt(r.usuarios)}</td>
          <td>${scoreCell(r.puntaje_prom)}</td><td>${fmtMs(r.tiempo_prom_ms)}</td><td>${sentimentDot(r.sentimiento_prom)}</td></tr>`
        )
        .join("")}</tbody>`;
  }

  function scoreCell(score) {
    if (score == null) return "-";
    const pct = Math.max(0, Math.min(100, ((score - 1) / 3) * 100));
    const color = score >= 3 ? COLORS.logrado : score >= 2 ? COLORS.en_proceso : COLORS.inicio;
    return `<span class="score"><span class="score-bar"><i style="width:${pct}%;background:${color}"></i></span>${fmtNum(score)}</span>`;
  }

  function sentimentDot(value) {
    if (value == null) return "-";
    const label = value > 0.25 ? "positivo" : value < -0.25 ? "negativo" : "neutral";
    return `<span class="pill pill-${label}">${fmtNum(value)}</span>`;
  }

  // ---------------------------------------------------------------- resumen
  function kpiCard(label, value, hint, tone = "") {
    return `<article class="kpi ${tone}"><span class="kpi-label">${esc(label)}</span><strong class="kpi-value">${value}</strong><span class="kpi-hint">${hint || "&nbsp;"}</span></article>`;
  }

  function renderSummary(data) {
    const k = data.kpis;
    $("#rp-kpis").innerHTML = [
      kpiCard("Ejecuciones", fmtInt(k.ejecuciones), `${fmtInt(k.exitosas)} exitosas`),
      kpiCard("Tasa de exito", fmtPct(k.tasa_exito), `${fmtInt(k.fallidas)} fallidas · ${fmtInt(k.rechazadas)} rechazadas`, "tone-teal"),
      kpiCard("Usuarios unicos", fmtInt(k.usuarios_unicos), `${fmtInt(k.usuarios_recurrentes)} con mas de una entrega`),
      kpiCard("Consultas guardadas", fmtInt(k.consultas_guardadas), "Reaperturas de una retroalimentacion ya generada"),
      kpiCard("Puntaje promedio", k.puntaje_promedio == null ? "-" : `${fmtNum(k.puntaje_promedio)} / 4`, "Promedio de criterios de rubrica", "tone-blue"),
      kpiCard("Valoracion de docentes", k.valoracion_promedio == null ? "-" : `${fmtNum(k.valoracion_promedio, 1)} / 5`, `${fmtInt(k.valoraciones)} valoraciones · responde ${fmtPct(k.tasa_valoracion)}`, "tone-violet"),
      kpiCard("Sentimiento del texto", k.sentimiento_promedio == null ? "-" : fmtNum(k.sentimiento_promedio), `${fmtInt(k.sentimiento_analizadas)} analizadas · ${fmtInt(k.sentimiento_pendientes)} pendientes`, "tone-violet"),
      kpiCard("Tiempo promedio", fmtMs(k.tiempo_prom_ms), `Moodle ${fmtMs(k.moodle_prom_ms)} · IA ${fmtMs(k.gpt_prom_ms)}`),
      kpiCard("Tokens consumidos", fmtInt(k.tokens_total), `${fmtInt(k.tokens_prom)} por retroalimentacion`),
    ].join("");

    const serie = data.serie || [];
    $("#rp-serie-sub").textContent = serie.length ? `Agrupado por ${data.granularidad}` : "";
    $("#rp-serie-legend").innerHTML =
      '<span><i style="background:#0f766e"></i>Ejecuciones</span><span><i style="background:#2563eb"></i>Consultas guardadas</span><span><i style="background:#b42318"></i>Fallidas / rechazadas</span>';
    lineChart(
      "#rp-chart-serie",
      serie.map((s) => s.fecha),
      [
        { name: "ejecuciones", color: "#0f766e", values: serie.map((s) => s.ejecuciones) },
        { name: "consultas", color: "#2563eb", values: serie.map((s) => s.consultas) },
        { name: "fallidas", color: "#b42318", values: serie.map((s) => s.fallidas) },
      ]
    );

    donut(
      "#rp-chart-estado",
      (data.por_estado || []).map((s) => ({ label: STATUS_LABELS[s.estado] || s.estado, value: s.total, color: COLORS[s.estado] || "#64748b" }))
    );
    columnChart("#rp-chart-hora", data.por_hora.map((_, i) => String(i)), data.por_hora);
    columnChart("#rp-chart-semana", data.por_dia_semana.map((d) => d.dia), data.por_dia_semana.map((d) => d.total), "#2563eb");

    usageTable("#rp-table-asistente", data.por_asistente, "Asistente");
    usageTable("#rp-table-programa", data.por_programa, "Programa");
    usageTable("#rp-table-curso", data.por_curso, "Curso");

    $("#rp-errores").innerHTML = data.errores.length
      ? `<ul class="error-list">${data.errores
          .map((e) => `<li><span class="pill pill-${e.tipo === "Error" ? "negativo" : "neutral"}">${esc(e.tipo)}</span><span>${esc(e.mensaje)}</span><b>${fmtInt(e.total)}</b></li>`)
          .join("")}</ul>`
      : emptyState("No hay errores ni rechazos en el periodo.");
  }

  // ---------------------------------------------------------------- rubrica
  function renderRubric(data) {
    stacked(
      "#rp-niveles",
      ["inicio", "en_proceso", "logrado", "destacado"].map((level) => ({ label: LEVEL_LABELS[level], value: data.niveles[level] || 0, color: COLORS[level] }))
    );
    hBars(
      "#rp-dimensiones",
      (data.dimensiones || []).map((d) => ({ label: d.dimension, value: d.puntaje_prom, color: d.puntaje_prom >= 3 ? COLORS.logrado : d.puntaje_prom >= 2 ? COLORS.en_proceso : COLORS.inicio })),
      { format: (v) => fmtNum(v), max: 4 }
    );
    renderCriteria();
  }

  function renderCriteria() {
    const needle = ($("#rp-criterios-q").value || "").trim().toLowerCase();
    const rows = (state.summary?.criterios || []).filter((c) => !needle || `${c.criterio} ${c.dimension} ${c.asistente}`.toLowerCase().includes(needle));
    const el = $("#rp-table-criterios");
    if (!rows.length) {
      el.innerHTML = `<tbody><tr><td>${emptyState()}</td></tr></tbody>`;
      return;
    }
    el.innerHTML = `<thead><tr><th>Criterio</th><th>Dimension</th><th>Asistente</th><th>Evaluaciones</th><th>Puntaje prom.</th><th>% en inicio / proceso</th><th>Distribucion de niveles</th></tr></thead>
      <tbody>${rows
        .slice(0, 80)
        .map((c) => {
          const total = Object.values(c.niveles).reduce((a, b) => a + b, 0) || 1;
          const bar = ["inicio", "en_proceso", "logrado", "destacado"]
            .map((l) => `<span style="width:${(c.niveles[l] / total) * 100}%;background:${COLORS[l]}" title="${LEVEL_LABELS[l]}: ${c.niveles[l]}"></span>`)
            .join("");
          return `<tr><td><strong>${esc(c.criterio)}</strong></td><td>${esc(c.dimension)}</td><td>${esc(c.asistente)}</td><td>${fmtInt(c.evaluaciones)}</td><td>${scoreCell(c.puntaje_prom)}</td><td>${fmtPct(c.pct_bajo)}</td><td><div class="stack stack-mini">${bar}</div></td></tr>`;
        })
        .join("")}</tbody>`;
  }

  // ---------------------------------------------------------------- sentimiento
  function renderSentiment(data) {
    const s = data.sentimiento;
    $("#rp-sent-sub").textContent = `${fmtInt(s.analizadas)} retroalimentaciones analizadas · ${fmtInt(s.pendientes)} pendientes de analizar`;
    $("#rp-sent-run").disabled = !s.pendientes;
    $("#rp-sent-run").textContent = s.pendientes ? `Analizar pendientes (${fmtInt(s.pendientes)})` : "Todo analizado";

    donut(
      "#rp-sent-dist",
      ["positivo", "neutral", "negativo"].map((label) => ({ label: SENT_LABELS[label], value: s.distribucion[label] || 0, color: COLORS[label] }))
    );

    if (s.promedio == null) {
      $("#rp-sent-gauge").innerHTML = emptyState("Aun no hay retroalimentaciones analizadas.");
    } else {
      const position = ((s.promedio + 1) / 2) * 100;
      $("#rp-sent-gauge").innerHTML = `<div class="gauge"><div class="gauge-track"><span class="gauge-marker" style="left:${position}%"></span></div>
        <div class="gauge-scale"><small>-1 negativo</small><small>0</small><small>+1 positivo</small></div><p class="gauge-value">${fmtNum(s.promedio)}</p></div>`;
    }

    hBars("#rp-sent-tonos", (s.tonos || []).map((t) => ({ label: t.tono, value: t.total })), { color: "#7c3aed" });

    const serie = (data.serie || []).filter((p) => p.sentimiento != null);
    if (!serie.length) {
      $("#rp-sent-serie").innerHTML = emptyState("Sin sentimiento analizado en el periodo.");
    } else {
      lineChart("#rp-sent-serie", serie.map((p) => p.fecha), [
        { name: "sentimiento", color: "#7c3aed", values: serie.map((p) => Number(((p.sentimiento + 1) * 50).toFixed(0))) },
      ]);
    }

    hBars("#rp-sent-fortalezas", (s.temas_fortalezas || []).map((t) => ({ label: t.tema, value: t.total })), { color: COLORS.logrado });
    hBars("#rp-sent-mejoras", (s.temas_mejora || []).map((t) => ({ label: t.tema, value: t.total })), { color: COLORS.en_proceso });
  }

  function renderCoherence(data) {
    const c = data.coherencia;
    donut(
      "#rp-coh-dist",
      ["alineada", "indulgente", "severa"].map((label) => ({ label: COH_LABELS[label], value: c.distribucion[label] || 0, color: COLORS[label] }))
    );
    const table = $("#rp-coh-alertas");
    if (!c.alertas.length) {
      table.innerHTML = `<tbody><tr><td>${emptyState(c.evaluadas ? "No hay alertas: el tono es coherente con la rubrica." : "Aun no hay retroalimentaciones evaluadas. Usa \"Analizar pendientes\".")}</td></tr></tbody>`;
      return;
    }
    table.innerHTML = `<thead><tr><th>Fecha</th><th>Docente</th><th>Asistente</th><th>Puntaje rubrica</th><th>Coherencia</th><th>Motivo</th><th></th></tr></thead>
      <tbody>${c.alertas
        .map(
          (a) => `<tr><td>${fmtDate(a.fecha)}</td><td><strong>${esc(a.nombre)}</strong></td><td>${esc(a.asistente)}</td><td>${scoreCell(a.puntaje_rubrica)}</td>
          <td><span class="pill" style="background:${COLORS[a.coherencia]}22;color:${COLORS[a.coherencia]}">${esc(COH_LABELS[a.coherencia])}</span></td>
          <td>${esc(a.motivo || "")}</td><td><button type="button" data-run="${esc(a.run_id)}">Ver detalle</button></td></tr>`
        )
        .join("")}</tbody>`;
    table.querySelectorAll("button[data-run]").forEach((button) => button.addEventListener("click", () => openDrawer(button.dataset.run)));
  }

  function renderRatings(data) {
    const v = data.valoraciones;
    $("#rp-val-kpis").innerHTML = [
      kpiCard("Valoracion promedio", v.promedio == null ? "-" : `${fmtNum(v.promedio, 1)} / 5`, v.promedio == null ? "Aun sin valoraciones" : starsInline(Math.round(v.promedio)), "tone-violet"),
      kpiCard("Valoraciones recibidas", fmtInt(v.total), "Una por retroalimentacion como maximo"),
      kpiCard("Tasa de respuesta", fmtPct(v.tasa_valoracion), "Valoraciones sobre retroalimentaciones exitosas de usuarios", "tone-teal"),
    ].join("");

    hBars(
      "#rp-val-dist",
      [5, 4, 3, 2, 1].map((star) => ({ label: `${star} estrellas`, value: v.distribucion[String(star)] || 0, color: star >= 4 ? COLORS.logrado : star === 3 ? COLORS.en_proceso : COLORS.inicio }))
    );

    const table = $("#rp-val-asistente");
    table.innerHTML = v.por_asistente.length
      ? `<thead><tr><th>Asistente</th><th>Valoraciones</th><th>Promedio</th></tr></thead><tbody>${v.por_asistente
          .map((a) => `<tr><td><strong>${esc(a.nombre)}</strong></td><td>${fmtInt(a.total)}</td><td>${starsInline(Math.round(a.promedio))} ${fmtNum(a.promedio, 1)}</td></tr>`)
          .join("")}</tbody>`
      : `<tbody><tr><td>${emptyState("Aun no hay valoraciones.")}</td></tr></tbody>`;

    $("#rp-val-comentarios").innerHTML = v.comentarios.length
      ? `<ul class="comment-list">${v.comentarios
          .map(
            (c) => `<li>${starsInline(c.rating)} <strong>${esc(c.nombre)}</strong> <small>· ${esc(c.asistente)} · ${fmtDate(c.fecha)}</small>
            <p>${esc(c.comentario)}</p><button type="button" data-run="${esc(c.run_id)}">Ver retroalimentacion</button></li>`
          )
          .join("")}</ul>`
      : emptyState("Aun no hay comentarios de los docentes.");
    $("#rp-val-comentarios").querySelectorAll("button[data-run]").forEach((button) => button.addEventListener("click", () => openDrawer(button.dataset.run)));
  }

  async function runSentimentAnalysis() {
    const button = $("#rp-sent-run");
    button.disabled = true;
    button.textContent = "Analizando...";
    try {
      const result = await api(`/reportes/sentimiento/analizar?${filterParams({ limite: 12 })}`, { method: "POST" });
      window.notify && window.notify(`Se analizaron ${result.procesadas} retroalimentaciones. Pendientes: ${result.pendientes}.`);
      await loadSummary();
    } catch (error) {
      window.notify && window.notify(error.message, "error");
      button.disabled = false;
      button.textContent = "Reintentar analisis";
    }
  }

  // ---------------------------------------------------------------- ejecuciones
  async function loadRuns() {
    const params = filterParams({ limit: PAGE_SIZE, offset: state.offset, q: $("#rp-runs-q").value.trim(), sentimiento: $("#rp-runs-sent").value });
    const table = $("#rp-runs-table");
    table.innerHTML = '<tbody><tr><td class="empty-note">Cargando...</td></tr></tbody>';
    try {
      const data = await api(`/reportes/ejecuciones?${params}`);
      $("#rp-runs-sub").textContent = `${fmtInt(data.total)} resultados`;
      if (!data.items.length) {
        table.innerHTML = `<tbody><tr><td>${emptyState()}</td></tr></tbody>`;
      } else {
        table.innerHTML = `<thead><tr><th>Fecha</th><th>Docente</th><th>Asistente</th><th>Estado</th><th>Puntaje</th><th>Nivel</th><th>Sentimiento</th><th>Valoracion</th><th>Tiempo</th><th></th></tr></thead>
          <tbody>${data.items
            .map(
              (r) => `<tr>
              <td>${fmtDate(r.fecha)}</td>
              <td><strong>${esc(r.nombre)}</strong><br><small>Usuario ${r.user_id} · CMID ${r.cmid}${r.rol === 1 ? " · Validador" : ""}</small></td>
              <td>${esc(r.asistente)}<br><small>${esc(r.curso)}</small></td>
              <td><span class="pill pill-status-${esc(r.estado)}">${esc(STATUS_LABELS[r.estado] || r.estado)}</span></td>
              <td>${scoreCell(r.puntaje)}</td>
              <td>${r.nivel ? `<span class="pill" style="background:${COLORS[r.nivel]}22;color:${COLORS[r.nivel]}">${esc(LEVEL_LABELS[r.nivel])}</span>` : "-"}</td>
              <td>${r.sentimiento ? `<span class="pill pill-${r.sentimiento}">${esc(SENT_LABELS[r.sentimiento])}</span>` : "-"}</td>
              <td>${starsInline(r.valoracion)}</td>
              <td>${fmtMs(r.total_ms)}</td>
              <td><button type="button" data-run="${esc(r.run_id)}">Ver detalle</button></td></tr>`
            )
            .join("")}</tbody>`;
        table.querySelectorAll("button[data-run]").forEach((button) => button.addEventListener("click", () => openDrawer(button.dataset.run)));
      }
      const page = Math.floor(state.offset / PAGE_SIZE) + 1;
      const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
      $("#rp-runs-pager").innerHTML = `<button type="button" id="rp-prev" ${page <= 1 ? "disabled" : ""}>Anterior</button><span>Pagina ${page} de ${pages}</span><button type="button" id="rp-next" ${page >= pages ? "disabled" : ""}>Siguiente</button>`;
      $("#rp-prev")?.addEventListener("click", () => {
        state.offset = Math.max(0, state.offset - PAGE_SIZE);
        loadRuns();
      });
      $("#rp-next")?.addEventListener("click", () => {
        state.offset += PAGE_SIZE;
        loadRuns();
      });
    } catch (error) {
      table.innerHTML = `<tbody><tr><td class="error-text">${esc(error.message)}</td></tr></tbody>`;
    }
  }

  // ---------------------------------------------------------------- detalle
  async function openDrawer(runId) {
    const drawer = $("#rp-drawer");
    drawer.hidden = false;
    $("#rp-drawer-title").textContent = "Cargando detalle...";
    $("#rp-drawer-body").innerHTML = "";
    try {
      const r = await api(`/reportes/ejecuciones/${runId}`);
      $("#rp-drawer-title").textContent = r.nombre || "Detalle";
      const sentiment = r.sentimiento_detalle;
      $("#rp-drawer-body").innerHTML = `
        <div class="badge-row">
          <span class="pill pill-status-${esc(r.estado)}">${esc(STATUS_LABELS[r.estado] || r.estado)}</span>
          <span class="badge badge-cmid">CMID ${r.cmid}</span>
          ${r.rol === 1 ? '<span class="badge badge-related">Validador</span>' : ""}
          ${sentiment ? `<span class="pill pill-${sentiment.sentimiento}">${esc(SENT_LABELS[sentiment.sentimiento])}</span>` : ""}
          ${sentiment && sentiment.coherencia ? `<span class="pill" style="background:${COLORS[sentiment.coherencia]}22;color:${COLORS[sentiment.coherencia]}">Coherencia ${esc(COH_LABELS[sentiment.coherencia])}</span>` : ""}
        </div>
        <p class="drawer-meta">${esc(r.asistente)} · ${esc(r.curso)} · ${esc(r.programa)}<br>${fmtDate(r.fecha)} · Usuario ${r.user_id} · Aula ${r.course_id}</p>
        <div class="kpi-grid kpi-grid-mini">
          ${kpiCard("Puntaje", r.puntaje == null ? "-" : `${fmtNum(r.puntaje)} / 4`, r.nivel ? LEVEL_LABELS[r.nivel] : "")}
          ${kpiCard("Tiempo total", fmtMs(r.total_ms), `Moodle ${fmtMs(r.moodle_ms)} · IA ${fmtMs(r.gpt_ms)}`)}
          ${kpiCard("Tokens", fmtInt(r.tokens), r.modelo ? esc(r.modelo) : "")}
          ${kpiCard("Documento", r.paginas == null ? "-" : `${r.paginas} pag.`, esc(r.pdf_filename || ""))}
        </div>
        ${r.error ? `<div class="alert-box">${esc(r.error)}</div>` : ""}
        ${r.validacion_motivo ? `<div class="note-box"><b>Validacion:</b> ${esc(r.validacion_motivo)}${r.relevancia != null ? ` (relevancia ${fmtNum(r.relevancia)})` : ""}</div>` : ""}
        ${
          r.relacionados.length
            ? `<div class="note-box"><b>Entregas relacionadas:</b> ${r.relacionados.map((x) => `CMID ${x.cmid} (similitud ${fmtNum(x.similarity_score)})`).join(" · ")}</div>`
            : ""
        }
        ${
          sentiment
            ? `<section class="drawer-section"><h4>Analisis de sentimiento</h4>
              <p>${esc(sentiment.resumen || "")}</p>
              <p class="drawer-meta">Puntaje ${fmtNum(sentiment.puntaje)} · Tono ${esc(sentiment.tono || "-")}</p>
              ${sentiment.coherencia_motivo ? `<p class="drawer-meta"><b>Coherencia:</b> ${esc(sentiment.coherencia_motivo)}</p>` : ""}
              <div class="chip-cloud"><b>Fortalezas</b>${sentiment.fortalezas.map((t) => `<span class="chip chip-good">${esc(t)}</span>`).join("") || "<small>-</small>"}</div>
              <div class="chip-cloud"><b>Mejoras</b>${sentiment.mejoras.map((t) => `<span class="chip chip-warn">${esc(t)}</span>`).join("") || "<small>-</small>"}</div></section>`
            : ""
        }
        ${
          r.valoracion_detalle
            ? `<section class="drawer-section"><h4>Valoracion del docente</h4><p>${starsInline(r.valoracion_detalle.rating)} ${r.valoracion_detalle.rating} / 5</p>${r.valoracion_detalle.comentario ? `<p>${esc(r.valoracion_detalle.comentario)}</p>` : ""}</section>`
            : ""
        }
        ${
          r.retroalimentacion
            ? `<section class="drawer-section"><h4>Retroalimentacion entregada</h4><div class="feedback-text">${esc(r.retroalimentacion)}</div></section>`
            : ""
        }
        ${
          r.evaluacion.length
            ? `<section class="drawer-section"><h4>Evaluacion por criterio</h4>
              <div class="table-wrap"><table><thead><tr><th>#</th><th>Criterio</th><th>Nivel</th><th>Comentario y recomendacion</th></tr></thead><tbody>${r.evaluacion
                .map(
                  (e) => `<tr><td>${e.indice}</td><td><strong>${esc(e.criterio)}</strong><br><small>${esc(e.dimension)}</small></td>
                  <td><span class="pill" style="background:${COLORS[e.nivel] || "#64748b"}22;color:${COLORS[e.nivel] || "#64748b"}">${esc(LEVEL_LABELS[e.nivel] || e.nivel)}</span></td>
                  <td>${esc(e.comentario || "")}${e.recomendacion ? `<br><small><b>Recomendacion:</b> ${esc(e.recomendacion)}</small>` : ""}${e.evidencia ? `<details><summary>Evidencia</summary><small>${esc(e.evidencia)}</small></details>` : ""}</td></tr>`
                )
                .join("")}</tbody></table></div></section>`
            : ""
        }
        ${
          r.eventos.length
            ? `<section class="drawer-section"><h4>Linea de eventos</h4><ol class="timeline">${r.eventos
                .map((e) => `<li class="ev-${esc(e.nivel)}"><b>${esc(e.etapa)}</b> ${esc(e.mensaje)}${e.ms != null ? ` <small>(${fmtMs(e.ms)})</small>` : ""}</li>`)
                .join("")}</ol></section>`
            : ""
        }`;
    } catch (error) {
      $("#rp-drawer-title").textContent = "No se pudo cargar";
      $("#rp-drawer-body").innerHTML = `<p class="error-text">${esc(error.message)}</p>`;
    }
  }

  function closeDrawer() {
    $("#rp-drawer").hidden = true;
  }

  // ---------------------------------------------------------------- carga
  async function loadSummary() {
    $("#rp-csv").href = `/reportes/ejecuciones.csv?${filterParams()}`;
    try {
      const data = await api(`/reportes/resumen?${filterParams()}`);
      state.summary = data;
      renderSummary(data);
      renderRubric(data);
      renderSentiment(data);
      renderCoherence(data);
      renderRatings(data);
    } catch (error) {
      window.notify && window.notify(`No se pudo cargar la reporteria: ${error.message}`, "error");
    }
  }

  async function refresh({ keepPage = false, silent = false } = {}) {
    if (state.refreshing) return;
    state.refreshing = true;
    const button = $("#rp-refresh");
    if (!silent) button.disabled = true;
    try {
      if (!keepPage) state.offset = 0;
      await loadSummary();
      if (state.tab === "ejecuciones") await loadRuns();
      $("#rp-updated").textContent = `Actualizado a las ${new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
    } finally {
      state.refreshing = false;
      button.disabled = false;
    }
  }

  function autoRefreshTick() {
    const visible = !$("#mod-reporteria").hidden && !document.hidden && $("#rp-drawer").hidden;
    if ($("#rp-auto").checked && visible) refresh({ keepPage: true, silent: true });
  }

  function setTab(tab) {
    state.tab = tab;
    $$("#rp-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.rtab === tab));
    $$("[data-rpanel]").forEach((panel) => {
      panel.hidden = panel.dataset.rpanel !== tab;
    });
    if (tab === "ejecuciones") loadRuns();
  }

  function bind() {
    $$("#rp-presets button").forEach((button) =>
      button.addEventListener("click", () => {
        applyPreset(button.dataset.range);
        refresh();
      })
    );
    $("#rp-apply").addEventListener("click", () => {
      $$("#rp-presets button").forEach((button) => button.classList.remove("active"));
      refresh();
    });
    $("#rp-reset").addEventListener("click", () => {
      ["#rp-asistente", "#rp-programa", "#rp-curso", "#rp-rol", "#rp-estado"].forEach((id) => ($(id).value = ""));
      renderCourseOptions();
      applyPreset("todo");
      refresh();
    });
    $("#rp-refresh").addEventListener("click", () => refresh({ keepPage: true }));
    try {
      $("#rp-auto").checked = localStorage.getItem("gestor.rp.auto") !== "0";
    } catch (error) {
      /* sin almacenamiento */
    }
    $("#rp-auto").addEventListener("change", () => {
      try {
        localStorage.setItem("gestor.rp.auto", $("#rp-auto").checked ? "1" : "0");
      } catch (error) {
        /* sin almacenamiento */
      }
    });
    setInterval(autoRefreshTick, 60000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) autoRefreshTick();
    });
    $("#rp-programa").addEventListener("change", renderCourseOptions);
    $$("#rp-tabs button").forEach((button) => button.addEventListener("click", () => setTab(button.dataset.rtab)));
    $("#rp-sent-run").addEventListener("click", runSentimentAnalysis);
    $("#rp-criterios-q").addEventListener("input", renderCriteria);

    let timer;
    $("#rp-runs-q").addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.offset = 0;
        loadRuns();
      }, 300);
    });
    $("#rp-runs-sent").addEventListener("change", () => {
      state.offset = 0;
      loadRuns();
    });

    $$("[data-close-drawer]").forEach((el) => el.addEventListener("click", closeDrawer));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeDrawer();
    });

    window.addEventListener("modulo-abierto", async (event) => {
      if (event.detail.modulo !== "reporteria") return;
      if (!state.loaded) {
        state.loaded = true;
        await loadFilterOptions();
      }
      if (state.pendingAssistant) {
        $("#rp-asistente").value = String(state.pendingAssistant);
        state.pendingAssistant = null;
      }
      refresh();
    });

    window.addEventListener("abrir-reporte", (event) => {
      state.pendingAssistant = event.detail?.assistant_id || null;
    });
  }

  bind();

  if (!$("#mod-reporteria").hidden) {
    window.dispatchEvent(new CustomEvent("modulo-abierto", { detail: { modulo: "reporteria" } }));
  }
})();
