/* NOVA AI 2.0 · estilos de voz (Nova › Voz). */
(() => {
  "use strict";
  const $ = (q) => document.querySelector(q);
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const call = (fn, args) => (typeof api === "function" ? api(fn, args) : Promise.reject(new Error("api")));
  const say = (text, kind) => { if (typeof toast === "function") toast(text, kind || ""); };
  const h = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ------------------------------------------------------------ estilos de voz
  const FX_NAMES = { cabina: "IA de cabina", casco: "Comunicador del casco", radio: "Radio", walkie: "Walkie-talkie" };
  const box = $("#voiceStyles");
  let loaded = false;
  async function paintStyles() {
    if (!box) return;
    let d;
    try { d = await call("voice_styles"); } catch { return; }
    box.innerHTML = d.estilos.map((e) => `
      <button type="button" class="vstyle${e.id === d.actual ? " on" : ""}" data-style="${h(e.id)}">
        <b>${h(e.nombre)}</b><span>${h(e.desc)}</span>
        <small>${h(e.voz.replace(/Neural$/, "").replace(/^[a-z]{2}-[A-Z]{2}-/, ""))} · ${e.velocidad > 0 ? "+" : ""}${e.velocidad}% · ${e.tono > 0 ? "+" : ""}${e.tono} Hz${e.efecto && e.efecto !== "ninguno" ? " · " + h(T(FX_NAMES[e.efecto] || e.efecto)) : ""}</small>
      </button>`).join("");
    loaded = true;
  }
  if (box) {
    box.addEventListener("click", async (ev) => {
      const b = ev.target.closest("[data-style]");
      if (!b) return;
      try {
        await call("voice_style", { estilo: b.dataset.style });
        const st = await call("state");
        if (st && st.settings && typeof S === "object") {
          ["tts_motor", "tts_voz_edge", "tts_velocidad", "tts_tono", "tts_efecto", "tts_efecto_fuerza", "tts_estilo"].forEach((k) => {
            S[k] = st.settings[k];
            if (typeof showSetting === "function") showSetting(k);
          });
        }
        box.querySelectorAll(".vstyle").forEach((x) => x.classList.toggle("on", x === b));
      } catch (e) { say(e.message, "bad"); }
    });
    // se pinta al abrir Nova › Voz (la lista de voces de Edge tarda un poco la primera vez)
    const sub = box.closest(".subsec");
    const obs = new MutationObserver(() => { if (!loaded && sub && sub.offsetParent) paintStyles(); });
    if (sub) obs.observe(sub, { attributes: true, attributeFilter: ["class", "hidden", "style"] });
    document.addEventListener("click", () => setTimeout(() => { if (!loaded && sub && sub.offsetParent) paintStyles(); }, 50));
    // un retoque a mano quita la marca del estilo
    ["tts_voz_edge", "tts_velocidad", "tts_tono", "tts_efecto", "tts_efecto_fuerza", "tts_motor"].forEach((k) =>
      document.querySelectorAll(`[data-set="${k}"]`).forEach((el) => el.addEventListener("change", () =>
        box.querySelectorAll(".vstyle.on").forEach((x) => x.classList.remove("on")))));
  }
  // ------------------------------------------------------------ temas de color
  const tp = $("#themePick");
  async function paintThemes() {
    if (!tp) return;
    let d;
    try { d = await call("themes"); } catch { return; }
    tp.innerHTML = d.temas.map((t) => `<button type="button" class="theme-sw${t.id === d.actual ? " on" : ""}" data-theme="${h(t.id)}"
      style="--sw:${h(t.muestra)}"><i></i><span>${h(t.nombre)}</span></button>`).join("");
  }
  if (tp) {
    tp.addEventListener("click", async (ev) => {
      const b = ev.target.closest("[data-theme]");
      if (!b || b.classList.contains("on")) return;
      try {
        await call("set", { key: "tema", value: b.dataset.theme });
        location.reload();  // la ventana se vuelve a pintar con los colores nuevos
      } catch (e) { say(e.message, "bad"); }
    });
    paintThemes();
  }
  // ------------------------------------------------------------ logos del overlay
  const lp = $("#logoPick");
  const LOGO_NAMES = { nova: "NOVA", nucleo: "Núcleo", onda: "Onda de voz", hexagono: "Hexágono", radar: "Radar",
                       reticula: "Retícula", personal: "El tuyo…" };
  async function paintLogos(d) {
    if (!lp) return;
    if (!d) { try { d = await call("overlay_logos"); } catch { return; } }
    const src = (id) => (id === "nova" ? "/logo.png" : id === "personal" ? `/overlay_logo.png?t=${Date.now()}` : `/logos/${id}.png`);
    lp.innerHTML = d.logos.map((id) => `<button type="button" class="logo-sw${id === d.actual ? " on" : ""}" data-logo="${h(id)}">
      ${id === "personal" && !d.propio ? "<i>＋</i>" : `<img src="${h(src(id))}" alt="">`}<span>${h(T(LOGO_NAMES[id] || id))}</span></button>`).join("");
    const img = $("#ovLogo img");
    if (img) img.src = `/overlay_logo.png?t=${Date.now()}`;
  }
  if (lp) {
    lp.addEventListener("click", async (ev) => {
      const b = ev.target.closest("[data-logo]");
      if (!b) return;
      try {
        if (b.dataset.logo === "personal") paintLogos(await call("pick_overlay_logo"));
        else { await call("set", { key: "overlay_logo", value: b.dataset.logo }); paintLogos(); }
      } catch (e) { say(e.message, "bad"); }
    });
    paintLogos();
  }
  // ------------------------------------------------------------ copias de seguridad
  const bkMsg = $("#bkMsg");
  const parts = () => [...document.querySelectorAll("#bkParts input:checked")].map((x) => x.value);
  const PART_NAMES = { ajustes: "Ajustes", comandos: "Comandos de voz", memoria: "Memoria y diccionario", bitacora: "Bitácora" };
  const ex = $("#btnBkExport"), im = $("#btnBkImport");
  if (ex) ex.addEventListener("click", async () => {
    if (!parts().length) { say(T("Marca al menos una cosa que guardar"), "bad"); return; }
    try {
      const r = await call("backup_export", { partes: parts() });
      if (r.cancelado) return;
      bkMsg.textContent = T("Copia guardada: {f}", { f: r.ruta });
      say(T("Copia guardada ({n} archivos)", { n: r.ficheros }), "ok");
    } catch (e) { say(e.message, "bad"); }
  });
  if (im) im.addEventListener("click", async () => {
    try {
      const info = await call("backup_pick");
      if (info.cancelado) return;
      const want = parts().filter((p) => info.partes.includes(p));
      if (!want.length) { say(T("Esa copia no trae nada de lo que has marcado"), "bad"); return; }
      const names = want.map((p) => T(PART_NAMES[p])).join(", ");
      if (!confirm(T("¿Importar {p} de la copia del {f} (NOVA {v})? Lo que tienes ahora se guarda antes en datos\\copias.", { p: names, f: info.fecha, v: info.version }))) return;
      const r = await call("backup_import", { ruta: info.ruta, partes: want });
      bkMsg.textContent = T("Importado: {p}. Lo anterior está en {d}", { p: names, d: r.anterior || "—" });
      say(T("Copia importada"), "ok");
      if (want.includes("ajustes")) setTimeout(() => location.reload(), 1200);
    } catch (e) { say(e.message, "bad"); }
  });

  // ------------------------------------------------------------ buscador de ajustes
  const sIn = $("#setSearchIn"), sOut = $("#setResults");
  const norm = (t) => (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();
  let index = null;
  function buildIndex() {
    index = [];
    document.querySelectorAll(".sec").forEach((sec) => {
      const secId = sec.id.slice(4);
      if (secId === "cabina") return;
      const secName = (document.querySelector(`#nav [data-sec="${secId}"] span`) || {}).textContent || secId;
      sec.querySelectorAll(".subsec").forEach((sub) => {
        const tab = sec.querySelector(`.subtabs button[data-sub="${sub.dataset.sub}"]`);
        const where = secName + " › " + (tab ? tab.textContent.replace(/^[^\p{L}]+/u, "").trim() : "");
        sub.querySelectorAll(".panel").forEach((panel) => {
          const head = panel.querySelector(".panel-h span");
          const title = head ? head.textContent.trim() : "";
          if (title) index.push({ sec: secId, sub: sub.dataset.sub, el: panel, label: title, where, key: norm(title + " " + where) });
          panel.querySelectorAll(".field > label").forEach((lab) => {
            const c = lab.cloneNode(true); c.querySelectorAll("small").forEach((x) => x.remove());
            const main = c.textContent.replace(/\s+/g, " ").trim();
            const extra = lab.querySelector("small") ? lab.querySelector("small").textContent : "";
            if (!main) return;
            index.push({ sec: secId, sub: sub.dataset.sub, el: lab.closest(".field"), label: main.trim(), where: where + (title ? " › " + title : ""),
                         key: norm(main + " " + extra + " " + title) });
          });
        });
      });
    });
  }
  function search(q) {
    const words = norm(q).split(" ").filter(Boolean);
    if (!words.length) return [];
    if (!index) buildIndex();
    const hits = index.filter((it) => words.every((w) => it.key.includes(w)));
    hits.sort((a, b) => (norm(b.label).startsWith(words[0]) - norm(a.label).startsWith(words[0])) || (a.label.length - b.label.length));
    const seen = new Set();
    return hits.filter((h2) => { const k = h2.label + h2.where; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 12);
  }
  let hits = [], sel = 0;
  function paintResults() {
    if (!hits.length) { sOut.innerHTML = `<div class="sr-none">${h(T("Nada con ese nombre"))}</div>`; sOut.hidden = !sIn.value.trim(); return; }
    sOut.innerHTML = hits.map((it, i) => `<button type="button" class="sr${i === sel ? " on" : ""}" data-i="${i}"><b>${h(it.label)}</b><span>${h(it.where)}</span></button>`).join("");
    sOut.hidden = false;
  }
  function open(it) {
    if (!it) return;
    if (typeof go === "function") go(it.sec, true, it.sub);
    sOut.hidden = true; sIn.blur();
    setTimeout(() => {
      it.el.scrollIntoView({ behavior: "smooth", block: "center" });
      it.el.classList.remove("found"); void it.el.offsetWidth; it.el.classList.add("found");
      const ctl = it.el.querySelector("input, select, textarea, button");
      if (ctl && it.el.classList.contains("field")) setTimeout(() => ctl.focus({ preventScroll: true }), 400);
    }, 80);
  }
  if (sIn) {
    sIn.addEventListener("input", () => { hits = search(sIn.value); sel = 0; paintResults(); });
    sIn.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, hits.length - 1); paintResults(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); paintResults(); }
      else if (e.key === "Enter") { e.preventDefault(); open(hits[sel]); }
      else if (e.key === "Escape") { sIn.value = ""; sOut.hidden = true; sIn.blur(); }
    });
    sIn.addEventListener("focus", () => { if (sIn.value.trim()) { hits = search(sIn.value); paintResults(); } });
    sOut.addEventListener("mousedown", (e) => { const b = e.target.closest("[data-i]"); if (b) { e.preventDefault(); open(hits[+b.dataset.i]); } });
    document.addEventListener("click", (e) => { if (!e.target.closest("#setSearch")) sOut.hidden = true; });
    document.addEventListener("keydown", (e) => {  // Ctrl+F abre el buscador
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") { e.preventDefault(); sIn.focus(); sIn.select(); }
    });
  }

  window.NovaV20 = { paintStyles, paintThemes, paintLogos, search: (q) => search(q).map((x) => [x.label, x.where]) };
})();
