/* NOVA AI 1.1 · temporizadores, estado de RSI, Discord, perfiles de nave, estadísticas,
   búsqueda de jugadores y «Limpiar transmisiones». Usa las utilidades de app.js ($, api, S, STATE…). */
"use strict";
window.V11 = (() => {
  let timers = [];
  let rsi = {};
  let ship = "";
  const TIPO = { refinado: "⚗", contrato: "📜", general: "⏰" };

  // ------------------------------------------------------------ utilidades
  function human(sec) {
    sec = Math.max(0, Math.round(sec));
    if (sec < 60) return sec + " s";
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    if (d) return `${d} d ${h} h`;
    if (h) return m ? `${h} h ${m} min` : `${h} h`;
    return m + " min";
  }
  // «90», «1:30», «2h30», «2 h 30 min», «45m» → minutos
  function parseMinutes(t) {
    t = String(t || "").trim().toLowerCase().replace(",", ".");
    let m = t.match(/^(\d+):(\d{1,2})$/);
    if (m) return +m[1] * 60 + +m[2];
    m = t.match(/^(?:(\d+(?:\.\d+)?)\s*d)?\s*(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*(?:m|min)?)?$/);
    if (!m || !(m[1] || m[2] || m[3])) return NaN;
    return (+(m[1] || 0)) * 1440 + (+(m[2] || 0)) * 60 + (+(m[3] || 0));
  }
  const n = (v) => Number(v || 0).toLocaleString(LOCALE);

  // ------------------------------------------------------------ cabina: limpiar
  $("#btnClearChat").addEventListener("click", safe(async () => {
    if (!confirm("¿Borrar todas las transmisiones de la cabina?\n(La memoria de la IA y la bitácora no se tocan.)")) return;
    await api("clear_chat");
    $("#chat").innerHTML = "";
    toast("Transmisiones borradas", "ok");
  }));

  // ------------------------------------------------------------ buscar jugador: escribir el apodo
  const msgIn = $("#msgIn");
  const PH = msgIn.placeholder;
  function askHandle() {
    if (!$("#sec-cabina").classList.contains("on")) go("cabina");
    msgIn.placeholder = "Apodo del jugador (handle de RSI)… y pulsa Enter";
    msgIn.classList.add("ask");
    msgIn.focus();
    clearTimeout(askHandle.t);
    askHandle.t = setTimeout(resetInput, 180000);
  }
  function resetInput() { msgIn.placeholder = PH; msgIn.classList.remove("ask"); }
  msgIn.addEventListener("keydown", (e) => { if (e.key === "Enter" && msgIn.classList.contains("ask")) setTimeout(resetInput, 50); });

  // ------------------------------------------------------------ temporizadores
  function renderTimers() {
    const box = $("#timerList");
    if (!timers.length) {
      box.innerHTML = `<div class="muted small">Sin temporizadores. Dile «avísame en 3 horas, el refinado de CRU-L1».</div>`;
      return;
    }
    const now = Date.now() / 1000;
    box.innerHTML = timers.map((t) => {
      const left = t.fin - now;
      const pct = Math.max(0, Math.min(100, 100 - (left / Math.max(1, t.fin - t.inicio)) * 100));
      return `<div class="timer ${left < 300 ? "soon" : ""}" title="${esc(T("Termina el {d} a las {h}", { d: t.dia, h: t.hora }))}">
        <span class="ic">${TIPO[t.tipo] || "⏰"}</span>
        <span class="what"><b>${esc(t.motivo)}</b>${t.lugar ? ` <small>${esc(t.lugar)}</small>` : ""}</span>
        <span class="left">${human(left)}</span><span class="at">${esc(t.hora)}</span>
        <button class="icon-btn" data-tcancel="${esc(t.id)}" title="Cancelar">✕</button>
        <i class="bar" style="width:${pct.toFixed(1)}%"></i></div>`;
    }).join("");
  }
  function setTimers(list) { timers = list || []; renderTimers(); }
  setInterval(() => { if (timers.length) renderTimers(); }, 1000);
  $("#timerList").addEventListener("click", safe(async (e) => {
    const b = e.target.closest("[data-tcancel]");
    if (!b) return;
    setTimers(await api("timer_cancel", { id: b.dataset.tcancel }));
  }));
  $("#btnTimerAdd").addEventListener("click", safe(async () => {
    const min = parseMinutes($("#tmMin").value);
    const motivo = $("#tmMotivo").value.trim() || "Temporizador";
    if (!(min > 0)) { toast("Pon la duración: 90, 1:30 o 2h30", "bad"); $("#tmMin").focus(); return; }
    setTimers(await api("timer_add", { minutos: min, motivo, tipo: $("#tmTipo").value }));
    $("#tmMin").value = ""; $("#tmMotivo").value = "";
    toast("Temporizador en marcha", "ok");
  }));
  $("#tmMin").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btnTimerAdd").click(); });

  // ------------------------------------------------------------ estado de RSI
  const ES = { Operational: "operativo", "Degraded Performance": "degradado", Degraded: "degradado", "Partial Outage": "caída parcial",
    "Major Outage": "caída grave", "Under Maintenance": "mantenimiento", Maintenance: "mantenimiento", Down: "caído", Disrupted: "incidencias" };
  function paintRsi(st) {
    rsi = st || {};
    const short = $("#rsiShort"), chip = $("#rsiChip"), txt = $("#rsiText");
    if (!rsi.comprobado) { short.textContent = S.estado_rsi_al_iniciar === false ? "sin comprobar" : "comprobando…"; chip.textContent = "—"; return; }
    if (rsi.error || rsi.ok === null || rsi.ok === undefined) {
      short.textContent = "sin conexión"; chip.textContent = "SIN DATOS"; chip.className = "chip warn";
      txt.textContent = rsi.texto || "No se pudo consultar status.robertsspaceindustries.com";
      return;
    }
    const comp = rsi.componentes || {};
    const pu = comp["Persistent Universe"];
    short.textContent = rsi.ok && !(rsi.avisos || []).length ? "✓ operativos" : (pu ? "PU " + (ES[pu] || pu) : "avisos") + ((rsi.avisos || []).length ? " · " + rsi.avisos.length + " aviso(s)" : "");
    short.className = rsi.ok ? "" : "warn";
    chip.textContent = rsi.ok ? "OPERATIVO" : "INCIDENCIAS"; chip.className = "chip" + (rsi.ok ? "" : " warn");
    const when = new Date(rsi.comprobado * 1000).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });
    txt.textContent = (rsi.texto || "") + "\n\n" + T("Comprobado a las {h}.", { h: when });
  }
  $("#btnRsi").addEventListener("click", safe(async () => {
    $("#rsiText").textContent = "Consultando status.robertsspaceindustries.com…";
    paintRsi(await api("rsi_status", { refrescar: true }));
  }));

  // ------------------------------------------------------------ Discord
  const dc = $("#dcUrl");
  function paintDc() {
    const v = S.discord_webhook || "";
    if (dc !== document.activeElement) dc.value = v ? "*".repeat(28) : "";
    $("#dcChip").textContent = v ? "CONFIGURADO" : "SIN CONFIGURAR";
    $("#dcChip").className = "chip" + (v ? "" : " dim");
  }
  dc.addEventListener("focus", () => dc.select());
  dc.addEventListener("blur", () => setTimeout(paintDc, 50));
  dc.addEventListener("change", safe(async () => {
    const v = dc.value.trim();
    if (/^\*+$/.test(v) || v === (S.discord_webhook || "")) return;
    try {
      S.discord_webhook = await api("set", { key: "discord_webhook", value: v });
      toast(v ? "Webhook de Discord guardado" : "Discord desactivado", "ok");
    } finally { dc.blur(); paintDc(); }
  }));
  $("#btnDcTest").addEventListener("click", safe(async () => toast(await api("discord_test"), "ok")));

  // ------------------------------------------------------------ perfiles de nave
  function cats() { return Object.entries(STATE.event_categories || {}); }
  function renderShips() {
    const profiles = S.perfiles_nave || {};
    const known = [...new Set([...(S.naves_conocidas || []), ship].filter(Boolean))];
    $("#shipList").innerHTML = known.map((x) => `<option value="${esc(x)}">`).join("");
    $("#shipNow").textContent = ship ? "Ahora vas en: " + ship : "";
    const base = S.gamelog_avisos || {};
    const names = Object.keys(profiles);
    $("#shipProfiles").innerHTML = names.length ? names.map((name) => {
      const p = profiles[name] || {};
      const active = ship && (ship.toLowerCase().includes(name.toLowerCase()) || name.toLowerCase().includes(ship.toLowerCase()));
      return `<div class="ship-prof ${active ? "on" : ""}" data-ship="${esc(name)}">
        <div class="sp-h"><b>${esc(name)}</b>${active ? `<span class="chip">EN USO</span>` : ""}<button class="icon-btn" data-sdel title="Borrar perfil">✕</button></div>
        <div class="avisos">${cats().map(([k, label]) => {
          const on = k in p ? p[k] : base[k] !== false;
          return `<label class="${k in p ? "custom" : ""}"><input type="checkbox" data-cat="${k}" ${on ? "checked" : ""}> ${esc(label)}</label>`;
        }).join("")}</div></div>`;
    }).join("") : `<div class="muted small">Sin perfiles: en todas las naves se usan los mismos avisos.</div>`;
  }
  async function saveProfiles(p) {
    S.perfiles_nave = await api("set", { key: "perfiles_nave", value: p });
    renderShips();
  }
  $("#btnShipAdd").addEventListener("click", safe(async () => {
    const name = $("#shipName").value.trim() || ship;
    if (!name) { toast("Escribe el nombre de la nave", "bad"); return; }
    const p = { ...(S.perfiles_nave || {}) };
    if (!p[name]) p[name] = {};
    $("#shipName").value = "";
    await saveProfiles(p);
  }));
  $("#shipProfiles").addEventListener("change", safe(async (e) => {
    const box = e.target.closest("[data-ship]");
    if (!box || !e.target.dataset.cat) return;
    const p = { ...(S.perfiles_nave || {}) };
    p[box.dataset.ship] = { ...(p[box.dataset.ship] || {}), [e.target.dataset.cat]: e.target.checked };
    await saveProfiles(p);
  }));
  $("#shipProfiles").addEventListener("click", safe(async (e) => {
    if (!e.target.closest("[data-sdel]")) return;
    const name = e.target.closest("[data-ship]").dataset.ship;
    if (!confirm(`¿Borrar el perfil de ${name}?`)) return;
    const p = { ...(S.perfiles_nave || {}) };
    delete p[name];
    await saveProfiles(p);
  }));

  // ------------------------------------------------------------ estadísticas
  const COLS = [["semana", "Semana"], ["sesiones", "Ses."], ["horas", "Horas"], ["bajas_npc", "Bajas NPC"], ["bajas_jugadores", "Bajas JcJ"],
    ["naves_abatidas", "Naves"], ["muertes", "Muertes"], ["saltos", "Saltos"], ["contratos_completados", "Contratos"], ["nave_favorita", "Nave favorita"]];
  async function loadStats() {
    const d = await api("stats");
    const t = d.total || {};
    $("#statsTotals").innerHTML = [["horas", "HORAS DE JUEGO"], ["sesiones", "SESIONES"], ["bajas", "BAJAS"], ["muertes", "MUERTES"],
      ["naves_abatidas", "NAVES DERRIBADAS"], ["saltos", "SALTOS CUÁNTICOS"], ["contratos_completados", "CONTRATOS"], ["auec_recibidos", "aUEC RECIBIDOS"]]
      .map(([k, l]) => `<div><b>${k === "horas" ? String(t[k] || 0).replace(".", ",") : n(t[k])}</b><span>${l}</span></div>`).join("");
    $("#statsHint").textContent = t.desde ? T("Desde el {d}", { d: new Date(t.desde * 1000).toLocaleDateString(LOCALE) }) : "Todas tus sesiones, semana a semana";
    const rows = d.semanas || [];
    $("#statsTable").innerHTML = rows.length
      ? `<thead><tr>${COLS.map(([, l]) => `<th>${l}</th>`).join("")}</tr></thead><tbody>` +
        rows.map((w) => `<tr>${COLS.map(([k]) => `<td>${k === "semana" ? new Date(w.semana + "T00:00").toLocaleDateString(LOCALE, { day: "2-digit", month: "short" })
          : k === "nave_favorita" ? esc(w[k] || "—") : k === "horas" ? String(w[k]).replace(".", ",") : n(w[k])}</td>`).join("")}</tr>`).join("") + "</tbody>"
      : `<tbody><tr><td class="muted">Aún no hay sesiones de juego registradas. Juega un rato o pulsa «Recalcular».</td></tr></tbody>`;
    paintJob(d.recalculando || {});
  }
  function paintJob(j) {
    const btn = $("#btnStatsRebuild"), el = $("#statsJob");
    btn.disabled = !!j.activo;
    if (j.activo) el.textContent = `Leyendo Game.log antiguos… ${j.hecho || 0} / ${j.total || "?"}`;
    else if (j.error) el.textContent = "Error: " + j.error;
    else if (j.total) el.textContent = `Hecho: ${j.nuevas || 0} sesiones nuevas añadidas (de ${j.total} archivos).`;
  }
  $("#btnStatsRebuild").addEventListener("click", safe(async () => paintJob(await api("stats_rebuild"))));

  // ------------------------------------------------------------ enganches con app.js
  return {
    onEvent(ev) {
      if (ev.t === "timers") setTimers(ev.lista);
      else if (ev.t === "estado_rsi") paintRsi(ev);
      else if (ev.t === "pedir_apodo") askHandle();
      else if (ev.t === "chat_limpio") $("#chat").innerHTML = "";
      else if (ev.t === "stats_job") { paintJob(ev); if (!ev.activo) loadStats().catch(() => {}); }
    },
    afterState() {
      setTimers(STATE.timers || []);
      paintRsi(STATE.estado_rsi || {});
      paintDc();
      ship = (STATE.game || {}).ship || "";
      renderShips();
    },
    onSection(sec) {
      if (sec === "memoria") loadStats().catch(() => {});
      if (sec === "juego") renderShips();
      if (sec === "datos") paintDc();
    },
    ship(name) {
      if (name === ship) return;
      ship = name;
      if (name && !(S.naves_conocidas || []).includes(name)) S.naves_conocidas = [...(S.naves_conocidas || []), name];
      renderShips();
    },
    parseMinutes, human,
  };
})();
