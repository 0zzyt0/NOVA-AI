/* NOVA · lógica de la interfaz */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = {};          // ajustes
let STATE = {};      // estado general
let CMDS = { commands: [], sync: {}, warnings: [], hidden: [] };
let CATALOG = [];
let LAYOUT = null;   // distribución de teclado real (para mostrar Ñ, Ç…)
let live = { mode: "idle", lvl: 0, mic: 0 };

// ------------------------------------------------------------------ API
async function api(fn, args = {}) {
  const r = await fetch("/api/call", {
    method: "POST", headers: { "Content-Type": "application/json", "X-Nova-Token": window.NOVA_TOKEN },
    body: JSON.stringify({ fn, args }),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "Error");
  return j.data;
}
function toast(text, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = text;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 3800);
}
const safe = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, "bad"); } };

// ------------------------------------------------------------ navegación
const TITLES = { cabina: "Cabina", juego: "Nave y comandos", nova: "Nova", overlay: "Overlay y hologramas",
                 datos: "Datos y memoria", ajustes: "Ajustes" };
// Nombres de secciones de versiones anteriores → [sección, pestaña]
const OLD_SECTIONS = { oido: ["nova", "mic"], voz: ["nova", "voz"], interfaz: ["nova", "mic"], ia: ["nova", "ia"],
                       memoria: ["datos", "memoria"] };
// Ganchos de las versiones anteriores: qué nombre antiguo «se abre» con cada sección nueva
const LEGACY = { cabina: ["cabina"], juego: ["juego"], nova: ["voz", "interfaz", "ia"], overlay: ["interfaz"],
                 datos: ["datos", "memoria"], ajustes: ["datos"] };
const secOn = (sec, sub) => { const r = $("#sec-" + sec); if (!r || !r.classList.contains("on")) return false;
  return !sub || !!$(`.subsec.on[data-sub="${sub}"]`, r); };
function go(sec, remember = true, sub = "") {
  if (OLD_SECTIONS[sec]) { const [a, b] = OLD_SECTIONS[sec]; sec = a; sub = sub || b; }
  if (!TITLES[sec]) sec = "cabina";
  if (sub) showSub(sec, sub);
  if (remember) api("ui_state", { seccion: sec }).catch(() => {});
  $$("#nav button[data-sec]").forEach((b) => b.classList.toggle("on", b.dataset.sec === sec));
  $$(".sec").forEach((s) => s.classList.toggle("on", s.id === "sec-" + sec));
  $("#secTitle").textContent = T(TITLES[sec]);
  if (sec === "datos") { loadMemory(); loadDiary(); loadSources(); Trad.load(); }
  if (sec === "juego") loadCommands();
  if (sec === "nova") { loadDevices(); loadIA(); }
  if (sec === "ajustes") loadSources();
  if (sec === "overlay") window.dispatchEvent(new Event("resize"));
  for (const old of LEGACY[sec] || [sec])
    for (const v of [window.V11, window.V12, window.V122, window.V13, window.V130]) if (v && v.onSection) { try { v.onSection(old); } catch (e) { console.warn(e); } }
}
$$("#nav button[data-sec]").forEach((b) => b.addEventListener("click", () => go(b.dataset.sec)));
$("#btnManual").addEventListener("click", safe(async () => { await api("open_manual"); toast("Manual abierto en tu navegador", "ok"); }));
// Subapartados (pestañas dentro de una sección)
function showSub(sec, sub) {
  const root = $("#sec-" + sec);
  if (!root) return;
  $$(".subtabs button", root).forEach((b) => b.classList.toggle("on", b.dataset.sub === sub));
  $$(".subsec", root).forEach((x) => x.classList.toggle("on", x.dataset.sub === sub));
  if (sec === "overlay") window.dispatchEvent(new Event("resize"));  // recoloca la vista previa
}
$$(".subtabs button").forEach((b) => b.addEventListener("click", () => showSub(b.closest(".sec").id.slice(4), b.dataset.sub)));

// ------------------------------------------------------------ ajustes
function fmtVal(key, v, fmt) {
  if (fmt === "%") return Math.round(v * 100) + " %";
  if (fmt.includes("{:+}")) return fmt.replace("{:+}", (v > 0 ? "+" : "") + v);
  return fmt.replace("{}", v);
}
function paintRange(el) {
  const p = ((el.value - el.min) / (el.max - el.min)) * 100;
  el.style.setProperty("--p", p + "%");
}
function showSetting(key) {
  const v = S[key];
  $$(`[data-set="${key}"]`).forEach((el) => {
    if (el === document.activeElement && (el.type === "text" || el.type === "password")) return;
    if (el.type === "checkbox") el.checked = !!v;
    else if (el.dataset.list) el.value = (v || []).join(", ");
    else if (el.dataset.lines) el.value = (v || []).join("\n");
    else if (el.type === "range") { el.value = v; paintRange(el); }
    else el.value = v ?? (el.tagName === "SELECT" ? "(predeterminado)" : "");
  });
  $$(`[data-val="${key}"]`).forEach((el) => (el.textContent = fmtVal(key, v, el.dataset.fmt || "{}")));
}
function bindSettings() {
  $$("[data-set]").forEach((el) => {
    const key = el.dataset.set;
    const ev = el.type === "range" ? "input" : "change";
    el.addEventListener(ev, safe(async () => {
      let value;
      if (el.type === "checkbox") value = el.checked;
      else if (el.dataset.list) value = el.value.split(",").map((s) => s.trim()).filter(Boolean);
      else if (el.dataset.lines) value = el.value.split("\n").map((s) => s.trim()).filter(Boolean);
      else if (el.type === "range") { value = parseFloat(el.value); paintRange(el); }
      else value = el.value;
      S[key] = value;
      $$(`[data-val="${key}"]`).forEach((v) => (v.textContent = fmtVal(key, value, v.dataset.fmt || "{}")));
      $$(`[data-set="${key}"]`).forEach((o) => { if (o !== el && o.type === "checkbox") o.checked = value; });
      clearTimeout(el._t);
      el._t = setTimeout(async () => {
        S[key] = await api("set", { key, value });
        if (["teclas_juego_sync", "actionmaps_ruta", "comandos_auto_juego"].includes(key)) loadCommands();
        if (key === "palabra_clave_activa") updatePttHint();
        if (key === "nombre_asistente") { S.nombre_variantes = []; paintNames(); showSetting("nombre_asistente"); }
        if (key.startsWith("overlay_")) placeOverlay();
      }, el.type === "range" ? 180 : 0);
      if (key.startsWith("overlay_")) placeOverlay();
    }));
  });
}

