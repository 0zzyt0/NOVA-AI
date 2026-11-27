/* NOVA AI 1.3.2 · el micrófono a la vista:
   - botón MUTE en el medidor del lateral (sin micrófono no oye ni con la tecla ni por su nombre);
   - en el asistente inicial y en Ajustes › Voz y audio, qué micrófono se abrió de verdad y, si no llega
     la voz, por qué (sin sonido, silencio total, silenciado…). */
(() => {
  "use strict";
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const IDS = ["suMicInfo", "micInfo"];
  let st = null, md = "", busy = false;

  async function refresh() {
    if (busy) return;
    busy = true;
    try { st = await api("mic_status"); } catch { st = null; } finally { busy = false; }
    paint();
  }
  function message() {
    if (!st) return ["", ""];
    const m = md || st.estado;
    if (m === "reposo") return ["warn", T("💤 En reposo: micrófono apagado hasta que la despiertes.")];
    if (!st.ok || m === "cerrado")
      return ["bad", T("⚠ No puedo abrir el micrófono. Elige otro en la lista o revisa que esté conectado y activado en Windows.")];
    if (m === "silenciado" || st.silenciado)
      return ["warn", T("🔇 Micrófono silenciado con el botón MUTE del medidor (lateral izquierdo).")];
    if (m === "sin_audio") return ["bad", T("⚠ Este micrófono no envía sonido. Prueba otro de la lista.")];
    if (m === "silencio")
      return ["bad", T("⚠ Llega silencio total: ¿está silenciado (botón de silencio o luz roja en los auriculares) o bloqueado en Windows › Privacidad y seguridad › Micrófono?")];
    if (st.reserva)
      return ["warn", T("⚠ No pude abrir «{a}»; uso el micrófono predeterminado de Windows: {d}", { a: st.elegido, d: st.dispositivo })];
    return ["ok", T("✓ Micrófono abierto: {d}", { d: st.dispositivo })];
  }
  function paint() {
    const [cls, text] = message();
    for (const id of IDS) {
      const el = document.getElementById(id);
      if (!el) continue;
      el.className = (id === "suMicInfo" ? "su-note mic-note " : "mic-info ") + cls;
      el.textContent = text;
    }
    paintMute(st ? !!st.silenciado : !!(typeof S !== "undefined" && S.microfono_silenciado));
  }
  const visible = () => IDS.some((id) => { const el = document.getElementById(id); return el && el.offsetParent; });

  // ---------------------------------------------------------------- botón MUTE
  function paintMute(on) {
    const b = document.getElementById("btnMicMute");
    if (!b) return;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
    b.textContent = on ? "MUTE ON" : "MUTE OFF";
    b.title = T(on ? "Micrófono silenciado: pulsa para volver a escuchar" : "Silenciar el micrófono: Nova no te oirá ni con la tecla ni por su nombre");
    document.body.classList.toggle("mic-muted", on);
  }
  async function toggleMute() {
    const on = !(st ? st.silenciado : (typeof S !== "undefined" && S.microfono_silenciado));
    try {
      const v = await api("set", { key: "microfono_silenciado", value: on });
      if (typeof S !== "undefined") S.microfono_silenciado = v;
      if (st) st.silenciado = !!v;
      paintMute(!!v);
      if (typeof toast === "function") toast(T(v ? "Micrófono silenciado" : "Micrófono activo"), v ? "" : "ok");
    } catch (e) { if (typeof toast === "function") toast(e.message, "bad"); }
    refresh();
  }

  window.MicInfo = {
    refresh,
    lv(ev) {
      const m = ev.md || "";
      if (m !== md) { md = m; refresh(); }
    },
  };
  document.addEventListener("click", (e) => { if (e.target && e.target.id === "btnMicMute") toggleMute(); });
  // al cambiar de micrófono (en el asistente o en ajustes), comprobar cuál se abrió
  document.addEventListener("change", (e) => {
    if (e.target && (e.target.id === "suMic" || e.target.id === "inDevs")) setTimeout(refresh, 700);
  });
  setInterval(() => { if (visible()) refresh(); }, 4000);
  const boot = () => setTimeout(refresh, 800);
  if (document.readyState !== "loading") boot(); else document.addEventListener("DOMContentLoaded", boot);
})();
