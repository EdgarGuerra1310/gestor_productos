(function () {
  const STORAGE_KEY = "gestor.modulo";
  const tabs = Array.from(document.querySelectorAll(".module-tab"));
  const panels = Array.from(document.querySelectorAll("[data-module-panel]"));
  const known = panels.map((panel) => panel.dataset.modulePanel);

  function open(name) {
    if (!known.includes(name)) name = "asistentes";
    tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.module === name));
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.modulePanel !== name;
    });
    try {
      sessionStorage.setItem(STORAGE_KEY, name);
    } catch (error) {
      /* sin almacenamiento disponible */
    }
    history.replaceState(null, "", `#${name}`);
    window.scrollTo({ top: 0 });
    window.dispatchEvent(new CustomEvent("modulo-abierto", { detail: { modulo: name } }));
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => open(tab.dataset.module)));

  window.addEventListener("abrir-reporte", () => setTimeout(() => open("reporteria"), 0));

  window.Modulos = { open };

  window.notify = function notify(message, type = "info") {
    const stack = document.querySelector("#toast-stack");
    if (!stack || !message) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    const text = document.createElement("span");
    text.textContent = String(message);
    const close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar aviso");
    close.textContent = "×";
    toast.append(text, close);
    stack.appendChild(toast);
    const remove = () => toast.remove();
    close.addEventListener("click", remove);
    setTimeout(remove, type === "error" ? 12000 : 5000);
    while (stack.children.length > 4) stack.firstChild.remove();
  };

  let initial = location.hash.slice(1);
  if (!known.includes(initial)) {
    try {
      initial = sessionStorage.getItem(STORAGE_KEY) || "asistentes";
    } catch (error) {
      initial = "asistentes";
    }
  }
  open(initial);
})();