// ------------------------------------------------------------- reloj
function tick() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  $("#clock").innerHTML = `UEE · STANTON<br>${d.getFullYear() + 930}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
setInterval(tick, 1000); tick();

// ------------------------------------------------------------ medidores
function buildMeter(el, n) { el.innerHTML = "<i></i>".repeat(n); }
buildMeter($("#sideMeter"), 18); buildMeter($("#bigMeter"), 32);
function paintMeter(el, v) {
  const bars = el.children, n = bars.length, lit = Math.round(Math.min(1, v * 1.3) * n);
  for (let i = 0; i < n; i++) {
    bars[i].classList.toggle("on", i < lit);
    bars[i].classList.toggle("hot", i < lit && i > n * 0.85);
    bars[i].style.height = 15 + (i < lit ? 85 * ((i + 1) / n) : 0) + "%";
  }
}

// ------------------------------------------------------------- chat
const STATE_TXT = { idle: "EN ESPERA", listening: "ESCUCHANDO", thinking: "PROCESANDO", speaking: "TRANSMITIENDO", searching: "BUSCANDO", off: "DETENIDA" };
const TINT_KEY = { base: "overlay_color", green: "overlay_color_ok", yellow: "overlay_color_busca", red: "overlay_color_error",
  purple: "overlay_color_memoria", white: "overlay_color_memoriza" };
const tintColor = (t) => S[TINT_KEY[t] || "overlay_color"] || "#20b8e8";
function stateText(mode, tint) {
  if (tint === "purple") return "MEMORIA FÍSICA";
  if (tint === "white") return "MEMORIZANDO";
  if (mode === "idle" && tint === "green") return "ENTENDIDO";
  if (mode === "idle" && tint === "red") return "NO ENTENDIDO";
  return STATE_TXT[mode] || "EN ESPERA";
}
let thinkingEl = null;
function addMsg(ev) {
  const chat = $("#chat");
  const name = S.nombre_asistente || "Nova";
  const el = document.createElement("div");
  if (ev.ai || ev.who === name) {
    removeThinking();
    const [text, model] = ev.text.split("   ·");
    el.className = "msg nova";
    el.innerHTML = `<div class="meta">${esc(String(ev.who || name).toUpperCase())} · ${esc(ev.ts || "")}</div><div class="body">${esc(text)}</div>` +
      (model ? `<div class="model">vía ${esc(model)}</div>` : "");
  } else if (ev.who === "ficha") {
    const [title, ...rows] = ev.text.split("\n");
    el.className = "msg card";
    el.innerHTML = `<div class="meta">${esc(title)} · ${esc(ev.ts || "")}</div><div class="body">${rows.map((r) => {
      const m = r.match(/^(\s*)(?:• )?([^:]{2,40}):\s(.*)$/);
      if (!m) return r.trim() ? `<div>${esc(r)}</div>` : `<div class="gap"></div>`;
      const v = /^https?:\/\//.test(m[3]) ? `<a href="${esc(m[3])}" target="_blank" rel="noopener">${esc(m[3])}</a>` : esc(m[3]);
      return `<div class="${m[1] ? "sub" : ""}"><span class="k">${esc(m[2])}</span><span class="v">${v}</span></div>`;
    }).join("")}</div>`;
  } else if (ev.who === "tú") {
    el.className = "msg user";
    el.innerHTML = `<div class="meta">TÚ · ${esc(ev.ts || "")}</div><div class="body">${esc(ev.text)}</div>`;
    showThinking();
  } else {
    el.className = "msg sys" + (ev.who === "juego" ? " game" : "") + (ev.text.startsWith("── ") ? " sep" : "");
    el.textContent = ev.ts ? `${ev.ts}  ${ev.text}` : ev.text;
  }
  chat.insertBefore(el, thinkingEl && thinkingEl.parentNode ? thinkingEl : null);
  while (chat.children.length > 160) chat.firstChild.remove();
  chat.scrollTop = chat.scrollHeight;
}
function showThinking() {
  removeThinking();
  thinkingEl = document.createElement("div");
  thinkingEl.className = "msg nova thinking";
  thinkingEl.innerHTML = `<div class="meta">${esc((S.nombre_asistente || "Nova").toUpperCase())}</div><div class="body"><span class="dots">Procesando</span></div>`;
  $("#chat").appendChild(thinkingEl);
  $("#chat").scrollTop = 1e9;
  clearTimeout(showThinking.t);
  showThinking.t = setTimeout(removeThinking, 4000);
}
function removeThinking() { if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; } }
const send = safe(async () => {
  const t = $("#msgIn").value.trim();
  if (!t) return;
  $("#msgIn").value = "";
  await api("send_text", { text: t });
});
$("#btnSend").addEventListener("click", send);
$("#msgIn").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
const talk = $("#btnTalk");
const ptt = (down) => { talk.classList.toggle("held", down); api("ptt", { down }).catch(() => {}); };
talk.addEventListener("pointerdown", (e) => { talk.setPointerCapture(e.pointerId); ptt(true); });
talk.addEventListener("pointerup", () => ptt(false));
talk.addEventListener("pointercancel", () => ptt(false));
$("#btnMute").addEventListener("click", safe(() => api("stop_voice")));
$("#swNova").addEventListener("change", safe(async () => {
  const on = $("#swNova").checked;
  await api("pause", { on: !on });  // apagado = detener: cancela búsquedas y para a Nova
}));
$("#btnPower").addEventListener("click", safe(async () => {
  if (confirm("¿Apagar Nova? Se cerrarán la ventana, el overlay y la escucha.")) { await api("shutdown"); goodbye(null); }
}));

// ------------------------------------------------------------- eventos en vivo
function connect() {
  const es = new EventSource("/api/events?token=" + encodeURIComponent(window.NOVA_TOKEN));
  es.onopen = () => { document.body.classList.remove("offline"); $("#chat").innerHTML = ""; thinkingEl = null; };
  es.onerror = () => document.body.classList.add("offline");
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.t === "msg") { addMsg(ev); if (ev.who === "juego") diaryLater(); }
    else if (ev.t === "status") $("#statusLine").textContent = ev.text || "Sistemas nominales";
    else if (ev.t === "lv") onLevels(ev);
    else if (ev.t === "bye") goodbye(es);
    else if (ev.t === "setup") Setup.phase(ev.phase);
    else if (ev.t === "upd") Boot.on(ev);
    else if (ev.t === "trad") Trad.progress(ev);
    else if (ev.t === "trad_aviso") { STATE.traduccion_aviso = true; Trad.maybeAsk(); }
    else if (ev.t === "reset") afterReset();
    else if (window.V11) {
      V11.onEvent(ev); if (window.V12) V12.onEvent(ev); if (window.V13) V13.onEvent(ev); if (window.V122) V122.onEvent(ev);
    }
  };
}
function goodbye(es) {
  if (es) es.close();
  $("#bye").hidden = false;
  document.body.classList.remove("offline");
  setTimeout(() => window.close(), 300);  // en la ventana de Nova se cierra sola
}
function onLevels(ev) {
  live = ev;
  document.body.className = document.body.className.replace(/\bst-\w+/, "st-" + ev.mode);
  document.body.classList.toggle("paused", !!ev.paused);
  if (window.V122) V122.power(!ev.paused);
  const lvl = ev.mode === "speaking" ? ev.lvl : ev.mode === "listening" ? Math.max(0.25, ev.mic)
    : (ev.mode === "searching" || ev.mode === "off" || ev.tint !== "base") ? 0.45 : 0;
  document.documentElement.style.setProperty("--lvl", lvl.toFixed(3));
  document.documentElement.style.setProperty("--tc", tintColor(ev.tint));
  document.documentElement.style.setProperty("--tt", ev.tint === "base" ? "0" : "0.8");
  $("#coreState").textContent = stateText(ev.mode, ev.tint);
  $("#stateText").textContent = stateText(ev.mode, ev.tint);
  paintMeter($("#sideMeter"), ev.mic);
  if (!$("#setup").hidden) paintMeter($("#suMeter"), ev.mic);
  if (secOn("nova", "mic")) paintMeter($("#bigMeter"), ev.mic);
  if (ev.mode !== "idle") removeThinking.idleSince = 0;
  else if (thinkingEl && !removeThinking.idleSince) removeThinking.idleSince = Date.now();
}

// ------------------------------------------------------------- estado
function updatePttHint() {
  const key = STATE.ptt_text || "—";
  $("#pttKey").textContent = key;
  $("#pttJoy").textContent = S.ptt_joystick ? `· ${S.ptt_joystick.nombre} · botón ${S.ptt_joystick.boton + 1}` : "";
  $("#pttHint").textContent = S.palabra_clave_activa ? T("Mantén {k} o di «{n}…» para hablar", { k: key, n: S.nombre_asistente || "Nova" })
    : T("Mantén {k} para hablar", { k: key });
}
function paintNames() {
  const n = S.nombre_asistente || "Nova";
  $$(".ai-name").forEach((el) => (el.textContent = n));
  $("#msgIn").placeholder = T("Escribe a {n}… (o mantén tu tecla para hablar)", { n });
  $("#btnMute").title = `Callar a ${n}`;
  $(".brand-sub").textContent = n.toLowerCase() === "nova" ? "ASISTENTE DE VUELO" : `ASISTENTE · ${n.toUpperCase()}`;
  document.title = `NOVA AI · ${n}`;
  $("#variants").innerHTML = (S.nombre_variantes || []).length
    ? S.nombre_variantes.map((v) => `<span class="chip">${esc(v)}</span>`).join("")
    : `<span class="muted" style="margin:0">nada todavía</span>`;
  api("setup_check_name", { nombre: n }).then((w) => { $("#nameWarn").textContent = w || "Al cambiarlo, entrénala para que reconozca cómo lo dices"; $("#nameWarn").style.color = w ? "var(--warn)" : ""; }).catch(() => {});
  updatePttHint();
}
function showStatus(st) {
  const g = st.game || {};
  $("#locText").textContent = g.location && g.location !== "desconocida" ? g.location : "—";
  $("#contractsText").textContent = (g.contracts || []).length ? g.contracts.join(" · ") : "ninguno";
  $("#gameStatus").textContent = g.status || "";
  if (window.V11) V11.ship(g.ship || "");
  $("#sttShort").textContent = st.stt ? (st.stt.mode === "groq" ? "Groq (nube)" : "Whisper local") + (st.stt.status ? " · " + st.stt.status : "") : "—";
  $("#sttStatus").textContent = st.stt ? st.stt.status : "";
  const ov = st.overlay || {};
  const where = ov.res ? `${ov.res} (${ov.source})` : "";
  $("#ovShort").textContent = !S.overlay_activo ? "desactivado" : [ov.status, where].filter(Boolean).join(" · ");
  $("#ovStatus").textContent = ov.status || "";
  STATE.overlay = ov;
  $("#ovResInfo").textContent = S.overlay_resolucion === "auto"
    ? (ov.res ? `Detectada: ${ov.res} (${ov.source})` : "Automática: se ajusta a la ventana del juego o al monitor")
    : "Fijada a mano";
  placeOverlay();
}
async function loadState() {
  STATE = await api("state");
  S = STATE.settings;
  Object.keys(S).forEach(showSetting);
  updatePttHint();
  showStatus(STATE);
  $("#btnPhraseDefault").onclick = safe(async () => {
    S.frases_inventadas = await api("set", { key: "frases_inventadas", value: [STATE.final_phrase] });
    showSetting("frases_inventadas"); toast("Frase original restaurada", "ok");
  });
  $("#piperVoices").innerHTML = STATE.piper_voices.map((v) => `<option>${esc(v)}</option>`).join("");
  $("#ovRes").innerHTML = `<option value="auto">Automática (detectar)</option>` +
    STATE.resolutions.map((r) => `<option value="${r}">${r.replace("x", " × ")}${{ "640x480": " " + T("(mínima)"), "1920x1080": " (Full HD)", "2560x1440": " (2K)", "3840x2160": " (4K)" }[r] || ""}</option>`).join("");
  showSetting("overlay_resolucion");
  $("#ovMon").innerHTML = STATE.monitors.map((m) => `<option value="${m.id}">${esc(m.label)}</option>`).join("") +
    `<option value="juego">El monitor donde esté el juego</option>`;
  showSetting("overlay_monitor");
  const av = S.gamelog_avisos || {};
  $("#avisos").innerHTML = Object.entries(STATE.event_categories).map(([k, label]) =>
    `<label><input type="checkbox" data-aviso="${k}" ${av[k] !== false ? "checked" : ""}> ${esc(label)}</label>`).join("");
  $$("#avisos [data-aviso]").forEach((c) => c.addEventListener("change", safe(async () => {
    const v = { ...(S.gamelog_avisos || {}) };
    v[c.dataset.aviso] = c.checked;
    S.gamelog_avisos = await api("set", { key: "gamelog_avisos", value: v });
  })));
  showSetting("tts_voz_piper");
  paintNames();
  if (window.V11) V11.afterState();
  if (window.V13) V13.afterState();
  if (window.V122) V122.afterState();
  if (window.V130) V130.afterState();
  if (STATE.session && STATE.session.seccion && STATE.session.seccion !== "cabina") go(STATE.session.seccion, false);
  paintSources(STATE.fuentes);
  if (STATE.arranque && STATE.arranque.comprobando) Boot.show(STATE.arranque.informe || {});
  else if (!STATE.setup.done) Setup.open(true);
  else Trad.maybeAsk();
  removeThinking();  // el historial llega por el flujo de eventos al conectar
  $("#statusLine").textContent = "Sistemas nominales";
  placeOverlay();
}
setInterval(() => api("status").then(showStatus).catch(() => {}), 3000);

// ------------------------------------------------------------- dispositivos y voces
let devicesLoaded = false;
const loadDevices = safe(async () => {
  if (devicesLoaded) return;
  devicesLoaded = true;
  const d = await api("devices");
  const opts = (list) => `<option value="(predeterminado)">(predeterminado)</option>` + list.map((n) => `<option>${esc(n)}</option>`).join("");
  $("#inDevs").innerHTML = opts(d.inputs);
  $("#outDevs").innerHTML = opts(d.outputs);
  showSetting("dispositivo_entrada"); showSetting("dispositivo_salida");
  const voices = await api("voices");
  $("#edgeVoices").innerHTML = voices.map((v) => `<option>${esc(v)}</option>`).join("");
  showSetting("tts_voz_edge");
});
const prevBtn = $("#btnPreview");
prevBtn.addEventListener("click", safe(async () => {
  const playing = await api("preview_voice");
  prevBtn.textContent = playing ? "■ DETENER" : "▶ PROBAR VOZ";
  clearInterval(prevBtn._t);
  if (playing) prevBtn._t = setInterval(() => {
    if (live.mode !== "speaking" && live.mode !== "thinking" && Date.now() - prevBtn._since > 2500) { prevBtn.textContent = "▶ PROBAR VOZ"; clearInterval(prevBtn._t); }
  }, 300);
  prevBtn._since = Date.now();
}));

// ------------------------------------------------------------- oído
$("#btnAssign").addEventListener("click", safe(async () => {
  const b = $("#btnAssign");
  b.textContent = "PULSA LA TECLA O BOTÓN… (6 s)"; b.classList.add("rec-on");
  try {
    const r = await api("assign_ptt");
    STATE.ptt_text = r.ptt_text; S.ptt_tecla = r.ptt_tecla; S.ptt_joystick = r.ptt_joystick;
    toast(r.hit ? "Asignado: " + (r.hit.tipo === "tecla" ? r.ptt_text : `${r.hit.nombre} · botón ${r.hit.boton + 1}`) : "No se pulsó nada", r.hit ? "ok" : "");
    updatePttHint();
  } finally { b.textContent = "ASIGNAR TECLA / BOTÓN HOTAS"; b.classList.remove("rec-on"); }
}));
$("#btnClearJoy").addEventListener("click", safe(async () => { await api("clear_joystick"); S.ptt_joystick = null; updatePttHint(); }));

// ------------------------------------------------------------- IA
let iaLoaded = false;
function loadIA() {
  if (iaLoaded) return;
  iaLoaded = true;
  const provs = Object.entries(STATE.providers).filter(([k]) => k !== "ollama");
  $("#provList").innerHTML = provs.map(([k, p]) => `
    <div class="prov"><div class="nm"><span class="dot ${STATE.keys_set[k] ? "on" : ""}" id="dot-${k}"></span>${esc(p.nombre)}</div>
    <input type="password" data-key="${k}" placeholder="${esc(STATE.keys_set[k] ? T("•••••••• configurada (escribe para cambiarla)") : T("pega aquí tu clave"))}">
    <button class="btn sm" data-url="${esc(p.url)}">CONSEGUIR CLAVE</button>
    <span class="hint" id="kst-${k}">${STATE.keys_set[k] ? "lista" : "sin clave"}</span></div>`).join("");
  $$("#provList input").forEach((inp) => inp.addEventListener("change", safe(async () => {
    const ok = await api("set_key", { provider: inp.dataset.key, value: inp.value });
    STATE.keys_set[inp.dataset.key] = ok;
    $("#dot-" + inp.dataset.key).classList.toggle("on", ok);
    $("#kst-" + inp.dataset.key).textContent = ok ? "lista" : "sin clave";
    inp.value = ""; inp.placeholder = ok ? "•••••••• configurada" : "pega aquí tu clave";
    toast(ok ? "Clave guardada" : "Clave borrada", "ok");
  })));
  $$("#provList [data-url]").forEach((b) => b.addEventListener("click", () => window.open(b.dataset.url, "_blank")));
  renderChain();
}
function renderChain() {
  const chain = [...(S.ia_cadena || [])];
  while (chain.length < 5) chain.push({ proveedor: "", modelo: "" });
  const provOpts = (sel) => `<option value="">—</option>` + Object.keys(STATE.providers).map((k) => `<option ${k === sel ? "selected" : ""}>${k}</option>`).join("");
  $("#chainList").innerHTML = chain.slice(0, 5).map((c, i) => `
    <div class="chain" data-i="${i}"><span class="i">${String(i + 1).padStart(2, "0")}</span>
    <select class="cp">${provOpts(c.proveedor)}</select>
    <input class="cm" list="ml-${i}" value="${esc(c.modelo)}" placeholder="modelo"><datalist id="ml-${i}">${(STATE.providers[c.proveedor]?.modelos || []).map((m) => `<option>${esc(m)}</option>`).join("")}</datalist>
    <button class="btn sm ct">PROBAR</button><button class="btn sm cl">MODELOS</button><span class="res"></span></div>`).join("");
  $$("#chainList .chain").forEach((row) => {
    const p = $(".cp", row), m = $(".cm", row), res = $(".res", row), dl = $("datalist", row);
    p.addEventListener("change", () => {
      const ms = STATE.providers[p.value]?.modelos || [];
      dl.innerHTML = ms.map((x) => `<option>${esc(x)}</option>`).join("");
      m.value = ms[0] || "";
      saveChain();
    });
    m.addEventListener("change", saveChain);
    $(".ct", row).addEventListener("click", safe(async () => {
      if (!p.value) return;
      res.className = "res"; res.textContent = "probando…";
      const r = await api("test_provider", { provider: p.value, model: m.value });
      res.textContent = r; res.className = "res " + (r.startsWith("OK") ? "ok" : "bad"); res.title = r;
    }));
    $(".cl", row).addEventListener("click", safe(async () => {
      if (!p.value) return;
      res.textContent = "pidiendo lista…";
      const ms = await api("list_models", { provider: p.value });
      dl.innerHTML = ms.slice(0, 150).map((x) => `<option>${esc(x)}</option>`).join("");
      res.textContent = ms.length ? `${ms.length} modelos: elige en la casilla` : "sin lista (¿clave?)";
    }));
  });
}
const saveChain = safe(async () => {
  const chain = $$("#chainList .chain").map((r) => ({ proveedor: $(".cp", r).value, modelo: $(".cm", r).value.trim() }))
    .filter((c) => c.proveedor && c.modelo);
  S.ia_cadena = await api("set", { key: "ia_cadena", value: chain });
  toast("Cadena de motores guardada", "ok");
});

// ------------------------------------------------------------- memoria
const loadMemory = safe(async () => {
  const m = await api("memory");
  $("#facts").innerHTML = m.facts.length ? m.facts.map((f) => `<div class="fact"><span>${esc(f.texto)}</span><small>${esc(f.fecha)}</small><button class="icon-btn" data-forget="${esc(f.texto)}" title="Olvidar">✕</button></div>`).join("")
    : `<div class="empty">Todavía no sabe nada de ti.</div>`;
  $$("[data-forget]").forEach((b) => b.addEventListener("click", safe(async () => { await api("forget", { text: b.dataset.forget }); loadMemory(); })));
});
$("#btnClearFacts").addEventListener("click", safe(async () => { if (confirm(`¿Olvidar todo lo que ${S.nombre_asistente || "Nova"} sabe de ti?`)) { await api("clear_facts"); loadMemory(); } }));
$("#btnClearHist").addEventListener("click", safe(async () => { await api("clear_history"); $("#chat").innerHTML = ""; toast("Conversación borrada", "ok"); }));
$$("[data-open]").forEach((b) => b.addEventListener("click", safe(() => api("open", { what: b.dataset.open }))));

// ============================================================ TECLAS
const CODE2NAME = {
  Escape: "esc", Tab: "tab", CapsLock: "capslock", ShiftLeft: "lshift", ShiftRight: "rshift", ControlLeft: "lctrl", ControlRight: "rctrl",
  AltLeft: "lalt", AltRight: "ralt", MetaLeft: "lwin", MetaRight: "rwin", ContextMenu: "apps", Space: "space", Enter: "enter", Backspace: "backspace",
  Insert: "insert", Delete: "delete", Home: "home", End: "end", PageUp: "pageup", PageDown: "pagedown",
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", NumpadAdd: "add", NumpadSubtract: "subtract",
  NumpadMultiply: "multiply", NumpadDivide: "divide", NumpadDecimal: "decimal", NumpadEnter: "numenter", NumLock: "numlock", ScrollLock: "scrolllock",
  Minus: "minus", Equal: "equals", BracketLeft: "lbracket", BracketRight: "rbracket", Backslash: "backslash", Semicolon: "semicolon",
  Quote: "apostrophe", Backquote: "grave", Comma: "comma", Period: "period", Slash: "slash", IntlBackslash: "intlbackslash",
};
for (let i = 0; i < 26; i++) { const c = String.fromCharCode(65 + i); CODE2NAME["Key" + c] = c.toLowerCase(); }
for (let i = 0; i < 10; i++) { CODE2NAME["Digit" + i] = String(i); CODE2NAME["Numpad" + i] = "num" + i; }
for (let i = 1; i <= 12; i++) CODE2NAME["F" + i] = "f" + i;
const NAME2CODE = Object.fromEntries(Object.entries(CODE2NAME).map(([c, n]) => [n, c]));
const MODS = ["lctrl", "rctrl", "lshift", "rshift", "lalt", "ralt", "lwin", "rwin"];
const KEYLBL = { lctrl: "Ctrl", rctrl: "Ctrl der", lshift: "Shift", rshift: "Shift der", lalt: "Alt", ralt: "Alt Gr", lwin: "Win", rwin: "Win der", apps: "Menú",
  space: "Espacio", enter: "Intro", esc: "Esc", tab: "Tab", backspace: "Retroceso", capslock: "Bloq Mayús", insert: "Insert", delete: "Supr",
  home: "Inicio", end: "Fin", pageup: "RePág", pagedown: "AvPág", up: "↑", down: "↓", left: "←", right: "→", add: "Num +", subtract: "Num −",
  multiply: "Num *", divide: "Num /", decimal: "Num .", numenter: "Num Intro", numlock: "Bloq Num", scrolllock: "Bloq Despl" };
const MOUSELBL = { left: "Clic izq", right: "Clic der", middle: "Clic rueda", x1: "Lateral 1", x2: "Lateral 2" };
if (navigator.keyboard && navigator.keyboard.getLayoutMap) navigator.keyboard.getLayoutMap().then((m) => (LAYOUT = m)).catch(() => {});

function keyLabel(n) {
  if (KEYLBL[n]) return KEYLBL[n];
  if (/^num\d$/.test(n)) return "Num " + n.slice(3);
  if (/^f\d+$/.test(n)) return n.toUpperCase();
  const code = NAME2CODE[n];
  if (LAYOUT && code && LAYOUT.get(code)) return LAYOUT.get(code).toUpperCase();
  return n.length === 1 ? n.toUpperCase() : n;
}
function comboHtml(combo) {
  if (!combo) return "";
  return combo.split("+").map((k) => `<kbd>${esc(keyLabel(k))}</kbd>`).join('<span class="plus">+</span>');
}
function stepHtml(a) {
  if ("esperar" in a) return `<span class="hint" style="margin:0">⏱ ${a.esperar} s</span>`;
  let h = a.tecla ? comboHtml(a.tecla) : a.raton ? `<kbd>🖱 ${esc(MOUSELBL[a.raton] || a.raton)}</kbd>` : `<span class="chip bad">sin tecla</span>`;
  if (a.mantener) h += `<span class="hint" style="margin:0 0 0 4px">${a.mantener}s</span>`;
  if (a.doble) h += `<span class="hint" style="margin:0 0 0 4px">×2</span>`;
  if (a.juego) h += `<span class="sync-mark" title="Se sincroniza con tu tecla del juego (${esc(a.juego)})">⟳</span>`;
  return h;
}

// ============================================================ COMANDOS
const loadCommands = safe(async () => {
  CMDS = await api("commands");
  if (!CATALOG.length) {
    CATALOG = await api("catalog");
    $("#addGame").innerHTML = `<option value="">＋ Acción del juego (se sincroniza sola)…</option>` +
      [...new Set(CATALOG.map((c) => c.categoria))].map((cat) => `<optgroup label="${esc(cat)}">` +
        CATALOG.filter((c) => c.categoria === cat).map((c) => `<option value="${c.id}">${esc(c.nombre)}</option>`).join("") + "</optgroup>").join("");
  }
  renderSync();
  renderCommands();
});
function renderSync() {
  const s = CMDS.sync || {};
  const chip = $("#syncChip");
  const map = { ok: ["SINCRONIZADO", "ok"], "no encontrado": ["ARCHIVO NO ENCONTRADO", "warn"], error: ["ERROR", "bad"], desactivado: ["DESACTIVADO", ""] };
  const [txt, cls] = map[s.estado] || ["—", ""];
  chip.textContent = txt; chip.className = "chip " + cls;
  $("#sAp").textContent = (s.aplicadas || []).length;
  $("#sNew").textContent = (s.nuevas || []).length;
  $("#sWarn").textContent = (s.sin_tecla || []).length + (s.solo_joystick || []).length;
  $("#syncDesc").textContent = s.estado === "ok"
    ? `Leído ${s.ruta} (${s.acciones_en_archivo} acciones personalizadas) · ${s.fecha}.`
    : s.detalle || `${S.nombre_asistente || "Nova"} lee tu archivo de controles del juego cada vez que arranca y usa tus teclas.`;
  const sec = (title, items) => items && items.length ? `<div class="h">${title}</div>` + items.map((i) => "· " + esc(i)).join("<br>") : "";
  $("#syncList").innerHTML = (sec("Teclas tuyas aplicadas", s.aplicadas) + sec("Comandos añadidos desde el juego", s.nuevas) +
    sec(`Sin tecla de teclado en el juego (${S.nombre_asistente || "Nova"} no puede pulsarlas)`, s.sin_tecla) +
    sec(`Solo en joystick/HOTAS (asígnales también una tecla para que ${S.nombre_asistente || "Nova"} pueda usarlas)`, s.solo_joystick) +
    sec("Avisos", CMDS.warnings)) || "Sin cambios: usas las teclas por defecto.";
  $("#syncShort").textContent = s.estado === "ok" ? `sincronizadas (${(s.aplicadas || []).length} tuyas)` : txt.toLowerCase();
  const nWarn = (s.sin_tecla || []).length + (s.solo_joystick || []).length + (CMDS.warnings || []).length;
  $("#navWarn").textContent = nWarn ? "⚠ " + nWarn : "";
}
function renderCommands() {
  const q = $("#cmdSearch").value.trim().toLowerCase();
  const cat = $("#cmdCat").value;
  const cats = [...new Set(CMDS.commands.map((c) => c.categoria || "Otros"))];
  const curCat = $("#cmdCat").value;
  $("#cmdCat").innerHTML = `<option value="">Todas las categorías (${CMDS.commands.length})</option>` + cats.map((c) => `<option ${c === curCat ? "selected" : ""}>${esc(c)}</option>`).join("");
  $("#catList").innerHTML = cats.map((c) => `<option>${esc(c)}</option>`).join("");
  const match = (c) => !q || [c.nombre, c.descripcion, ...(c.frases || []), ...(c.acciones || []).map((a) => a.tecla || a.raton || "")].join(" ").toLowerCase().includes(q);
  const list = CMDS.commands.filter((c) => (!cat || (c.categoria || "Otros") === cat) && match(c));
  $("#cmdCount").textContent = `${list.length} de ${CMDS.commands.length} comandos`;
  let html = "", last = null;
  for (const c of list) {
    const cg = c.categoria || "Otros";
    if (cg !== last) { html += `<div class="cat-h">${esc(cg.toUpperCase())}</div>`; last = cg; }
    const ph = (c.frases || []).slice(0, 4).map((f) => `<span>«${esc(f)}»</span>`).join("") + ((c.frases || []).length > 4 ? `<em>+${c.frases.length - 4}</em>` : "") ||
      `<em>${c.solo_frase_exacta ? "" : "solo por IA (sin frase fija)"}</em>`;
    const keys = (c.acciones || []).filter((a) => !("esperar" in a)).map(stepHtml).join('<span class="plus">→</span>');
    const src = c.origen !== "base" ? `<span class="src ${c.origen}">${{ personal: "TUYO", modificado: "MODIFICADO", juego: "DEL JUEGO" }[c.origen]}</span>` : "";
    html += `<div class="cmd" data-id="${esc(c.id)}">
      <div class="n">${esc(c.nombre)}${src}${c.solo_frase_exacta ? '<small class="hint">🔒 solo frase exacta</small>' : ""}</div>
      <div class="ph">${ph}</div><div class="k">${keys}</div>
      <div class="acts"><button class="icon-btn" data-act="test" title="Probar en 3 s">▶</button><button class="icon-btn" data-act="edit" title="Editar">✎</button>
      ${c.origen === "modificado" ? '<button class="icon-btn" data-act="restore" title="Volver al original">↺</button>' : ""}
      <button class="icon-btn" data-act="del" title="${c.origen === "personal" ? "Borrar" : "Ocultar"}">🗑</button></div></div>`;
  }
  $("#cmdList").innerHTML = html || `<div class="empty">Ningún comando coincide.</div>`;
  const hidden = CMDS.hidden || [];
  $("#hiddenBox").hidden = !hidden.length;
  $("#hiddenList").innerHTML = hidden.map((id) => `<div class="kv"><span>${esc(id)}</span><button class="btn sm" data-restore="${esc(id)}">MOSTRAR DE NUEVO</button></div>`).join("");
  $$("[data-restore]").forEach((b) => b.addEventListener("click", safe(async () => { CMDS = await api("restore_command", { id: b.dataset.restore }); renderSync(); renderCommands(); })));
}
$("#cmdSearch").addEventListener("input", renderCommands);
$("#cmdCat").addEventListener("change", renderCommands);
$("#cmdList").addEventListener("click", safe(async (e) => {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  const id = b.closest(".cmd").dataset.id;
  const c = CMDS.commands.find((x) => x.id === id);
  if (b.dataset.act === "edit") openEditor(c);
  else if (b.dataset.act === "test") testCommand(c);
  else if (b.dataset.act === "restore") { CMDS = await api("restore_command", { id }); renderSync(); renderCommands(); toast("Restaurado el original", "ok"); }
  else if (b.dataset.act === "del") {
    const msg = c.origen === "personal" ? `¿Borrar «${c.nombre}»?` : `¿Ocultar «${c.nombre}»? Podrás recuperarlo en «Comandos ocultos».`;
    if (confirm(msg)) { CMDS = await api("delete_command", { id }); renderSync(); renderCommands(); }
  }
}));
$("#btnSync").addEventListener("click", safe(async () => {
  CMDS = await api("sync_keys"); renderSync(); renderCommands();
  toast(CMDS.sync.estado === "ok" ? "Teclas sincronizadas con Star Citizen" : (CMDS.sync.detalle || "No se pudo sincronizar"), CMDS.sync.estado === "ok" ? "ok" : "bad");
}));
async function testCommand(c) {
  await api("test_command", { data: { nombre: c.nombre, acciones: c.acciones }, delay: 3 });
  let n = 3;
  toast(`Probando «${c.nombre}» en ${n} s… cambia al juego`);
}

// ============================================================ EDITOR
let ED = null, REC = null;
function openEditor(c) {
  ED = c ? JSON.parse(JSON.stringify(c)) : { id: null, nombre: "", categoria: "Personales", frases: [], respuestas: [], descripcion: "", acciones: [{ tecla: "" }], solo_frase_exacta: false };
  $("#edTitle").textContent = c ? `EDITAR · ${c.nombre.toUpperCase()}` : "NUEVO COMANDO";
  $("#edName").value = ED.nombre; $("#edCat").value = ED.categoria || "";
  $("#edPhrases").value = (ED.frases || []).join("\n"); $("#edResp").value = (ED.respuestas || []).join("\n");
  $("#edDesc").value = ED.descripcion || ""; $("#edExact").checked = !!ED.solo_frase_exacta;
  $("#edShips").value = (ED.naves || []).join(", "); $("#edLog").checked = !!ED.registrar;
  $("#edErr").textContent = "";
  renderSteps();
  $("#editor").hidden = false;
  setTimeout(() => $("#edName").focus(), 50);
}
function closeEditor() { stopRec(); $("#editor").hidden = true; ED = null; }
$$("#editor [data-close]").forEach((b) => b.addEventListener("click", closeEditor));
$("#btnNewCmd").addEventListener("click", () => openEditor(null));

function renderSteps() {
  const n = ED.acciones.length;
  $("#edSteps").innerHTML = ED.acciones.map((a, i) => {
    let body;
    if ("esperar" in a) {
      body = `<span class="step-t">ESPERA</span><span class="lbl"><input type="number" min="0" max="60" step="0.1" value="${a.esperar}" data-f="esperar"> segundos</span>`;
    } else if ("raton" in a) {
      body = `<span class="step-t">RATÓN</span><select data-f="raton">${Object.entries(MOUSELBL).map(([k, v]) => `<option value="${k}" ${k === a.raton ? "selected" : ""}>${v}</option>`).join("")}</select>
        <span class="lbl">Mantener <input type="number" min="0" max="30" step="0.1" value="${a.mantener || 0}" data-f="mantener"> s</span>`;
    } else {
      const rec = REC && REC.i === i;
      body = `<span class="step-t">TECLA</span>
        <span class="combo ${a.tecla || rec ? "" : "empty"}" data-manual title="Clic para escribirla a mano">${rec ? recDisplay() : comboHtml(a.tecla)}</span>
        <button class="btn sm ${rec ? "rec-on" : ""}" data-rec>${rec ? "■ PULSA AHORA…" : "● GRABAR"}</button>
        <span class="lbl">Mantener <input type="number" min="0" max="30" step="0.1" value="${a.mantener || 0}" data-f="mantener"> s</span>
        <label class="lbl"><input type="checkbox" data-f="doble" ${a.doble ? "checked" : ""}> Doble pulsación</label>
        ${a.juego ? `<span class="game" title="Si cambias esta tecla en el juego, Nova la actualiza sola">⟳ ${esc(a.juego)} <a href="#" data-unlink>desvincular</a></span>` : ""}`;
    }
    return `<div class="step ${REC && REC.i === i ? "recording" : ""}" data-i="${i}"><span class="step-n">${String(i + 1).padStart(2, "0")}</span>${body}<span class="sp"></span>
      <button class="icon-btn" data-mv="-1" ${i === 0 ? "disabled" : ""} title="Subir">↑</button><button class="icon-btn" data-mv="1" ${i === n - 1 ? "disabled" : ""} title="Bajar">↓</button>
      <button class="icon-btn" data-rm title="Quitar">✕</button></div>`;
  }).join("") || `<div class="empty">Añade al menos una tecla.</div>`;
  if (REC) $("#edSteps").insertAdjacentHTML("afterbegin", `<div class="rec-hint">● GRABANDO · pulsa la combinación en tu teclado (Esc para cancelar)</div>`);
}
function recDisplay() {
  const parts = [...MODS.filter((m) => REC.mods.has(m)), ...(REC.main ? [REC.main] : [])];
  return parts.length ? comboHtml(parts.join("+")) : `<span class="hint" style="margin:0">esperando…</span>`;
}
$("#edSteps").addEventListener("input", (e) => {
  const f = e.target.dataset.f; if (!f) return;
  const a = ED.acciones[+e.target.closest(".step").dataset.i];
  a[f] = e.target.type === "checkbox" ? e.target.checked : e.target.tagName === "SELECT" ? e.target.value : parseFloat(e.target.value) || 0;
});
$("#edSteps").addEventListener("click", (e) => {
  const step = e.target.closest(".step"); if (!step) return;
  const i = +step.dataset.i, a = ED.acciones[i];
  if (e.target.closest("[data-rec]")) { REC && REC.i === i ? stopRec() : startRec(i); return; }
  if (e.target.closest("[data-rm]")) { stopRec(); ED.acciones.splice(i, 1); renderSteps(); return; }
  const mv = e.target.closest("[data-mv]");
  if (mv) { stopRec(); const j = i + +mv.dataset.mv; [ED.acciones[i], ED.acciones[j]] = [ED.acciones[j], ED.acciones[i]]; renderSteps(); return; }
  if (e.target.closest("[data-unlink]")) { e.preventDefault(); delete a.juego; renderSteps(); return; }
  if (e.target.closest("[data-manual]") && !REC) {
    const v = prompt("Escribe la combinación con nombres de tecla de Nova (ej.: lalt+n, rctrl+num5, f1, space):", a.tecla || "");
    if (v !== null) { a.tecla = v.trim().toLowerCase(); renderSteps(); }
  }
});
function startRec(i) { REC = { i, mods: new Set(), main: null }; renderSteps(); }
function stopRec() { if (REC) { REC = null; if (ED) renderSteps(); } }
function finishRec() {
  const parts = [...MODS.filter((m) => REC.mods.has(m)), ...(REC.main ? [REC.main] : [])];
  if (parts.length) ED.acciones[REC.i].tecla = parts.join("+");
  REC = null; renderSteps();
}
window.addEventListener("keydown", (e) => {
  if (!REC) {
    if (e.key === "Escape" && ED) closeEditor();
    return;
  }
  e.preventDefault(); e.stopPropagation();
  if (e.repeat) return;
  if (e.code === "Escape" && !REC.mods.size && !REC.main) { stopRec(); return; }
  const n = CODE2NAME[e.code];
  if (!n) { toast(`Esa tecla (${e.code}) no se puede pulsar desde Nova`, "bad"); return; }
  if (MODS.includes(n)) { REC.mods.add(n); if (n === "ralt") REC.mods.delete("lctrl"); }
  else REC.main = n;
  const comboEl = $(`.step[data-i="${REC.i}"] .combo`);
  if (comboEl) { comboEl.classList.remove("empty"); comboEl.innerHTML = recDisplay(); }
}, true);
window.addEventListener("keyup", (e) => {
  if (!REC) return;
  e.preventDefault(); e.stopPropagation();
  const n = CODE2NAME[e.code];
  if (REC.main && n === REC.main) finishRec();
  else if (!REC.main && MODS.includes(n) && REC.mods.size) finishRec();  // solo un modificador (p. ej. Alt Gr)
}, true);

$("#addKey").addEventListener("click", () => { ED.acciones.push({ tecla: "" }); renderSteps(); startRec(ED.acciones.length - 1); });
$("#addMouse").addEventListener("click", () => { ED.acciones.push({ raton: "left" }); renderSteps(); });
$("#addWait").addEventListener("click", () => { ED.acciones.push({ esperar: 0.5 }); renderSteps(); });
$("#addGame").addEventListener("change", (e) => {
  const c = CATALOG.find((x) => x.id === e.target.value);
  e.target.value = "";
  if (!c) return;
  const existing = CMDS.commands.flatMap((cmd) => cmd.acciones).find((a) => a.juego === c.id && (a.tecla || a.raton));
  const step = { juego: c.id, mantener: c.mantener || 0 };
  if (existing && existing.raton) step.raton = existing.raton; else step.tecla = (existing && existing.tecla) || c.tecla || "";
  ED.acciones.push(step);
  if (!$("#edName").value.trim()) $("#edName").value = c.nombre;
  renderSteps();
  if (!step.tecla && !step.raton) toast("Esa acción no tiene tecla por defecto: grábala o asígnale una en el juego", "bad");
});
function editorData() {
  return {
    id: ED.id, nombre: $("#edName").value.trim(), categoria: $("#edCat").value.trim() || "Personales",
    frases: $("#edPhrases").value.split("\n"), respuestas: $("#edResp").value.split("\n"),
    descripcion: $("#edDesc").value.trim(), solo_frase_exacta: $("#edExact").checked,
    naves: $("#edShips").value.split(",").map((x) => x.trim()).filter(Boolean), registrar: $("#edLog").checked,
    acciones: ED.acciones.filter((a) => "esperar" in a || a.tecla || a.raton),
  };
}
$("#edSave").addEventListener("click", async () => {
  stopRec();
  try {
    const r = await api("save_command", { data: editorData() });
    CMDS = r; closeEditor(); renderSync(); renderCommands(); toast("Comando guardado", "ok");
  } catch (e) { $("#edErr").textContent = "⚠ " + e.message; }
});
$("#edTest").addEventListener("click", safe(async () => {
  stopRec();
  const d = editorData();
  if (!d.acciones.length) { $("#edErr").textContent = "⚠ Graba al menos una tecla."; return; }
  await api("test_command", { data: d, delay: 3 });
  toast("Probando en 3 s… cambia al juego", "ok");
}));

// ============================================================ OVERLAY (vista previa)
const SPOTS = { "arriba-izquierda": [0, 0], "arriba-centro": [0.5, 0], "arriba-derecha": [1, 0], "centro-derecha": [1, 0.5], "abajo-izquierda": [0, 1], "abajo-derecha": [1, 1] };
let demo = null, demoTint = "base", demoUntil = 0;
function previewResolution() {
  const pick = S.overlay_resolucion && S.overlay_resolucion !== "auto" ? S.overlay_resolucion : (STATE.overlay && STATE.overlay.res) || "1920x1080";
  const [w, h] = pick.replace("×", "x").split("x").map(Number);
  return w && h ? [w, h] : [1920, 1080];
}
function buildSpots() {
  const scr = $("#ovScreen");
  Object.entries(SPOTS).forEach(([k, [x, y]]) => {
    const s = document.createElement("div");
    s.className = "ov-spot"; s.dataset.pos = k; s.title = k.replace("-", " ");
    s.style.left = `calc(${x * 100}% - ${x * 26}px + ${x === 0 ? 6 : x === 1 ? -6 : 0}px)`;
    s.style.top = `calc(${y * 100}% - ${y * 26}px + ${y === 0 ? 6 : y === 1 ? -6 : 0}px)`;
    s.addEventListener("click", safe(async () => { S.overlay_posicion = await api("set", { key: "overlay_posicion", value: k }); placeOverlay(); }));
    scr.appendChild(s);
  });
}
function placeOverlay() {
  const scr = $("#ovScreen"); if (!scr) return;
  const [rw, rh] = previewResolution();
  scr.style.setProperty("--ar", `${rw}/${rh}`);
  const W = scr.clientWidth || 640, H = scr.clientHeight || 360;
  const sc = Math.max(0.35, Math.min(rh / 1080, 2.6)), k = W / rw;  // misma escala que el overlay real
  const size = Math.max(14, (S.overlay_tamano || 110) * sc * k), m = (S.overlay_margen || 40) * sc * k;
  const [x, y] = SPOTS[S.overlay_posicion] || SPOTS["arriba-derecha"];
  const logo = $("#ovLogo");
  logo.style.setProperty("--sz", size + "px");
  logo.style.left = (x === 0 ? m : x === 1 ? W - size - m : (W - size) / 2) + "px";
  logo.style.top = (y === 0 ? m : y === 1 ? H - size - m : (H - size) / 2) + "px";
  $("#ovTag").dataset.res = `${rw}×${rh}`;
  $$(".ov-spot").forEach((s) => s.classList.toggle("on", s.dataset.pos === S.overlay_posicion));
}
let ovA = 0.35, ovG = 0, nextBlink = 0, blinkUntil = 0;
function ovFrame(t) {
  requestAnimationFrame(ovFrame);
  if (!secOn("overlay", "logo")) return;
  const now = t / 1000;
  const isDemo = demo && performance.now() < demoUntil;
  const mode = isDemo ? demo : live.mode, tint = isDemo ? demoTint : (live.tint || "base");
  let lvl = mode === "speaking" ? (isDemo ? Math.abs(Math.sin(now * 9)) * 0.8 : live.lvl) : 0;
  let ta, tg, k;
  if (mode === "speaking") {  // el único estado que parpadea
    ta = 1; tg = 0.45 + 0.9 * Math.min(1, lvl * 1.6); k = 0.6;
    if (now >= nextBlink) { blinkUntil = now + 0.04 + Math.random() * 0.05; nextBlink = now + 0.25 + Math.random() * 0.65; }
    if (now < blinkUntil) { ta = 0.55; tg = 0.25; }
  } else if (mode === "off") { ta = 0.85; tg = 0.5; k = 0.2; }
  else if (mode === "searching") { ta = 1; tg = 0.7; k = 0.25; }
  else if (mode === "listening" || mode === "thinking") { ta = 1; tg = 0.55; k = 0.3; }
  else if (tint !== "base") { ta = 1; tg = 0.65; k = 0.3; }
  else { ta = S.overlay_reposo === "oculto" ? 0.05 : S.overlay_opacidad_reposo || 0.35; tg = 0; k = 0.12; }
  ovA += (ta - ovA) * k; ovG += (tg * (S.overlay_intensidad || 1) - ovG) * k;
  const logo = $("#ovLogo");
  logo.style.setProperty("--oa", ovA.toFixed(3));
  logo.style.setProperty("--og", ovG.toFixed(3));
  logo.style.setProperty("--oc", tintColor(tint));
  logo.style.setProperty("--ot", tint === "base" ? "0" : (0.75 * ovA).toFixed(3));
  $("#ovTag").textContent = `${T(stateText(mode, tint))} · ${$("#ovTag").dataset.res || ""}`;
}
$$("[data-demo]").forEach((b) => b.addEventListener("click", () => { [demo, demoTint] = b.dataset.demo.split(":"); demoUntil = performance.now() + 6000; }));
$("#btnOvTest").addEventListener("click", safe(async () => {
  const st = await api("overlay_test");
  toast(st === "activo" ? "Mira la pantalla: el overlay recorre sus estados durante 8 s" : "Overlay: " + st, st === "activo" ? "ok" : "bad");
}));
new ResizeObserver(() => placeOverlay()).observe($("#ovScreen"));

// ============================================================ fuentes de datos
const SRC_LABEL = { juego: "Textos del juego", scmdb: "scmdb.net", uex: "UEX Corp", wiki: "Star Citizen Wiki", indice: "Enciclopedia" };
function dotClass(st) {
  return { ok: "ok", "sin cambios": "ok", actualizado: "ok", "sin conexión": "warn", omitido: "warn", error: "bad",
           comprobando: "run", descargando: "run" }[st] || "";
}
const ago = (t) => {
  if (!t) return "nunca";
  const m = Math.round((Date.now() / 1000 - t) / 60);
  return m < 1 ? "ahora mismo" : m < 60 ? `hace ${m} min` : m < 1440 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} d`;
};
function paintSources(f) {
  if (!f) return;
  $("#sources").innerHTML = f.paginas.map((p) => `<div class="src">
      <h4><span class="dot ${dotClass(p.estado)}"></span>${esc(p.nombre)}</h4>
      <div class="what">${esc(p.que)}</div>
      <div class="ver">${esc(p.version || "—")}</div>
      <div class="when">Comprobado ${ago(p.comprobado)}${p.actualizado ? " · actualizado " + ago(p.actualizado) : ""}</div>
      ${p.texto ? `<div class="st muted">${esc(p.texto)}</div>` : ""}
      ${p.url ? `<button class="btn sm" data-href="${esc(p.url)}">ABRIR WEB ↗</button>` : ""}</div>`).join("");
  $$("#sources [data-href]").forEach((b) => b.addEventListener("click", () => window.open(b.dataset.href, "_blank")));
  const e = f.enciclopedia || {};
  $("#kbChip").textContent = e.estado || "—";
  $("#kbStats").innerHTML = [["entradas", "ENTRADAS"], ["misiones", "MISIONES"], ["planos", "PLANOS"], ["minerales", "MINERALES"]]
    .map(([k, l]) => `<div><b>${(e[k] || 0).toLocaleString(LOCALE)}</b><span>${l}</span></div>`).join("");
  const g = f.globalini || {};
  $("#iniInfo").textContent = g.ruta ? T("{i} · {n} textos · {r} avisos reconocibles", { i: g.idioma, n: g.textos.toLocaleString(LOCALE), r: g.reglas }) : T("No encontrado: avisos en inglés");
  const bad = f.paginas.filter((p) => ["error"].includes(p.estado)).length;
  $("#navData").textContent = bad ? "!" : "";
  $("#btnUpdate").disabled = !!f.comprobando;
}
async function loadSources() { const f = await api("sources"); STATE.fuentes = f; paintSources(f); }
$("#btnUpdate").addEventListener("click", safe(async () => {
  if (await api("update_now")) { toast("Comprobando las fuentes…", "ok"); $("#btnUpdate").disabled = true; }
}));
async function kbSearch() {
  const q = $("#kbQuery").value.trim();
  if (!q) return;
  const res = await api("kb_search", { q });
  $("#kbRes").innerHTML = res.length ? res.map((r) => `<div class="r"><i>${esc(r.tipo)} · ${esc(r.fuente)}</i><b>${esc(r.titulo)}</b> — ${esc(r.texto)}</div>`).join("")
    : `<div class="muted">Nada encontrado.</div>`;
}
$("#btnKb").addEventListener("click", safe(kbSearch));
$("#kbQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") safe(kbSearch)(); });

