const demoAssistant = {
  nombre: "Calendario comunal EIB",
  descripcion_producto:
    "El calendario comunal es una herramienta pedagogica fundamental en Educacion Inicial EIB para ambito rural. Organiza actividades socioculturales y socioproductivas de la comunidad, saberes asociados, problemas del contexto y aliados posibles. Sirve como insumo para una planificacion curricular pertinente y para promover dialogo de saberes.",
  contexto_curso:
    "Unidad 1, sesion 2: se aborda el calendario comunal como herramienta para recoger actividades socioculturales y socioproductivas, saberes comunitarios, problemas del contexto y aliados. Se relaciona con la planificacion curricular pertinente y el dialogo de saberes en Educacion Inicial EIB.",
  ejemplo_producto:
    "Ejemplo de referencia: un calendario organizado por epocas o meses, con columnas para actividades de la comunidad, saberes asociados, problemas o potencialidades, aliados y posibilidades pedagogicas. Debe evidenciar actividades como siembra, cosecha, festividades, preparacion de alimentos u otras practicas propias de la comunidad.",
  analiza_texto: true,
  analiza_tablas: true,
  analiza_imagenes: false,
  usa_cmid_relacionado: false,
  cmid_relacionado: null,
  validar_documento: true,
  validar_similitud: true,
  rubrica: [
    {
      dimension: "Estructura y organizacion del calendario comunal",
      descripcion_dimension:
        "Evalua si el producto presenta una estructura clara, completa y organizada segun los componentes esperados del calendario comunal.",
      criterio: "Presencia de las cinco columnas estructurales",
      descripcion_criterio:
        "Verifica que el calendario incluya las columnas necesarias para organizar epocas, actividades, saberes, problemas y aliados de la comunidad.",
      niveles: {
        inicio: "Carece de mas de dos columnas o las columnas no corresponden a las definidas.",
        en_proceso: "Tiene columnas basicas, pero algunas estan incompletas, fusionadas o mal nombradas.",
        logrado: "Las cinco columnas estan presentes, correctamente nombradas y con contenido.",
        destacado: "Las cinco columnas estan completas y agrega valor, como nomenclatura en lengua originaria.",
      },
    },
    {
      dimension: "Estructura y organizacion del calendario comunal",
      descripcion_dimension:
        "Evalua si el producto presenta una estructura clara, completa y organizada segun los componentes esperados del calendario comunal.",
      criterio: "Organizacion temporal por epocas o ciclos comunales",
      descripcion_criterio:
        "Revisa si las actividades estan ordenadas segun los tiempos, epocas o ciclos reconocidos por la comunidad.",
      niveles: {
        inicio: "No organiza la informacion por epocas, meses o ciclos comunales.",
        en_proceso: "Presenta una organizacion temporal parcial o poco clara.",
        logrado: "Organiza las actividades segun epocas o ciclos comunales de manera comprensible.",
        destacado: "Relaciona ciclos comunales con actividades, saberes, senas y momentos pedagogicos.",
      },
    },
    {
      dimension: "Actividades socioculturales y socioproductivas",
      descripcion_dimension:
        "Evalua la pertinencia de las actividades seleccionadas y su relacion con la vida cotidiana, cultural y productiva de la comunidad.",
      criterio: "Pertinencia y contextualizacion de las actividades",
      descripcion_criterio:
        "Verifica que las actividades respondan al contexto real de la comunidad y no sean ejemplos genericos o descontextualizados.",
      niveles: {
        inicio: "Las actividades son genericas o no reflejan el contexto de la comunidad.",
        en_proceso: "Incluye actividades del contexto, pero con poca descripcion o precision.",
        logrado: "Las actividades son pertinentes y reflejan practicas socioculturales y socioproductivas.",
        destacado: "Contextualiza actividades con saberes, ritos, senas, secretos, lengua y territorio.",
      },
    },
    {
      dimension: "Actividades socioculturales y socioproductivas",
      descripcion_dimension:
        "Evalua la pertinencia de las actividades seleccionadas y su relacion con la vida cotidiana, cultural y productiva de la comunidad.",
      criterio: "Priorizacion pedagogica para el nivel inicial",
      descripcion_criterio:
        "Revisa si las actividades seleccionadas pueden convertirse en situaciones significativas adecuadas para ninos y ninas de Educacion Inicial.",
      niveles: {
        inicio: "No se evidencia vinculacion con necesidades pedagogicas de Educacion Inicial.",
        en_proceso: "La vinculacion pedagogica es general o insuficiente.",
        logrado: "Prioriza actividades viables para experiencias de aprendizaje en Inicial.",
        destacado: "Propone situaciones significativas claras y articulables con competencias del CNEB.",
      },
    },
  ],
  perfil_retroalimentacion: [
    "Iniciar reconociendo aciertos y explicar por que son valiosos.",
    "Senalar omisiones o debilidades de manera especifica e indicar como incorporarlas.",
    "Relacionar observaciones con contenidos del curso y con la planificacion curricular pertinente.",
    "Proponer preguntas reflexivas que ayuden al docente a profundizar.",
    "Sugerir ejemplos concretos adaptados al contexto del docente.",
    "Recordar que el calendario comunal es una herramienta viva que puede actualizarse.",
    "Nunca emitir juicios de valor sobre la cultura o las practicas de la comunidad.",
    "Evitar comparaciones que jerarquicen comunidades.",
    "Fomentar articulacion con caracterizacion linguistica, tratamiento de lenguas y dialogo de saberes.",
  ],
  modelo: "",
  activo: true,
};

