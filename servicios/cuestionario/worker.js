// NOVA AI · servicio del cuestionario anónimo (Cloudflare Worker).
//
// Recibe el cuestionario que envía NOVA AI y lo publica como issue en github.com/0zzyt0/NOVA-AI con la
// etiqueta «cuestionario». El token de GitHub vive aquí, como secreto GITHUB_TOKEN del Worker, y nunca en el
// programa. Instrucciones de despliegue: LEEME.md de esta carpeta.
//
// Privacidad: no se guarda nada. La IP solo se usa en memoria, resumida con SHA-256, para frenar envíos en
// masa (como mucho LIMIT_PER_HOUR por hora) y se olvida en una hora. A GitHub solo llegan las notas, el texto,
// la versión de NOVA AI y el idioma.

const REPO = "0zzyt0/NOVA-AI";
const LABEL = "cuestionario";
const MAX_BODY = 8000;
const MAX_IDEA = 2000;
const LIMIT_PER_HOUR = 3;
const GLOBAL_PER_HOUR = 60;

const QUESTIONS = {
  reconocimiento: "¿Te entiende bien cuando le hablas?",
  comandos: "¿Obedece bien los comandos de la nave?",
  respuestas: "¿Son útiles sus respuestas y búsquedas?",
  voz: "¿Te gusta su voz y su forma de hablar?",
  configuracion: "¿Fue fácil instalarla y configurarla?",
  overlay: "¿Qué te parecen el overlay y los hologramas?",
  ventana: "¿Encuentras fácilmente las opciones en la ventana?",
  recomendarias: "¿Recomendarías NOVA AI a otro jugador?",
};
const LANGS = new Set(["es", "en", "ca", "fr", "de"]);

// Límite «de buena fe» en la memoria de esta instancia del Worker (Cloudflare puede tener varias).
const seen = new Map(); // huella de la IP → [instantes]
let globalSeen = [];

function reply(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function fingerprint(ip) {
  const bytes = new TextEncoder().encode("nova-ai-cuestionario:" + ip);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].slice(0, 12).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function tooMany(key, now) {
  const hour = 3600 * 1000;
  globalSeen = globalSeen.filter((t) => now - t < hour);
  for (const [k, list] of seen) {
    const fresh = list.filter((t) => now - t < hour);
    if (fresh.length) seen.set(k, fresh); else seen.delete(k);
  }
  const mine = seen.get(key) || [];
  if (mine.length >= LIMIT_PER_HOUR || globalSeen.length >= GLOBAL_PER_HOUR) return true;
  mine.push(now);
  seen.set(key, mine);
  globalSeen.push(now);
  return false;
}

export function validate(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return "Formato no válido";
  const version = String(data.version || "");
  if (!/^\d+\.\d+(\.\d+)?$/.test(version)) return "Versión no válida";
  const idioma = String(data.idioma || "es");
  if (!LANGS.has(idioma)) return "Idioma no válido";
  const r = data.respuestas;
  if (!r || typeof r !== "object" || Array.isArray(r)) return "Faltan las respuestas";
  const answers = {};
  let rated = 0;
  for (const key of Object.keys(QUESTIONS)) {
    const v = r[key];
    if (v === null || v === undefined) { answers[key] = null; continue; }
    if (!Number.isInteger(v) || v < 1 || v > 10) return "Las notas van del 1 al 10";
    answers[key] = v;
    rated++;
  }
  if (Object.keys(r).some((k) => !(k in QUESTIONS))) return "Pregunta desconocida";
  if (!rated) return "Sin notas";
  const idea = typeof data.idea === "string" ? data.idea : "";
  if (idea.length > MAX_IDEA) return "Texto demasiado largo";
  return { version, idioma, answers, idea };
}

// El texto libre va citado y «desactivado»: sin menciones (@alguien), sin referencias (#12) y sin HTML.
export function quote(text) {
  const clean = text
    .replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/@/g, "@​")
    .replace(/#(\d)/g, "#​$1")
    .trim();
  if (!clean) return "_(sin comentarios)_";
  return clean.split("\n").map((l) => "> " + l).join("\n");
}

export function issue(v) {
  const scores = Object.values(v.answers).filter((n) => n !== null);
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  const avgTxt = avg.toFixed(1).replace(".", ",");
  const rows = Object.entries(QUESTIONS)
    .map(([k, q]) => `| ${q} | ${v.answers[k] === null ? "N/S" : v.answers[k]} |`)
    .join("\n");
  return {
    title: `Cuestionario anónimo · ${v.version} · media ${avgTxt}`,
    labels: [LABEL],
    body: [
      `**Versión:** ${v.version} · **Idioma:** ${v.idioma} · **Media:** ${avgTxt} / 10`,
      "",
      "| Pregunta | Nota |",
      "|---|---|",
      rows,
      "",
      "**¿Alguna idea? ¿Algo que mejorar?**",
      "",
      quote(v.idea),
      "",
      "<sub>Enviado de forma anónima desde NOVA AI. Sin nombre, gametag ni datos del equipo.</sub>",
    ].join("\n"),
  };
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return reply(405, { error: "Solo POST" });
    if (!(request.headers.get("User-Agent") || "").startsWith("NOVA-AI/")) return reply(403, { error: "Solo NOVA AI" });
    if (!env.GITHUB_TOKEN) return reply(503, { error: "Servicio sin configurar" });
    const raw = await request.text();
    if (raw.length > MAX_BODY) return reply(413, { error: "Demasiado grande" });
    let data;
    try { data = JSON.parse(raw); } catch { return reply(400, { error: "JSON no válido" }); }
    const v = validate(data);
    if (typeof v === "string") return reply(400, { error: v });

    const key = await fingerprint(request.headers.get("CF-Connecting-IP") || "");
    if (tooMany(key, Date.now())) return reply(429, { error: "Demasiados envíos" });

    const gh = await fetch(`https://api.github.com/repos/${REPO}/issues`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nova-ai-cuestionario",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(issue(v)),
    });
    if (!gh.ok) return reply(502, { error: `GitHub respondió ${gh.status}` });
    return reply(201, { ok: true });
  },
};
