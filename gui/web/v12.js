/* NOVA AI 1.2 · Hologramas: vista previa, pruebas y estado. */
"use strict";
window.V12 = (() => {
  async function preview() {
    try {
      const r = await api("holo_preview");
      if (r && r.png) $("#holoPrev").innerHTML = `<img src="${r.png}" alt="Holograma">`;
      $("#holoStatus").textContent = r && r.status ? "Overlay: " + r.status : "";
    } catch (e) { /* sin ficha todavía */ }
  }
  $$("[data-holo-test]").forEach((b) => b.addEventListener("click", safe(async () => {
    b.disabled = true;
    try {
      const r = await api("holo_test", { tipo: b.dataset.holoTest });
      if (r && r.png) $("#holoPrev").innerHTML = `<img src="${r.png}" alt="Holograma">`;
      toast(r && r.nota ? r.nota : "Holograma en pantalla", "ok");
    } finally { b.disabled = false; }
  })));
  $("#btnHoloHide").addEventListener("click", safe(async () => { await api("holo_hide"); }));
  return {
    onEvent(ev) { if (ev.t === "holo") preview(); },
    onSection(sec) { if (sec === "interfaz") preview(); },
  };
})();
