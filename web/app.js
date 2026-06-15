"use strict";

const DIMS = [
  { key: "d1", short: "Reviewability", full: "PR Reviewability & Intent", color: "#4f74cf" },
  { key: "d2", short: "Post-Merge", full: "Post-Merge Health", color: "#1f968a" },
  { key: "d3", short: "Tests", full: "Requirement-Aligned Tests", color: "#7a64c8" },
  { key: "d4", short: "Code Reduction", full: "Code Reduction & Cleanup", color: "#bd7338" },
  { key: "d5", short: "Process", full: "Process Influence", color: "#5f8a47" },
];

const DIM_ORDER = DIMS.map(d => d.key);
const DIM_SHORT = Object.fromEntries(DIMS.map(d => [d.key, d.short]));
const DIM_COLOR = Object.fromEntries(DIMS.map(d => [d.key, d.color]));
const DIM_FULL = Object.fromEntries(DIMS.map(d => [d.key, d.full]));

const SUBS = {
  d1: ["size", "scope", "intent", "testing", "friction"],
  d2: ["clean_churn", "revert_avoid", "fix_forward"],
  d3: ["requirement_linkage", "regression_coverage"],
  d4: ["safe_reduction", "dead_code"],
  d5: ["reviews_given", "centrality", "changes_requested"],
};

const METRIC_LABEL = {
  size: "PR size: median lines (smaller = higher)",
  scope: "Scope focus: fewer top-level dirs per PR",
  intent: "Diff intent: description + clear title + link",
  testing: "Testing signals on PRs",
  friction: "Low review friction: fewer review threads",
  clean_churn: "No cross-author corrective churn (≤30d)",
  revert_avoid: "Revert avoidance",
  fix_forward: "Fix-forward: ships bug/regression fixes",
  requirement_linkage: "Issue / PR linkage (#n in body)",
  regression_coverage: "Tests shipped on bug-fix PRs",
  safe_reduction: "Safe net code reduction",
  dead_code: "Cleanup / dead-code removal PRs",
  reviews_given: "Reviews given on others' PRs",
  centrality: "Review-graph centrality (PageRank)",
  changes_requested: "Changes-requested reviews",
};

const STORY = [
  { kind: "text", head: "More PRs ≠ more impact",
    body: "The busiest engineer isn't automatically the most impactful. Shipping a lot of code says nothing about whether it was reviewable, stable, or well-tested." },
  { kind: "text", head: "So we measure the change, not the amount of it",
    body: "We score whether someone's work is easy to review, stays stable after it ships, and comes with real tests — the things that actually move a codebase forward." },
  { kind: "bars", head: "Five signals, weighted by how much they matter",
    bars: [
      { label: "Reviewability & intent", pct: 33, color: "#4f74cf" },
      { label: "Stayed stable after merging", pct: 28, color: "#1f968a" },
      { label: "Tests", pct: 17, color: "#7a64c8" },
      { label: "Code reduction & cleanup", pct: 17, color: "#bd7338" },
      { label: "Review influence (helping others' PRs)", pct: 6, color: "#5f8a47" },
    ],
    foot: "Each engineer is ranked against the whole team on every signal." },
  { kind: "text", head: "We're honest about what we can't see",
    body: "Plenty of real impact never lands in a PR: architecture, mentorship, on-call, design decisions. We don't invent scores for those. If we can't measure it, we say so." },
  { kind: "cta", head: "Every number is real, and so is the result",
    body: "Each score drills down to the actual GitHub PRs behind it. The punchline: the five most active engineers mostly aren't the five most impactful.",
    cta: "See who is" },
];

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
const fmtDate = (iso) => { try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); } catch { return iso; } };
const fmtDay = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }); } catch { return iso; } };
const av = (u, s) => (u ? (u.includes("?") ? u + "&s=" + s : u + "?s=" + s) : "");
const profileUrl = (login) => `engineer-profile.html?login=${encodeURIComponent(login)}`;

let DATA = null;
let slide = 0;
let slidePaused = false;
let slideActed = false;
let slideTimer = null;
let radarHover = null;

