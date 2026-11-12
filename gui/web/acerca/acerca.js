/* NOVA AI · «Acerca de» al estilo de los keygens de los 90/2000:
   túnel infinito de 8 bits, una flecha volando dentro, scroller en seno y música en bucle.
   1.3: todo va al ritmo de la música (analizador de Web Audio; sin música, a 108 ppm):
   el túnel acelera y cambia de dibujo, la flecha hace toneles, el logo salta letra a letra. */
(() => {
  "use strict";
  const VERSION = "1.3.1";

  // ------------------------------------------------------------ fuente de píxeles 5×7
  const F = {
    "A": ["01110","10001","10001","11111","10001","10001","10001"], "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01110","10001","10000","10000","10000","10001","01110"], "D": ["11110","10001","10001","10001","10001","10001","11110"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"], "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01110","10001","10000","10111","10001","10001","01111"], "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["01110","00100","00100","00100","00100","00100","01110"], "J": ["00111","00010","00010","00010","00010","10010","01100"],
    "K": ["10001","10010","10100","11000","10100","10010","10001"], "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"], "N": ["10001","10001","11001","10101","10011","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"], "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "Q": ["01110","10001","10001","10001","10101","10010","01101"], "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"], "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"], "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","10101","01010"], "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","10001","01010","00100","00100","00100","00100"], "Z": ["11111","00001","00010","00100","01000","10000","11111"],
    "0": ["01110","10001","10011","10101","11001","10001","01110"], "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"], "3": ["11111","00010","00100","00010","00001","10001","01110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"], "5": ["11111","10000","11110","00001","00001","10001","01110"],
    "6": ["00110","01000","10000","11110","10001","10001","01110"], "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"], "9": ["01110","10001","10001","01111","00001","00010","01100"],
    " ": ["00000","00000","00000","00000","00000","00000","00000"], ".": ["00000","00000","00000","00000","00000","01100","01100"],
    ",": ["00000","00000","00000","00000","01100","00100","01000"], ":": ["00000","01100","01100","00000","01100","01100","00000"],
    "!": ["00100","00100","00100","00100","00100","00000","00100"], "?": ["01110","10001","00001","00010","00100","00000","00100"],
    "-": ["00000","00000","00000","11111","00000","00000","00000"], "'": ["00100","00100","01000","00000","00000","00000","00000"],
    "*": ["00000","00100","10101","01110","10101","00100","00000"], "/": ["00001","00001","00010","00100","01000","10000","10000"],
    "(": ["00010","00100","01000","01000","01000","00100","00010"], ")": ["01000","00100","00010","00010","00010","00100","01000"],
    "+": ["00000","00100","00100","11111","00100","00100","00000"], "&": ["01100","10010","10100","01000","10101","10010","01101"],
    "<": ["00010","00100","01000","10000","01000","00100","00010"], ">": ["01000","00100","00010","00001","00010","00100","01000"],
    "=": ["00000","00000","11111","00000","11111","00000","00000"], "#": ["01010","01010","11111","01010","11111","01010","01010"],
  };
  const clean = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
  function drawText(ctx, text, x, y, scale, colorFn, waveFn) {
    const t = clean(text);
    for (let i = 0; i < t.length; i++) {
      const g = F[t[i]] || F["?"];
      const cx = x + i * 6 * scale;
      if (cx < -6 * scale || cx > ctx.canvas.width) continue;
      ctx.fillStyle = colorFn ? colorFn(i, cx) : "#fff";
      for (let col = 0; col < 5; col++) {
        const dy = waveFn ? waveFn(cx + col * scale) : 0;
        for (let row = 0; row < 7; row++) if (g[row][col] === "1") ctx.fillRect(cx + col * scale, Math.round(y + dy) + row * scale, scale, scale);
      }
    }
  }
  const textWidth = (text, scale) => clean(text).length * 6 * scale;

  // ------------------------------------------------------------ paleta «8 bits»
  const q = (v) => Math.round(Math.max(0, Math.min(255, v)) / 51) * 51; // 6 niveles por canal (216 colores)
  const PAL = [];
  for (let i = 0; i < 32; i++) {
    const a = (i / 32) * Math.PI * 2;
    PAL.push([q(128 + 127 * Math.sin(a)), q(128 + 127 * Math.sin(a + 2.09)), q(128 + 127 * Math.sin(a + 4.19))]);
  }
  const hsl = (h) => { const [r, g, b] = PAL[((h % 32) + 32) % 32]; return `rgb(${r},${g},${b})`; };

  // ------------------------------------------------------------ flecha (sprite 13×17)
  const ARROW = [
    "......#......", ".....###.....", "....#####....", "...##ooo##...", "..##ooooo##..", ".##ooo#ooo##.",
    "##ooo###ooo##", "#####ooo#####", ".....###.....", ".....#o#.....", ".....#o#.....", "....##o##....",
    "...##ooo##...", "..##.#o#.##..", "..#..#o#..#..", ".....#.#.....", ".............",
  ];

  // ------------------------------------------------------------ ventana
  const NFO = `
<div class="kg-h">▓▒░ NOVA AI · ASISTENTE DE VUELO PARA STAR CITIZEN ░▒▓</div>
<div class="kg-c">Versión oficial <b>${VERSION}</b></div>
<div class="kg-logos"><img src="/logos/made_by_the_community.png" alt="Made by the Community"><img src="/logos/logo_0zzyt0.png" alt="0zzyt0"></div>

<div class="kg-s">[ DESARROLLO ]</div>
<p><b>Aaron B. Roldan</b><br>Gametag de Star Citizen: <b class="kg-y">0zzyt0</b> (con ceros: así lo encuentras en sus redes)<br>Desarrollado con el motor de IA <b>Claude Opus 5.5</b> (Anthropic)<br>Proyecto abierto: <b>github.com/0zzyt0/NOVA-AI</b> · tu opinión y tus ideas son bienvenidas</p>

<div class="kg-s">[ AGRADECIMIENTOS ]</div>
<p>A la <b class="kg-y">Org. Defcorp</b>.<br>Gracias a: <b>Faibo</b> · <b>Galleg0</b> · <b>Sr.Scott</b> · <b>AlpacaInTrouble</b> · <b>Lother</b>… ¡y muchos más!</p>

<div class="kg-s">[ LICENCIA ]</div>
<p><b>Licencia MIT: software libre.</b><br>Puedes usarlo, modificarlo y compartirlo; solo conserva el aviso de copyright y la licencia en tus versiones. Texto completo en <b>LICENSE</b> y <b>LICENCIA.txt</b>, en la carpeta del programa.</p>

<div class="kg-s">[ DERECHOS DE TERCEROS ]</div>
<p>Star Citizen®, Squadron 42®, Roberts Space Industries® y Cloud Imperium® son marcas registradas de Cloud Imperium Rights LLC. Todas las referencias a Star Citizen que aparecen en NOVA AI (logotipos, nombres de naves, personajes, objetos, lugares y demás contenidos del juego) pertenecen a sus legítimos titulares y están sujetas a sus propios derechos de uso.</p>
<p>NOVA AI es un proyecto de fans, independiente y sin ánimo de lucro. No está afiliado, patrocinado ni respaldado por Cloud Imperium Games.</p>

<div class="kg-s">[ PÁGINAS DE CONSULTA: GRACIAS ]</div>
<p><b>NOVA AI no sería posible sin estos proyectos de la comunidad.</b> Todo el mérito de la información es de quienes los crean y los mantienen, a menudo en su tiempo libre:</p>
<p class="kg-l">» <b>Star Citizen Wiki</b> · starcitizen.tools — la enciclopedia de la comunidad: lore, naves, armas y lugares. Textos bajo licencia CC BY-SA de sus autores.<br>
» <b>UEX Corp</b> · uexcorp.space — precios de mercancías, rutas de comercio, naves y refinerías, mantenidos día a día por sus usuarios.<br>
» <b>SCMDB</b> · scmdb.net — misiones, recompensas, planos de fabricación y minería extraídos de cada parche (CC BY-NC-ND 4.0).<br>
» <b>VerseGuide</b> · verseguide.com — fichas de planetas, lunas y lugares planetarios.<br>
» <b>StarMap</b> · starmap.space — planetas, estaciones y miles de lugares con coordenadas, servicios y minerales, con su API pública y gratuita.<br>
» <b>SC Ships Performances Viewer</b> · spviewer.eu — rendimiento de naves: combustible, autonomía, condensadores y componentes.<br>
» <b>Universal Item Finder</b> de Meepowski · finder.cstone.space (CStone) — dónde comprar cada objeto del verso.<br>
» <b>SC Haulers</b> · schaulers.com — calculadoras de rutas, carga y misiones de transporte para la industria.<br>
» <b>Roberts Space Industries</b> · robertsspaceindustries.com — fichas públicas de ciudadanos y organizaciones, y estado de los servidores.<br>
» <b>Traducción al español</b> de la comunidad (0zzyt0 y colaboradores) y los textos del juego (global.ini).<br>
» <b>Google Translate</b> (traducciones) y <b>DuckDuckGo</b> (búsquedas en internet).</p>
<p>Cada página es propiedad de sus autores, tiene sus propias condiciones de uso y sus contenidos están protegidos. NOVA AI se limita a <b>consultarlas en línea</b> como lo haría cualquier persona desde su navegador (o con las API públicas que ofrecen):</p>
<p class="kg-l">» <b>No modifica, altera ni manipula</b> sus datos.<br>» <b>No los redistribuye</b>: lo que se descarga se guarda solo en tu equipo, para tu uso personal.<br>» <b>No se atribuye su autoría</b>.<br>» Algunas solo se abren en tu navegador para que las visites tú, con sus anuncios y donaciones: <b>apóyalas</b> si te resultan útiles.</p>

<div class="kg-s">[ DISCLAIMER ]</div>
<p>NOVA AI es un proyecto de fans, gratuito, independiente y sin ánimo de lucro. <b>No es un producto oficial</b> de Cloud Imperium Games ni de ninguna de las páginas citadas, que no lo patrocinan ni lo respaldan. Se ofrece <b>tal cual</b>, sin garantías: los datos del juego cambian con cada parche y las respuestas de la IA pueden equivocarse. Úsalo respetando las condiciones de Star Citizen; tú eres responsable de lo que hagas en el juego. El logotipo <b>Made by the Community</b> se usa según el programa de fans de Cloud Imperium Games.</p>

<div class="kg-c kg-y" style="margin-top:14px">o7 · Nos vemos en el 'verso</div>`;

  const LANG = (window.NOVA_LANG || "es").slice(0, 2);
  const T = (s) => (window.T ? window.T(s) : s);
  const SCROLLS = {
    es: "*** NOVA AI V" + VERSION + " *** ASISTENTE DE VUELO PARA STAR CITIZEN *** CODIGO: AARON B. ROLDAN - 0ZZYT0 *** " +
      "MOTOR DE IA: CLAUDE OPUS 5.5 *** SALUDOS A LA ORG. DEFCORP *** GRACIAS A FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
      "LOTHER Y MUCHOS MAS *** GRACIAS A STARCITIZEN.TOOLS, UEX, SCMDB, VERSEGUIDE, STARMAP, SPVIEWER, CSTONE Y SC HAULERS: " +
      "SIN VOSOTROS NOVA NO SERIA POSIBLE *** LICENCIA MIT: SOFTWARE LIBRE *** SUBE EL VOLUMEN *** PULSA ESC PARA SALIR *** O7 ***          ",
    en: "*** NOVA AI V" + VERSION + " *** FLIGHT ASSISTANT FOR STAR CITIZEN *** CODE: AARON B. ROLDAN - 0ZZYT0 *** " +
      "AI ENGINE: CLAUDE OPUS 5.5 *** GREETINGS TO THE DEFCORP ORG *** THANKS TO FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
      "LOTHER AND MANY MORE *** THANKS TO STARCITIZEN.TOOLS, UEX, SCMDB, VERSEGUIDE, STARMAP, SPVIEWER, CSTONE AND SC HAULERS: " +
      "NOVA WOULD NOT EXIST WITHOUT YOU *** MIT LICENSE: FREE SOFTWARE *** TURN IT UP *** PRESS ESC TO EXIT *** O7 ***          ",
    ca: "*** NOVA AI V" + VERSION + " *** ASSISTENT DE VOL PER A STAR CITIZEN *** CODI: AARON B. ROLDAN - 0ZZYT0 *** " +
      "MOTOR D'IA: CLAUDE OPUS 5.5 *** SALUTACIONS A L'ORG. DEFCORP *** GRACIES A FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
      "LOTHER I MOLTS MES *** GRACIES A STARCITIZEN.TOOLS, UEX, SCMDB, VERSEGUIDE, STARMAP, SPVIEWER, CSTONE I SC HAULERS: " +
      "SENSE VOSALTRES NOVA NO SERIA POSSIBLE *** LLICENCIA MIT: PROGRAMARI LLIURE *** APUJA EL VOLUM *** PREM ESC PER SORTIR *** O7 ***          ",
    fr: "*** NOVA AI V" + VERSION + " *** ASSISTANT DE VOL POUR STAR CITIZEN *** CODE : AARON B. ROLDAN - 0ZZYT0 *** " +
      "MOTEUR IA : CLAUDE OPUS 5.5 *** SALUT A L'ORG. DEFCORP *** MERCI A FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
      "LOTHER ET BIEN D'AUTRES *** MERCI A STARCITIZEN.TOOLS, UEX, SCMDB, VERSEGUIDE, STARMAP, SPVIEWER, CSTONE ET SC HAULERS : " +
      "SANS VOUS NOVA N'EXISTERAIT PAS *** LICENCE MIT : LOGICIEL LIBRE *** MONTEZ LE SON *** ECHAP POUR QUITTER *** O7 ***          ",
    de: "*** NOVA AI V" + VERSION + " *** FLUGASSISTENTIN FUER STAR CITIZEN *** CODE: AARON B. ROLDAN - 0ZZYT0 *** " +
      "KI-MOTOR: CLAUDE OPUS 5.5 *** GRUESSE AN DIE ORG. DEFCORP *** DANKE AN FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
      "LOTHER UND VIELE MEHR *** DANKE AN STARCITIZEN.TOOLS, UEX, SCMDB, VERSEGUIDE, STARMAP, SPVIEWER, CSTONE UND SC HAULERS: " +
      "OHNE EUCH GAEBE ES NOVA NICHT *** MIT-LIZENZ: FREIE SOFTWARE *** LAUTER DREHEN *** ESC ZUM BEENDEN *** O7 ***          ",
  };
  const SCROLL = SCROLLS[LANG] || SCROLLS.es;
  const SUB = ({ es: "VERSION OFICIAL ", en: "OFFICIAL VERSION ", ca: "VERSIO OFICIAL ", fr: "VERSION OFFICIELLE ", de: "OFFIZIELLE VERSION " }[LANG] || "VERSION OFICIAL ") + VERSION;
  const calm = () => document.body.classList.contains("fx-ninguno") ||
    (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  let root, fx, fxc, img, logoC, logoX, sc, scx, raf = 0, t0 = 0, open = false, lastFocus = null;
  function build() {
    root = document.createElement("div");
    root.id = "about";
    root.className = "kg-back";
    root.hidden = true;
    root.innerHTML = `
      <div class="kg-win" role="dialog" aria-modal="true" aria-label="${T("Acerca de NOVA AI")}">
        <canvas class="kg-fx" width="200" height="160"></canvas>
        <div class="kg-bar"><span>░▒▓ NOVA AI · ${T("ACERCA DE")} ▓▒░</span><button class="kg-x" title="${T("Cerrar (Esc)")}">×</button></div>
        <canvas class="kg-logo" width="240" height="44"></canvas>
        <div class="kg-stage"></div>
        <div class="kg-nfo" tabindex="0">${NFO}</div>
        <canvas class="kg-scroll" width="380" height="26"></canvas>
        <div class="kg-btns"><button class="kg-btn" data-kg="music">${T("♪ MÚSICA: SÍ")}</button><button class="kg-btn" data-kg="close">${T("CERRAR · ESC")}</button></div>
      </div>`;
    document.body.appendChild(root);
    fx = root.querySelector(".kg-fx"); fxc = fx.getContext("2d");
    img = fxc.createImageData(fx.width, fx.height);
    logoC = root.querySelector(".kg-logo"); logoX = logoC.getContext("2d");
    sc = root.querySelector(".kg-scroll"); scx = sc.getContext("2d");
    root.querySelector(".kg-x").addEventListener("click", close);
    root.querySelector('[data-kg="close"]').addEventListener("click", close);
    root.querySelector('[data-kg="music"]').addEventListener("click", toggleMusic);
    root.addEventListener("mousedown", (e) => { if (e.target === root) close(); });
    // logo de Nova pixelado, para la esquina del título
    const im = new Image();
    im.onload = () => { logoImg = document.createElement("canvas"); logoImg.width = logoImg.height = 26;
      const c = logoImg.getContext("2d"); c.imageSmoothingEnabled = true; c.drawImage(im, 0, 0, 26, 26); };
    im.src = "/logo.png";
  }
  let logoImg = null;

  // ------------------------------------------------------------ música (bucle sin cortes con Web Audio) + analizador
  let actx = null, buf = null, src = null, gain = null, an = null, bins = null, musicOn = true, loading = null;
  async function loadMusic() {
    if (buf) return buf;
    if (!loading) loading = (async () => {
      const r = await fetch("/acerca/nova_theme.ogg");
      const data = await r.arrayBuffer();
      buf = await actx.decodeAudioData(data);
      return buf;
    })();
    return loading;
  }
  async function startMusic() {
    if (!musicOn) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === "suspended") await actx.resume();
      await loadMusic();
      if (!open || !musicOn || src) return;
      gain = actx.createGain(); gain.gain.value = 0; gain.connect(actx.destination);
      an = actx.createAnalyser(); an.fftSize = 1024; an.smoothingTimeConstant = 0.3; an.minDecibels = -85; an.maxDecibels = -12; bins = new Uint8Array(an.frequencyBinCount);
      src = actx.createBufferSource(); src.buffer = buf; src.loop = true; src.connect(gain); src.connect(an); src.start();
      gain.gain.linearRampToValueAtTime(0.6, actx.currentTime + 0.8);
    } catch (e) { console.warn("Música del Acerca de:", e); }
  }
  function stopMusic(fast) {
    if (!src || !actx) return;
    const s = src, g = gain; src = null; gain = null; an = null;
    const end = actx.currentTime + (fast ? 0.05 : 0.45);
    try { g.gain.cancelScheduledValues(actx.currentTime); g.gain.setValueAtTime(g.gain.value, actx.currentTime); g.gain.linearRampToValueAtTime(0, end); s.stop(end + 0.02); } catch { /* ya parada */ }
  }
  function toggleMusic() {
    musicOn = !musicOn;
    root.querySelector('[data-kg="music"]').textContent = T(musicOn ? "♪ MÚSICA: SÍ" : "♪ MÚSICA: NO");
    if (musicOn) startMusic(); else stopMusic();
  }

  // ------------------------------------------------------------ el ritmo
  // kick: golpe de bombo (salta a 1 y cae), energy: volumen general suavizado, beats: golpes contados
  const B = { kick: 0, energy: 0.35, beats: 0, last: -1, avg: 0, roll: -9, mode: 0, hue: 0, flash: 0 };
  const BEAT = 60 / 108;
  const lowPrev = new Uint8Array(16);
  function rhythm(t, dt) {
    let hit = false;
    if (an) {
      // «spectral flux» de los graves: cuánto suben de golpe respecto al fotograma anterior
      an.getByteFrequencyData(bins);
      let flux = 0, all = 0;
      for (let i = 1; i < 9; i++) { flux += Math.max(0, bins[i] - lowPrev[i]); lowPrev[i] = bins[i]; }
      for (let i = 1; i < 160; i++) all += bins[i];
      flux /= 8 * 255; all /= 159 * 255;
      B.energy += (all * 1.6 - B.energy) * Math.min(1, dt * 6);
      if (flux > B.avg * 1.6 + 0.02 && t - B.last > 0.4) hit = true;
      else if (t - B.last > BEAT * 2.2) hit = true;          // un pasaje sin bombo: que siga el pulso
      B.avg += (flux - B.avg) * Math.min(1, dt * 2.5);
    } else {
      // sin música: pulso fijo a 108 ppm para que no pare la fiesta
      B.energy += (0.55 - B.energy) * Math.min(1, dt * 2);
      if (Math.floor(t / BEAT) !== Math.floor((t - dt) / BEAT)) hit = true;
    }
    if (hit) {
      B.last = t; B.beats++; B.kick = 1; B.flash = 1; B.hue += 5;
      if (B.beats % 8 === 0) B.roll = t;                     // tonel de la flecha cada 8 golpes
      if (B.beats % 16 === 0) B.mode = (B.mode + 1) % 4;     // el túnel cambia de dibujo cada 16
    }
    B.kick = Math.max(0, B.kick - dt * 3.2);
    B.flash = Math.max(0, B.flash - dt * 6);
  }

  // ------------------------------------------------------------ efectos
  let depth = 0, spinA = 0;
  const stars = Array.from({ length: 70 }, (_, i) => ({ a: i * 2.39996, z: (i * 0.137) % 1, v: 0.6 + (i % 7) * 0.12 }));
  const trail = [];
  function tunnel(t, dt) {
    const W = fx.width, H = fx.height, d = img.data;
    // el centro baila en Lissajous por la franja libre entre el título y los créditos
    const cx = W / 2 + Math.sin(t * 1.1) * W * 0.26 + Math.sin(t * 2.7) * W * 0.05;
    const cy = H * 0.31 + Math.cos(t * 1.7) * H * 0.07;
    depth += dt * (70 + 220 * B.kick + 60 * B.energy);        // acelera con cada golpe
    spinA += dt * (Math.sin(t * 0.45) * 46 + 14 * B.kick * (B.beats & 1 ? 1 : -1) * 6);
    const twist = Math.sin(t * 0.8) * 0.09;                   // espiral que se retuerce
    const shift = Math.floor(t * 14) + B.hue;
    const fl = 1 + B.flash * 0.9;
    const mode = B.mode;
    let p = 0;
    for (let y = 0; y < H; y++) {
      const dy = y - cy;
      for (let x = 0; x < W; x++) {
        const dx = x - cx;
        const r = Math.sqrt(dx * dx + dy * dy) + 0.001;
        const v = 2600 / r + depth;                           // profundidad: infinita
        const u = (Math.atan2(dy, dx) / Math.PI) * 32 + spinA + r * twist * 8;
        let band, seg, on;
        if (mode === 0) { band = Math.floor(v / 9); seg = Math.floor(u / 4); on = (band + seg) & 1; }           // tablero
        else if (mode === 1) { band = Math.floor((v + u * 3) / 10); seg = 0; on = band & 1; }                    // espiral
        else if (mode === 2) { band = Math.floor(v / 6); seg = Math.floor(u / 2); on = ((band >> 1) + seg) & 1; } // tablero fino
        else { band = Math.floor(v / 12 + Math.sin(u * 0.4 + t * 3) * 1.5); seg = 0; on = band & 1; }            // anillos ondulados
        const c = PAL[(band + shift) & 31];
        let k = Math.min(1, r / (H * 0.42)) * 0.9;            // al fondo, oscuro
        k = Math.round(k * 4) / 4;                            // 5 niveles de brillo (estilo 8 bits)
        if (on) k *= 0.5;
        k *= fl;
        d[p] = c[0] * k; d[p + 1] = c[1] * k; d[p + 2] = c[2] * k; d[p + 3] = 255; p += 4;
      }
    }
    fxc.putImageData(img, 0, 0);
    // barras «copper» que cruzan la pantalla
    for (let i = 0; i < 3; i++) {
      const by = Math.round(H * 0.5 + Math.sin(t * (1.3 + i * 0.4) + i * 2.1) * H * 0.42);
      const c = PAL[(shift * 2 + i * 10) & 31];
      for (let j = -3; j <= 3; j++) {
        fxc.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.32 - Math.abs(j) * 0.08) * (0.7 + B.kick * 0.6)})`;
        fxc.fillRect(0, by + j, W, 1);
      }
    }
    // estrellas en «warp»: estelas que salen del fondo, más largas con cada golpe
    const warp = 0.55 + B.energy * 0.6 + B.kick * 1.4;
    for (const st of stars) {
      st.z += dt * st.v * warp * 0.6;
      if (st.z > 1) st.z -= 1;
      const z = st.z, rr = z * z * W * 1.1, rr0 = Math.max(0, z - 0.05 * warp) ** 2 * W * 1.1;
      const ca = Math.cos(st.a + spinA * 0.01), sa = Math.sin(st.a + spinA * 0.01);
      fxc.strokeStyle = z > 0.7 ? "#fff" : z > 0.4 ? "#9cf" : "#58a";
      fxc.lineWidth = z > 0.6 ? 2 : 1;
      fxc.beginPath(); fxc.moveTo(cx + ca * rr0, cy + sa * rr0); fxc.lineTo(cx + ca * rr, cy + sa * rr); fxc.stroke();
    }
    // la flecha: ochos alrededor del centro, toneles cada 8 golpes y estela de colores
    const ax = cx + Math.sin(t * 2.2) * 22 + Math.sin(t * 5.1) * 4;
    const ay = cy + Math.sin(t * 4.4) * 7 - B.kick * 4;
    const rollP = Math.min(1, (t - B.roll) / 0.55);
    const ang = Math.sin(t * 3.1) * 0.5 + (rollP < 1 ? (1 - Math.cos(rollP * Math.PI)) * Math.PI : 0);
    const sz = 1.3 + B.kick * 0.5;
    trail.push([ax, ay, ang, sz]); if (trail.length > 7) trail.shift();
    for (let i = 0; i < trail.length - 1; i += 2) {
      const [tx, ty, ta, ts] = trail[i], c = PAL[(shift * 3 + i * 4) & 31];
      sprite(tx, ty, ta, ts, `rgba(${c[0]},${c[1]},${c[2]},${0.12 + i * 0.05})`, null);
    }
    const glow = PAL[(shift * 2) & 31];
    sprite(ax, ay, ang, sz, "#e8f8ff", `rgb(${glow[0]},${glow[1]},${glow[2]})`);
    // llama del motor (parpadea y crece con el bombo)
    const ex = ax - Math.sin(ang) * 10 * sz, ey = ay + Math.cos(ang) * 10 * sz;
    const fl2 = 2 + Math.floor(B.kick * 5) + (Math.floor(t * 30) % 3);
    fxc.fillStyle = (Math.floor(t * 20) & 1) ? "#ffd84a" : "#ff7a2a";
    for (let i = 0; i < fl2; i++) fxc.fillRect(Math.round(ex - Math.sin(ang) * i - 1), Math.round(ey + Math.cos(ang) * i), 3 - (i > 2), 1);
    fxc.fillStyle = "#ff3b4e"; fxc.fillRect(Math.round(ex - Math.sin(ang) * fl2), Math.round(ey + Math.cos(ang) * fl2), 1, 2);
  }
  // pinta la flecha girada y escalada (píxel a píxel, como un sprite de la época)
  function sprite(x, y, ang, s, edge, core) {
    const ca = Math.cos(ang), sa = Math.sin(ang), px = Math.max(1, Math.ceil(s * (Math.abs(ca) + Math.abs(sa)) - 0.15));
    for (let row = 0; row < ARROW.length; row++) for (let col = 0; col < 13; col++) {
      const ch = ARROW[row][col];
      if (ch === ".") continue;
      if (!core && ch === "o") continue;
      const lx = (col - 6) * s, ly = (row - 8) * s;
      fxc.fillStyle = ch === "#" || !core ? edge : core;
      fxc.fillRect(Math.round(x + lx * ca - ly * sa), Math.round(y + lx * sa + ly * ca), px, px);
    }
  }
  function logo(t) {
    const W = logoC.width;
    logoX.clearRect(0, 0, W, logoC.height);
    const title = "NOVA AI";
    const s = 4, w = textWidth(title, s);
    const x0 = Math.round((W - w) / 2) + 14 + Math.round(Math.sin(t * 2.3) * 6);
    // cada letra salta por turnos, al ritmo
    const jump = (i) => {
      const k = (B.beats + i) % 7 === 0 ? B.kick : 0;
      return Math.sin(t * 6 + i * 0.9) * 2.2 - k * 5;
    };
    const wave = (x) => { const i = Math.floor((x - x0) / (6 * s)); return jump(i) + 4; };
    const split = 1 + Math.round(B.kick * 3);
    drawText(logoX, title, x0 + 2, 6, s, () => "rgba(0,0,0,.65)", (x) => wave(x) + 2);
    if (!calm()) {
      drawText(logoX, title, x0 - split, 3, s, () => "rgba(255,40,90,.55)", wave);   // aberración cromática
      drawText(logoX, title, x0 + split, 3, s, () => "rgba(40,220,255,.55)", wave);
    }
    drawText(logoX, title, x0, 3, s, (i) => hsl(Math.floor(t * 26) + i * 4 + B.hue), wave);
    if (logoImg) {
      logoX.save(); logoX.translate(x0 - 21, 17); logoX.rotate(t * 3 + B.kick * 2);
      const z = 1 + B.kick * 0.25; logoX.scale(z, z); logoX.drawImage(logoImg, -13, -13); logoX.restore();
    }
    drawText(logoX, SUB, Math.round((W - textWidth(SUB, 1)) / 2) + 14, logoC.height - 8, 1,
      (i) => ((i + B.beats) % 6 === 0 && B.kick > 0.3 ? "#fff" : "#ffd84a"), (x) => Math.sin(x * 0.12 + t * 8) * 1.2);
  }
  function scroller(t, dt) {
    const W = sc.width, H = sc.height;
    scx.fillStyle = "#000"; scx.fillRect(0, 0, W, H);
    // líneas «raster» de colores
    for (let y = 0; y < H; y += 2) { const c = PAL[(y + Math.floor(t * 40) + B.hue) & 31]; scx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.16 + B.kick * 0.25})`; scx.fillRect(0, y, W, 1); }
    const s = 2, tw = textWidth(SCROLL, s);
    scrollX += dt * (115 + B.kick * 160);
    const x = W - (scrollX % (tw + W));
    drawText(scx, SCROLL, Math.round(x), 6, s, (i) => hsl(i * 3 + Math.floor(t * 22) + B.hue),
      (px) => Math.sin(px * 0.05 + t * 7) * 3.5 + Math.sin(px * 0.013 - t * 3) * 1.5 - B.kick * 2);
  }
  let scrollX = 0, prev = 0;
  function shake() {
    const win = root.querySelector(".kg-win");
    if (calm()) { fx.style.transform = logoC.style.transform = ""; win.style.removeProperty("--kg-edge"); return; }
    const k = B.kick * B.kick;
    const sx = (Math.random() - 0.5) * 6 * k, sy = (Math.random() - 0.5) * 6 * k;
    fx.style.transform = `translate(${sx.toFixed(1)}px,${sy.toFixed(1)}px) scale(${(1.03 + B.kick * 0.03).toFixed(3)})`;
    logoC.style.transform = `translate(${(-sx).toFixed(1)}px,${(sy * 0.6).toFixed(1)}px)`;
    const c = PAL[(B.hue * 2) & 31];
    win.style.setProperty("--kg-edge", `rgba(${c[0]},${c[1]},${c[2]},${(0.35 + B.flash * 0.65).toFixed(2)})`);
  }
  function frame(now) {
    if (!open) return;
    const t = (now - t0) / 1000;
    const dt = Math.min(0.05, Math.max(0, t - prev)); prev = t;
    rhythm(t, dt);
    tunnel(t, dt); logo(t); scroller(t, dt); shake();
    raf = requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------ abrir y cerrar
  function onKey(e) {
    if (!open) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); close(); }
  }
  function show() {
    if (!root) build();
    if (open) return;
    open = true; lastFocus = document.activeElement;
    root.hidden = false;
    requestAnimationFrame(() => root.classList.add("on"));
    root.querySelector(".kg-nfo").scrollTop = 0;
    t0 = performance.now(); prev = 0; scrollX = 0;
    raf = requestAnimationFrame(frame);
    window.addEventListener("keydown", onKey, true);
    root.querySelector('[data-kg="close"]').focus();
    startMusic();
  }
  function close() {
    if (!open) return;
    open = false;
    cancelAnimationFrame(raf);
    stopMusic();
    window.removeEventListener("keydown", onKey, true);
    root.classList.remove("on");
    setTimeout(() => { if (!open) root.hidden = true; }, 180);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  window.NovaAbout = { open: show, close, state: () => ({ analyser: !!an, beats: B.beats, mode: B.mode, energy: +B.energy.toFixed(2) }) };
  const btn = document.getElementById("btnAbout");
  if (btn) btn.addEventListener("click", show);
})();