// Pantalla de arranque: comprobación de actualizaciones antes de activar nada
const Boot = (() => {
  const box = $("#boot");
  const order = ["juego", "scmdb", "uex", "wiki", "indice"];
  let skipped = false;
  function rows(rep) {
    $("#bootRows").innerHTML = order.map((k) => {
      const r = rep[k] || {};
      return `<div class="boot-row" data-k="${k}"><span class="dot ${dotClass(r.estado)}"></span><b>${SRC_LABEL[k]}</b>
        <span class="t">${esc(r.texto || "En espera…")}</span><div class="bar"><i style="width:${r.pct ?? (r.estado && r.estado !== "comprobando" ? 100 : 0)}%"></i></div></div>`;
    }).join("");
  }
  function show(rep) { if (skipped) return; rows(rep || {}); box.hidden = false; }
  function on(ev) {
    if (ev.fuente === "fin") {
      setTimeout(() => {
        box.hidden = true; loadSources().catch(() => {});
        if (STATE.setup && !STATE.setup.done && $("#setup").hidden) Setup.open(true); else Trad.maybeAsk();
      }, 900);
      $("#bootFoot").textContent = ev.texto || "Listo";
      return;
    }
    if (box.hidden && !skipped && STATE.arranque && STATE.arranque.comprobando !== false) show({});
    const row = $(`#bootRows [data-k="${ev.fuente}"]`);
    if (!row) return;
    $(".dot", row).className = "dot " + dotClass(ev.estado);
    $(".t", row).textContent = ev.texto || "";
    const pct = ev.pct ?? (["comprobando", "descargando"].includes(ev.estado) ? null : 100);
    if (pct != null) $(".bar i", row).style.width = pct + "%";
  }
  $("#btnBootSkip").addEventListener("click", safe(async () => {
    skipped = true; await api("update_skip"); box.hidden = true;
    if (STATE.setup && !STATE.setup.done) Setup.open(true);
  }));
  return { show, on };
})();

