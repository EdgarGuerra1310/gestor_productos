const demoAssistant = {
  nombre: "Calendario comunal EIB",
  cmids: [194522],
  descripcion_producto:
    "El calendario comunal es una herramienta pedagogica fundamental en Educacion Inicial EIB para ambito rural. Organiza actividades socioculturales y socioproductivas de la comunidad, saberes asociados, problemas del contexto y aliados posibles. Sirve como insumo para una planificacion curricular pertinente y para promover dialogo de saberes.",
  contexto_curso:
    "Unidad 1, sesion 2: se aborda el calendario comunal como herramienta para recoger actividades socioculturales y socioproductivas, saberes comunitarios, problemas del contexto y aliados. Se relaciona con la planificacion curricular pertinente y el dialogo de saberes en Educacion Inicial EIB.",
  ejemplo_producto:
    "Ejemplo de referencia: un calendario organizado por epocas o meses, con columnas para actividades de la comunidad, saberes asociados, problemas o potencialidades, aliados y posibilidades pedagogicas. Debe evidenciar actividades como siembra, cosecha, festividades, preparacion de alimentos u otras practicas propias de la comunidad.",
  analiza_texto: true,
  analiza_tablas: true,
  analiza_imagenes: false,
  dependencias: {},
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
  programa_id: null,
  curso_id: null,
  activo: true,
};

