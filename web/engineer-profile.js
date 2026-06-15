"use strict";

const DIMS = [
  { key: "d1", short: "Reviewability", color: "#4f74cf" },
  { key: "d2", short: "Post-Merge", color: "#1f968a" },
  { key: "d3", short: "Tests", color: "#7a64c8" },
  { key: "d4", short: "Code Reduction", color: "#bd7338" },
  { key: "d5", short: "Process", color: "#5f8a47" },
];

const TYPE_STYLE = {
  feat: { bg: "rgba(79,116,207,.1)", border: "rgba(79,116,207,.3)", color: "#3f5fb0" },
  fix: { bg: "rgba(189,115,56,.12)", border: "rgba(189,115,56,.34)", color: "#a5612b" },
  refactor: { bg: "rgba(122,100,200,.12)", border: "rgba(122,100,200,.32)", color: "#6b59b0" },
  chore: { bg: "#eef0f2", border: "rgba(0,0,0,.1)", color: "#6b7178" },
};

const CONF_STYLE = {
  High: { bg: "rgba(31,157,91,.1)", border: "rgba(31,157,91,.3)", color: "#1f7d4b" },
  Medium: { bg: "rgba(245,166,35,.12)", border: "rgba(245,166,35,.34)", color: "#a5681a" },
  Low: { bg: "#eef0f2", border: "rgba(0,0,0,.1)", color: "#6b7178" },
};

const EV_COLORS = ["#4f74cf", "#1f968a", "#7a64c8", "#5f8a47"];

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
const av = (u, s) => (u ? (u.includes("?") ? u + "&s=" + s : u + "?s=" + s) : "");
const prUrl = (n) => `https://github.com/PostHog/posthog/pull/${n}`;
const dims = (e) => Object.fromEntries(DIMS.map(d => [d.key, e.sub_scores[d.key].percentile]));

let state = { dd: null, profiles: null, login: null, sortKey: "date", sortDir: "desc", filter: "all" };

function getLogin() {
  try {
    return new URLSearchParams(window.location.search).get("login");
  } catch {
    return null;
  }
}

function buildRadarSVG(eng, R) {
  const d = dims(eng);
  const M = 42;
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
    parts.push(`<line x1="${cx}" y1="${cy}" x2="${o[0].toFixed(1)}" y2="${o[1].toFixed(1)}" stroke="rgba(0,0,0,.07)" stroke-width="1"/>`);
  });
  parts.push(`<polygon points="${poly(50)}" fill="rgba(0,0,0,.04)" stroke="rgba(0,0,0,.4)" stroke-width="1" stroke-dasharray="3 3"/>`);
  parts.push(`<polygon points="${DIMS.map((dm, i) => pt(d[dm.key], i).map(n => n.toFixed(1)).join(",")).join(" ")}" fill="rgba(245,166,35,.2)" stroke="#e0930f" stroke-width="2" stroke-linejoin="round"/>`);
  DIMS.forEach((dm, i) => {
    const co = Math.cos(ang(i)), si = Math.sin(ang(i));
    const lp = at(R + 16, i);
    const anchor = co > 0.25 ? "start" : co < -0.25 ? "end" : "middle";
    const baseline = si > 0.4 ? "hanging" : si < -0.4 ? "auto" : "middle";
    parts.push(`<text x="${lp[0].toFixed(1)}" y="${lp[1].toFixed(1)}" text-anchor="${anchor}" dominant-baseline="${baseline}" fill="${dm.color}" font-size="10.5" font-weight="600" font-family="Inter,sans-serif">${esc(dm.short)}</text>`);
  });
  DIMS.forEach((dm, i) => {
    const p = pt(d[dm.key], i);
    parts.push(`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="4.5" fill="${dm.color}" stroke="#fff" stroke-width="1.6"><title>${esc(dm.short)}: ${d[dm.key]}th percentile</title></circle>`);
  });
  return `<svg class="bl-radar" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}">${parts.join("")}</svg>`;
}

function rankOf(pct, cohort) {
  return Math.max(1, Math.round((100 - pct) / 100 * cohort));
}

