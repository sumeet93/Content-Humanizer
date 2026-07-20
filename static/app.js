"use strict";

const $ = (id) => document.getElementById(id);
const input = $("input"), output = $("output");
let mode = "standard";
let keywords = [];
let result = null;       // last /api/humanize response
let variantIdx = 0;
let view = "clean";

/* ---------- helpers ---------- */
const wordCount = (t) => (t.trim().match(/\S+/g) || []).length;

function scoreColor(v) {
  if (v <= 25) return "#2e7d4f";
  if (v <= 50) return "#7d8f2e";
  if (v <= 75) return "#c07b2a";
  return "#b3372c";
}

function renderGauge(el, s, label) {
  if (!s || s.score === null) {
    el.hidden = false;
    el.innerHTML = `<div class="gauge-top"><span class="gauge-verdict">${s ? s.verdict : ""}</span></div>`;
    return;
  }
  const metrics = Object.values(s.metrics).map(m =>
    `<span class="gm ${m.good ? "ok" : "warn"}" title="${m.hint}">${m.label} <b>${m.value}</b></span>`
  ).join("");
  el.hidden = false;
  el.innerHTML = `
    <div class="gauge-top">
      <span class="gauge-num" style="color:${scoreColor(s.score)}">${s.score}</span>
      <span class="gauge-verdict">${label} AI-likeness · ${s.verdict}</span>
    </div>
    <div class="gauge-bar"><div class="gauge-fill" style="width:${s.score}%;background:${scoreColor(s.score)}"></div></div>
    <div class="gauge-metrics">${metrics}</div>`;
}

function esc(t) {
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ---------- controls ---------- */
$("modePills").addEventListener("click", (e) => {
  const btn = e.target.closest(".pill");
  if (!btn) return;
  mode = btn.dataset.mode;
  document.querySelectorAll("#modePills .pill").forEach(p => p.classList.toggle("active", p === btn));
});

const chipInput = $("chipInput");
chipInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && chipInput.value.trim()) {
    e.preventDefault();
    keywords.push(chipInput.value.trim());
    chipInput.value = "";
    renderChips();
  } else if (e.key === "Backspace" && !chipInput.value && keywords.length) {
    keywords.pop();
    renderChips();
  }
});
function renderChips() {
  document.querySelectorAll(".chip").forEach(c => c.remove());
  keywords.forEach((k, i) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `${esc(k)}<button aria-label="remove">✕</button>`;
    chip.querySelector("button").onclick = () => { keywords.splice(i, 1); renderChips(); };
    $("chips").insertBefore(chip, chipInput);
  });
}

input.addEventListener("input", () => {
  $("inCount").textContent = wordCount(input.value) + " words";
});

$("clearBtn").onclick = () => {
  input.value = "";
  $("inCount").textContent = "0 words";
  $("gaugeBefore").hidden = true;
};

/* ---------- scoring ---------- */
$("checkBtn").onclick = async () => {
  if (!input.value.trim()) return;
  const r = await fetch("/api/score", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: input.value }),
  });
  renderGauge($("gaugeBefore"), await r.json(), "Original");
};

/* ---------- humanize ---------- */
$("goBtn").onclick = async () => {
  const text = input.value.trim();
  if (!text) { input.focus(); return; }
  const btn = $("goBtn");
  btn.disabled = true;
  output.classList.add("busy");
  output.textContent = "Rewriting… long texts are processed in parallel chunks.";
  $("warnings").hidden = true;
  try {
    const r = await fetch("/api/humanize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode, keywords, variants: +$("variants").value }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${r.status})`);
    }
    result = await r.json();
    variantIdx = 0;
    renderGauge($("gaugeBefore"), result.score_before, "Original");
    renderResult();
  } catch (e) {
    output.classList.remove("busy");
    output.innerHTML = `<p class="placeholder">⚠ ${esc(e.message)}</p>`;
  } finally {
    btn.disabled = false;
  }
};

function renderResult() {
  const v = result.variants[variantIdx];
  output.classList.remove("busy");

  if (view === "diff") {
    output.innerHTML = v.diff.map(s =>
      s.changed ? `<mark>${esc(s.text)}</mark>` : esc(s.text)
    ).join("");
  } else {
    output.textContent = v.text;
  }

  $("outCount").textContent = wordCount(v.text) + " words";
  $("viewTabs").hidden = false;
  $("copyBtn").hidden = false;
  renderGauge($("gaugeAfter"), v.score, "Rewrite");

  const vt = $("variantTabs");
  if (result.variants.length > 1) {
    vt.hidden = false;
    vt.innerHTML = result.variants.map((_, i) =>
      `<button class="tab ${i === variantIdx ? "active" : ""}" data-v="${i}">v${i + 1}</button>`
    ).join("");
  } else {
    vt.hidden = true;
  }

  const warnings = v.warnings || [];
  $("warnings").hidden = warnings.length === 0;
  $("warnings").textContent = warnings.join(" · ");
}

$("viewTabs").addEventListener("click", (e) => {
  const t = e.target.closest(".tab");
  if (!t) return;
  view = t.dataset.view;
  document.querySelectorAll("#viewTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  if (result) renderResult();
});

$("variantTabs").addEventListener("click", (e) => {
  const t = e.target.closest(".tab");
  if (!t) return;
  variantIdx = +t.dataset.v;
  renderResult();
});

$("copyBtn").onclick = async () => {
  if (!result) return;
  await navigator.clipboard.writeText(result.variants[variantIdx].text);
  $("copyBtn").textContent = "Copied ✓";
  setTimeout(() => ($("copyBtn").textContent = "Copy"), 1400);
};

/* ---------- boot ---------- */
fetch("/api/health").then(r => r.json()).then(h => {
  $("engineBadge").textContent = `${h.engine} · ${h.model}`;
}).catch(() => { $("engineBadge").textContent = "engine offline"; });