function main() {
const fields = {
  testCmid: document.querySelector("#test-cmid"),
  nombre: document.querySelector("#nombre-asistente"),
  descripcion: document.querySelector("#descripcion-producto"),
  contextoCurso: document.querySelector("#contexto-curso"),
  ejemploProducto: document.querySelector("#ejemplo-producto"),
  analizaTexto: document.querySelector("#analiza-texto"),
  analizaTablas: document.querySelector("#analiza-tablas"),
  analizaImagenes: document.querySelector("#analiza-imagenes"),
  dependenciasList: document.querySelector("#dependencias-list"),
  validarDocumento: document.querySelector("#validar-documento"),
  validarSimilitud: document.querySelector("#validar-similitud"),
  rubrica: document.querySelector("#rubrica"),
  perfil: document.querySelector("#perfil"),
  modelo: document.querySelector("#modelo"),
  status: document.querySelector("#status"),
  result: document.querySelector("#result"),
  list: document.querySelector("#assistant-list"),
  search: document.querySelector("#assistant-search"),
};

const programaSelect = document.querySelector("#programa-select");
const cursoSelect = document.querySelector("#curso-select");
const newCursoProgramaSelect = document.querySelector("#new-curso-programa");

let formMode = "create";
let loadedId = null;
let cachedAssistants = [];
let cachedCourses = [];
// Dependencias por CMID del asistente: { cmid: [cmids preliminares] }.
let dependencies = {};

function createCmidPicker(prefix, onAdd, onMoodleSelect, onChange) {
  const chipsEl = document.querySelector(`#${prefix}-chips`);
  const manualInput = document.querySelector(`#${prefix}-manual`);
  const manualAddBtn = document.querySelector(`#${prefix}-manual-add`);
  const courseIdInput = document.querySelector(`#${prefix}-course-id`);
  const filterInput = document.querySelector(`#${prefix}-filter-text`);
  const searchBtn = document.querySelector(`#${prefix}-search-btn`);
  const resultsEl = document.querySelector(`#${prefix}-results`);

  let cmids = [];

  function render() {
    chipsEl.innerHTML = cmids.length
      ? cmids
          .map(
            (cmid) => `
        <span class="chip">${cmid}<button type="button" data-remove="${cmid}" aria-label="Quitar ${cmid}">&times;</button></span>
      `
          )
          .join("")
      : '<span class="chip-empty">Sin CMID agregados</span>';

    chipsEl.querySelectorAll("button[data-remove]").forEach((button) => {
      button.addEventListener("click", () => {
        const value = Number(button.dataset.remove);
        cmids = cmids.filter((cmid) => cmid !== value);
        render();
      });
    });

    if (typeof onChange === "function") onChange([...cmids]);
  }

  function addMany(values, { silent = false } = {}) {
    const added = [];
    for (const raw of values) {
      const value = Number(String(raw).trim());
      if (Number.isInteger(value) && value > 0 && !cmids.includes(value)) {
        cmids.push(value);
        added.push(value);
      }
    }
    render();
    if (!silent && added.length && typeof onAdd === "function") {
      onAdd(added);
    }
  }

  function remove(cmid) {
    cmids = cmids.filter((value) => value !== cmid);
    render();
  }

  manualAddBtn.addEventListener("click", () => {
    addMany(manualInput.value.split(","));
    manualInput.value = "";
  });

  manualInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addMany(manualInput.value.split(","));
      manualInput.value = "";
    }
  });

  searchBtn.addEventListener("click", async () => {
    const courseId = courseIdInput.value;
    if (!courseId) {
      resultsEl.innerHTML = '<p class="error-text">Escribe un Course ID primero.</p>';
      return;
    }
    resultsEl.innerHTML = "<p>Buscando actividades...</p>";
    try {
      const params = new URLSearchParams();
      if (filterInput.value.trim()) params.set("q", filterInput.value.trim());
      const response = await fetch(`/moodle/cursos/${courseId}/actividades?${params.toString()}`);
      const activities = await parseResponse(response);
      if (!activities.length) {
        resultsEl.innerHTML = "<p>No se encontraron tareas para ese curso/filtro.</p>";
        return;
      }
      resultsEl.innerHTML = `
        <div class="moodle-results-list">
          ${activities
            .map(
              (activity) => `
            <label class="check-row moodle-result-item">
              <input type="checkbox" value="${activity.cmid}" data-name="${escapeHtml(activity.name)}" />
              <span>${activity.cmid} - ${escapeHtml(activity.name)}${
                activity.section ? ` &middot; ${escapeHtml(activity.section)}` : ""
              }</span>
            </label>
          `
            )
            .join("")}
        </div>
        <button type="button" class="add-selected">Agregar seleccionados</button>
      `;
      resultsEl.querySelector(".add-selected").addEventListener("click", () => {
        const checkedInputs = Array.from(resultsEl.querySelectorAll("input[type=checkbox]:checked"));
        addMany(checkedInputs.map((input) => input.value));
        if (checkedInputs.length && typeof onMoodleSelect === "function") {
          onMoodleSelect(checkedInputs.map((input) => ({ cmid: Number(input.value), name: input.dataset.name || "" })));
        }
      });
    } catch (error) {
      resultsEl.innerHTML = `<p class="error-text">${escapeHtml(error.message)}</p>`;
    }
  });

  render();

  return {
    get: () => [...cmids],
    set: (values) => {
      cmids = [];
      addMany(values || [], { silent: true });
    },
    // Agrega lo que quedo escrito en el campo manual sin presionar "Agregar".
    flushPending: () => {
      if (manualInput.value.trim()) {
        addMany(manualInput.value.split(","), { silent: true });
        manualInput.value = "";
      }
    },
    remove,
  };
}

const cmidsPicker = createCmidPicker(
  "cmids",
  handlePrimaryCmidsAdded,
  handleCmidsSelectedFromMoodle,
  renderDependencies
);

