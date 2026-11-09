/* NOVA AI · «Acerca de» al estilo de los keygens de los 90/2000:
   túnel infinito de 8 bits, una flecha volando dentro, scroller en seno y música en bucle. */
(() => {
  "use strict";
  const VERSION = "1.1";

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

<div class="kg-s">[ DESARROLLO ]</div>
<p><b>Aaron B. Roldan</b><br>Gametag de Star Citizen: <b class="kg-y">0zzyt0</b><br>Desarrollado con el motor de IA <b>Claude Opus 5.5</b> (Anthropic)</p>

<div class="kg-s">[ AGRADECIMIENTOS ]</div>
<p>A la <b class="kg-y">Org. Defcorp</b>.<br>Gracias a: <b>Faibo</b> · <b>Galleg0</b> · <b>Sr.Scott</b> · <b>AlpacaInTrouble</b> · <b>Lother</b>… ¡y muchos más!</p>

<div class="kg-s">[ LICENCIA ]</div>
<p><b>Libre uso y modificación.</b><br>Si usas este proyecto o lo modificas, por favor menciona de dónde has sacado las ideas y cuál es tu base. Texto completo en <b>LICENCIA.txt</b>, en la carpeta del programa.</p>

<div class="kg-s">[ DERECHOS DE TERCEROS ]</div>
<p>Star Citizen®, Squadron 42®, Roberts Space Industries® y Cloud Imperium® son marcas registradas de Cloud Imperium Rights LLC. Todas las referencias a Star Citizen que aparecen en NOVA AI (logotipos, nombres de naves, personajes, objetos, lugares y demás contenidos del juego) pertenecen a sus legítimos titulares y están sujetas a sus propios derechos de uso.</p>
<p>NOVA AI es un proyecto de fans, independiente y sin ánimo de lucro. No está afiliado, patrocinado ni respaldado por Cloud Imperium Games.</p>

<div class="kg-s">[ FUENTES DE DATOS ]</div>
<p>Las páginas de consulta <b>scmdb.net</b> (https://scmdb.net) y <b>UEX Corp</b> (https://uexcorp.space) son propiedad de sus respectivos autores, tienen sus propias condiciones de uso y sus contenidos están protegidos.</p>
<p>NOVA AI se limita a <b>consultarlas en línea y a leer la información que publican</b>, igual que lo haría cualquier persona desde su navegador:</p>
<p class="kg-l">» <b>No modifica, altera ni manipula</b> sus datos.<br>» <b>No los redistribuye</b> ni los publica en ningún otro lugar: lo que se descarga se guarda solo en tu equipo, para tu uso personal.<br>» <b>No se atribuye su autoría</b>: todo el mérito de esa información es de quienes la crean y la mantienen.</p>
<p>Lo mismo se aplica a Star Citizen Wiki (starcitizen.tools) y a la traducción al español de la comunidad.</p>

<div class="kg-c kg-y" style="margin-top:14px">o7 · Nos vemos en el 'verso</div>`;

  const SCROLL = "*** NOVA AI V1.1 *** ASISTENTE DE VUELO PARA STAR CITIZEN *** CODIGO: AARON B. ROLDAN - 0ZZYT0 *** " +
    "MOTOR DE IA: CLAUDE OPUS 5.5 *** SALUDOS A LA ORG. DEFCORP *** GRACIAS A FAIBO, GALLEG0, SR.SCOTT, ALPACAINTROUBLE, " +
    "LOTHER Y MUCHOS MAS *** LIBRE USO Y MODIFICACION: CITA TU BASE *** PULSA ESC PARA SALIR *** O7 ***          ";

  let root, fx, fxc, img, logoC, logoX, sc, scx, raf = 0, t0 = 0, open = false, lastFocus = null;
  function build() {
    root = document.createElement("div");
    root.id = "about";
    root.className = "kg-back";
    root.hidden = true;
    root.innerHTML = `
      <div class="kg-win" role="dialog" aria-modal="true" aria-label="Acerca de NOVA AI">
        <canvas class="kg-fx" width="190" height="150"></canvas>
        <div class="kg-bar"><span>░▒▓ NOVA AI · ACERCA DE ▓▒░</span><button class="kg-x" title="Cerrar (Esc)">×</button></div>
        <canvas class="kg-logo" width="240" height="40"></canvas>
        <div class="kg-stage"></div>
        <div class="kg-nfo" tabindex="0">${NFO}</div>
        <canvas class="kg-scroll" width="380" height="22"></canvas>
        <div class="kg-btns"><button class="kg-btn" data-kg="music">♪ MÚSICA: SÍ</button><button class="kg-btn" data-kg="close">CERRAR · ESC</button></div>
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

  // ------------------------------------------------------------ música (bucle sin cortes con Web Audio)
  let actx = null, buf = null, src = null, gain = null, musicOn = true, loading = null;
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
      src = actx.createBufferSource(); src.buffer = buf; src.loop = true; src.connect(gain); src.start();
      gain.gain.linearRampToValueAtTime(0.6, actx.currentTime + 0.8);
    } catch (e) { console.warn("Música del Acerca de:", e); }
  }
  function stopMusic(fast) {
    if (!src || !actx) return;
    const s = src, g = gain; src = null; gain = null;
    const end = actx.currentTime + (fast ? 0.05 : 0.45);
    try { g.gain.cancelScheduledValues(actx.currentTime); g.gain.setValueAtTime(g.gain.value, actx.currentTime); g.gain.linearRampToValueAtTime(0, end); s.stop(end + 0.02); } catch { /* ya parada */ }
  }
  function toggleMusic() {
    musicOn = !musicOn;
    root.querySelector('[data-kg="music"]').textContent = musicOn ? "♪ MÚSICA: SÍ" : "♪ MÚSICA: NO";
    if (musicOn) startMusic(); else stopMusic();
  }

  // ------------------------------------------------------------ efectos
  function tunnel(t) {
    const W = fx.width, H = fx.height, d = img.data;
    // el fondo del túnel se mueve por la franja libre entre el título y los créditos
    const cx = W / 2 + Math.sin(t * 0.63) * W * 0.18, cy = H * 0.32 + Math.cos(t * 0.81) * H * 0.04;
    const speed = t * 26, spin = t * 9, shift = Math.floor(t * 6);
    let p = 0;
    for (let y = 0; y < H; y++) {
      const dy = y - cy;
      for (let x = 0; x < W; x++) {
        const dx = x - cx;
        const r = Math.sqrt(dx * dx + dy * dy) + 0.001;
        const v = 2600 / r + speed;                       // profundidad: infinita
        const u = (Math.atan2(dy, dx) / Math.PI) * 32 + spin; // vuelta del túnel
        const band = Math.floor(v / 9), seg = Math.floor(u / 4);
        const c = PAL[(band + shift) & 31];
        let k = Math.min(1, r / (H * 0.45)) * 0.85;                // al fondo, oscuro
        k = Math.round(k * 4) / 4;                          // 5 niveles de brillo (estilo 8 bits)
        if ((band + seg) & 1) k *= 0.55;                    // tablero
        d[p] = c[0] * k; d[p + 1] = c[1] * k; d[p + 2] = c[2] * k; d[p + 3] = 255; p += 4;
      }
    }
    fxc.putImageData(img, 0, 0);
    // estrellas que salen del fondo
    for (let i = 0; i < 26; i++) {
      const a = i * 2.39996, z = ((t * 0.55 + i * 0.137) % 1);
      const rr = z * z * W * 0.9;
      const sx = cx + Math.cos(a) * rr, sy = cy + Math.sin(a) * rr;
      fxc.fillStyle = z > 0.7 ? "#fff" : "#9cf";
      fxc.fillRect(Math.round(sx), Math.round(sy), z > 0.6 ? 2 : 1, z > 0.6 ? 2 : 1);
    }
    // la flecha, volando dentro del túnel
    const ax = Math.round(cx - 6 + Math.sin(t * 1.3) * 14);
    const ay = Math.round(cy - 3 + Math.sin(t * 2.1) * 3);
    const glow = PAL[(shift * 2) & 31];
    for (let row = 0; row < ARROW.length; row++) for (let col = 0; col < 13; col++) {
      const ch = ARROW[row][col];
      if (ch === ".") continue;
      fxc.fillStyle = ch === "#" ? "#e8f8ff" : `rgb(${glow[0]},${glow[1]},${glow[2]})`;
      fxc.fillRect(ax + col, ay + row, 1, 1);
    }
    // estela del motor (parpadea)
    const flick = (Math.floor(t * 20) & 1) ? "#ffd84a" : "#ff7a2a";
    fxc.fillStyle = flick; fxc.fillRect(ax + 5, ay + 16, 3, 2 + (Math.floor(t * 30) % 3));
    fxc.fillStyle = "#ff3b4e"; fxc.fillRect(ax + 6, ay + 19, 1, 1 + (Math.floor(t * 17) % 3));
  }
  function logo(t) {
    const W = logoC.width;
    logoX.clearRect(0, 0, W, logoC.height);
    const title = "NOVA AI";
    const s = 4, w = textWidth(title, s);
    const x0 = Math.round((W - w) / 2) + 14;
    // sombra
    drawText(logoX, title, x0 + 2, 5, s, () => "rgba(0,0,0,.65)", (x) => Math.sin(x * 0.05 + t * 3) * 2 + 2);
    drawText(logoX, title, x0, 3, s, (i) => hsl(Math.floor(t * 12) + i * 3), (x) => Math.sin(x * 0.05 + t * 3) * 2);
    if (logoImg) logoX.drawImage(logoImg, x0 - 34, 4);
    const sub = "VERSION OFICIAL " + VERSION;
    drawText(logoX, sub, Math.round((W - textWidth(sub, 1)) / 2) + 14, logoC.height - 8, 1, () => "#ffd84a");
  }
  function scroller(t) {
    const W = sc.width, H = sc.height;
    scx.fillStyle = "#000"; scx.fillRect(0, 0, W, H);
    // líneas «raster» de colores
    for (let y = 0; y < H; y += 2) { const c = PAL[(y + Math.floor(t * 20)) & 31]; scx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},.18)`; scx.fillRect(0, y, W, 1); }
    const s = 2, tw = textWidth(SCROLL, s);
    const x = W - ((t * 60) % (tw + W));
    drawText(scx, SCROLL, Math.round(x), 4, s, (i) => hsl(i * 2 + Math.floor(t * 10)), (px) => Math.sin(px * 0.045 + t * 4) * 3);
  }
  function frame(now) {
    if (!open) return;
    const t = (now - t0) / 1000;
    tunnel(t); logo(t); scroller(t);
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
    t0 = performance.now();
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
  window.NovaAbout = { open: show, close };
  const btn = document.getElementById("btnAbout");
  if (btn) btn.addEventListener("click", show);
})();
