(function () {
  const LABELS = ["Nada util", "Poco util", "Util", "Muy util", "Excelente"];

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "No se pudo guardar la valoracion.");
    }
    return data;
  }

  window.mountRating = async function mountRating(container, data) {
    if (!data || !data.run_id || !data.user_id) return;
    const base = `/retroalimentaciones/${encodeURIComponent(data.run_id)}/valoracion`;

    const box = document.createElement("section");
    box.className = "rating-box";
    box.innerHTML = `
      <h3>Te fue util esta retroalimentacion?</h3>
      <p class="meta-line">Tu opinion ayuda a mejorar el asistente.</p>
      <div class="rating-stars" role="radiogroup" aria-label="Valoracion de 1 a 5">
        ${[1, 2, 3, 4, 5]
          .map((n) => `<button type="button" class="star" role="radio" aria-checked="false" data-star="${n}" title="${LABELS[n - 1]}">&#9733;</button>`)
          .join("")}
        <span class="rating-label"></span>
      </div>
      <textarea class="rating-comment" rows="2" maxlength="1000" placeholder="Comentario opcional: que te sirvio o que mejorarias"></textarea>
      <div class="rating-actions">
        <button type="button" class="primary-inline rating-send" disabled>Enviar valoracion</button>
        <span class="rating-status" aria-live="polite"></span>
      </div>`;
    container.appendChild(box);

    const stars = Array.from(box.querySelectorAll(".star"));
    const label = box.querySelector(".rating-label");
    const comment = box.querySelector(".rating-comment");
    const send = box.querySelector(".rating-send");
    const status = box.querySelector(".rating-status");
    let selected = 0;

    function paint(value) {
      stars.forEach((star) => {
        const on = Number(star.dataset.star) <= value;
        star.classList.toggle("on", on);
        star.setAttribute("aria-checked", String(Number(star.dataset.star) === selected));
      });
      label.textContent = value ? LABELS[value - 1] : "";
    }

    stars.forEach((star) => {
      star.addEventListener("click", () => {
        selected = Number(star.dataset.star);
        paint(selected);
        send.disabled = false;
        status.textContent = "";
      });
      star.addEventListener("mouseenter", () => paint(Number(star.dataset.star)));
      star.addEventListener("mouseleave", () => paint(selected));
    });

    send.addEventListener("click", async () => {
      send.disabled = true;
      status.className = "rating-status";
      status.textContent = "Guardando...";
      try {
        await request(base, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: data.user_id, rating: selected, comentario: comment.value.trim() || null }),
        });
        status.className = "rating-status ok";
        status.textContent = "Gracias por tu valoracion. Puedes cambiarla cuando quieras.";
        send.textContent = "Actualizar valoracion";
      } catch (error) {
        status.className = "rating-status error-text";
        status.textContent = esc(error.message);
      } finally {
        send.disabled = false;
      }
    });

    try {
      const existing = await request(`${base}?user_id=${encodeURIComponent(data.user_id)}`);
      if (existing.rating) {
        selected = existing.rating;
        paint(selected);
        comment.value = existing.comentario || "";
        send.disabled = false;
        send.textContent = "Actualizar valoracion";
        status.className = "rating-status ok";
        status.textContent = "Ya valoraste esta retroalimentacion.";
      }
    } catch (error) {
      /* si no se puede consultar, se permite valorar igual */
    }
  };
})();