function parseCmidList(text) {
  return String(text || "")
    .split(",")
    .map((raw) => Number(raw.trim()))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function addDependencies(cmid, values) {
  const current = dependencies[cmid] || [];
  for (const value of values) {
    if (value !== cmid && !current.includes(value)) current.push(value);
  }
  dependencies[cmid] = current;
}

function normalizeDependencies(assistant) {
  const result = {};
  const source = assistant.dependencias || {};
  for (const [key, values] of Object.entries(source)) {
    result[Number(key)] = (values || []).map(Number);
  }
  // Asistentes antiguos: una sola lista para todos sus CMID.
  if (!Object.keys(source).length && assistant.usa_cmid_relacionado && (assistant.cmids_relacionados || []).length) {
    for (const cmid of assistant.cmids || []) {
      result[cmid] = assistant.cmids_relacionados.filter((value) => value !== cmid);
    }
  }
  return result;
}

function renderDependencies(cmids = cmidsPicker.get()) {
  const container = fields.dependenciasList;
  if (!cmids.length) {
    container.innerHTML =
      '<p class="chip-empty">Primero agrega los CMID del asistente (seccion 1); aqui aparecera una fila por cada uno.</p>';
  } else {
    container.innerHTML = cmids
      .map((cmid) => {
        const related = dependencies[cmid] || [];
        const chips = related.length
          ? related
              .map(
                (value) =>
                  `<span class="chip">${value}<button type="button" data-dep-remove="${cmid}:${value}" aria-label="Quitar ${value}">&times;</button></span>`
              )
              .join("")
          : '<span class="chip-empty">Sin dependencia</span>';
        return `
          <div class="dep-row">
            <div class="dep-head"><span class="badge badge-cmid">${cmid}</span> depende de:</div>
            <div class="chip-list">${chips}</div>
            <div class="chip-input-row">
              <input type="text" data-dep-input="${cmid}" placeholder="CMID preliminares de ${cmid}, separados por coma" />
              <button type="button" data-dep-add="${cmid}">Agregar</button>
            </div>
          </div>
        `;
      })
      .join("");
  }

  container.querySelectorAll("button[data-dep-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const [cmid, value] = button.dataset.depRemove.split(":").map(Number);
      dependencies[cmid] = (dependencies[cmid] || []).filter((item) => item !== value);
      renderDependencies();
    });
  });

  container.querySelectorAll("input[data-dep-input]").forEach((input) => {
    const cmid = Number(input.dataset.depInput);
    const add = () => {
      addDependencies(cmid, parseCmidList(input.value));
      renderDependencies();
    };
    container.querySelector(`button[data-dep-add="${cmid}"]`).addEventListener("click", add);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        add();
      }
    });
  });

  const target = document.querySelector("#dep-target");
  if (target) fillDependencyTarget(target, cmids);
}

function flushDependencyInputs() {
  fields.dependenciasList.querySelectorAll("input[data-dep-input]").forEach((input) => {
    if (input.value.trim()) addDependencies(Number(input.dataset.depInput), parseCmidList(input.value));
  });
}

function fillDependencyTarget(select, cmids = cmidsPicker.get()) {
  const previous = select.value;
  select.innerHTML = cmids.map((cmid) => `<option value="${cmid}">${cmid}</option>`).join("");
  if (cmids.map(String).includes(previous)) select.value = previous;
}

document.querySelector("#dep-search-btn").addEventListener("click", async () => {
  const resultsEl = document.querySelector("#dep-results");
  const courseId = document.querySelector("#dep-course-id").value;
  const filterText = document.querySelector("#dep-filter-text").value.trim();
  if (!courseId) {
    resultsEl.innerHTML = '<p class="error-text">Escribe un Course ID primero.</p>';
    return;
  }
  resultsEl.innerHTML = "<p>Buscando actividades...</p>";
  try {
    const params = new URLSearchParams();
    if (filterText) params.set("q", filterText);
    const response = await fetch(`/moodle/cursos/${courseId}/actividades?${params.toString()}`);
    const activities = await parseResponse(response);
    if (!activities.length) {
      resultsEl.innerHTML = "<p>No se encontraron tareas para ese curso/filtro.</p>";
      return;
    }
    resultsEl.innerHTML = `
      <div class="moodle-results-list">
        ${activities
          .map(
            (activity) => `
          <label class="check-row moodle-result-item">
            <input type="checkbox" value="${activity.cmid}" />
            <span>${activity.cmid} - ${escapeHtml(activity.name)}${
              activity.section ? ` &middot; ${escapeHtml(activity.section)}` : ""
            }</span>
          </label>
        `
          )
          .join("")}
      </div>
      <div class="dep-target-row">
        <span>Agregar como dependencia del CMID</span>
        <select id="dep-target"></select>
        <button type="button" class="add-selected">Agregar seleccionados</button>
      </div>
    `;
    fillDependencyTarget(resultsEl.querySelector("#dep-target"));
    resultsEl.querySelector(".add-selected").addEventListener("click", () => {
      const target = Number(resultsEl.querySelector("#dep-target").value);
      if (!target) {
        setError("Primero agrega los CMID del asistente (seccion 1) para asignarles dependencias.");
        return;
      }
      const checked = Array.from(resultsEl.querySelectorAll("input[type=checkbox]:checked"));
      addDependencies(target, checked.map((input) => Number(input.value)));
      checked.forEach((input) => {
        input.checked = false;
      });
      renderDependencies();
    });
  } catch (error) {
    resultsEl.innerHTML = `<p class="error-text">${escapeHtml(error.message)}</p>`;
  }
});