function render() {
  const root = document.getElementById("profile-root");
  const { dd, profiles, login } = state;
  if (!dd || !profiles) return;

  const cohort = dd.totals.cohort_size;
  const top15 = dd.engineers.slice(0, 15);
  const e = top15.find(x => x.login === login) || top15[0];
  const p = profiles[e.login] || { prs: [], postMerge: [], evidence: [] };
  const F = e.facts;

  document.title = `${e.name || e.login} — BlameLess`;

  const bars = DIMS.map(dm => {
    const pct = e.sub_scores[dm.key].percentile;
    return { dm, pct, rank: rankOf(pct, cohort), w: Math.max(2, pct) };
  });

  const prTotal = p.prs.length;
  const nCited = p.prs.filter(x => x.verified).length;
  const first = (e.name || e.login).split(" ")[0];
  const prCaption = `Every one of ${first}'s ${F.merged_prs} merged PRs in the window — real titles, sizes and flags straight from the GitHub data: ${F.bugfix_prs} fixes (${F.bugfix_with_tests} shipping tests), ${F.cleanup_prs} cleanups, ${F.churned_prs} with a documented later fix, ${F.reverted_prs} reverted. Every row links to the real PR; the ${nCited} cited in the scoring evidence are marked ★.`;

  const counts = { all: p.prs.length, feat: 0, fix: 0, refactor: 0, chore: 0 };
  p.prs.forEach(x => { counts[x.type] = (counts[x.type] || 0) + 1; });

  const filterBtns = ["all", "feat", "fix", "refactor", "chore"].map(k => {
    const active = state.filter === k;
    const label = k === "all" ? "All" : k;
    return `<button type="button" class="bl-profile-filter-btn${active ? " active" : ""}" data-filter="${k}">${label}<span class="count">${counts[k] || 0}</span></button>`;
  }).join("");

  const arrow = (key) => state.sortKey === key ? (state.sortDir === "desc" ? "↓" : "↑") : "↕";
  const sortBtn = (key, label) => {
    const active = state.sortKey === key;
    return `<button type="button" class="bl-profile-sort-btn${active ? " active" : ""}" data-sort="${key}">${label} ${arrow(key)}</button>`;
  };

  let list = p.prs.slice();
  if (state.filter !== "all") list = list.filter(x => x.type === state.filter);
  const dir = state.sortDir === "desc" ? -1 : 1;
  list.sort((a, b) => state.sortKey === "size" ? dir * (Math.abs(a.size) - Math.abs(b.size)) : dir * (a.date - b.date));

  const rows = list.map(x => {
    const ts = TYPE_STYLE[x.type] || TYPE_STYLE.chore;
    const neg = x.size < 0;
    const tests = !!(x.tests || x.hasTests);
    const flags = tests || x.churned || x.reverted;
    const dateLabel = new Date(x.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    return `<tr>
      <td><a href="${prUrl(x.number)}" target="_blank" rel="noopener" class="bl-pr-link">${x.verified ? '<span class="bl-pr-verified" title="Cited in scoring evidence">★</span> ' : ""}#${x.number}<span style="font-size:10px;color:#c79a4a">↗</span></a></td>
      <td style="max-width:380px;color:var(--ink2)">${esc(x.title)}</td>
      <td><span class="bl-pr-type" style="background:${ts.bg};border:1px solid ${ts.border};color:${ts.color}">${esc(x.type)}</span></td>
      <td class="num"><b style="color:${neg ? "#1f9d5b" : "var(--muted)"};font-weight:600">${neg ? "−" : "+"}${Math.abs(x.size)} ln</b> <span style="color:var(--faint2)">· ${x.files} ${x.files === 1 ? "file" : "files"}</span></td>
      <td class="num">${dateLabel}</td>
      <td><span class="bl-profile-flags">
        ${tests ? '<span class="bl-flag-ok" title="Shipped a test file">✓</span>' : ""}
        ${x.churned ? '<span class="bl-flag-churn" title="Had a documented later fix">↻</span>' : ""}
        ${x.reverted ? '<span class="bl-flag-revert" title="Reverted">↺</span>' : ""}
        ${!flags ? '<span class="bl-flag-none">·</span>' : ""}
      </span></td></tr>`;
  }).join("");

  const postMerge = (p.postMerge || []).map(m => {
    const c = CONF_STYLE[m.confidence] || CONF_STYLE.Medium;
    const meta = (m.by ? `by @${m.by}` : "by another engineer") + (m.days != null ? `, ${m.days} days later` : "");
    return `<div class="bl-post-merge-item">
      <a href="${prUrl(m.src)}" target="_blank" rel="noopener" class="bl-pr-link">#${m.src}<span style="font-size:10px;color:#c79a4a">↗</span></a>
      <span style="color:var(--faint3)">later fixed by</span>
      <a href="${prUrl(m.fixedBy)}" target="_blank" rel="noopener" class="bl-post-merge-fix">#${m.fixedBy}<span style="font-size:10px;color:#7d97d8">↗</span></a>
      <span class="bl-post-merge-meta">${esc(meta)}</span>
      <span class="bl-conf-badge" style="background:${c.bg};border:1px solid ${c.border};color:${c.color}">${esc(m.confidence)} confidence</span>
    </div>`;
  }).join("");

  const evidence = (p.evidence || []).map((ev, i) => {
    const chips = (ev.prs || []).map(n =>
      `<a href="${prUrl(n)}" target="_blank" rel="noopener" class="bl-evidence-chip">#${n} ↗</a>`
    ).join("");
    return `<div class="bl-evidence-row">
      <div class="bl-evidence-label-row">
        <span class="bl-evidence-dot" style="background:${EV_COLORS[i] || "#9aa0a8"}"></span>
        <span class="bl-evidence-label">${esc(ev.label)}</span>
      </div>
      <div class="bl-evidence-text">${esc(ev.text)}${chips ? `<span class="bl-evidence-chips">${chips}</span>` : ""}</div>
    </div>`;
  }).join("");

  const postMergeSummary = `Across ${F.merged_prs} merged PRs, ${F.churned_prs} had a documented corrective fix (${F.churn_rate_pct}%) and ${F.reverted_prs} were reverted.`;

  root.innerHTML = `
    <header class="bl-profile-header">
      <div class="bl-profile-who">
        <img class="bl-profile-avatar" src="${esc(av(e.avatar, 160))}" alt="">
        <div>
          <div class="bl-profile-name-row">
            <h1 class="bl-profile-name">${esc(e.name || e.login)}</h1>
            <span class="bl-profile-tag">${esc(e.association_label)}</span>
          </div>
          <a href="${esc(e.url)}" target="_blank" rel="noopener" class="bl-profile-github">@${esc(e.login)} ↗</a>
          <div class="bl-profile-strength">Primary strength: <b>${esc(e.primary_strength)}</b></div>
        </div>
      </div>
      <div class="bl-profile-scorebox">
        <div class="bl-profile-score">
          <span class="bl-profile-score-val">${e.impact_score}</span>
          <span class="bl-profile-score-denom">/100</span>
        </div>
        <div class="bl-lead-score-label">Impact score</div>
        <div class="bl-profile-rank-ctx">impact #${e.impact_rank} of ${cohort} · volume #${e.volume_rank} · ${e.pr_count} PRs</div>
      </div>
    </header>

    <section class="bl-profile-section">
      <div class="bl-section-eyebrow">Where they stand</div>
      <h2 class="bl-section-title" style="margin-top:7px;font-size:21px">Five signals vs the cohort</h2>
      <div class="bl-profile-panel bl-profile-stand-grid">
        <div class="bl-profile-radar-wrap">
          ${buildRadarSVG(e, 92)}
          <div class="bl-profile-legend">
            <span><span class="bl-profile-legend-line"></span> ${esc(e.name || e.login)}</span>
            <span><span class="bl-profile-legend-dash"></span> Cohort median</span>
          </div>
        </div>
        <div class="bl-profile-signal-bars">
          ${bars.map(b => `
            <div>
              <div class="bl-profile-signal-bar-top">
                <span class="bl-profile-signal-name">${esc(b.dm.short)}</span>
                <span class="bl-profile-signal-meta"><b style="color:${b.dm.color}">${b.pct}th</b> percentile <span style="color:var(--faint2)">· #${b.rank} of ${cohort}</span></span>
              </div>
              <span class="bl-pct-track">
                <span class="bl-pct-fill" style="width:${b.w}%;background:${b.dm.color}"></span>
                <span class="bl-pct-median"></span>
              </span>
            </div>`).join("")}
          <div style="font-size:11.5px;color:var(--faint);margin-top:2px">The tick marks the cohort median (50th percentile) on each signal.</div>
        </div>
      </div>
    </section>

    <section class="bl-profile-section-lg">
      <div class="bl-section-eyebrow">Their pull requests</div>
      <h2 class="bl-section-title" style="margin-top:7px;font-size:21px">All ${prTotal} merged PRs in the window</h2>
      <p class="bl-profile-caption">${esc(prCaption)}</p>
      <div class="bl-profile-toolbar">
        <div class="bl-profile-filters">${filterBtns}</div>
        <div class="bl-profile-sort-row">
          <span class="bl-profile-sort-label">Sort by</span>
          ${sortBtn("date", "Date")}
          ${sortBtn("size", "Size")}
        </div>
      </div>
      <div class="bl-profile-pr-wrap bl-scroll">
        <table class="bl-profile-pr-table">
          <thead><tr>
            <th>PR</th><th>Title</th><th>Type</th>
            <th class="num">Size</th><th class="num">Merged</th><th>Flags</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="6" style="padding:20px;color:var(--faint)">No PRs match this filter.</td></tr>'}</tbody>
        </table>
      </div>
      <div class="bl-profile-flag-legend">
        <span><span class="bl-flag-ok">✓</span> shipped tests</span>
        <span><span class="bl-flag-churn">↻</span> documented later fix</span>
        <span><span class="bl-flag-revert">↺</span> reverted</span>
        <span><span class="bl-pr-verified">★</span> cited in evidence (verified real PR)</span>
      </div>
    </section>

    <section class="bl-profile-section-lg">
      <div class="bl-section-eyebrow">What happened after these merged</div>
      <h2 class="bl-section-title" style="margin-top:7px;font-size:21px">Documented corrective links</h2>
      <p class="bl-profile-caption">Later fixes that <b>explicitly reference</b> the original PR. Fixes that don't name it aren't captured, so this is a <b>floor, not a full accounting</b>.</p>
      ${postMerge ? `<div class="bl-post-merge-list">${postMerge}</div><div style="font-size:12px;color:var(--faint);margin-top:2px">${esc(postMergeSummary)}</div>` : `
        <div class="bl-post-merge-ok">
          <span class="icon">✓</span>
          <div><b>No documented corrective fixes.</b> Nothing they shipped needed a named follow-up within 30 days. For an engineer at this volume, an empty section here is a good sign.</div>
        </div>`}
    </section>

    <section class="bl-profile-section-lg">
      <div class="bl-section-eyebrow">In plain English</div>
      <h2 class="bl-section-title" style="margin-top:7px;font-size:21px">What the score is made of</h2>
      <div class="bl-evidence-panel">${evidence || '<div style="padding:18px 0;color:var(--faint)">No evidence summaries available.</div>'}</div>
    </section>

    <section class="bl-profile-honesty">
      <div class="bl-profile-honesty-title">A low rank is <span>NOT</span> a low-value engineer.</div>
      <p style="margin:8px 0 0;font-size:12.5px;line-height:1.6;color:var(--muted);max-width:840px">These scores are <b style="color:var(--ink2)">relative</b> to PostHog's active cohort over 90 days — a standing on what shows up in pull requests, not an absolute grade of a person. Architecture, mentorship, on-call and design work rarely land in a PR and aren't counted here.</p>
      <a href="index.html" class="bl-method-back">&larr; Back to the full ranking</a>
    </section>`;

  root.querySelectorAll("[data-filter]").forEach(btn => {
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter;
      render();
    });
  });
  root.querySelectorAll("[data-sort]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.sort;
      if (state.sortKey === key) state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      else { state.sortKey = key; state.sortDir = "desc"; }
      render();
    });
  });
}

Promise.all([
  fetch("dashboard.json?v=" + Date.now()).then(r => r.json()),
  fetch("profiles.json?v=" + Date.now()).then(r => r.json()),
]).then(([dd, profiles]) => {
  const requested = getLogin();
  const top15 = dd.engineers.slice(0, 15).map(e => e.login);
  const login = requested && top15.includes(requested) ? requested : top15[0];
  state = { ...state, dd, profiles, login };
  render();
}).catch(err => {
  document.getElementById("profile-root").innerHTML =
    `<pre style="color:#c44;padding:20px">Failed to load profile: ${esc(err)}</pre>`;
});