function dims(e) {
  const out = {};
  for (const d of DIM_ORDER) out[d] = e.sub_scores[d].percentile;
  return out;
}

fetch("dashboard.json")
  .then(r => r.json())
  .then(d => { DATA = d; render(d); })
  .catch(e => { document.body.innerHTML = `<pre style="color:#c44;padding:30px;font-family:Inter,sans-serif">Failed to load dashboard.json: ${esc(e)}</pre>`; });

function render(d) {
  $("#repo-label").textContent = d.repo;
  renderMeta(d);
  renderSlideshow();
  renderMethodologyLink();
  renderTop5(d);
  renderSupporting(d);
  renderFooter(d);
  setupModal();
  setupSlideshow();
}

function renderMeta(d) {
  const t = d.totals;
  const chips = [
    { k: "Repo", v: d.repo },
    { k: "Window", v: `${d.window.days}-day` },
    { k: "Human PRs", v: t.merged_prs_humans.toLocaleString() },
    { k: "Cohort", v: `${t.cohort_size} active engineers` },
    { k: "Fresh", v: new Date(d.generated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) },
  ];
  $("#meta-strip").innerHTML = chips.map(c =>
    `<span class="bl-chip"><span class="bl-chip-k">${esc(c.k)}</span><b>${esc(c.v)}</b></span>`
  ).join("");
}

function renderSlideshow() {
  const stage = $("#slide-stage");
  stage.innerHTML = STORY.map((s, i) => {
    let inner = `<h3 class="bl-slide-head">${esc(s.head)}</h3>`;
    if (s.kind === "text" || s.kind === "cta") {
      inner += `<p class="bl-slide-text">${esc(s.body)}</p>`;
    }
    if (s.kind === "cta") {
      inner += `<div class="bl-slide-cta">${esc(s.cta)} <span class="bl-slide-cta-arrow">&darr;</span></div>`;
    }
    if (s.kind === "bars") {
      const bars = s.bars.map(b => `
        <div class="bl-slide-bar-row">
          <span class="bl-slide-bar-label">${esc(b.label)}</span>
          <span class="bl-slide-bar-track"><span class="bl-slide-bar-fill" style="width:${Math.round(b.pct / 33 * 100)}%;background:${b.color}"></span></span>
          <span class="bl-slide-bar-pct">${b.pct}%</span>
        </div>`).join("");
      inner += `<div class="bl-slide-bars">${bars}<div class="bl-slide-foot">${esc(s.foot)}</div></div>`;
    }
    return `<div class="bl-slide${i === slide ? " active" : ""}" data-slide="${i}" aria-hidden="${i !== slide}">
      <div class="bl-slide-num">${String(i + 1).padStart(2, "0")}</div>
      <div class="bl-slide-body">${inner}</div>
    </div>`;
  }).join("");
  $("#slide-counter").textContent = `${String(slide + 1).padStart(2, "0")} / ${String(STORY.length).padStart(2, "0")}`;
  $("#slide-dots").innerHTML = STORY.map((_, i) =>
    `<button class="bl-slide-dot${i === slide ? " active" : ""}" data-dot="${i}" aria-label="Go to slide ${i + 1}"></button>`
  ).join("");
}

function setupSlideshow() {
  const el = $("#slideshow");
  const go = (i) => {
    slide = (i + STORY.length) % STORY.length;
    slideActed = true;
    renderSlideshow();
    bindDots();
  };
  const bindDots = () => {
    $("#slide-dots").querySelectorAll("[data-dot]").forEach(btn =>
      btn.addEventListener("click", () => go(+btn.dataset.dot)));
  };
  bindDots();
  $("#slide-prev").addEventListener("click", () => go(slide - 1));
  $("#slide-next").addEventListener("click", () => go(slide + 1));
  el.addEventListener("mouseenter", () => { slidePaused = true; });
  el.addEventListener("mouseleave", () => { slidePaused = false; });
  el.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); go(slide + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(slide - 1); }
  });
  if (slideTimer) clearInterval(slideTimer);
  slideTimer = setInterval(() => {
    if (slideActed || slidePaused) return;
    go(slide + 1);
  }, 6000);
}