function handleCmidsSelectedFromMoodle(activities) {
  if (!activities.length) return;
  const name = (activities[0].name || "").replace(/\/+\s*$/, "").trim();
  if (name) {
    fields.nombre.value = name;
  }
}

document.querySelector("#load-demo").addEventListener("click", async () => {
  fillAssistantForm(demoAssistant, "create");
  setStatus("Ejemplo cargado. Cambia los CMID si crearas una configuracion nueva.");
  await checkExistingCmid(194522);
});

document.querySelector("#new-assistant-btn").addEventListener("click", () => {
  resetAssistantForm();
  setStatus("Formulario limpio. Completa los datos y elige CMID para crear un asistente nuevo.");
  scrollToEditor();
});

document.querySelector("#duplicate-assistant-btn").addEventListener("click", () => {
  if (formMode !== "edit" || !loadedId) {
    setStatus("Primero carga un asistente existente para poder duplicarlo.");
    return;
  }

  let snapshot;
  try {
    snapshot = readAssistantPayload();
  } catch (error) {
    setError(`No se pudo leer la rubrica actual: ${error.message}`);
    return;
  }

  const programaId = snapshot.programa_id;
  const cursoId = snapshot.curso_id;

  resetAssistantForm();
  fields.nombre.value = snapshot.nombre ? `${snapshot.nombre} (copia)` : "";
  fields.descripcion.value = snapshot.descripcion_producto || "";
  fields.contextoCurso.value = snapshot.contexto_curso || "";
  fields.ejemploProducto.value = snapshot.ejemplo_producto || "";
  fields.analizaTexto.checked = snapshot.analiza_texto;
  fields.analizaTablas.checked = snapshot.analiza_tablas;
  fields.analizaImagenes.checked = snapshot.analiza_imagenes;
  fields.validarDocumento.checked = snapshot.validar_documento;
  fields.validarSimilitud.checked = snapshot.validar_similitud;
  fields.rubrica.value = JSON.stringify(snapshot.rubrica, null, 2);
  fields.perfil.value = (snapshot.perfil_retroalimentacion || []).join("\n");
  fields.modelo.value = snapshot.modelo || "";
  if (programaId != null) programaSelect.value = String(programaId);
  loadCourses(programaId != null ? programaId : null).then(() => {
    if (cursoId != null) cursoSelect.value = String(cursoId);
  });

  setStatus("Asistente duplicado como borrador nuevo (los CMID no se copian). Elige uno o mas CMID y guarda para crearlo.");
  scrollToEditor();
});

async function handlePrimaryCmidsAdded(addedCmids) {
  for (const cmid of addedCmids) {
    let assistant;
    try {
      const response = await fetch(`/asistentes/por-cmid/${cmid}`);
      if (response.status === 404) continue;
      assistant = await parseResponse(response);
    } catch (error) {
      setError(error.message);
      continue;
    }

    if (formMode === "edit" && loadedId === assistant.id) continue;

    if (formMode === "create" && cmidsPicker.get().length === 1) {
      fillAssistantForm(assistant, "edit");
      setStatus(`El CMID ${cmid} ya tenia un asistente guardado ("${assistant.nombre}", ID ${assistant.id}). Se cargo para editar.`);
    } else {
      cmidsPicker.remove(cmid);
      setError(
        `El CMID ${cmid} ya pertenece al asistente "${assistant.nombre}" (ID ${assistant.id}). Se quito de la lista; edita ese asistente en su lugar desde "CMID configurados".`
      );
    }
  }
}

