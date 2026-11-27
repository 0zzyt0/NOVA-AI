/* NOVA AI 2.0 · estilos de voz (Ajustes › Voz y audio). */
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
    // se pinta al abrir Ajustes › Voz y audio (la lista de voces de Edge tarda un poco la primera vez)
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
  // 2.1.7: «Tipo de agente y estados»: un desplegable de logos animados y otro de fijos (los fijos, para «Sin efectos»)
  const LOGO_NAMES = { nova: "NOVA", nucleo: "Núcleo", onda: "Onda de voz", hexagono: "Hexágono", radar: "Radar",
                       reticula: "Retícula", personal: "El tuyo…",
                       nova_pulso: "NOVA · latido", nucleo_latido: "Núcleo · latido", radar_barrido: "Radar · barrido",
                       onda_voz: "Onda de voz · ecualizador", orbitas: "Órbitas · giroscopio", escudo_hex: "Escudo hexagonal · escaneo",
                       reticula_fijando: "Retícula · fijando objetivo", fijo: "Usar el logo fijo (sin animación)" };
  const selA = $("#logoAnim"), selF = $("#logoFixed");
  let logos = null;
  function refreshLogoImgs() {
    const t = Date.now();
    const a = $("#agentPrevImg"); if (a) a.src = `/overlay_logo_actual?t=${t}`;
    const img = $("#ovLogo img"); if (img) img.src = `/overlay_logo_actual?t=${t}`;
  }
  async function paintLogos(d) {
    if (!selA && !selF) return;
    if (!d) { try { d = await call("overlay_logos"); } catch { return; } }
    logos = d;
    const opt = (id, cur) => `<option value="${h(id)}"${id === cur ? " selected" : ""}>${h(T(LOGO_NAMES[id] || id))}</option>`;
    if (selA) selA.innerHTML = [...d.animados, "fijo"].map((id) => opt(id, d.animados.includes(d.animado) ? d.animado : "fijo")).join("");
    if (selF) selF.innerHTML = d.logos.filter((id) => id !== "personal" || d.propio).map((id) => opt(id, d.actual)).join("");
    const now = $("#logoNow");
    if (now) now.textContent = d.efectos === "ninguno" ? T("Ahora: el fijo (Sin efectos)")
      : d.animados.includes(d.animado) ? T("Ahora: el animado") : T("Ahora: el fijo");
    refreshLogoImgs();
  }
  if (selA) selA.addEventListener("change", async () => {
    try { await call("set", { key: "overlay_logo_animado", value: selA.value }); paintLogos(); } catch (e) { say(e.message, "bad"); }
  });
  if (selF) selF.addEventListener("change", async () => {
    try { await call("set", { key: "overlay_logo", value: selF.value }); paintLogos(); } catch (e) { say(e.message, "bad"); }
  });
  const own = $("#btnLogoOwn");
  if (own) own.addEventListener("click", async () => {
    try { paintLogos(await call("pick_overlay_logo")); } catch (e) { say(e.message, "bad"); }
  });
  // Al cambiar los efectos cambia el logo que se usa (animado ↔ fijo)
  window.addEventListener("nova-fx", () => paintLogos());
  paintLogos();

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
      const tabName = (b) => (b ? b.textContent.replace(/^[^\p{L}]+/u, "").trim() : "");
      sec.querySelectorAll(":scope > .subsec").forEach((sub) => {
        const tab = sec.querySelector(`:scope > .subtabs button[data-sub="${sub.dataset.sub}"]`);
        const where0 = secName + " › " + tabName(tab);
        sub.querySelectorAll(".panel").forEach((panel) => {
          // 2.1.7: pestañas dentro de una pestaña (Ajustes › Pantalla › …)
          const inner = panel.closest(".subsec2");
          const subId = inner ? sub.dataset.sub + ":" + inner.dataset.sub2 : sub.dataset.sub;
          const where = inner ? where0 + " › " + tabName(sub.querySelector(`.subtabs2 button[data-sub2="${inner.dataset.sub2}"]`)) : where0;
          const head = panel.querySelector(".panel-h span");
          const title = head ? head.textContent.trim() : "";
          if (title) index.push({ sec: secId, sub: subId, el: panel, label: title, where, key: norm(title + " " + where) });
          panel.querySelectorAll(".field > label").forEach((lab) => {
            const c = lab.cloneNode(true); c.querySelectorAll("small").forEach((x) => x.remove());
            const main = c.textContent.replace(/\s+/g, " ").trim();
            const extra = lab.querySelector("small") ? lab.querySelector("small").textContent : "";
            if (!main) return;
            index.push({ sec: secId, sub: subId, el: lab.closest(".field"), label: main.trim(), where: where + (title ? " › " + title : ""),
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