function renderMethodologyLink() {
  $("#methodology-link").innerHTML = `
    <a href="methodology.html" class="bl-methodology-link">
      <span class="bl-methodology-icon">
        <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#bf7d14" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 3h7l5 5v12.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>
          <path d="M14 3v5h5"/><path d="M9 13h6M9 16.5h6"/>
        </svg>
      </span>
      <div class="bl-methodology-text">
        <div class="bl-methodology-title">Methodology &amp; roadmap</div>
        <div class="bl-methodology-desc">How the score is calculated, the five signals, what we deliberately don't measure — and what's next.</div>
      </div>
      <span class="bl-methodology-cta">View full methodology &amp; roadmap <span>&rarr;</span></span>
    </a>`;
}

function buildRadarSVG(eng, R, hideLabels) {
  const d = dims(eng);
  const M = hideLabels ? 16 : 30;
  const W = 2 * R + 2 * M;
  const cx = W / 2, cy = W / 2;
  const ang = (i) => (-90 + 72 * i) * Math.PI / 180;
  const at = (rad, i) => [cx + rad * Math.cos(ang(i)), cy + rad * Math.sin(ang(i))];
  const pt = (p, i) => at(R * Math.max(0, Math.min(100, p)) / 100, i);
  const poly = (p) => DIMS.map((_, i) => pt(p, i).map(n => n.toFixed(1)).join(",")).join(" ");
  const parts = [];

  [25, 50, 75, 100].forEach(lvl => {
    parts.push(`<polygon points="${poly(lvl)}" fill="none" stroke="rgba(0,0,0,${lvl === 100 ? 0.16 : 0.07})" stroke-width="1"/>`);
  });
  DIMS.forEach((_, i) => {
    const o = pt(100, i);
    parts.push(`<line x1="${cx}" y1="${cy}" x2="${o[0].toFixed(1)}" y2="${o[1].toFixed(1)}" stroke="rgba(0,0,0,.05)" stroke-width="1"/>`);
  });
  parts.push(`<polygon points="${poly(50)}" fill="rgba(0,0,0,.04)" stroke="rgba(0,0,0,.32)" stroke-width="1" stroke-dasharray="3 3"/>`);
  parts.push(`<polygon points="${DIMS.map((dm, i) => pt(d[dm.key], i).map(n => n.toFixed(1)).join(",")).join(" ")}" fill="rgba(245,166,35,.16)" stroke="#f5a623" stroke-width="2" stroke-linejoin="round"/>`);

  if (!hideLabels) {
    DIMS.forEach((dm, i) => {
      const co = Math.cos(ang(i)), si = Math.sin(ang(i));
      const lp = at(R + 13, i);
      const anchor = co > 0.25 ? "start" : co < -0.25 ? "end" : "middle";
      const baseline = si > 0.4 ? "hanging" : si < -0.4 ? "auto" : "middle";
      parts.push(`<text x="${lp[0].toFixed(1)}" y="${lp[1].toFixed(1)}" text-anchor="${anchor}" dominant-baseline="${baseline}" fill="${dm.color}" font-size="8.5" font-weight="600" font-family="Inter,sans-serif">${esc(dm.short.split(" ")[0])}</text>`);
    });
  }

  DIMS.forEach((dm, i) => {
    const v = d[dm.key];
    const p = pt(v, i);
    const hov = radarHover && radarHover.login === eng.login && radarHover.key === dm.key;
    const r = hov ? 5 : 3.4;
    parts.push(`<circle data-login="${esc(eng.login)}" data-dim="${dm.key}" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${r}" fill="${dm.color}" stroke="#fff" stroke-width="1.5"><title>${esc(dm.short)}, ${v}th percentile · click for sub-metrics</title></circle>`);
  });

  return `<svg class="bl-radar" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}">${parts.join("")}</svg>`;
}