document.querySelector("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus(formMode === "edit" ? "Actualizando configuracion..." : "Creando configuracion...");

  try {
    cmidsPicker.flushPending();
    flushDependencyInputs();
    if (!cmidsPicker.get().length) {
      setError(
        'Falta el CMID del asistente (seccion 1). Escribelo y presiona "Agregar" o Enter, o buscalo por codigo de aula. La dependencia de otros CMID (seccion 6) es opcional.'
      );
      document.querySelector("#cmids-chips").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const payload = readAssistantPayload();
    const method = formMode === "edit" ? "PUT" : "POST";
    const url = formMode === "edit" ? `/asistentes/${loadedId}` : "/asistentes";
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await parseResponse(response);
    formMode = "edit";
    loadedId = data.id;
    updateModeBadge("edit", data.id);
    if (data.cmids && data.cmids.length) {
      fields.testCmid.value = data.cmids[0];
    }
    setStatus(method === "POST" ? `Asistente creado (ID ${data.id}).` : `Asistente actualizado (ID ${data.id}).`);
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
  } catch (error) {
    setError(error.message);
  }
});

document.querySelector("#refresh-list").addEventListener("click", loadAssistants);

fields.search.addEventListener("input", () => {
  renderAssistants(filterAssistants(cachedAssistants, fields.search.value));
});

programaSelect.addEventListener("change", async () => {
  await loadCourses(programaSelect.value ? Number(programaSelect.value) : null);
});

document.querySelector("#new-programa-btn").addEventListener("click", async () => {
  const nombre = document.querySelector("#new-programa-nombre").value.trim();
  if (!nombre) return;
  try {
    const response = await fetch("/programas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre }),
    });
    const program = await parseResponse(response);
    document.querySelector("#new-programa-nombre").value = "";
    await loadPrograms();
    programaSelect.value = String(program.id);
    await loadCourses(program.id);
    setStatus(`Programa "${program.nombre}" creado.`);
  } catch (error) {
    setError(error.message);
  }
});

document.querySelector("#new-curso-btn").addEventListener("click", async () => {
  const programaId = Number(newCursoProgramaSelect.value);
  const courseId = Number(document.querySelector("#new-curso-course-id").value);
  const statusEl = document.querySelector("#new-curso-status");
  if (!programaId || !courseId) {
    statusEl.textContent = "Selecciona un programa y escribe un course_id valido.";
    statusEl.classList.add("error-text");
    return;
  }
  statusEl.classList.remove("error-text");
  statusEl.textContent = "Buscando nombre del curso en Moodle...";
  try {
    const response = await fetch("/cursos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ programa_id: programaId, course_id: courseId }),
    });
    const course = await parseResponse(response);
    statusEl.textContent = `Curso guardado: ${course.nombre}`;
    document.querySelector("#new-curso-course-id").value = "";
    await loadCourses(programaSelect.value ? Number(programaSelect.value) : null);
  } catch (error) {
    statusEl.classList.add("error-text");
    statusEl.textContent = error.message;
  }
});

