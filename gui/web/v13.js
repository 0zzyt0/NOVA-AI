/* NOVA AI 1.3 · Actualizaciones desde GitHub: aviso «¿Quieres actualizar ahora?» y progreso. */
"use strict";
window.V13 = (() => {
  let info = {};
  let dismissed = false;  // el usuario ya respondió en esta ventana
  const modal = $("#updModal");

  function md(text) {  // notas de la versión: texto plano con viñetas sencillas
    return esc(text || "").replace(/^#+\s*(.*)$/gm, "<b>$1</b>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/^\s*[-*]\s+/gm, "• ").replace(/\n/g, "<br>");
  }
  function paint(i) {
    info = i || {};
    const st = info.estado;
    $("#updNew").textContent = info.nueva || "";
    $("#updCur").textContent = info.actual || "";
    $("#updNotes").innerHTML = info.notas ? md(info.notas) : '<span class="muted">Sin notas de la versión.</span>';
    if (info.pagina) $("#updPage").href = info.pagina;
    const busy = st === "descargando";
    $("#updBar").hidden = !(busy || st === "listo");
    $("#updFill").style.width = Math.round((info.progreso || 0) * 100) + "%";
    $("#updPct").textContent = st === "listo" ? "Descargado · abriendo el instalador…" : Math.round((info.progreso || 0) * 100) + " %";
    $$("[data-upd]").forEach((b) => (b.disabled = busy));
    const chip = $("#updChip");
    const map = { al_dia: T("AL DÍA"), disponible: T("NUEVA {v}", { v: info.nueva || "" }), descargando: T("DESCARGANDO"), listo: T("LISTA"),
      error: T("SIN CONEXIÓN"), comprobando: T("COMPROBANDO…"), inactivo: "—" };
    chip.textContent = map[st] || "—";
    chip.className = "chip" + (st === "disponible" || st === "listo" ? " warn" : st === "error" ? " dim" : "");
    let txt = T("Versión instalada: {v}", { v: info.actual || "?" });
    if (info.comprobado) txt += " · " + T("comprobado a las {h}", { h: new Date(info.comprobado * 1000).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" }) });
    if (st === "error" && info.error) txt += " · " + T(info.error);
    if (info.eleccion === "al_cerrar") txt += " · " + T("se instalará al cerrar NOVA");
    $("#updInfo").textContent = txt;
    $("#btnUpdShow").hidden = !(st === "disponible" || st === "listo");
  }
  function ask() {
    if (dismissed || !(info.estado === "disponible" || info.estado === "listo") || info.eleccion) return;
    if (!$("#setup").hidden) return;  // no interrumpir la configuración inicial
    modal.hidden = false;
  }
  $$("[data-upd]").forEach((b) => b.addEventListener("click", safe(async () => {
    const choice = b.dataset.upd;
    const msg = await api("update_choice", { eleccion: choice });
    if (choice !== "ahora") { dismissed = true; modal.hidden = true; }
    toast(msg, "ok");
  })));
  $("#btnUpdCheck").addEventListener("click", safe(async () => {
    $("#updChip").textContent = "COMPROBANDO…";
    paint(await api("update_check"));
    if (info.estado === "al_dia") toast("NOVA AI está al día (" + info.actual + ")", "ok");
    else if (info.estado === "disponible") { dismissed = false; info.eleccion = ""; ask(); }
    else if (info.estado === "error") toast("No se pudo comprobar: " + (info.error || "sin conexión"), "bad");
  }));
  $("#btnUpdShow").addEventListener("click", () => { dismissed = false; modal.hidden = false; });
  return {
    onEvent(ev) {
      if (ev.t !== "actualizacion") return;
      api("update_info").then((i) => { paint(i); if (ev.preguntar) { dismissed = false; ask(); } }).catch(() => {});
    },
    afterState() { paint(STATE.actualizacion || {}); ask(); },
    onSection(sec) { if (sec === "datos") api("update_info").then(paint).catch(() => {}); },
  };
})();
