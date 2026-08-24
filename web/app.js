/* Shared helpers for Klubb1 Tivoli. Vanilla JS, no build step. */

const API = "api";

async function fetchJSON(path, opts = {}) {
  const r = await fetch(`${API}/${path}`, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  let data = null;
  try { data = await r.json(); } catch (_) { /* no body */ }
  if (!r.ok) throw new Error((data && data.detail) || `Feil ${r.status}`);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const store = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch (_) { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* private mode */ } },
  del(key) { try { localStorage.removeItem(key); } catch (_) { /* ignore */ } },
};

/* A tiny mechanical clack, synthesised — no audio files. Silently no-ops if blocked. */
function clack(kind = "lever") {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    clack.ctx = clack.ctx || new Ctx();
    const ctx = clack.ctx;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const filt = ctx.createBiquadFilter();
    filt.type = "bandpass";
    filt.frequency.value = kind === "ding" ? 1800 : 220;
    osc.type = kind === "ding" ? "triangle" : "square";
    osc.frequency.setValueAtTime(kind === "ding" ? 1760 : 140, t);
    osc.frequency.exponentialRampToValueAtTime(kind === "ding" ? 1200 : 60, t + (kind === "ding" ? 0.4 : 0.12));
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(kind === "ding" ? 0.12 : 0.25, t + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + (kind === "ding" ? 0.5 : 0.15));
    osc.connect(filt).connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.6);
  } catch (_) { /* audio is optional */ }
}

const KATEGORI_NAVN = {
  lyd: "Lyd & musikk", bilde: "Bilde & film", ord: "Ord & historier", spill: "Spill & kode",
  hamar: "Hamar & verden", kropp: "Scene & kropp", overrask: "Overrask meg",
};
const NIVA_NAVN = { nybegynner: "Nybegynner", vant: "Vant", nerd: "Nerd" };

function pad(n, w = 6) { return String(n ?? 0).padStart(w, "0"); }

function renderTicket(t) {
  const steg = (t.steg || []).map((s) => `<li><span class="tid">${esc(s.tid)}</span><span>${esc(s.tekst)}</span></li>`).join("");
  const tools = (t.verktoy || []).map((v) => `<li><b>${esc(v.navn)}</b>${esc(v.hvorfor)}</li>`).join("");
  const hints = (t.hvis_du_star_fast || []).map((h) => `<li>${esc(h)}</li>`).join("");
  const tags = (t.tags || []).map((x) => `#${esc(x)}`).join("  ");
  const kilde = t.kilde === "luna" ? "nytrykt" : t.kilde === "arkiv" ? "fra arkivet" : "fra seed-banken";
  const share = t.id ? `${location.origin}${location.pathname.replace(/[^/]*$/, "")}automat.html?id=${t.id}` : "";
  return `
  <article class="ticket" id="ticket">
    <div class="no">Lapp nr. ${pad(t.id)}</div>
    <div class="meta">${t.minutter} min · ${esc(KATEGORI_NAVN[t.kategori] || t.kategori)} · ${esc(NIVA_NAVN[t.niva] || t.niva)}${t.gruppe ? " · gruppe" : ""}</div>
    <h2>${esc(t.tittel)}</h2>
    <p class="teaser">${esc(t.teaser)}</p>
    <p class="oppdrag">${esc(t.oppdrag)}</p>

    <h3>Slik gjør du det</h3>
    <ol class="steg">${steg}</ol>

    <h3>AI-grepet</h3>
    <div class="grep"><span class="stamp">nytt grep</span>${esc(t.ai_grepet)}</div>

    <h3>Verktøy du kan bruke (velg selv)</h3>
    <ul class="tools">${tools}</ul>

    <details><summary>Hvis du står fast</summary><ul>${hints}</ul></details>

    <h3>Vis fram</h3>
    <p>${esc(t.vis_fram)}</p>
    <h3>Bonus</h3>
    <p>${esc(t.bonus)}</p>

    <details class="helper-details"><summary>Til hjelperen</summary><div class="helper"><p>${esc(t.til_hjelperen)}</p></div></details>

    <div class="tags">${tags}</div>
    <div class="actions no-print">
      <button class="btn" type="button" onclick="window.print()">Skriv ut</button>
      ${share ? `<button class="btn" type="button" data-copy="${esc(share)}">Kopier lenke</button>` : ""}
      <span class="kilde">${kilde}</span>
    </div>
  </article>`;
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  try {
    await navigator.clipboard.writeText(b.dataset.copy);
    const old = b.textContent;
    b.textContent = "Kopiert!";
    setTimeout(() => { b.textContent = old; }, 1400);
  } catch (_) {
    prompt("Kopier lenken:", b.dataset.copy);
  }
});

/* Parse an SSE stream of {delta}/{error} events. Calls onDelta for each text chunk. */
async function readSSE(response, onDelta) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!chunk.startsWith("data:")) continue;
      const raw = chunk.slice(5).trim();
      if (raw === "[DONE]") return;
      try {
        const ev = JSON.parse(raw);
        if (ev.error) throw new Error(ev.error);
        if (ev.delta) onDelta(ev.delta);
      } catch (err) {
        if (err instanceof SyntaxError) continue;
        throw err;
      }
    }
  }
}

window.Tivoli = { API, fetchJSON, esc, store, clack, renderTicket, readSSE, KATEGORI_NAVN, NIVA_NAVN, pad };