// ============================================================ traducción al español
const Trad = (() => {
  let st = {};
  const fmtDate = (t) => (t ? new Date(t * 1000).toLocaleDateString(LOCALE) : "—");
  function bar(el, ev) {
    if (!el) return;
    el.hidden = false;
    const pct = ev.pct == null || ev.pct < 0 ? null : ev.pct;
    el.classList.toggle("indet", pct == null);
    $("i", el).style.width = (pct ?? 0) + "%";
    $("span", el).textContent = ev.texto || "";
  }
  function paint() {
    let txt, chip;
    if (!st.live) { txt = "No encuentro la carpeta de Star Citizen en ninguna unidad. Elígela con «Elegir carpeta del juego»."; chip = "SIN JUEGO"; }
    else if (st.encontrado) {
      txt = `Instalada en ${st.live}\\data\\Localization\\${st.idioma} · archivo del ${fmtDate(st.fecha)}` +
            (st.instalada_por_nova ? ` · instalada por Nova el ${fmtDate(st.instalada_por_nova)}` : "") +
            ` · próximo aviso de actualización: ${fmtDate(st.aviso)}` + (st.activo === false ? " · ⚠ user.cfg no la tiene activada" : "");
      chip = st.espanol ? "ESPAÑOL ✓" : st.idioma.toUpperCase();
    } else { txt = `Veo que no dispones de una traducción al español de Star Citizen (${st.live}). Pulsa «Actualizar traducción» para descargar la versión más actual de 0zzyt0.`; chip = "SIN TRADUCCIÓN"; }
    $("#trText").textContent = txt; $("#trChip").textContent = chip;
    $("#trLive").textContent = st.carpetas && st.carpetas.length ? "Encontrada: " + st.carpetas.join(" · ") : "Vacío = buscarla en todas las unidades";
    $("#btnTrUpdate").disabled = !!st.instalando || !st.live;
  }
  async function load() { st = await api("translation_status"); paint(); paintUrl(); return st; }
  // El enlace de descarga se enseña tapado con asteriscos; al escribir otro se guarda (vacío = el de 0zzyt0).
  function paintUrl() {
    const el = $("#trUrl");
    if (!el || el === document.activeElement) return;
    const v = S.traduccion_url || "";
    el.value = v ? "*".repeat(Math.min(Math.max(v.length, 8), 28)) : "";
  }
  const urlEl = $("#trUrl");
  if (urlEl) {
    urlEl.addEventListener("focus", () => urlEl.select());
    urlEl.addEventListener("blur", () => setTimeout(paintUrl, 50));
    urlEl.addEventListener("change", safe(async () => {
      const v = urlEl.value.trim();
      if (/^\*+$/.test(v) || v === (S.traduccion_url || "")) return;  // sin cambios
      S.traduccion_url = await api("set", { key: "traduccion_url", value: v });
      toast(v ? "Enlace de la traducción cambiado" : "Se usará el enlace de 0zzyt0");
      urlEl.blur(); paintUrl();
    }));
  }
  async function install(origen) { if (await api("translation_install", { origen })) bar($("#trBar"), { texto: "Conectando con Google Drive…", pct: -1 }); }
  function progress(ev) {
    const targets = [$("#trBar")];
    if (ev.origen === "asistente") targets.push($("#trWizBar"));
    if (ev.origen === "aviso") targets.push($("#askBar"));
    targets.forEach((el) => bar(el, ev));
    if (ev.estado === "ok" || ev.estado === "error") {
      toast(ev.texto, ev.estado === "ok" ? "ok" : "bad");
      load().catch(() => {});
      if (ev.origen === "asistente") wizardDone(ev);
      if (ev.origen === "aviso") { $("#askText").textContent = ev.texto; $("#askBtns").innerHTML = `<button class="btn pri" id="askClose">CERRAR</button>`; $("#askClose").onclick = () => ($("#ask").hidden = true); }
    }
  }
  // --- en la configuración inicial
  async function wizard() {
    const t = $("#trWizText"), v = $("#vTr");
    $("#trWizAsk").hidden = $("#trWizFolder").hidden = true; $("#trWizBar").hidden = true;
    t.className = "su-note"; t.textContent = "Buscando tu carpeta de Star Citizen…"; v.className = "verdict";
    const s2 = await load();
    if (!s2.live) {
      t.className = "su-note bad"; t.textContent = "No encuentro la carpeta de Star Citizen en ninguna unidad. Dime dónde está.";
      $("#trWizFolder").hidden = false; v.className = "verdict bad";
      api("setup_say", { text: "No encuentro la carpeta de Star Citizen. Dime dónde está." });
    } else if (s2.encontrado && s2.espanol) {
      t.className = "su-note ok"; t.textContent = `Tienes la traducción al español instalada (${s2.idioma}, ${fmtDate(s2.fecha)}). La usaré para entender el juego.`;
      v.className = "verdict ok";
      api("setup_say", { text: "Perfecto, ya tienes Star Citizen en español." });
    } else {
      const q = "Veo que no dispones de una traducción al Español de Star Citizen. ¿Quieres que te descargue la versión más actual de 0zzyt0?";
      t.className = "su-note"; t.textContent = q + (s2.encontrado ? ` (Ahora tienes: ${s2.idioma}.)` : "");
      $("#trWizAsk").hidden = false;
      api("setup_say", { text: q });
    }
  }
  function wizardDone(ev) {
    const ok = ev.estado === "ok";
    $("#trWizText").className = "su-note " + (ok ? "ok" : "bad");
    $("#trWizText").textContent = ok ? "¡Traducción instalada! Star Citizen ya está en español (reinicia el juego si estaba abierto)." : ev.texto;
    $("#vTr").className = "verdict " + (ok ? "ok" : "bad");
    $("#trWizAsk").hidden = ok; $("#trWizYes").disabled = false;
    api("setup_say", { text: ok ? "Traducción instalada." : "No he podido instalar la traducción." });
  }
  $("#trWizYes").addEventListener("click", safe(async () => {
    $("#trWizYes").disabled = true;
    if (!(await api("translation_install", { origen: "asistente" }))) $("#trWizYes").disabled = false;
    else bar($("#trWizBar"), { texto: "Conectando con Google Drive…", pct: -1 });
  }));
  $("#trWizNo").addEventListener("click", safe(async () => {
    await api("translation_answer", { respuesta: "rechazar" });
    $("#trWizAsk").hidden = true; $("#trWizText").textContent = "De acuerdo, sin traducción. Puedes instalarla cuando quieras en Fuentes de datos.";
  }));
  const pick = safe(async () => { if (await api("pick_folder", {})) { S.juego_carpeta = (await api("state")).settings.juego_carpeta; showSetting("juego_carpeta"); } wizard(); });
  $("#trWizPick").addEventListener("click", pick);
  $("#trWizRetry").addEventListener("click", () => wizard());
  // --- en Fuentes de datos
  $("#btnTrUpdate").addEventListener("click", safe(() => install("boton")));
  $("#btnTrFolder").addEventListener("click", safe(async () => {
    const p = await api("pick_folder", {});
    if (p) { S.juego_carpeta = p; showSetting("juego_carpeta"); toast("Carpeta del juego: " + p, "ok"); }
    load();
  }));
  // --- aviso cada 3 meses
  function maybeAsk() {
    if (!STATE.traduccion_aviso || !$("#boot").hidden || !$("#setup").hidden || !$("#ask").hidden) return;
    STATE.traduccion_aviso = false;
    load().then((s2) => {
      $("#askText").textContent = `Han pasado 3 meses desde que se instaló la traducción al español (${s2.idioma || "global.ini"}, ${fmtDate(s2.instalada_por_nova || s2.fecha)}). Puede que haya una versión nueva de 0zzyt0. ¿Comprobar y reinstalar?`;
      $("#ask").hidden = false;
      api("setup_say", { text: "Han pasado tres meses desde la última traducción. ¿Quiere que compruebe si hay una versión nueva?" });
    }).catch(() => {});
  }
  $$("#askBtns [data-ans]").forEach((b) => b.addEventListener("click", safe(async () => {
    const ans = b.dataset.ans;
    await api("translation_answer", { respuesta: ans });
    if (ans === "si") { $$("#askBtns button").forEach((x) => (x.disabled = true)); bar($("#askBar"), { texto: "Conectando con Google Drive…", pct: -1 }); }
    else { $("#ask").hidden = true; toast(ans === "luego" ? "Te lo recordaré la próxima vez que abras Nova." : "De acuerdo. Te volveré a avisar dentro de 3 meses.", "ok"); }
  })));
  return { load, progress, wizard, maybeAsk };
})();

