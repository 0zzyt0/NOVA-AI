/* NOVA AI 2.1 · Telemetría en directo del juego (Juego › Avisos del juego). */
(() => {
  "use strict";
  const $ = (q) => document.querySelector(q);
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const call = (fn, args) => (typeof api === "function" ? api(fn, args) : Promise.reject(new Error("api")));
  const say = (text, kind) => { if (typeof toast === "function") toast(text, kind || ""); };
  const h = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  if (!$("#telePanel")) return;

  const NAMES = { salud: "SALUD", sed: "HIDRATACIÓN", hambre: "NUTRICIÓN", oxigeno: "OXÍGENO",
    hidrogeno: "HIDRÓGENO", cuantico: "CUÁNTICO", escudos: "ESCUDOS", casco: "CASCO" };
  const LOW = { salud: 0.35, sed: 0.25, hambre: 0.25, oxigeno: 0.25, hidrogeno: 0.2, cuantico: 0.15, escudos: 0.25, casco: 0.5 };

  function paintReader(t) {
    const chip = $("#teleChip");
    if (!t) return;
    chip.textContent = t.conectada ? T("EN DIRECTO") : t.activa === false ? T("APAGADA") : T("SIN CONEXIÓN");
    chip.className = "chip " + (t.conectada ? "ok" : "");
    chip.title = t.status || "";
    const v = t.valores || {};
    const cells = Object.keys(NAMES).filter((k) => typeof v[k] === "number").map((k) => {
      const p = Math.round(v[k] * 100);
      const cls = v[k] <= LOW[k] / 2 ? "bad" : v[k] <= LOW[k] ? "warn" : "";
      return `<div class="tele-v ${cls}"><b>${h(T(NAMES[k]))}</b><span>${p} %</span><i style="--p:${p}%"></i></div>`;
    });
    const where = [t.nave, t.lugar].filter(Boolean).join(" · ");
    if (t.conectada && where) cells.push(`<div class="tele-where">${h(where)}</div>`);
    $("#teleGrid").innerHTML = t.conectada ? cells.join("") : "";
    if (!t.conectada) $("#teleMsg").dataset.reader = t.status || "";
    showMsg();
  }

  let lastAction = "";
  function showMsg() {
    const r = $("#teleMsg").dataset.reader || "";
    $("#teleMsg").textContent = [lastAction, r ? T("Estado: {s}", { s: r }) : ""].filter(Boolean).join("  ·  ");
  }

  function paintSetup(st) {
    if (!st) return;
    $("#teleChans").innerHTML = (st.canales || []).map((c) => {
      const ok = c.cfg && (c.lee_cfg || st.variable);
      return `<span class="chip ${ok ? "ok" : "warn"}" title="${h(c.ruta)}">${h(c.canal)} ${h((c.version || "").split(".").slice(0, 2).join("."))} · ${ok ? T("activada") : T("sin activar")}</span>`;
    }).join("") + (st.canales && st.canales.length ? `<span class="chip ${st.variable ? "ok" : "warn"}">${T("variable de Windows")}: ${st.variable ? T("sí") : T("no")}</span>` : "");
    $("#btnTeleInstall").hidden = !!st.componente;
    $("#btnTeleOn").textContent = st.activada ? T("VOLVER A ACTIVAR") : T("ACTIVAR EN STAR CITIZEN");
    if (st.lector) paintReader(st.lector);
  }

  async function refresh() {
    try { paintSetup(await call("telemetry_status")); } catch { /* Nova aún arrancando */ }
  }

  function busy(btn, on) { btn.disabled = on; }

  $("#btnTeleOn").addEventListener("click", async () => {
    const b = $("#btnTeleOn"); busy(b, true);
    try {
      const r = await call("telemetry_enable", { on: true });
      lastAction = r.mensaje || ""; paintSetup(r); say(T("Telemetría activada"), "ok");
    } catch (e) { say(e.message, "bad"); } finally { busy(b, false); showMsg(); }
  });
  $("#btnTeleOff").addEventListener("click", async () => {
    if (!confirm(T("¿Quitar la telemetría del user.cfg y la variable de Windows?"))) return;
    const b = $("#btnTeleOff"); busy(b, true);
    try {
      const r = await call("telemetry_enable", { on: false });
      lastAction = r.mensaje || ""; paintSetup(r);
    } catch (e) { say(e.message, "bad"); } finally { busy(b, false); showMsg(); }
  });
  $("#btnTeleInstall").addEventListener("click", async () => {
    const b = $("#btnTeleInstall"); busy(b, true);
    lastAction = T("Instalando el componente (Windows puede pedir permiso)…"); showMsg();
    try {
      const r = await call("telemetry_install");
      lastAction = r.mensaje || ""; say(lastAction, r.ok ? "ok" : "bad");
    } catch (e) { say(e.message, "bad"); } finally { busy(b, false); refresh(); }
  });
  $("#btnTeleSample").addEventListener("click", async () => {
    try {
      const r = await call("telemetry_sample");
      say(r.texto, r.ok ? "ok" : "");
    } catch (e) { say(e.message, "bad"); }
  });

  // El estado general (cada 3 s) ya trae el lector; la configuración se mira al abrir y cada 30 s.
  const origShow = window.showStatus;
  if (typeof origShow === "function") {
    window.showStatus = function (st) { origShow(st); if (st && st.telemetria) paintReader(st.telemetria); };
  } else {
    setInterval(() => call("status").then((st) => st && st.telemetria && paintReader(st.telemetria)).catch(() => {}), 3000);
  }
  setInterval(refresh, 30000);
  setTimeout(refresh, 1200);
})();