const fields = {
  cmid: document.querySelector("#cmid"),
  testCmid: document.querySelector("#test-cmid"),
  nombre: document.querySelector("#nombre-asistente"),
  descripcion: document.querySelector("#descripcion-producto"),
  contextoCurso: document.querySelector("#contexto-curso"),
  ejemploProducto: document.querySelector("#ejemplo-producto"),
  analizaTexto: document.querySelector("#analiza-texto"),
  analizaTablas: document.querySelector("#analiza-tablas"),
  analizaImagenes: document.querySelector("#analiza-imagenes"),
  usaCmidRelacionado: document.querySelector("#usa-cmid-relacionado"),
  cmidRelacionado: document.querySelector("#cmid-relacionado"),
  validarDocumento: document.querySelector("#validar-documento"),
  validarSimilitud: document.querySelector("#validar-similitud"),
  rubrica: document.querySelector("#rubrica"),
  perfil: document.querySelector("#perfil"),
  modelo: document.querySelector("#modelo"),
  status: document.querySelector("#status"),
  result: document.querySelector("#result"),
  list: document.querySelector("#assistant-list"),
  analytics: document.querySelector("#analytics-list"),
};

let formMode = "create";
let loadedCmid = null;

document.querySelector("#load-demo").addEventListener("click", async () => {
  fillAssistantForm(194522, demoAssistant, "create");
  setStatus("Ejemplo cargado. Cambia el CMID si crearas una configuracion nueva.");
  await checkExistingCmid();
});

