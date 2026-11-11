// NOVA AI v1.3: idioma, nivel de efectos, comprobación de páginas y «Add your language global.ini [HERE]».
window.V130 = (() => {
  const LANG = (window.I18N && I18N.lang) || "es";
  document.body.classList.toggle("lang-es", LANG === "es");
  document.body.dataset.lang = LANG;

  // ------------------------------------------------------------ idioma
  let langBusy = false;
  async function setLanguage(code) {
    if (langBusy || code === LANG) return;
    langBusy = true;
    try {
      const r = await api("set_language", { idioma: code });
      if (r.recargar) {
        toast(T("Cambiando de idioma…"), "ok");
        setTimeout(() => location.reload(), 500);
      }
    } finally { langBusy = false; }
  }
  // El selector de idioma no usa el guardado normal (data-set): cambia también voz, tratamiento y comandos.
  // Se muestra como cinco tarjetas grandes (cada una en su propio idioma, para que nadie se pierda).
  const LANGS = [["es", "Español", "Nova habla español"], ["en", "English", "Nova speaks English"],
                 ["ca", "Català", "La Nova parla català"], ["fr", "Français", "Nova parle français"],
                 ["de", "Deutsch", "Nova spricht Deutsch"]];
  $$(".lang-sel").forEach((sel) => {
    sel.removeAttribute("data-set");
    sel.value = LANG;
    sel.addEventListener("change", safe(() => setLanguage(sel.value)));
    const field = sel.closest(".field");
    const box = document.createElement("div");
    box.className = "lang-cards"; box.setAttribute("data-no-i18n", "");
    box.innerHTML = LANGS.map(([c, n, d]) => `<button type="button" class="lang-card${c === LANG ? " on" : ""}" data-lang="${c}">
      <b>${c.toUpperCase()}</b><span>${n}</span><small>${d}</small></button>`).join("");
    field.after(box);
    field.hidden = true;
    $$(".lang-card", box).forEach((b) => b.addEventListener("click", safe(async () => {
      $$(".lang-card").forEach((x) => x.classList.toggle("on", x.dataset.lang === b.dataset.lang));
      await setLanguage(b.dataset.lang);
    })));
  });

  // Solo en español: la traducción de 0zzyt0 (Google Drive) y su aviso
  $$(".es-only").forEach((el) => { el.hidden = LANG !== "es"; });

  // ------------------------------------------------------------ efectos
  function paintFx(v) {
    v = v || "cine";
    $$(".fx-card").forEach((c) => c.classList.toggle("on", c.dataset.fx === v));
    document.body.classList.toggle("fx-ligero", v === "ligero");
    document.body.classList.toggle("fx-ninguno", v === "ninguno");
    const sel = $("#fxSel"); if (sel) sel.value = v;
  }
  $$(".fx-card").forEach((c) => c.addEventListener("click", safe(async () => {
    await api("set", { key: "efectos_nivel", value: c.dataset.fx });
    S.efectos_nivel = c.dataset.fx;
    paintFx(c.dataset.fx);
    toast(T("Efectos: {x}", { x: c.querySelector("b").textContent.replace(/^[^A-Za-zÀ-ÿ]+/, "") }), "ok");
  })));

  // ------------------------------------------------------------ comprobar páginas
  const NAMES = {};
  function paintCheck(list) {
    const box = $("#chkList"); if (!box) return;
    box.innerHTML = list.map((r) => {
      const cls = !r.ok ? "bad" : (r.ms > 2500 ? "slow" : "ok");
      const why = r.ok ? `${r.ms} ms` : T(r.texto || r.error || "sin respuesta");
      return `<div class="chk-item ${cls}" title="${esc(r.url || "")}"><b></b><span>${esc(r.nombre)}</span><small>${esc(why)}</small></div>`;
    }).join("");
    const bad = list.filter((r) => !r.ok).length;
    const chip = $("#chkChip");
    chip.textContent = bad ? T("{n} sin respuesta", { n: bad }) : T("todas responden");
    chip.className = "chip " + (bad ? "bad" : "ok");
  }
  async function runCheck() {
    const b = $("#btnCheckSrc"); b.disabled = true;
    $("#chkChip").textContent = T("comprobando…"); $("#chkChip").className = "chip";
    try { paintCheck(await api("sources_check")); } finally { b.disabled = false; }
  }
  $("#btnCheckSrc") && $("#btnCheckSrc").addEventListener("click", safe(runCheck));

  // ------------------------------------------------------------ global.ini propio
  let gini = null;
  async function loadGini() {
    gini = await api("globalini_info");
    const st = $("#giniState"), chip = $("#giniChip");
    if (gini.propio) {
      st.textContent = T("Instalado: {ruta}", { ruta: gini.propio });
      chip.textContent = gini.propio_idioma; chip.className = "chip ok";
    } else {
      st.textContent = gini.live ? T("Juego encontrado en {live}", { live: gini.live }) : T("No encuentro Star Citizen: indica su carpeta abajo");
      chip.textContent = gini.idioma_juego || "—"; chip.className = "chip";
    }
    $("#btnGiniUndo").hidden = !gini.propio;
    const w = $("#giniStateWiz"); if (w) w.textContent = st.textContent;
  }
  function pickFile() {
    return new Promise((resolve) => {
      const inp = document.createElement("input");
      inp.type = "file"; inp.accept = ".ini";
      inp.onchange = () => resolve(inp.files[0] || null);
      inp.click();
    });
  }
  const readB64 = (f) => new Promise((ok, ko) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = ko; r.readAsDataURL(f); });
  $("#btnGini") && $("#btnGini").addEventListener("click", safe(async () => {
    const f = await pickFile();
    if (!f) return;
    if (!gini) await loadGini();
    const slot = gini.hueco;
    if (!confirm(T("Se instalará «{f}» en Star Citizen como idioma «{slot}» (se guarda una copia del que hubiera) y se ajustará user.cfg. ¿Continuar?", { f: f.name, slot }))) return;
    toast(T("Instalando el global.ini…"), "ok");
    const r = await api("globalini_install", { nombre: f.name, datos: await readB64(f), hueco: slot });
    toast(T("global.ini instalado: {n} textos · idioma del juego: {slot}", { n: r.textos.toLocaleString(), slot: r.idioma }), "ok");
    await loadGini();
  }));
  $("#btnGiniUndo") && $("#btnGiniUndo").addEventListener("click", safe(async () => {
    if (!confirm(T("¿Quitar el global.ini que instalaste y dejar el juego como estaba?"))) return;
    const r = await api("globalini_undo");
    toast(r.restaurado ? T("Restaurado el global.ini que había antes") : T("global.ini quitado"), "ok");
    await loadGini();
  }));

  // ------------------------------------------------------------ configuración inicial en otros idiomas
  const TRAT = { en: ["sir", "ma'am", "captain", "commander", "pilot"], ca: ["senyor", "senyora", "capità", "capitana", "comandant", "pilot"],
                 fr: ["monsieur", "madame", "capitaine", "commandant", "pilote"], de: ["Herr", "Frau", "Kapitän", "Kapitänin", "Kommandant", "Pilot"] };
  if (LANG !== "es") {
    const sel = $("#suTrat");
    if (sel && TRAT[LANG]) {
      sel.innerHTML = TRAT[LANG].map((t) => `<option>${esc(t)}</option>`).join("") + `<option value="__nombre">${esc(T("por mi nombre"))}</option>`;
      sel.setAttribute("data-no-i18n", "");
    }
    const page = $('#setup .su-page[data-p="1"]');
    if (page) {
      page.querySelector("h2").textContent = T("Los textos de Star Citizen en tu idioma");
      page.querySelector(".su-lead").textContent = T("Si tienes un global.ini de la comunidad en tu idioma, puedes instalarlo ahora o más tarde en Datos y memoria › Idioma del juego.");
      const ans = page.querySelector(".su-answer");
      if (ans) {
        ans.hidden = true;
        const box = document.createElement("div");
        box.className = "gini-box";
        box.innerHTML = `<button class="btn pri" id="btnGiniWiz">${esc(T("Añade el global.ini de tu idioma de Star Citizen [AQUÍ]"))}</button><span class="gini-state" id="giniStateWiz"></span>`;
        ans.after(box);
        $("#btnGiniWiz").addEventListener("click", () => $("#btnGini").click());
        loadGini().catch(() => {});
      }
    }
  }

  // ------------------------------------------------------------ Ajustes › General
  $("#btnAbout2") && $("#btnAbout2").addEventListener("click", () => $("#btnAbout").click());
  $("#btnManual2") && $("#btnManual2").addEventListener("click", () => $("#btnManual").click());

  return {
    onSection(sec) {
      if (sec === "datos") loadGini().catch(() => {});
    },
    afterState() {
      paintFx(S.efectos_nivel);
      const v = $("#aboutVer"); const ver = STATE.app && STATE.app.version; if (v && ver) v.textContent = "v" + ver;
    },
    setLanguage,
  };
})();
