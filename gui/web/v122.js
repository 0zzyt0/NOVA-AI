/* NOVA AI 1.2.2 · Interruptor de la cabina, sonidos propios, chat del juego, Discord y ahorro de tokens. */
"use strict";
window.V122 = (() => {
  // ------------------------------------------------------------ interruptor: detener a Nova
  function power(on) {
    const sw = $("#swNova");
    if (sw && sw !== document.activeElement) sw.checked = on;
    $("#powerLine").classList.toggle("off", !on);
    $("#powerTxt").innerHTML = on ? '◉ <span class="ai-name up">' + esc((S.nombre_asistente || "Nova").toUpperCase()) + "</span> ACTIVA"
      : '■ <span class="ai-name up">' + esc((S.nombre_asistente || "Nova").toUpperCase()) + "</span> DETENIDA";
    $("#powerSub").textContent = on ? "Apágalo para detener todas las búsquedas y pararla"
      : "Búsquedas canceladas · enciéndelo (o di «actívate») para volver";
  }

  // ------------------------------------------------------------ sonidos propios
  function paintSfxNames() {
    [["holo_on", "holo_sonido_on"], ["holo_off", "holo_sonido_off"], ["alerta", "holo_sonido_alerta"]].forEach(([ev, key]) => {
      const el = $(`[data-sfx-name="${ev}"]`);
      if (el) el.textContent = S[key] === "archivo" ? "Archivo: " + (S[key + "_nombre"] || "propio") : "";
    });
  }
  function pick(ev) { $(`[data-sfx-file="${ev}"]`).click(); }
  $$("[data-sfx-pick]").forEach((b) => b.addEventListener("click", () => pick(b.dataset.sfxPick)));
  $$("[data-set^='holo_sonido_']").forEach((sel) => {
    if (sel.tagName !== "SELECT") return;
    sel.addEventListener("change", () => {
      const ev = sel.closest("[data-sfx-row]").dataset.sfxRow;
      if (sel.value === "archivo" && !S[sel.dataset.set + "_archivo"]) pick(ev);
      setTimeout(paintSfxNames, 50);
    });
  });
  $$("[data-sfx-file]").forEach((inp) => inp.addEventListener("change", safe(async () => {
    const f = inp.files && inp.files[0];
    inp.value = "";
    if (!f) return;
    if (f.size > 4 * 1024 * 1024) { toast("El archivo es demasiado grande (máximo 4 MB)", "bad"); return; }
    const datos = await new Promise((ok, ko) => {
      const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => ko(new Error("No pude leer el archivo")); r.readAsDataURL(f);
    });
    const ev = inp.dataset.sfxFile;
    const r = await api("sfx_upload", { evento: ev, nombre: f.name, datos });
    const key = { holo_on: "holo_sonido_on", holo_off: "holo_sonido_off", alerta: "holo_sonido_alerta" }[ev];
    S[key] = "archivo"; S[key + "_nombre"] = r.nombre; S[key + "_archivo"] = "x";
    showSetting(key); paintSfxNames();
    toast(`Sonido propio guardado (${r.segundos} s)`, "ok");
  })));

  // ------------------------------------------------------------ chat del juego
  async function chatTest(enviar) {
    const t = $("#chatTestIn").value.trim();
    if (!t) { toast("Escribe un mensaje de prueba", "bad"); return; }
    const r = await api("chat_test", { texto: t, enviar });
    const motor = { google: "Google Translate", ia: "IA", guardada: "traducción guardada" }[r.motor] || "";
    $("#chatTestOut").innerHTML = `«${esc(r.traduccion)}»` + (motor ? ` <span class="muted">· ${motor}</span>` : "")
      + (enviar ? '<br><b class="warn">Vuelve a Star Citizen: se escribe en 5 segundos…</b>' : "");
  }
  $("#btnChatTr").addEventListener("click", safe(() => chatTest(false)));
  $("#btnChatSend").addEventListener("click", safe(() => chatTest(true)));
  $("#chatTestIn").addEventListener("keydown", (e) => { if (e.key === "Enter") safe(() => chatTest(false))(); });

  const msgIn = $("#msgIn");
  function askChat() {
    msgIn.placeholder = "Mensaje para el chat del juego (se traduce)… y pulsa Enter";
    msgIn.classList.add("ask-chat");
    clearTimeout(askChat.t);
    askChat.t = setTimeout(resetChat, 120000);
  }
  function resetChat() {
    if (!msgIn.classList.contains("ask-chat")) return;
    msgIn.classList.remove("ask-chat");
    msgIn.placeholder = T("Escribe a {n}… (o mantén tu tecla para hablar)", { n: S.nombre_asistente || "Nova" });
  }
  msgIn.addEventListener("keydown", (e) => { if (e.key === "Enter") setTimeout(resetChat, 50); });

  // ------------------------------------------------------------ Discord: último envío
  function paintDiscord(d) {
    const el = $("#dcLast");
    if (!el) return;
    if (!d || !d.hora) { el.textContent = ""; return; }
    const when = new Date(d.hora * 1000).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });
    el.textContent = T("Último envío ({h}):", { h: when }) + " " + T((d.texto || "").replace(/^📨 |^⚠ /, ""));
    el.className = "small";
    el.style.color = d.ok ? "var(--ok)" : "var(--bad)";
  }

  // ------------------------------------------------------------ ahorro de tokens
  function paintSavings(a) {
    if (!a) return;
    $("#svAns").textContent = a.respuestas_guardadas || 0;
    $("#svLoc").textContent = a.respuestas_locales || 0;
    $("#svTr").textContent = (a.traducciones_google || 0) + (a.traducciones_guardadas || 0);
    $("#svCount").textContent = a.respuestas || 0;
    $("#svTrCount").textContent = a.traducciones || 0;
    $("#saveChip").textContent = T("{n} SIN IA", { n: a.total || 0 });
    $("#saveChip").className = "chip" + (a.total ? " ok" : " dim");
    const rows = a.recientes || [];
    $("#svList").innerHTML = rows.length ? rows.map((r) => `<div>${esc(r.fecha)} · ${esc(r.pregunta)}`
      + (r.usos ? ` <span class="muted">(${r.usos}× sin IA)</span>` : "") + "</div>").join("")
      : '<div class="muted">Todavía no hay respuestas guardadas.</div>';
  }
  async function loadSavings() { paintSavings(await api("savings")); }
  $("#btnAnsClear").addEventListener("click", safe(async () => {
    const n = await api("answers_clear"); toast(`${n} respuestas borradas`, "ok"); loadSavings();
  }));
  $("#btnTrClear").addEventListener("click", safe(async () => {
    const n = await api("translations_clear"); toast(`${n} traducciones borradas`, "ok"); loadSavings();
  }));

  // ------------------------------------------------------------ Diccionario de consultas
  async function loadDictionary() {
    const d = await api("dictionary_info");
    $("#dicN").textContent = (d.entradas || 0).toLocaleString(LOCALE);
    $("#dicL").textContent = d.aprendidas || 0;
    $("#dicE").textContent = d.editadas || 0;
    $("#dicChip").textContent = d.existe ? `${d.tamano_kb.toLocaleString(LOCALE)} KB` : T("SIN CREAR");
    $("#dicChip").className = "chip" + (d.existe ? " ok" : " dim");
    $("#dicGroups").innerHTML = Object.entries(d.grupos || {}).sort((a, b) => a[0].localeCompare(b[0], LOCALE))
      .map(([g, n]) => `<div>${esc(T(g))} · ${n}</div>`).join("") || '<div class="muted">Todavía vacío.</div>';
  }
  async function searchDictionary() {
    const q = $("#dicQ").value.trim();
    if (!q) return;
    const r = await api("dictionary_search", { consulta: q });
    const out = $("#dicOut");
    out.hidden = false;
    out.textContent = r.encontrado ? r.texto : `«${q}» no está en el diccionario. Pregúntaselo a ${S.nombre_asistente || "Nova"} y lo aprenderá.`;
  }
  $("#btnDicQ").addEventListener("click", safe(searchDictionary));
  $("#dicQ").addEventListener("keydown", (e) => { if (e.key === "Enter") safe(searchDictionary)(); });
  $("#btnDicOpen").addEventListener("click", safe(() => api("dictionary_open")));
  $("#btnDicRefresh").addEventListener("click", safe(async () => {
    const n = await api("dictionary_refresh"); toast(n ? `${n} entradas actualizadas` : "El diccionario ya estaba al día", "ok"); loadDictionary();
  }));

  return {
    power,
    onEvent(ev) {
      if (ev.t === "detenida") power(false);
      else if (ev.t === "activa") power(true);
      else if (ev.t === "pedir_chat") askChat();
      else if (ev.t === "discord") paintDiscord(ev);
      else if (ev.t === "diccionario" && $("#sec-datos").classList.contains("on")) loadDictionary().catch(() => {});
    },
    onSection(sec) {
      if (sec === "ia") loadSavings().catch(() => {});
      if (sec === "memoria") loadDictionary().catch(() => {});
    },
    afterState() {
      paintSfxNames();
      paintDiscord(STATE.discord_last);
      paintSavings(STATE.ahorro);
      power(!(typeof live !== "undefined" && live && live.paused));
    },
  };
})();