document.querySelector("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus(formMode === "edit" ? "Actualizando configuracion..." : "Creando configuracion...");

  try {
    const payload = readAssistantPayload();
    const method = formMode === "edit" ? "PUT" : "POST";
    const response = await fetch(`/asistentes/${fields.cmid.value}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await parseResponse(response);
    fields.testCmid.value = fields.cmid.value;
    formMode = "edit";
    loadedCmid = String(data.cmid);
    setStatus(method === "POST" ? `CMID ${data.cmid} creado.` : `CMID ${data.cmid} actualizado.`);
    await loadAssistants();
  } catch (error) {
    setError(error.message);
  }
});

document.querySelector("#moodle-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Consultando Moodle y procesando PDF...");
  fields.result.textContent = "";

  try {
    const formData = new FormData(event.currentTarget);
    const params = new URLSearchParams({
      cmid: formData.get("cmid"),
      user_id: formData.get("user_id"),
      course_id: formData.get("course_id"),
      nombre: formData.get("nombre"),
      role: formData.get("role") || "0",
      formato: "json",
      force_refresh: formData.get("force_refresh") === "on" ? "true" : "false",
    });
    const response = await fetch(`/procesar_producto?${params.toString()}`);
    const data = await parseResponse(response);
    setStatus(
      `${data.desde_cache ? "Cache" : "Nuevo"} / Run: ${data.run_id} / Paginas: ${data.paginas_detectadas} / Tablas: ${data.tablas_detectadas} / Imagenes: ${data.imagenes_analizadas || 0}`
    );
    fields.result.textContent = formatProcessingResult(data);
    await loadAnalytics();
  } catch (error) {
    setError(error.message);
  }
});

document.querySelector("#refresh-list").addEventListener("click", loadAssistants);
document.querySelector("#refresh-analytics").addEventListener("click", loadAnalytics);

fields.cmid.addEventListener("change", () => {
  fields.testCmid.value = fields.cmid.value;
  checkExistingCmid();
});

function fillAssistantForm(cmid, assistant, mode = "edit") {
  fields.cmid.value = cmid;
  fields.testCmid.value = cmid;
  fields.nombre.value = assistant.nombre;
  fields.descripcion.value = assistant.descripcion_producto;
  fields.contextoCurso.value = assistant.contexto_curso || "";
  fields.ejemploProducto.value = assistant.ejemplo_producto || "";
  fields.analizaTexto.checked = assistant.analiza_texto !== false;
  fields.analizaTablas.checked = assistant.analiza_tablas !== false;
  fields.analizaImagenes.checked = assistant.analiza_imagenes === true;
  fields.usaCmidRelacionado.checked = assistant.usa_cmid_relacionado === true;
  fields.cmidRelacionado.value = assistant.cmid_relacionado || "";
  fields.validarDocumento.checked = assistant.validar_documento !== false;
  fields.validarSimilitud.checked = assistant.validar_similitud !== false;
  fields.rubrica.value = JSON.stringify(assistant.rubrica, null, 2);
  fields.perfil.value = assistant.perfil_retroalimentacion.join("\n");
  fields.modelo.value = assistant.modelo || "";
  formMode = mode;
  loadedCmid = mode === "edit" ? String(cmid) : null;
}

function readAssistantPayload() {
  return {
    nombre: fields.nombre.value.trim(),
    descripcion_producto: fields.descripcion.value.trim(),
    contexto_curso: fields.contextoCurso.value.trim() || null,
    ejemplo_producto: fields.ejemploProducto.value.trim() || null,
    analiza_texto: fields.analizaTexto.checked,
    analiza_tablas: fields.analizaTablas.checked,
    analiza_imagenes: fields.analizaImagenes.checked,
    usa_cmid_relacionado: fields.usaCmidRelacionado.checked,
    cmid_relacionado: fields.cmidRelacionado.value ? Number(fields.cmidRelacionado.value) : null,
    validar_documento: fields.validarDocumento.checked,
    validar_similitud: fields.validarSimilitud.checked,
    rubrica: JSON.parse(fields.rubrica.value),
    perfil_retroalimentacion: fields.perfil.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    modelo: fields.modelo.value.trim() || null,
    activo: true,
  };
}

async function loadAssistants() {
  try {
    const response = await fetch("/asistentes");
    const assistants = await parseResponse(response);
    renderAssistants(assistants);
  } catch (error) {
    fields.list.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

async function checkExistingCmid() {
  const cmid = fields.cmid.value;
  if (!cmid) return;

  try {
    const response = await fetch(`/asistentes/${cmid}`);
    if (response.status === 404) {
      formMode = "create";
      loadedCmid = null;
      setStatus(`CMID ${cmid} disponible para crear.`);
      return;
    }
    const assistant = await parseResponse(response);
    fillAssistantForm(assistant.cmid, assistant, "edit");
    setStatus(`El CMID ${assistant.cmid} ya existe. Se cargo para editar, no para crear duplicado.`);
  } catch (error) {
    setError(error.message);
  }
}

async function loadAnalytics() {
  try {
    const response = await fetch("/analitica?limit=100&minutes=5");
    const runs = await parseResponse(response);
    renderAnalytics(runs);
  } catch (error) {
    fields.analytics.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

function renderAssistants(assistants) {
  if (!assistants.length) {
    fields.list.innerHTML = "<p>Todavia no hay CMID configurados.</p>";
    return;
  }

  fields.list.innerHTML = assistants
    .map(
      (assistant) => `
        <article class="assistant-card">
          <strong>CMID ${assistant.cmid}: ${escapeHtml(assistant.nombre)}</strong>
          <p>${assistant.rubrica.length} criterios de rubrica</p>
          <p>Modo: ${analysisModeLabel(assistant)}</p>
          ${assistant.usa_cmid_relacionado ? `<p>Relacionado: CMID ${assistant.cmid_relacionado || "-"}</p>` : ""}
          <p>${assistant.perfil_retroalimentacion.length} orientaciones</p>
          <button type="button" data-cmid="${assistant.cmid}">Editar</button>
        </article>
      `
    )
    .join("");

  fields.list.querySelectorAll("button[data-cmid]").forEach((button) => {
    button.addEventListener("click", async () => {
      const response = await fetch(`/asistentes/${button.dataset.cmid}`);
      const assistant = await parseResponse(response);
      fillAssistantForm(assistant.cmid, assistant, "edit");
      setStatus(`Editando CMID ${assistant.cmid}.`);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function renderAnalytics(runs) {
  if (!runs.length) {
    fields.analytics.innerHTML = "<p>Todavia no hay ejecuciones registradas.</p>";
    return;
  }

  fields.analytics.innerHTML = runs
    .map(
      (run) => `
        <article class="assistant-card">
          <strong>${escapeHtml(run.status)} - CMID ${run.cmid}</strong>
          <p>Run: ${escapeHtml(run.id)}</p>
          <p>Usuario ${run.user_id} - Curso ${run.course_id} - ${escapeHtml(run.nombre)}</p>
          <p>Tiempo: ${run.total_ms ?? "-"} ms - Etapa: ${escapeHtml(run.stage)}</p>
          ${run.error_message ? `<p class="error-text">${escapeHtml(run.error_message)}</p>` : ""}
          <button type="button" data-run-id="${run.id}">Ver detalle JSON</button>
        </article>
      `
    )
    .join("");

  fields.analytics.querySelectorAll("button[data-run-id]").forEach((button) => {
    button.addEventListener("click", () => {
      window.open(`/analitica/${button.dataset.runId}`, "_blank", "noopener,noreferrer");
    });
  });
}

function formatProcessingResult(data) {
  const rubric = (data.evaluacion_rubrica || [])
    .map(
      (item) =>
        `${item.criterion_index}. ${item.criterio}\n   Descripcion: ${item.descripcion_criterio || "-"}\n   Nivel: ${item.nivel_obtenido || "-"}\n   Evidencia: ${item.evidencia || "-"}\n   Recomendacion: ${item.recomendacion || "-"}`
    )
    .join("\n\n");

  return [
    `RUN ID: ${data.run_id}`,
    `Origen: ${data.desde_cache ? "retroalimentacion guardada" : "generado ahora"}`,
    `Rol: ${data.role === 1 ? "validador" : "usuario"}`,
    `Validacion: ${data.validation_passed === false ? "rechazada" : "aprobada"}`,
    data.validation_reason ? `Motivo validacion: ${data.validation_reason}` : "",
    data.cmid_relacionado ? `CMID relacionado: ${data.cmid_relacionado}` : "",
    data.similarity_score != null ? `Similitud: ${data.similarity_score}` : "",
    `Modelo: ${data.modelo || "-"}`,
    `Tiempo total: ${data.total_ms || "-"} ms`,
    `Imagenes analizadas: ${data.imagenes_analizadas || 0}`,
    `Tokens: ${data.total_tokens || "-"}`,
    "",
    cleanDisplayText(data.retroalimentacion),
    rubric ? "\nEVALUACION POR RUBRICA\n" + rubric : "",
  ].join("\n");
}

function analysisModeLabel(assistant) {
  const modes = [];
  if (assistant.analiza_texto !== false) modes.push("texto");
  if (assistant.analiza_tablas !== false) modes.push("tablas");
  if (assistant.analiza_imagenes === true) modes.push("imagenes");
  return modes.join(" + ") || "sin contenido";
}

async function parseResponse(response) {
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    throw new Error(detail || `Error HTTP ${response.status}`);
  }
  return data;
}

function setStatus(message) {
  fields.status.classList.remove("error");
  fields.status.textContent = message;
}

function setError(message) {
  fields.status.classList.add("error");
  fields.status.textContent = "Error";
  fields.result.textContent = message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanDisplayText(value) {
  return String(value ?? "")
    .replaceAll("\\r\\n", "\n")
    .replaceAll("\\n", "\n")
    .replaceAll("\\t", " ")
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(p|div|li|h[1-6])\s*>/gi, "\n")
    .replace(/<\s*li\s*>/gi, "- ")
    .replace(/<[^>]+>/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

fillAssistantForm(194522, demoAssistant, "create");
loadAssistants();
loadAnalytics();