document.querySelector("#generar-borrador-btn").addEventListener("click", async () => {
  const filesInput = document.querySelector("#evidencia-files");
  const statusEl = document.querySelector("#borrador-status");
  if (!filesInput.files.length) {
    statusEl.classList.add("error-text");
    statusEl.textContent = "Selecciona al menos un documento de evidencia (PDF o Word).";
    return;
  }
  statusEl.classList.remove("error-text");
  statusEl.textContent = "Generando borrador con IA, esto puede tardar unos segundos...";

  try {
    const formData = new FormData();
    for (const file of filesInput.files) {
      formData.append("files", file);
    }
    const response = await fetch("/asistentes/generar-borrador", { method: "POST", body: formData });
    const draft = await parseResponse(response);

    if (draft.descripcion_producto) fields.descripcion.value = draft.descripcion_producto;
    if (draft.contexto_curso) fields.contextoCurso.value = draft.contexto_curso;
    if (draft.ejemplo_producto) fields.ejemploProducto.value = draft.ejemplo_producto;
    if (draft.rubrica && draft.rubrica.length) fields.rubrica.value = JSON.stringify(draft.rubrica, null, 2);
    if (draft.perfil_retroalimentacion && draft.perfil_retroalimentacion.length) {
      fields.perfil.value = draft.perfil_retroalimentacion.join("\n");
    }

    const incompleteLabels = {
      descripcion_producto: "Descripcion del producto",
      contexto_curso: "Contexto del curso",
      ejemplo_producto: "Ejemplo del producto",
      rubrica: "Rubrica",
      perfil_retroalimentacion: "Perfil de retroalimentacion",
    };
    const incompletos = (draft.campos_incompletos || []).map((key) => incompleteLabels[key] || key);

    if (incompletos.length) {
      statusEl.classList.add("error-text");
      statusEl.textContent = `Borrador generado, pero los documentos no tenian suficiente informacion para: ${incompletos.join(", ")}. Completa esos campos a mano antes de guardar.`;
    } else {
      statusEl.classList.remove("error-text");
      statusEl.textContent = "Borrador generado con todos los campos. Revisa y ajusta antes de guardar.";
    }
  } catch (error) {
    statusEl.classList.add("error-text");
    statusEl.textContent = error.message;
  }
});

function fillAssistantForm(assistant, mode = "edit") {
  dependencies = normalizeDependencies(assistant);
  cmidsPicker.set(assistant.cmids || []);
  if (assistant.cmids && assistant.cmids.length) {
    fields.testCmid.value = assistant.cmids[0];
  }
  fields.nombre.value = assistant.nombre;
  fields.descripcion.value = assistant.descripcion_producto;
  fields.contextoCurso.value = assistant.contexto_curso || "";
  fields.ejemploProducto.value = assistant.ejemplo_producto || "";
  fields.analizaTexto.checked = assistant.analiza_texto !== false;
  fields.analizaTablas.checked = assistant.analiza_tablas !== false;
  fields.analizaImagenes.checked = assistant.analiza_imagenes === true;
  fields.validarDocumento.checked = assistant.validar_documento !== false;
  fields.validarSimilitud.checked = assistant.validar_similitud !== false;
  fields.rubrica.value = JSON.stringify(assistant.rubrica, null, 2);
  fields.perfil.value = assistant.perfil_retroalimentacion.join("\n");
  fields.modelo.value = assistant.modelo || "";

  programaSelect.value = assistant.programa_id != null ? String(assistant.programa_id) : "";
  loadCourses(assistant.programa_id != null ? assistant.programa_id : null).then(() => {
    cursoSelect.value = assistant.curso_id != null ? String(assistant.curso_id) : "";
  });

  formMode = mode;
  loadedId = mode === "edit" ? assistant.id : null;
  updateModeBadge(mode, assistant.id);
}

function updateModeBadge(mode, id) {
  const badge = document.querySelector("#form-mode-badge");
  const duplicateBtn = document.querySelector("#duplicate-assistant-btn");
  if (mode === "edit") {
    badge.textContent = `Editando asistente ID ${id}`;
    badge.classList.remove("mode-badge-create");
    badge.classList.add("mode-badge-edit");
    duplicateBtn.disabled = false;
  } else {
    badge.textContent = "Nuevo asistente";
    badge.classList.remove("mode-badge-edit");
    badge.classList.add("mode-badge-create");
    duplicateBtn.disabled = true;
  }
}

