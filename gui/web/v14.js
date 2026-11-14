/* NOVA AI 1.4 · modo reposo, bandeja de Windows y cuestionario anónimo.
   - Botón 💤 / ☀ en la Cabina, «EN REPOSO» en el núcleo y en el medidor.
   - ⤓ en la cabecera y en Ajustes › General: cerrar la ventana y seguir en la bandeja. */
(() => {
  "use strict";
  const $ = (q) => document.querySelector(q);
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const call = (fn, args) => (typeof api === "function" ? api(fn, args) : Promise.reject(new Error("api")));
  const say = (text, kind) => { if (typeof toast === "function") toast(text, kind || ""); };
  let asleep = null;

  // ------------------------------------------------------------ modo reposo
  function paintSleep(on) {
    if (on === asleep) return;
    asleep = on;
    document.body.classList.toggle("asleep", on);
    const b = $("#btnSleep");
    if (b) {
      b.textContent = on ? "☀" : "💤";
      b.classList.toggle("on", on);
      b.title = T(on ? "Despertar a Nova" : "Modo reposo: deja de escuchar hasta que pulses tu tecla");
      b.setAttribute("aria-pressed", on ? "true" : "false");
    }
    const st = $("#sleepState");
    if (st) st.textContent = on ? T("ACTIVO") : "";
    const hint = $("#pttHint");
    if (hint) {
      if (on) {
        hint.dataset.v14 = hint.textContent;
        const k = (typeof STATE !== "undefined" && STATE && STATE.ptt_text) || "—";
        hint.textContent = (typeof S !== "undefined" && S.reposo_despertar === "nombre")
          ? T("En reposo · pulsa {k} o di «{n}» para despertarla", { k, n: (typeof S !== "undefined" && S.nombre_asistente) || "Nova" })
          : T("En reposo · pulsa {k} o ☀ para despertarla", { k });
      } else if (hint.dataset.v14 !== undefined) {
        hint.textContent = hint.dataset.v14;
        delete hint.dataset.v14;
      }
    }
  }
  async function toggleSleep(want) {
    try {
      const on = await call("sleep", { on: want === undefined ? !asleep : want });
      paintSleep(!!on);
    } catch (e) { say(String(e.message || e), "bad"); }
  }
  function wakeNote() {
    const n = $("#sleepWakeNote");
    if (!n || typeof S === "undefined") return;
    n.textContent = S.reposo_despertar === "nombre"
      ? T("El micrófono sigue abierto para oír su nombre (con Groq gasta algo de cuota)")
      : T("Con la tecla: el micrófono se apaga del todo");
  }

  // ------------------------------------------------------------ bandeja
  function paintTray(ok) {
    const b = $("#btnTray");
    if (b) b.hidden = !ok;
    const b2 = $("#btnTray2");
    if (b2) b2.disabled = !ok;
    const h = $("#trayHint");
    if (h) h.textContent = ok ? T("Icono en la bandeja activo") : T("Sin icono en la bandeja (solo en Windows)");
  }
  async function toTray() {
    try {
      const ok = await call("to_tray");
      if (!ok) say(T("No hay icono en la bandeja: activa «Al cerrar la ventana, seguir en la bandeja»."), "bad");
    } catch (e) { say(String(e.message || e), "bad"); }
  }


  // ------------------------------------------------------------ cuestionario anónimo
  const answers = {};
  let survey = null;
  const modalOpen = () => [...document.querySelectorAll(".modal")].some((m) => !m.hidden);
  function openSurvey() {
    $("#qnForm").hidden = false;
    $("#qnDone").hidden = true;
    $("#qnMsg").textContent = "";
    $("#surveyModal").hidden = false;
  }
  function closeSurvey() { $("#surveyModal").hidden = true; }
  function paintAnswers() {
    document.querySelectorAll("#surveyModal .qn-q").forEach((q) => {
      const v = answers[q.dataset.q];
      q.querySelectorAll("button").forEach((b) => b.classList.toggle("on", v !== undefined && String(v) === b.dataset.v));
    });
    $("#qnSend").disabled = !Object.values(answers).some((v) => v !== "ns");
  }
  async function sendSurvey() {
    const b = $("#qnSend");
    b.disabled = true;
    $("#qnMsg").textContent = T("Enviando…");
    try {
      const msg = await call("survey_send", { respuestas: answers, idea: $("#qnIdea").value });
      $("#qnForm").hidden = true;
      $("#qnDone").hidden = false;
      $("#qnDone .qn-thanks").textContent = T(msg);
      if (survey) survey.estado = "enviado";
      paintSurveyBtn();
    } catch (e) {
      $("#qnMsg").textContent = T(String(e.message || e));
      b.disabled = false;
    }
  }
  function paintSurveyBtn() {
    const b = $("#btnSurvey");
    if (!b) return;
    b.hidden = !(survey && survey.disponible);
    b.classList.toggle("done", !!(survey && survey.estado === "enviado"));
  }
  function askLater() {
    $("#qnAsk1").hidden = true;
    $("#qnAsk2").hidden = false;
  }
  async function later(remind) {
    try { survey = await call("survey_later", { recordar: remind }); } catch { /* se volverá a preguntar */ }
    $("#surveyAsk").hidden = true;
    if (typeof toast === "function")
      toast(T(remind ? "De acuerdo: te lo recuerdo dentro de 3 días." : "De acuerdo, no te lo volveré a preguntar. El botón «Cuestionario» sigue en el lateral."), "ok");
  }
  function maybeAsk(tries = 0) {
    if (!survey || !survey.aviso) return;
    if (modalOpen() || !document.getElementById("setup").hidden || document.body.classList.contains("touring")) {
      if (tries < 20) setTimeout(() => maybeAsk(tries + 1), 15000);  // después de otros avisos
      return;
    }
    survey.aviso = false;
    $("#qnAsk1").hidden = false;
    $("#qnAsk2").hidden = true;
    $("#surveyAsk").hidden = false;
  }
  document.addEventListener("click", (e) => {
    const t = e.target.closest ? e.target.closest("button") : null;
    if (!t) return;
    if (t.id === "btnSurvey") openSurvey();
    else if (t.closest("#surveyModal .qn-scale")) { answers[t.closest(".qn-q").dataset.q] = t.dataset.v; paintAnswers(); }
    else if (t.id === "qnSend") sendSurvey();
    else if (t.id === "qnCancel" || t.id === "qnClose") closeSurvey();
    else if (t.id === "qnAskYes") { $("#surveyAsk").hidden = true; openSurvey(); }
    else if (t.id === "qnAskNo") askLater();
    else if (t.id === "qnRemind") later(true);
    else if (t.id === "qnNever") later(false);
  });
  document.addEventListener("input", (e) => {
    if (e.target && e.target.id === "qnIdea") $("#qnCount").textContent = `${e.target.value.length} / 2000`;
  });

  // ------------------------------------------------------------ enganches
  document.addEventListener("click", (e) => {
    const id = e.target && e.target.id;
    if (id === "btnSleep") toggleSleep();
    else if (id === "btnSleepNow") toggleSleep(true);
    else if (id === "btnTray" || id === "btnTray2") toTray();
  });
  document.addEventListener("change", (e) => {
    if (e.target && e.target.dataset && e.target.dataset.set === "reposo_despertar") setTimeout(wakeNote, 300);
  });

  window.V14 = {
    lv(ev) { if ("sleep" in ev) paintSleep(!!ev.sleep); },
    state(st) {
      if (!st) return;
      paintTray(!!st.bandeja);
      paintSleep(!!st.reposo);
      wakeNote();
      survey = st.cuestionario || null;
      paintSurveyBtn();
      if (survey && survey.aviso) setTimeout(maybeAsk, 9000);  // al iniciar, cuando ya ha saludado
      setTimeout(() => { if (window.Tour) Tour.maybeStart(); }, 4000);  // 1.4: recorrido guiado una vez
    },
    onEvent(ev) {
      if (ev.t === "reposo") paintSleep(!!ev.on);
    },
  };
})();
