/* NOVA AI 1.4 · recorrido guiado: dónde está cada cosa.
   Sale solo una vez, al terminar la configuración inicial (o al estrenar la 1.4 si ya la tenías configurada).
   Se repite desde Ajustes › General › «Recorrido guiado». */
(() => {
  "use strict";
  const $ = (q) => document.querySelector(q);
  const T = (s, v) => (window.T ? window.T(s, v) : s.replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m)));
  const nm = () => (typeof S !== "undefined" && S.nombre_asistente) || "Nova";
  const key = () => (typeof STATE !== "undefined" && STATE && STATE.ptt_text) || "INSERT";

  // [selector (vacío = centrado), título, texto]. Los pasos cuyo elemento no se ve se saltan solos.
  const STEPS = () => [
    ["", "Bienvenido a bordo", "Te enseño en un minuto dónde está cada cosa. Puedes salir cuando quieras y repetirlo desde Ajustes."],
    ['#nav [data-sec="cabina"]', "Cabina", "Aquí hablas con {n}: ves lo que entiende, lo que responde, los temporizadores y la situación del juego."],
    ["#btnTalk", "Hablarle", "Mantén este botón, o tu tecla {k}, mientras hablas. También puedes escribirle abajo, en el cuadro de texto."],
    ["#powerLine", "Detenerla al momento", "Apágalo para parar todas las búsquedas y que deje de atender órdenes. Vuelve a encenderlo o di «{n}, actívate»."],
    ["#btnSleep", "Modo reposo", "💤 apaga el micrófono hasta que pulses tu tecla. Puede entrar sola tras unos minutos sin hablarle (Nova › Micrófono)."],
    ["#sideQuick", "Accesos rápidos", "Escuchar «{n}…» sin tecla, el overlay en el juego y los comentarios de lo que pasa, a un clic."],
    [".side-foot", "Micrófono y MUTE", "El medidor se mueve cuando te oye. MUTE ON (verde) la deja sorda: ni tecla ni nombre."],
    ['#nav [data-sec="juego"]', "Nave y comandos", "Tus teclas de Star Citizen, los comandos de voz (crea los tuyos), la lectura del Game.log y los perfiles de nave."],
    ['#nav [data-sec="nova"]', "Nova", "Su nombre e idioma, la voz, el micrófono, cómo hablarle, la inteligencia (pega aquí tus claves gratis) y el ahorro de cuota."],
    ['#nav [data-sec="overlay"]', "Overlay y hologramas", "El logo que brilla sobre el juego mientras te habla y las fichas holográficas de jugadores y planetas."],
    ['#nav [data-sec="datos"]', "Datos y memoria", "Diccionario de consultas, lo que sabe de ti, bitácoras, Discord y el idioma del juego."],
    ['#nav [data-sec="ajustes"]', "Ajustes", "Idioma de NOVA AI, actualizaciones, la bandeja de Windows, tus archivos y empezar de cero."],
    ["#btnManual", "El manual", "Todo explicado paso a paso, con capturas. También puedes decirle «{n}, abre el manual»."],
    ["#btnSurvey", "Cuestionario", "Anónimo y de un minuto: puntúa NOVA AI y cuéntanos qué mejorar."],
    ["#btnTray", "A la bandeja", "Cierra la ventana y {n} sigue funcionando junto al reloj de Windows, con el overlay activo."],
    ["", "¡Listo, piloto!", "Ya sabes dónde está todo. Prueba a decir «{n}, ¿quién eres?» o «{n}, ¿qué puedes hacer?»."],
  ];

  let steps = [], i = 0, box = null, hole = null;
  const visible = (el) => el && el.offsetParent !== null && el.getClientRects().length;

  function build() {
    hole = document.createElement("div");
    hole.className = "tour-hole";
    box = document.createElement("div");
    box.className = "tour-box panel";
    box.setAttribute("role", "dialog");
    box.innerHTML = '<div class="tour-step"></div><h3></h3><p></p><div class="tour-foot">' +
      '<button class="btn" data-tour="skip"></button><span></span>' +
      '<button class="btn" data-tour="prev"></button><button class="btn pri" data-tour="next"></button></div>';
    document.body.append(hole, box);
    box.addEventListener("click", (e) => {
      const a = e.target.dataset && e.target.dataset.tour;
      if (a === "next") go(i + 1);
      else if (a === "prev") go(i - 1, -1);
      else if (a === "skip") end();
    });
  }

  function place(el) {
    const pad = 6, W = innerWidth, H = innerHeight;
    if (!el) {  // centrado, sin hueco
      hole.style.cssText = `left:${W / 2}px;top:${H / 2}px;width:0;height:0`;
      box.style.left = `${Math.max(12, (W - box.offsetWidth) / 2)}px`;
      box.style.top = `${Math.max(12, (H - box.offsetHeight) / 2)}px`;
      return;
    }
    el.scrollIntoView({ block: "nearest", inline: "nearest" });
    const r = el.getBoundingClientRect();
    hole.style.cssText = `left:${r.left - pad}px;top:${r.top - pad}px;width:${r.width + pad * 2}px;height:${r.height + pad * 2}px`;
    const bw = box.offsetWidth, bh = box.offsetHeight;
    let x = r.right + 18, y = r.top;  // a la derecha; si no cabe, debajo o encima
    if (x + bw > W - 12) { x = Math.min(Math.max(12, r.left), W - bw - 12); y = r.bottom + 16; }
    if (y + bh > H - 12) y = Math.max(12, r.top - bh - 16);
    box.style.left = `${x}px`;
    box.style.top = `${Math.max(12, Math.min(y, H - bh - 12))}px`;
  }

  function go(n, dir = 1) {
    while (n > 0 && n < steps.length - 1 && steps[n][0] && !visible($(steps[n][0]))) n += dir;  // sin ese botón
    if (n < 0) n = 0;
    if (n >= steps.length) return end();
    i = n;
    const [sel, title, text] = steps[i];
    const v = { n: nm(), k: key() };
    box.querySelector(".tour-step").textContent = T("Paso {a} de {b}", { a: i + 1, b: steps.length });
    box.querySelector("h3").textContent = T(title, v);
    box.querySelector("p").textContent = T(text, v);
    box.querySelector('[data-tour="skip"]').textContent = T("SALIR");
    box.querySelector('[data-tour="skip"]').hidden = i === steps.length - 1;
    box.querySelector('[data-tour="prev"]').textContent = T("ATRÁS");
    box.querySelector('[data-tour="prev"]').hidden = i === 0;
    box.querySelector('[data-tour="next"]').textContent = T(i === 0 ? "EMPEZAR" : i === steps.length - 1 ? "TERMINAR" : "SIGUIENTE");
    hole.classList.toggle("center", !sel);
    requestAnimationFrame(() => place(sel ? $(sel) : null));
    box.querySelector('[data-tour="next"]').focus({ preventScroll: true });
  }

  function start() {
    if (document.body.classList.contains("touring")) return;
    const cab = $('#nav [data-sec="cabina"]');
    if (cab) cab.click();  // los primeros pasos están en la Cabina
    if (!box) build();
    steps = STEPS();
    document.body.classList.add("touring");
    hole.hidden = box.hidden = false;
    go(0);
  }

  async function end() {
    document.body.classList.remove("touring");
    if (box) { box.hidden = true; hole.hidden = true; }
    try {
      if (typeof api === "function") await api("set", { key: "tutorial_visto", value: true });
      if (typeof S !== "undefined") S.tutorial_visto = true;
    } catch { /* se ofrecerá otra vez */ }
  }

  function maybeStart(tries = 0) {
    if (typeof S === "undefined" || !S.asistente_completado || S.tutorial_visto) return;
    const busy = [...document.querySelectorAll(".modal")].some((m) => !m.hidden) || !$("#setup").hidden;
    if (busy) { if (tries < 40) setTimeout(() => maybeStart(tries + 1), 4000); return; }
    start();
  }

  document.addEventListener("keydown", (e) => {
    if (!document.body.classList.contains("touring")) return;
    if (e.key === "Escape") end();
    else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); go(i + 1); }
    else if (e.key === "ArrowLeft") go(i - 1, -1);
  });
  addEventListener("resize", () => { if (document.body.classList.contains("touring")) place(steps[i][0] ? $(steps[i][0]) : null); });
  document.addEventListener("click", (e) => { if (e.target && e.target.id === "btnTour") start(); });

  // Al terminar la configuración inicial (el asistente se cierra) empieza el recorrido.
  const setup = $("#setup");
  if (setup) new MutationObserver(() => { if (setup.hidden) setTimeout(maybeStart, 1500); })
    .observe(setup, { attributes: true, attributeFilter: ["hidden"] });

  window.Tour = { start, end, maybeStart };
})();