// ============================================================ empezar de cero
$("#btnResetAll").addEventListener("click", safe(async () => {
  if (!confirm("⚠ Esto borra TODO lo que el asistente sabe de ti: tu nombre y el suyo, lo que recuerda, la conversación, las bitácoras, el entrenamiento de voz y tus ajustes.\n\nNo se puede deshacer. ¿Seguro que quieres empezar de cero?")) return;
  await api("reset_all", { conservar_claves: $("#rsKeys").checked, conservar_comandos: $("#rsCmds").checked });
}));
async function afterReset() {
  $("#chat").innerHTML = "";
  toast("Datos borrados. Empezamos de cero.", "ok");
  await loadState();
  go("cabina", false);
}
$("#btnPreview2").addEventListener("click", () => $("#btnPreview").click());

// ============================================================ diario de vuelo
async function loadDiary() {
  const d = await api("diary");
  $("#diarySum").textContent = d.resumen;
  $("#diaryFiles").innerHTML = d.archivos.length ? d.archivos.map((f) => `<div class="diary-file"><span>${esc(f.nombre)}</span>
      <button class="btn sm" data-diary="${esc(f.nombre)}">ABRIR</button></div>`).join("") : `<div class="muted">Aún no hay sesiones guardadas.</div>`;
  $$("#diaryFiles [data-diary]").forEach((b) => b.addEventListener("click", safe(() => api("open_diary", { nombre: b.dataset.diary }))));
}
function diaryLater() {
  if (!secOn("datos")) return;
  clearTimeout(diaryLater.t); diaryLater.t = setTimeout(() => loadDiary().catch(() => {}), 1500);
}
$("#btnDiaryOpen").addEventListener("click", safe(() => api("open_diary", {})));
$("#btnDiaryFolder").addEventListener("click", safe(() => api("open_diary", { nombre: "carpeta" })));