function resetAssistantForm() {
  dependencies = {};
  cmidsPicker.set([]);
  fields.nombre.value = "";
  fields.descripcion.value = "";
  fields.contextoCurso.value = "";
  fields.ejemploProducto.value = "";
  fields.analizaTexto.checked = true;
  fields.analizaTablas.checked = true;
  fields.analizaImagenes.checked = false;
  fields.validarDocumento.checked = true;
  fields.validarSimilitud.checked = true;
  fields.rubrica.value = "";
  fields.perfil.value = "";
  fields.modelo.value = "";
  programaSelect.value = "";
  cursoSelect.innerHTML = '<option value="">Sin curso</option>';
  const borradorStatus = document.querySelector("#borrador-status");
  if (borradorStatus) borradorStatus.textContent = "";
  formMode = "create";
  loadedId = null;
  updateModeBadge("create", null);
}

function readAssistantPayload() {
  const cmids = cmidsPicker.get();
  const dependencias = Object.fromEntries(cmids.map((cmid) => [cmid, dependencies[cmid] || []]));
  const cmidsRelacionados = [...new Set(Object.values(dependencias).flat())].sort((a, b) => a - b);
  return {
    nombre: fields.nombre.value.trim(),
    cmids,
    descripcion_producto: fields.descripcion.value.trim(),
    contexto_curso: fields.contextoCurso.value.trim() || null,
    ejemplo_producto: fields.ejemploProducto.value.trim() || null,
    analiza_texto: fields.analizaTexto.checked,
    analiza_tablas: fields.analizaTablas.checked,
    analiza_imagenes: fields.analizaImagenes.checked,
    usa_cmid_relacionado: cmidsRelacionados.length > 0,
    cmids_relacionados: cmidsRelacionados,
    dependencias,
    validar_documento: fields.validarDocumento.checked,
    validar_similitud: fields.validarSimilitud.checked,
    rubrica: JSON.parse(fields.rubrica.value),
    perfil_retroalimentacion: fields.perfil.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    modelo: fields.modelo.value.trim() || null,
    programa_id: programaSelect.value ? Number(programaSelect.value) : null,
    curso_id: cursoSelect.value ? Number(cursoSelect.value) : null,
    activo: true,
  };
}

async function loadAssistants() {
  const countLabel = document.querySelector("#assistant-count-label");
  try {
    const response = await fetch("/asistentes");
    const assistants = await parseResponse(response);
    cachedAssistants = assistants;
    renderAssistants(filterAssistants(cachedAssistants, fields.search.value));
    if (countLabel) {
      countLabel.textContent = `${assistants.length} asistente${assistants.length === 1 ? "" : "s"} configurado${assistants.length === 1 ? "" : "s"}`;
    }
  } catch (error) {
    fields.list.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    if (countLabel) countLabel.textContent = "Error al cargar";
  }
}

