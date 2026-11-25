/* NOVA AI 2.1.6 · Copias de seguridad de los controles de Star Citizen (Juego › Teclas y joystick)
   y de lo que NOVA ha aprendido (Ajustes › Copias). Pregunta «¿Quieres realizar una copia…?» /
   «¿Quiere reponer sus controles personalizados?» con SÍ · NO · MÁS TARDE · AL CERRAR NOVA. */
(() => {
  "use strict";
  const $ = (q, r) => (r || document).querySelector(q);
  const $$ = (q, r) => [...(r || document).querySelectorAll(q)];
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const call = (fn, args) => (typeof api === "function" ? api(fn, args) : Promise.reject(new Error("api")));
  const say = (text, kind) => { if (typeof toast === "function") toast(text, kind || ""); };
  const h = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  if (!$("#ctlPanel")) return;

  const MOTIVO = { primera: "primera copia", manual: "a mano", cambios: "tus cambios", nueva_version: "versión nueva",
    repuesta: "tras reponer", al_cerrar_nova: "al cerrar NOVA", antes_de_reponer: "antes de reponer" };
  let ST = null;
  const queue = [];  // preguntas pendientes (una a la vez)
  let showing = null;

  // ------------------------------------------------------------ panel
  function paint(st) {
    if (!st) return;
    ST = st;
    const ch = st.canales || [];
    const chip = $("#ctlChip");
    const pend = ch.filter((c) => !c.al_dia && c.teclas);
    chip.textContent = !ch.length ? T("SIN JUEGO") : pend.length ? T("CAMBIOS SIN COPIAR") : T("AL DÍA");
    chip.className = "chip " + (!ch.length ? "" : pend.length ? "warn" : "ok");
    $("#ctlPath").textContent = st.carpeta || "";
    $("#ctlChans").innerHTML = ch.map((c) => `
      <div class="ctl-chan ${c.al_dia ? "ok" : c.teclas ? "warn" : ""}">
        <div class="ctl-name"><b>${h(c.canal)}</b><span class="muted small">${h(c.version || "")}</span></div>
        <div class="ctl-info">${h(c.resumen)}<br><span class="muted small">${c.ultima
          ? h(T("Última copia: {f}", { f: c.ultima })) + (c.ultima_version && c.ultima_version !== c.version ? " · " + h(T("de la versión {v}", { v: c.ultima_version })) : "")
          : h(T("Sin copias todavía"))}${c.pendiente_al_cerrar ? " · " + h(T("se copiará al cerrar NOVA")) : ""}</span></div>
        <div class="ctl-state">${c.al_dia ? "✓ " + h(T("Copia al día")) : c.teclas ? "⚠ " + h(T("Cambios sin copiar")) : ""}</div>
        <button class="btn sm" data-ctl-backup="${h(c.canal)}">${h(T("COPIA AHORA"))}</button>
      </div>`).join("") || `<p class="muted small">${h(T("No encuentro Star Citizen en este PC (o aún no lo has abierto nunca)."))}</p>`;
    const sel = $("#ctlCopy");
    const keep = sel.value;
    sel.innerHTML = (st.copias || []).map((m) =>
      `<option value="${h(m.id)}">${h(m.canal)} · ${h(m.fecha)}${m.version ? " · " + h(m.version) : ""} · ${h(T(MOTIVO[m.motivo] || m.motivo))} · ${h(m.resumen)}</option>`).join("")
      || `<option value="">${h(T("Sin copias todavía"))}</option>`;
    if (keep && $$("option", sel).some((o) => o.value === keep)) sel.value = keep;
    const tgt = $("#ctlTarget");
    const keepT = tgt.value;
    tgt.innerHTML = ch.map((c) => `<option>${h(c.canal)}</option>`).join("");
    if (keepT && ch.some((c) => c.canal === keepT)) tgt.value = keepT;
    $("#btnCtlRestore").disabled = !(st.copias || []).length || !ch.length;
    for (const p of st.preguntas || []) ask(p);
  }

  async function load() { try { paint(await call("controls")); } catch { /* la ventana se cierra */ } }

  $("#ctlChans").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-ctl-backup]");
    if (!b) return;
    b.disabled = true;
    try { const r = await call("controls_backup", { canal: b.dataset.ctlBackup }); say(r.texto, "ok"); paint(r.estado); }
    catch (err) { say(err.message, "bad"); }
    finally { b.disabled = false; }
  });
  $("#ctlCopy").addEventListener("change", () => {
    const m = (ST && ST.copias || []).find((x) => x.id === $("#ctlCopy").value);
    if (m && $$("option", $("#ctlTarget")).some((o) => o.value === m.canal)) $("#ctlTarget").value = m.canal;
  });
  $("#btnCtlRestore").addEventListener("click", async () => {
    const copia = $("#ctlCopy").value, canal = $("#ctlTarget").value;
    if (!copia || !canal) return;
    if (!confirm(T("¿Reponer tus controles en {c} desde esa copia? Antes se guarda lo que hay ahora.", { c: canal }))) return;
    const btn = $("#btnCtlRestore");
    btn.disabled = true;
    try {
      const r = await call("controls_restore", { canal, copia });
      $("#ctlMsg").textContent = r.texto;
      say(T("Controles repuestos"), "ok");
      paint(r.estado);
    } catch (err) { $("#ctlMsg").textContent = err.message; say(err.message, "bad"); }
    finally { btn.disabled = false; }
  });
  $("#btnCtlOpen").addEventListener("click", () => call("open", { what: "copias_controles" }).catch((e) => say(e.message, "bad")));
  $("#btnCtlCheck").addEventListener("click", async () => {
    try { paint(await call("controls_check")); say(T("Controles comprobados"), "ok"); } catch (err) { say(err.message, "bad"); }
  });

  // ------------------------------------------------------------ copia de NOVA (Ajustes › Copias)
  const nb = $("#btnNovaBkNow");
  if (nb) {
    nb.addEventListener("click", async () => {
      nb.disabled = true;
      try { const r = await call("nova_backup_now"); $("#novaBkMsg").textContent = r.texto; say(T("Copia de NOVA guardada"), "ok"); }
      catch (err) { $("#novaBkMsg").textContent = err.message; }
      finally { nb.disabled = false; }
    });
    $("#btnNovaBkOpen").addEventListener("click", () => call("open", { what: "copias_nova" }).catch((e) => say(e.message, "bad")));
  }

  // ------------------------------------------------------------ la pregunta
  function ask(p) {
    if (!p || !p.id) return;
    if (showing && showing.id === p.id) { showing = p; return; }
    const i = queue.findIndex((q) => q.id === p.id);
    if (i >= 0) queue[i] = p; else queue.push(p);
    next();
  }
  function next() {
    if (showing || !queue.length) return;
    const p = showing = queue.shift();
    const m = $("#ctlModal");
    $("#ctlAskChan").textContent = [p.canal, p.version].filter(Boolean).join(" · ");
    $("#ctlAskText").textContent = p.texto;
    const facts = [];
    if (p.actual) facts.push(`<div><span>${h(T("Ahora"))}</span>${h(p.actual)}</div>`);
    if (p.copia_fecha) facts.push(`<div><span>${h(T("Tu copia"))}</span>${h(p.copia_fecha)} · ${h(p.copia_resumen)}</div>`);
    $("#ctlAskFacts").innerHTML = facts.join("");
    const news = p.nuevas || [];
    $("#ctlAskNews").hidden = !news.length;
    $("#ctlAskNewsList").innerHTML = news.slice(0, 12).map((n) => `<li>${h(n)}</li>`).join("") + (news.length > 12 ? `<li>…</li>` : "");
    const yes = $('[data-ctl="si"]', m);
    yes.textContent = p.tipo === "reponer" ? T("SÍ, REPONER") : T("SÍ");
    $('[data-ctl="al_cerrar"]', m).hidden = p.tipo === "reponer";
    m.hidden = false;
  }
  $$("#ctlModal [data-ctl]").forEach((b) => b.addEventListener("click", async () => {
    const p = showing;
    if (!p) return;
    $$("#ctlModal [data-ctl]").forEach((x) => { x.disabled = true; });
    try {
      const r = await call("controls_answer", { id: p.id, respuesta: b.dataset.ctl });
      say(r.texto, r.ok ? "ok" : "bad");
      if (r.estado) paint(r.estado);
    } catch (err) { say(err.message, "bad"); }
    finally {
      $$("#ctlModal [data-ctl]").forEach((x) => { x.disabled = false; });
      $("#ctlModal").hidden = true;
      showing = null;
      setTimeout(next, 250);
    }
  }));

  // ------------------------------------------------------------ eventos y arranque
  window.V216 = {
    onEvent(ev) {
      if (ev.t === "controles" && ev.pregunta) { ask(ev.pregunta); load(); }
    },
  };
  try { if (typeof STATE !== "undefined" && STATE && STATE.controles_preguntas) STATE.controles_preguntas.forEach(ask); } catch { /* aún no */ }
  // el panel se refresca al abrir la pestaña y cada 30 s mientras se ve
  const visible = () => typeof secOn === "function" ? secOn("juego", "teclas") : !$("#ctlPanel").closest(".subsec:not(.on)");
  setTimeout(load, 1500);
  setInterval(() => { if (visible() && !document.hidden) load(); }, 30000);
  $$('.subtabs[data-group="juego"] button[data-sub="teclas"]').forEach((b) => b.addEventListener("click", () => setTimeout(load, 50)));
})();
