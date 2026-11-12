/* NOVA AI 1.3 · paneles plegables y columnas sin barras de desplazamiento.
   - Pulsar la cabecera de un panel .fold lo pliega o despliega (se recuerda).
   - Si una columna no cabe en la ventana, pliega sola sus paneles en orden
     (primero Situación, luego Temporizadores; en el lateral, Accesos rápidos)
     y los vuelve a abrir cuando hay sitio. */
(() => {
  "use strict";
  const KEY = "nova.fold.";
  const pref = (id) => { try { return localStorage.getItem(KEY + id); } catch { return null; } };
  const setPref = (id, v) => { try { localStorage.setItem(KEY + id, v); } catch { /* sin almacenamiento */ } };
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));

  // columnas que deben caber, y el orden en que se pliegan sus paneles
  const BOXES = [
    { box: () => document.querySelector("#sec-cabina .hud"), order: ["sit", "timers"] },
    { box: () => document.querySelector(".side"), order: ["quick"] },
  ];
  let lastOpened = null;
  const panel = (id) => document.querySelector(`.fold[data-fold="${id}"]`);
  const overflows = (el) => el.scrollHeight > el.clientHeight + 1;

  function fit() {
    for (const { box, order } of BOXES) {
      const el = box();
      if (!el || !el.offsetParent && el !== document.querySelector(".side")) continue; // sección oculta
      // 1) estado que eligió el usuario
      for (const id of order) {
        const p = panel(id); if (!p) continue;
        p.classList.toggle("col", pref(id) === "closed");
        p.classList.remove("auto");
      }
      // 2) en la Cabina, antes de plegar nada, encoge el núcleo (hasta 140 px)
      const core = el.querySelector(".core.big");
      if (core) {
        core.style.removeProperty("--core-fit");
        const extra = el.scrollHeight - el.clientHeight;
        if (extra > 1) {
          const now = core.getBoundingClientRect().width;
          const want = Math.max(140, Math.floor(now - extra));
          if (want < now) core.style.setProperty("--core-fit", want + "px");
        }
      }
      // 3) si aun así no cabe, pliega en orden (el que acaba de abrir el usuario, el último)
      const seq = order.filter((id) => id !== lastOpened).concat(order.includes(lastOpened) ? [lastOpened] : []);
      for (const id of seq) {
        if (!overflows(el)) break;
        const p = panel(id);
        if (p && !p.classList.contains("col")) p.classList.add("col", "auto");
      }
      if (core && core.style.getPropertyValue("--core-fit")) {
        const room = el.clientHeight - el.scrollHeight;
        // scrollHeight no baja de clientHeight: mide el hueco con el último panel
        const last = el.lastElementChild;
        const free = last ? el.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom - 2 : room;
        if (free > 2) {
          const now = core.getBoundingClientRect().width;
          core.style.setProperty("--core-fit", Math.min(236, Math.floor(now + free)) + "px");
          if (overflows(el)) core.style.setProperty("--core-fit", now + "px");
        }
      }
    }
    summaries();
  }

  // resumen que se ve en la cabecera cuando el panel está plegado
  function summaries() {
    const tp = panel("timers");
    if (tp) {
      const n = document.querySelectorAll("#timerList .timer").length;
      const s = tp.querySelector(".fold-sum");
      s.textContent = n ? (n === 1 ? T("1 activo") : T("{n} activos", { n })) : "";
      tp.classList.toggle("has-sum", !!n);
    }
    const sp = panel("sit");
    if (sp) {
      const loc = (document.getElementById("locText") || {}).textContent || "";
      const s = sp.querySelector(".fold-sum");
      s.textContent = loc && loc !== "—" ? loc : "";
      sp.classList.toggle("has-sum", !!s.textContent);
    }
    const qp = panel("quick");
    if (qp) {
      const on = qp.querySelectorAll(".fold-body input:checked").length;
      const all = qp.querySelectorAll(".fold-body input").length;
      qp.querySelector(".fold-sum").textContent = `${on}/${all}`;
    }
  }

  document.addEventListener("click", (e) => {
    const h = e.target.closest(".fold > .panel-h");
    if (!h || e.target.closest("button,input,select,a")) return;
    const p = h.parentElement, id = p.dataset.fold;
    const closing = !p.classList.contains("col");
    setPref(id, closing ? "closed" : "open");
    lastOpened = closing ? null : id;
    fit();
  });

  let pending = 0;
  const later = () => { if (!pending) pending = requestAnimationFrame(() => { pending = 0; fit(); }); };
  window.addEventListener("resize", later);
  document.addEventListener("change", (e) => { if (e.target.closest(".side-quick")) summaries(); });
  const mo = new MutationObserver(later);
  const watch = () => {
    for (const id of ["timerList", "locText", "contractsText", "syncShort", "sttShort", "ovShort", "rsiShort"]) {
      const el = document.getElementById(id); if (el) mo.observe(el, { childList: true, characterData: true, subtree: true });
    }
    // al volver a la Cabina desde otra sección
    const cab = document.getElementById("sec-cabina");
    if (cab) new MutationObserver(later).observe(cab, { attributes: true, attributeFilter: ["class"] });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { watch(); later(); });
  else { watch(); later(); }
  setInterval(summaries, 5000); // los ajustes rápidos también cambian desde otras secciones
  window.NovaFold = { fit };
})();