function bindRadarClicks(container) {
  container.querySelectorAll("circle[data-dim]").forEach(c => {
    c.addEventListener("click", (e) => {
      e.stopPropagation();
      openMetricModal(c.dataset.login, c.dataset.dim);
    });
    c.addEventListener("mouseenter", () => {
      radarHover = { login: c.dataset.login, key: c.dataset.dim };
      rerenderRadars();
    });
    c.addEventListener("mouseleave", () => {
      radarHover = null;
      rerenderRadars();
    });
  });
}

function rerenderRadars() {
  if (!DATA) return;
  const top = DATA.engineers.slice(0, 5);
  const leadRadar = $("#lead-card .bl-lead-radar");
  if (leadRadar) leadRadar.innerHTML = buildRadarSVG(top[0], 100, true);
  $("#impact-grid").querySelectorAll(".bl-impact-radar").forEach((el, i) => {
    el.innerHTML = buildRadarSVG(top[i + 1], 64, false);
  });
  bindRadarClicks($("#lead-card"));
  bindRadarClicks($("#impact-grid"));
}

function pctBarHTML(dm, pct, onClickAttr) {
  const w = Math.max(2, pct);
  return `
    <div class="bl-pct-bar" ${onClickAttr || ""}>
      <div class="bl-pct-bar-top">
        <span class="bl-pct-bar-label"><span class="bl-pct-dot" style="background:${dm.color}"></span>${esc(dm.short)}</span>
        <span class="bl-pct-val">${pct}<span class="bl-pct-val-suffix">th</span></span>
      </div>
      <span class="bl-pct-track">
        <span class="bl-pct-fill" style="width:${w}%;background:${dm.color}"></span>
        <span class="bl-pct-median"></span>
      </span>
    </div>`;
}

function miniBarHTML(dm, pct, login) {
  const w = Math.max(2, pct);
  return `
    <div class="bl-mini-bar" data-login="${esc(login)}" data-dim="${dm.key}">
      <span class="bl-mini-bar-label">${esc(dm.short)}</span>
      <span class="bl-pct-track sm">
        <span class="bl-pct-fill" style="width:${w}%;background:${dm.color}"></span>
        <span class="bl-pct-median"></span>
      </span>
      <span class="bl-mini-bar-pct">${pct}</span>
    </div>`;
}

function renderTop5(d) {
  const top = d.engineers.slice(0, 5);
  const lead = top[0];
  const tie = top.slice(1);
  const peers = d.totals.cohort_size - 1;

  const leadBars = DIMS.map(dm => {
    const pct = lead.sub_scores[dm.key].percentile;
    return pctBarHTML(dm, pct, `data-login="${esc(lead.login)}" data-dim="${dm.key}"`);
  }).join("");

  $("#lead-card").innerHTML = `
    <div class="bl-lead-card">
      <div>
        <div class="bl-lead-rank-row">
          <div class="bl-lead-rank">1</div>
          <span class="bl-standout-badge">&#9733; Clear standout</span>
        </div>
        <a href="${esc(lead.url)}" target="_blank" rel="noopener" class="bl-lead-who" title="View GitHub profile">
          <img class="bl-lead-avatar" src="${esc(av(lead.avatar, 160))}" alt="" loading="lazy">
          <div>
            <div class="bl-lead-name">${esc(lead.name || lead.login)}</div>
            <div class="bl-lead-login">@${esc(lead.login)} &middot; <span>${esc(lead.association_label)}</span></div>
          </div>
        </a>
        <div class="bl-lead-score-row">
          <span class="bl-lead-score">${lead.impact_score}</span>
          <span class="bl-lead-score-denom">/100</span>
        </div>
        <div class="bl-lead-score-label">Impact score</div>
        <div class="bl-stat-pills">
          <span class="bl-stat-pill accent">impact <b>#${lead.impact_rank}</b></span>
          <span class="bl-stat-pill">volume <b>#${lead.volume_rank}</b></span>
          <span class="bl-stat-pill"><b>${lead.pr_count}</b> PRs</span>
        </div>
        <div class="bl-lead-strength">Primary strength: <b>${esc(lead.primary_strength)}</b></div>
        <a href="${esc(profileUrl(lead.login))}" class="bl-profile-btn">View full profile <span>&rarr;</span></a>
      </div>
      <div class="bl-lead-radar">${buildRadarSVG(lead, 100, true)}</div>
      <div>
        <div class="bl-lead-bars-header">
          <span class="bl-lead-bars-title">Percentile vs cohort</span>
          <span class="bl-lead-bars-peers">vs ${peers} peers</span>
        </div>
        <div class="bl-pct-bars">${leadBars}</div>
        <div class="bl-lead-bars-foot">Ranked against the cohort on each signal · tick marks the median · click a bar for the sub-metrics.</div>
      </div>
    </div>`;

  const gap = (lead.impact_score - tie[0].impact_score).toFixed(1);
  const spread = (tie[0].impact_score - tie[tie.length - 1].impact_score).toFixed(1);
  $("#tie-banners").innerHTML = `
    <span class="bl-tie-banner amber"><b>#1 leads by ${gap} pts</b>, a genuine outlier</span>
    <span class="bl-tie-banner gray">Ranks <b>2–5 sit within ${spread} pts</b>, read them as a matched group, not a strict 2&gt;3&gt;4&gt;5 order</span>`;

  $("#impact-grid").innerHTML = tie.map(e => impactCardHTML(e)).join("");

  $("#lead-card").querySelectorAll(".bl-pct-bar[data-dim]").forEach(b =>
    b.addEventListener("click", () => openMetricModal(b.dataset.login, b.dataset.dim)));
  $("#impact-grid").querySelectorAll(".bl-mini-bar[data-dim]").forEach(b =>
    b.addEventListener("click", () => openMetricModal(b.dataset.login, b.dataset.dim)));
  bindRadarClicks($("#lead-card"));
  bindRadarClicks($("#impact-grid"));
}