function filterAssistants(assistants, term) {
  const needle = (term || "").trim().toLowerCase();
  if (!needle) return assistants;
  return assistants.filter((assistant) => {
    const haystack = [
      assistant.nombre,
      ...(assistant.cmids || []).map(String),
      assistant.programa_nombre || "",
      assistant.curso_nombre || "",
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

async function checkExistingCmid(cmid, notifyIfMissing = false) {
  if (!cmid) return;
  try {
    const response = await fetch(`/asistentes/por-cmid/${cmid}`);
    if (response.status === 404) {
      if (notifyIfMissing) setStatus(`No hay ningun asistente configurado con el cmid ${cmid}.`);
      return;
    }
    const assistant = await parseResponse(response);
    fillAssistantForm(assistant, "edit");
    setStatus(`Se cargo el asistente ID ${assistant.id} (incluye el cmid ${cmid}).`);
    scrollToEditor();
  } catch (error) {
    setError(error.message);
  }
}

async function loadPrograms() {
  try {
    const response = await fetch("/programas");
    const programs = await parseResponse(response);
    const options = programs.map((program) => `<option value="${program.id}">${escapeHtml(program.nombre)}</option>`);
    programaSelect.innerHTML = `<option value="">Sin programa</option>${options.join("")}`;
    newCursoProgramaSelect.innerHTML = options.join("") || "<option value=''>Crea un programa primero</option>";
  } catch (error) {
    setError(error.message);
  }
}

async function loadCourses(programaId) {
  try {
    const params = new URLSearchParams();
    if (programaId) params.set("programa_id", programaId);
    const response = await fetch(`/cursos?${params.toString()}`);
    const courses = await parseResponse(response);
    cachedCourses = courses;
    cursoSelect.innerHTML = `<option value="">Sin curso</option>${courses
      .map(
        (course) =>
          `<option value="${course.id}">${escapeHtml(course.nombre)} (curid ${course.course_id}${
            course.programa_nombre ? " - " + escapeHtml(course.programa_nombre) : ""
          })</option>`
      )
      .join("")}`;
  } catch (error) {
    setError(error.message);
  }
}

function renderAssistants(assistants) {
  if (!assistants.length) {
    fields.list.innerHTML = "<p>No hay CMID configurados que coincidan.</p>";
    return;
  }

  fields.list.innerHTML = assistants
    .map((assistant) => {
      const cmidBadges = (assistant.cmids || [])
        .map((cmid) => `<span class="badge badge-cmid">${cmid}</span>`)
        .join("");
      const programaBadge = assistant.programa_nombre
        ? `<span class="badge badge-programa">${escapeHtml(assistant.programa_nombre)}</span>`
        : "";
      const cursoBadge = assistant.curso_nombre
        ? `<span class="badge badge-curso">${escapeHtml(assistant.curso_nombre)}</span>`
        : "";
      const relatedBadges = Object.entries(normalizeDependencies(assistant))
        .filter(([, values]) => values.length)
        .map(
          ([cmid, values]) =>
            `<span class="badge badge-related">${cmid} depende de: ${values.join(", ")}</span>`
        )
        .join("");
      return `
        <article class="assistant-card">
          <strong>${escapeHtml(assistant.nombre)}</strong>
          <div class="badge-row">${cmidBadges}</div>
          ${programaBadge || cursoBadge ? `<div class="badge-row">${programaBadge}${cursoBadge}</div>` : ""}
          ${relatedBadges ? `<div class="badge-row">${relatedBadges}</div>` : ""}
          <p>${assistant.rubrica.length} criterios de rubrica &middot; ${assistant.perfil_retroalimentacion.length} orientaciones</p>
          <p>Modo: ${analysisModeLabel(assistant)}</p>
          <div class="card-actions">
            <button type="button" data-id="${assistant.id}">Editar</button>
            <button type="button" class="ghost" data-report-id="${assistant.id}">Ver reporte</button>
          </div>
        </article>
      `;
    })
    .join("");

  fields.list.querySelectorAll("button[data-report-id]").forEach((button) => {
    button.addEventListener("click", () => {
      window.dispatchEvent(
        new CustomEvent("abrir-reporte", { detail: { assistant_id: Number(button.dataset.reportId) } })
      );
    });
  });

  fields.list.querySelectorAll("button[data-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const response = await fetch(`/asistentes/${button.dataset.id}`);
      const assistant = await parseResponse(response);
      fillAssistantForm(assistant, "edit");
      setStatus(`Editando asistente ID ${assistant.id}.`);
      scrollToEditor();
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
    data.cmids_relacionados && data.cmids_relacionados.length
      ? `CMID relacionados: ${data.cmids_relacionados.join(", ")}`
      : "",
    data.similarity_score != null ? `Similitud maxima: ${data.similarity_score}` : "",
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
  if (window.notify) window.notify(message, "info");
}

function setError(message) {
  fields.status.classList.add("error");
  fields.status.textContent = "Error";
  fields.result.textContent = message;
  if (window.notify) window.notify(message, "error");
}

function scrollToEditor() {
  const editor = document.querySelector(".manager-panel");
  if (editor) editor.scrollIntoView({ behavior: "smooth", block: "start" });
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

async function init() {
  await loadPrograms();
  await loadCourses(null);
  fillAssistantForm(demoAssistant, "create");
  await loadAssistants();
}

init();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
