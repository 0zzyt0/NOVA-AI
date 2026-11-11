// NOVA AI v1.3 — traducción de la ventana.
// El HTML y los scripts están escritos en español; este archivo cambia cada texto
// visible por el del idioma elegido (catálogo que inyecta el servidor en
// window.NOVA_I18N). Vigila los cambios para traducir también lo que se pinta después.
// Lo marcado con data-no-i18n (tu chat con Nova, tus datos…) nunca se toca.
(() => {
  const LANG = window.NOVA_LANG || "es";
  const CAT = window.NOVA_I18N || {};
  document.documentElement.lang = LANG;
  const HOLE = /\{(\w*)\}/g;
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const PATS = [];
  if (LANG !== "es") {
    for (const [k, v] of Object.entries(CAT)) {
      if (!k.includes("{")) continue;
      const names = [];
      const parts = k.split(HOLE);
      let rx = "^";
      parts.forEach((p, i) => { if (i % 2) { names.push(p); rx += "([\\s\\S]+?)"; } else rx += esc(p); });
      PATS.push([new RegExp(rx + "$"), v, names]);
    }
    PATS.sort((a, b) => b[0].source.length - a[0].source.length);
  }
  function fill(s, vars) { return vars ? s.replace(HOLE, (m, n) => (n in vars ? vars[n] : m)) : s; }
  function lookup(s) {
    if (LANG === "es" || !s) return null;
    let hit = CAT[s];
    if (hit !== undefined) return hit;
    const t = s.trim();
    if (!t || t.length > 600) return null;
    hit = CAT[t];
    if (hit !== undefined) return s.slice(0, s.indexOf(t)) + hit + s.slice(s.indexOf(t) + t.length);
    if (!/[A-Za-zÁÉÍÓÚÑáéíóúñ]/.test(t)) return null;
    for (const [rx, v, names] of PATS) {
      const m = rx.exec(t);
      if (!m) continue;
      const vars = {}; names.forEach((n, i) => { vars[n] = m[i + 1]; });
      let i = 0;
      const out = v.replace(HOLE, (mm, n) => (/^\d+$/.test(n) ? (m[+n] ?? "") : n ? (vars[n] ?? mm) : (m[++i] ?? "")));
      return s.slice(0, s.indexOf(t)) + out + s.slice(s.indexOf(t) + t.length);
    }
    return null;
  }
  // T("texto en español", {huecos}) → texto traducido
  window.T = (s, vars) => fill(lookup(s) ?? s, vars);
  window.I18N = { lang: LANG, lookup };
  window.LOCALE = { es: "es-ES", en: "en-GB", ca: "ca-ES", fr: "fr-FR", de: "de-DE" }[LANG] || "es-ES";
  if (LANG === "es") return;

  const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"]);
  const ATTRS = ["title", "placeholder", "aria-label", "data-tip", "alt", "data-off", "data-on"];
  const done = new WeakMap();
  const skipped = (el) => !el || (el.closest && el.closest("[data-no-i18n]"));
  function textNode(n) {
    const p = n.parentElement;
    if (!p || SKIP.has(p.tagName) || skipped(p)) return;
    const v = n.data;
    if (done.get(n) === v) return;
    const hit = lookup(v);
    if (hit != null && hit !== v) { done.set(n, hit); n.data = hit; } else done.set(n, v);
  }
  function attrs(el) {
    if (skipped(el)) return;
    for (const a of ATTRS) {
      const v = el.getAttribute && el.getAttribute(a);
      if (!v) continue;
      const key = "a:" + a;
      const memo = el[key];
      if (memo === v) continue;
      const hit = lookup(v);
      if (hit != null && hit !== v) { el[key] = hit; el.setAttribute(a, hit); } else el[key] = v;
    }
  }
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { textNode(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.nodeType === 1) { if (SKIP.has(root.tagName) || skipped(root)) return; attrs(root); }
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode: (n) => {
        if (n.nodeType !== 1) return NodeFilter.FILTER_ACCEPT;
        if (n.hasAttribute("data-no-i18n")) return NodeFilter.FILTER_REJECT;
        if (SKIP.has(n.tagName)) { attrs(n); return NodeFilter.FILTER_REJECT; }  // placeholder de un textarea…
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n;
    while ((n = tw.nextNode())) { if (n.nodeType === 3) textNode(n); else attrs(n); }
  }
  window.I18N.walk = walk;
  const start = () => {
    walk(document.body);
    if (document.title) document.title = window.T(document.title);
    new MutationObserver((list) => {
      for (const m of list) {
        if (m.type === "characterData") textNode(m.target);
        else if (m.type === "attributes") attrs(m.target);
        else m.addedNodes.forEach(walk);
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    // Los avisos nativos (confirm/alert/prompt) también hablan el idioma elegido
    for (const fn of ["alert", "confirm", "prompt"]) {
      const orig = window[fn].bind(window);
      window[fn] = (msg, ...rest) => orig(typeof msg === "string" ? window.T(msg) : msg, ...rest);
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