function impactCardHTML(e) {
  const bars = DIMS.map(dm => miniBarHTML(dm, e.sub_scores[dm.key].percentile, e.login)).join("");
  return `
    <div class="bl-impact-card">
      <div class="bl-impact-card-top">
        <div class="bl-impact-rank">#${e.impact_rank}</div>
        <a href="${esc(e.url)}" target="_blank" rel="noopener" class="bl-impact-who" title="View GitHub profile">
          <img class="bl-impact-avatar" src="${esc(av(e.avatar, 110))}" alt="" loading="lazy">
          <div style="min-width:0">
            <div class="bl-impact-name">${esc(e.name || e.login)}</div>
            <div class="bl-impact-login">@${esc(e.login)} &middot; ${esc(e.association_label)}</div>
          </div>
        </a>
      </div>
      <div class="bl-impact-score-row">
        <span class="bl-impact-score">${e.impact_score}</span>
        <span class="bl-impact-score-denom">/100</span>
        <span class="bl-impact-meta">vol <b>#${e.volume_rank}</b> &middot; <b>${e.pr_count}</b> PRs</span>
      </div>
      <div class="bl-impact-radar">${buildRadarSVG(e, 64, false)}</div>
      <div class="bl-mini-bars">${bars}</div>
      <a href="${esc(profileUrl(e.login))}" class="bl-impact-profile-link">View full profile <span>&rarr;</span></a>
    </div>`;
}

