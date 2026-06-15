"use strict";

const SIGNALS = [
  { color: "#4f74cf", name: "Reviewability & intent", pct: "33%", desc: "Is the work easy to review — small, focused PRs with a clear description and linked intent." },
  { color: "#1f968a", name: "Post-merge health", pct: "28%", desc: "Does it stay stable after shipping — low corrective churn, few reverts, ships fixes forward." },
  { color: "#7a64c8", name: "Requirement-aligned tests", pct: "17%", desc: "Does the change come with real tests — test files on bug and feature PRs, linked to requirements." },
  { color: "#bd7338", name: "Code reduction & cleanup", pct: "17%", desc: "Net removal and cleanup, not just additions. A low score means additive feature work, not poor quality." },
  { color: "#5f8a47", name: "Process influence", pct: "6%", desc: "Helping others' PRs — reviews given, changes requested, and centrality in the review graph." },
];

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));

document.getElementById("signals").innerHTML = SIGNALS.map(s => `
  <div class="bl-signal-row">
    <div class="bl-signal-name-row">
      <span class="bl-signal-dot" style="background:${s.color}"></span>
      <span class="bl-signal-name">${esc(s.name)}</span>
      <span class="bl-signal-pct" style="color:${s.color}">${s.pct}</span>
    </div>
    <span class="bl-signal-desc">${esc(s.desc)}</span>
  </div>`).join("");

fetch("dashboard.json?v=" + Date.now())
  .then(r => r.json())
  .then(d => {
    const t = d.totals;
    document.getElementById("data-scope").innerHTML =
      `Built from merged pull requests on <b>${esc(d.repo)}</b> over a rolling <b>${d.window.days}-day window</b>. Every engineer with <b>≥3 merged PRs</b> is scored against the active cohort of <b>${t.cohort_size} engineers</b>.`;
    const nm = d.not_measured || [];
    document.getElementById("not-measured").innerHTML = nm.map(x => `
      <div class="bl-not-measured-item">
        <span>—</span>
        <span><b>${esc(x.dimension)}</b> · ${esc(x.reason)}</span>
      </div>`).join("");
  })
  .catch(() => {
    document.getElementById("not-measured").innerHTML =
      '<div class="bl-not-measured-item"><span>—</span><span>Could not load not-measured dimensions from dashboard.json.</span></div>';
  });