// ============================================================ dónde lo dejaste
function reportWindow() {
  const v = { x: window.screenX, y: window.screenY, w: window.outerWidth, h: window.outerHeight };
  const k = JSON.stringify(v);
  if (k === reportWindow.last || v.w < 400) return;
  reportWindow.last = k;
  api("ui_state", { ventana: v }).catch(() => {});
}
window.addEventListener("resize", () => { clearTimeout(reportWindow.t); reportWindow.t = setTimeout(reportWindow, 800); });
setInterval(reportWindow, 4000);  // mover la ventana no lanza ningún evento
$("#btnForgetVar").addEventListener("click", safe(async () => { S.nombre_variantes = await api("forget_variants"); paintNames(); toast("Olvidado. Entrénala otra vez para que te reconozca mejor.", "ok"); }));
$$("[data-train]").forEach((b) => b.addEventListener("click", () => Setup.open(false)));
$$("[data-url]").forEach((b) => { if (!b.closest("#provList")) b.addEventListener("click", () => window.open(b.dataset.url, "_blank")); });

// ============================================================ configuración inicial
const Setup = (() => {
  let page = 0, info = {}, firstRun = true, listening = null;
  const results = { ex: [null, null, null], ph: [] };
  const box = $("#setup");
  const name = () => ($("#suName").value.trim() || info.nombre || "Nova");
  const pilot = () => $("#suPilot").value.trim();
  const trat = () => ($("#suTrat").value === "__nombre" ? pilot() : $("#suTrat").value);
  const say = (text) => api("setup_say", { text }).catch(() => {});

  function verdict(el, ok) { el.className = "verdict" + (ok === true ? " ok" : ok === false ? " bad" : ""); }
  function note(el, r) {
    el.className = "su-note" + (r ? (r.ok ? " ok" : " bad") : "");
    el.innerHTML = r ? esc(r.note || "") + (r.heard ? `<span class="heard">He oído: «${esc(r.heard)}»</span>` : "") : "";
  }
  function phase(p) {
    if (!listening) return;
    const b = listening;
    b.classList.remove("wait", "rec", "proc");
    if (p === "listening") { b.classList.add("rec"); b.textContent = "● TE ESCUCHO… HABLA"; box.classList.add("listening"); }
    if (p === "processing") { b.classList.add("proc"); b.textContent = "◌ PROCESANDO…"; box.classList.remove("listening"); }
  }
  async function listen(btn, kind, index = 0) {
    if (listening) return null;
    listening = btn;
    const label = btn.textContent;
    btn.classList.add("wait"); btn.textContent = "◌ UN MOMENTO…";
    const slow = setTimeout(() => { if (btn.classList.contains("proc")) btn.textContent = "◌ CARGANDO EL OÍDO… (1ª vez)"; }, 6000);
    try { return await api("setup_listen", { kind, index }); }
    catch (e) { toast(e.message, "bad"); return null; }
    finally { clearTimeout(slow); listening = null; btn.classList.remove("wait", "rec", "proc"); btn.textContent = label; box.classList.remove("listening"); }
  }

  function show(n) {
    page = Math.max(0, Math.min(6, n));
    $$(".su-page", box).forEach((p) => p.classList.toggle("on", +p.dataset.p === page));
    $$("#suSteps li").forEach((li) => { const i = +li.dataset.n; li.classList.toggle("on", i === page); li.classList.toggle("done", i < page); });
    enter(page);
  }
  function enter(p) {
    if (p === 0 && firstRun && !enter.greeted) { enter.greeted = true; say("Bienvenido a bordo. Antes de despegar, vamos a terminar de configurarme."); }
    if (p === 1) Trad.wizard();
    if (p === 2) { say(`Hola. Soy tu nueva inteligencia de a bordo. ¿Cómo te llamas?`); setTimeout(() => $("#suPilot").focus(), 50); }
    if (p === 3) { say(`Un placer, ${pilot()}. ¿Y cómo quieres que me llame yo?`); setTimeout(() => $("#suName").focus(), 50); checkName(); }
    if (p === 4) {
      $("#suHello").textContent = name();
      buildExercises();
      say(`Perfecto, mi nombre es ${name()}. Vamos a entrenar mis oídos para ver cómo se pronuncia mi nombre y familiarizarme con tu voz. Escucha cómo lo digo yo: ${name()}. Ahora dilo tú, tres veces.`);
    }
    if (p === 5) { buildPhrases(); say("A continuación, lee las siguientes tres frases que contienen mi nombre."); }
    if (p === 6) summary();
  }

  // --- paso 1: micrófono
  async function loadMic() {
    const d = await api("devices");
    $("#suMic").innerHTML = `<option value="(predeterminado)">(predeterminado de Windows)</option>` + d.inputs.map((n) => `<option>${esc(n)}</option>`).join("");
    $("#suMic").value = S.dispositivo_entrada || "(predeterminado)";
    sttInfo();
  }
  function sttInfo() {
    const st = info.stt || {};
    $("#suSttInfo").textContent = st.mode === "groq" ? "En la nube con Groq: instantáneo ✓"
      : "En tu PC con Whisper (la primera vez descarga el modelo y tarda un poco). Con una clave gratis de Groq es instantáneo.";
    $("#suNoMic").hidden = !!info.mic;
  }
  $("#suMic").addEventListener("change", safe(async () => { S.dispositivo_entrada = await api("set", { key: "dispositivo_entrada", value: $("#suMic").value }); }));
  $("#suGroq").addEventListener("change", safe(async () => {
    const ok = await api("set_key", { provider: "groq", value: $("#suGroq").value });
    $("#suGroq").value = ""; $("#suGroq").placeholder = ok ? "•••••••• clave de Groq guardada" : "Opcional: clave gratis de Groq";
    info = await api("setup_begin"); sttInfo(); toast(ok ? "Clave de Groq guardada" : "Clave borrada", "ok");
  }));

  // --- pasos 2 y 3: nombres
  function typed(input, v, n, nextBtn) {
    const val = input.value.trim();
    verdict(v, val ? true : null);
    note(n, val ? { ok: true, note: input === $("#suPilot") ? `Te llamas ${val}.` : `Me llamaré ${val}.` } : null);
    nextBtn.disabled = !val;
  }
  $("#suPilot").addEventListener("input", () => typed($("#suPilot"), $("#vPilot"), $("#nPilot"), $("#suNext1")));
  $("#suName").addEventListener("input", () => { typed($("#suName"), $("#vName"), $("#nName"), $("#suNext2")); clearTimeout(checkName.t); checkName.t = setTimeout(checkName, 300); });
  async function checkName() {
    const w = await api("setup_check_name", { nombre: name() }).catch(() => "");
    $("#wName").hidden = !w; $("#wName").textContent = w ? "⚠ " + w : "";
    $("#suNext2").disabled = !$("#suName").value.trim();
  }
  $$("[data-listen]", box).forEach((b) => b.addEventListener("click", async () => {
    const kind = b.dataset.listen, input = $(b.dataset.target);
    const v = kind === "piloto" ? $("#vPilot") : $("#vName"), n = kind === "piloto" ? $("#nPilot") : $("#nName");
    const r = await listen(b, kind);
    if (!r) return;
    if (r.value) input.value = r.value;
    verdict(v, r.ok); note(n, r);
    (kind === "piloto" ? $("#suNext1") : $("#suNext2")).disabled = !input.value.trim();
    if (kind === "ia") checkName();
    if (r.ok) say(kind === "piloto" ? `Entendido, ${r.value}.` : `¿${r.value}? Me gusta.`);
    else say("Perdona, no te he entendido. ¿Puedes repetirlo?");
  }));

  // --- paso 4: ejercicios de sonido
  function rowHTML(i, text, kind) {
    return `<div class="su-row" data-i="${i}"><span class="n">${String(i + 1).padStart(2, "0")}</span>
      <span class="ph">${text}</span><button class="btn mic-btn" data-rec="${kind}">🎙 GRABAR</button><span class="verdict"></span>
      <div class="su-note"></div></div>`;
  }
  function wireRows(container, kind, store) {
    const rows = $$(".su-row", container);
    const markNext = () => { const i = store.findIndex((r) => !r || !r.ok); rows.forEach((r, j) => r.classList.toggle("next", j === i)); };
    rows.forEach((row, i) => {
      const r = store[i];
      if (r) { verdict($(".verdict", row), r.ok); note($(".su-note", row), r); row.classList.add(r.ok ? "okr" : "badr"); }
      $("[data-rec]", row).addEventListener("click", async (e) => {
        const res = await listen(e.currentTarget, kind, i);
        if (!res) return;
        store[i] = res;
        row.classList.remove("okr", "badr"); row.classList.add(res.ok ? "okr" : "badr");
        verdict($(".verdict", row), res.ok); note($(".su-note", row), res);
        if (res.variantes) S.nombre_variantes = res.variantes;
        markNext();
        if (!res.ok) say("No te he entendido. Repítelo, por favor.");
        else if (store.every((x) => x && x.ok)) say(kind === "ejercicio" ? "Perfecto. Ya sé cómo suena mi nombre en tu voz." : "Excelente. Entrenamiento completado.");
      });
    });
    markNext();
  }
  function buildExercises() {
    const hl = `Di «<span class="hl">${esc(name())}</span>»`;
    $("#suEx").innerHTML = [0, 1, 2].map((i) => rowHTML(i, hl, "ejercicio")).join("");
    wireRows($("#suEx"), "ejercicio", results.ex);
  }
  $("#suHear").addEventListener("click", () => say(`${name()}. ... ${name()}.`));
  function buildPhrases() {
    const n = name();
    const hl = (t) => esc(t).replace(new RegExp(n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), (m) => `<span class="hl">${m}</span>`);
    if (results.ph.length !== info.frases.length) results.ph = Array(info.frases.length).fill(null);
    $("#suPh").innerHTML = info.frases.map((f, i) => rowHTML(i, "«" + hl(f) + "»", "frase")).join("");
    wireRows($("#suPh"), "frase", results.ph);
  }

  // --- paso 6: resumen
  function summary() {
    const okEx = results.ex.filter((r) => r && r.ok).length, okPh = results.ph.filter((r) => r && r.ok).length;
    const vars = S.nombre_variantes || [];
    $("#suSum").innerHTML = `
      <span>Tu nombre</span><b>${esc(pilot())}</b>
      <span>Te llamaré</span><b>${esc(trat())}</b>
      <span>Mi nombre</span><b>${esc(name())}</b>
      <span>Ejercicios de sonido</span><b class="${okEx === 3 ? "ok" : ""}">${okEx} de 3 ✓</b>
      <span>Frases de entrenamiento</span><b class="${okPh === results.ph.length ? "ok" : ""}">${okPh} de ${results.ph.length} ✓</b>
      <span>Cómo oigo mi nombre en tu voz</span><b>${vars.length ? esc([name().toLowerCase(), ...vars].join(" · ")) : esc(name().toLowerCase()) + " (tal cual)"}</b>`;
    $("#suKeyRow").hidden = !!(info.keys && info.keys.gemini);
    say(`Todo listo, ${trat()}. Pulsa terminar y despegamos.`);
  }
  $("#suGemini").addEventListener("change", safe(async () => {
    const ok = await api("set_key", { provider: "gemini", value: $("#suGemini").value });
    $("#suGemini").value = ""; $("#suGemini").placeholder = ok ? "•••••••• clave de Gemini guardada" : "Opcional: clave gratis de Google Gemini";
    if (STATE.keys_set) STATE.keys_set.gemini = ok;
    toast(ok ? "Clave de Gemini guardada" : "Clave borrada", "ok");
  }));

  // --- navegación
  $$("[data-prev]", box).forEach((b) => b.addEventListener("click", () => show(page - 1)));
  $$("[data-next]", box).forEach((b) => b.addEventListener("click", safe(async () => {
    if (page === 3) {  // guarda los nombres antes de entrenar el oído con el nombre nuevo
      const before = info.nombre;
      info = await api("setup_save", { piloto: pilot(), nombre: name(), tratamiento: trat() });
      S.nombre_asistente = info.nombre; S.nombre_piloto = info.piloto; S.tratamiento = info.tratamiento; S.nombre_variantes = info.variantes;
      if (before !== info.nombre) { results.ex.fill(null); results.ph = []; }
      ["nombre_asistente", "nombre_piloto", "tratamiento"].forEach(showSetting); paintNames();
    }
    if (page === 4 && !results.ex.some((r) => r && r.ok) && info.mic && !confirm("Aún no has hecho ningún ejercicio. Sin ellos me costará más reconocer mi nombre. ¿Seguir igualmente?")) return;
    if (page === 5 && !results.ph.some((r) => r && r.ok) && info.mic && !confirm("No has leído ninguna frase. ¿Seguir igualmente?")) return;
    show(page + 1);
  })));
  $("#suFinish").addEventListener("click", safe(async () => {
    const r = await api("setup_finish");
    S.asistente_completado = true; S.nombre_variantes = r.variantes;
    if (r.sensibilidad != null) { S.sensibilidad_vad = r.sensibilidad; showSetting("sensibilidad_vad"); }
    paintNames(); box.hidden = true;
    toast(`Configuración guardada · ${r.nombre} ya reconoce su nombre en tu voz`, "ok");
  }));
  $("#suClose").addEventListener("click", safe(async () => { await api("setup_close"); box.hidden = true; }));

  async function open(first) {
    firstRun = first;
    info = await api("setup_begin");
    results.ex.fill(null); results.ph = [];
    $("#suPilot").value = info.piloto || ""; $("#suName").value = info.nombre || "Nova";
    const tr = [...$("#suTrat").options].map((o) => o.value);
    $("#suTrat").value = tr.includes(info.tratamiento) ? info.tratamiento : (info.tratamiento === info.piloto && info.piloto ? "__nombre" : "señor");
    ["#vPilot", "#vName"].forEach((v) => verdict($(v), null)); ["#nPilot", "#nName"].forEach((n) => note($(n), null));
    $("#suNext1").disabled = !pilot(); $("#suNext2").disabled = !$("#suName").value.trim();
    $("#suClose").hidden = first;
    buildMeter($("#suMeter"), 16);
    box.hidden = false;
    show(0);
    loadMic().catch(() => {});
  }
  return { open, phase };
})();

// ============================================================ inicio
bindSettings();
buildSpots();
requestAnimationFrame(ovFrame);
loadState().then(() => { connect(); loadCommands(); }).catch((e) => { toast("No puedo hablar con Nova: " + e.message, "bad"); document.body.classList.add("offline"); });