function renderSupporting(d) {
  const rows = d.engineers.slice(5, 15);
  const head = `<thead><tr>
    <th>#</th><th>Engineer</th>
    <th class="num">Impact</th><th class="num">Vol</th>
    ${DIMS.map(dm => `<th style="color:${dm.color}">${esc(dm.short)}</th>`).join("")}
    <th>Strength</th></tr></thead>`;
  const body = rows.map(e => `<tr>
    <td>${e.impact_rank}</td>
    <td>
      <a href="${esc(profileUrl(e.login))}" class="bl-table-engineer" title="View full profile">
        <img class="bl-table-avatar" src="${esc(av(e.avatar, 56))}" alt="" loading="lazy">
        <span class="bl-table-name">${esc(e.name || e.login)}</span>
        <span class="bl-table-arrow">&rarr;</span>
      </a>
    </td>
    <td class="num score">${e.impact_score}</td>
    <td class="num vol">#${e.volume_rank}</td>
    ${DIMS.map(dm => {
      const pct = e.sub_scores[dm.key].percentile;
      const w = Math.max(2, pct);
      return `<td class="bl-table-mini" data-login="${esc(e.login)}" data-dim="${dm.key}" title="Click for the sub-metrics">
        <div class="bl-table-mini-inner">
          <span class="bl-table-mini-track">
            <span class="bl-table-mini-fill" style="width:${w}%;background:${dm.color}"></span>
            <span class="bl-table-mini-median"></span>
          </span>
          <span class="bl-table-mini-pct">${pct}</span>
        </div></td>`;
    }).join("")}
    <td class="strength">${esc(e.primary_strength)}</td></tr>`).join("");
  $("#supporting").innerHTML = head + `<tbody>${body}</tbody>`;
  $("#supporting").querySelectorAll(".bl-table-mini[data-dim]").forEach(cell =>
    cell.addEventListener("click", () => openMetricModal(cell.dataset.login, cell.dataset.dim)));
}

function renderFooter(d) {
  const t = d.totals;
  $("#footer").innerHTML =
    `BlameLess &middot; ${esc(d.repo)} &middot; ${t.merged_prs_humans.toLocaleString()} human-merged PRs over ${d.window.days} days &middot; ${t.cohort_size} active engineers &middot; every number drills down to real pull requests. Scores are relative, not absolute.`;
}

function setupModal() {
  $("#modal").addEventListener("click", e => {
    if (e.target.id === "modal") closeModal();
  });
  $("#modal-card").addEventListener("click", e => e.stopPropagation());
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
}

function closeModal() { $("#modal").classList.add("hidden"); }

function openMetricModal(login, dim) {
  const e = DATA.engineers.find(x => x.login === login);
  const dm = DIMS.find(x => x.key === dim);
  if (!e || !dm) return;

  const rows = SUBS[dim].map(m => {
    const has = (m in e.metric_percentiles);
    const pct = has ? e.metric_percentiles[m] : 0;
    const fill = has
      ? `<span class="modal-row-fill" style="width:${Math.max(2, pct)}%;background:${dm.color};opacity:1"></span><span class="modal-row-median"></span>`
      : "";
    return `<div class="modal-row">
      <span class="modal-row-label">${esc(METRIC_LABEL[m] || m)}</span>
      <span class="modal-row-track">${fill}</span>
      <span class="modal-row-val">${has ? pct + "th" : "n/a"}</span>
    </div>`;
  }).join("");

  const f = e.facts;
  const facts = [
    { k: "Merged PRs", v: f.merged_prs },
    { k: "Median size", v: `${f.median_pr_size} ln · ${f.median_files} files` },
    { k: "Churn / reverts", v: `${f.churn_rate_pct}% · ${f.reverted_prs}` },
    { k: "Bug-fix + tests", v: `${f.bugfix_with_tests}/${f.bugfix_prs}` },
    { k: "Issue linkage", v: `${f.requirement_linkage_pct}%` },
    { k: "Reviews / chg-req", v: `${f.reviews_given} · ${f.changes_requested_given}` },
  ].map(x => `<div class="modal-fact"><span class="modal-fact-k">${esc(x.k)}</span><b class="modal-fact-v">${esc(String(x.v))}</b></div>`).join("");

  $("#modal-body").innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-dim" style="color:${dm.color}">${esc(dm.full)}</div>
        <h3>${esc(e.name || e.login)}</h3>
      </div>
      <button class="modal-close" aria-label="Close">&times;</button>
    </div>
    <p class="modal-sub">Each sub-metric is percentile-ranked across the ${DATA.totals.cohort_size} active engineers. The notch marks the cohort median (50th).</p>
    <div class="modal-rows">${rows}</div>
    <div class="modal-facts-title">Underlying facts &middot; real data</div>
    <div class="modal-facts">${facts}</div>`;

  $(".modal-close", $("#modal")).addEventListener("click", closeModal);
  $("#modal").classList.remove("hidden");
}
