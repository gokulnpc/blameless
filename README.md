# BlameLess — Engineering Impact Dashboard

**Who are the 5 most impactful engineers on [`PostHog/posthog`](https://github.com/PostHog/posthog) over the last 90 days — and *why*?**

A single, fast, fully-auditable static page that ranks engineers by the **quality and durability of their changes**, not by raw output. Every number drills down to the real pull requests behind it.

🔗 **Live:** https://gokulnpc.github.io/blameless/

> The name is the thesis: this is **not** about blaming anyone. It uses PR structure, review behaviour and post-merge signals to find engineers whose changes are *intentional, reviewable, and durable* — and it is explicit about what these signals **can't** see.

---

## The core idea: impact ≠ volume

The busiest engineer is rarely the most impactful. Over the current 90-day window, the highest-volume author lands well outside the impact top 5, while engineers with far fewer but cleaner, better-tested, more-stable PRs rise to the top. Every engineer carries **both** an impact rank and a raw-volume rank so the contrast is visible (e.g. *"impact #1 / volume #28"*).

## What it measures

Each engineer with **≥ 3 merged PRs** in the window (a ~125-person cohort) is scored on five dimensions. Signals are computed as **rates and medians** (so high-volume accounts don't win automatically) — the one exception is Process Influence, where review volume legitimately matters.

| # | Dimension | Weight | What it rewards |
|---|-----------|:------:|-----------------|
| D1 | **PR Reviewability & Intent** | 33.3% | Focused, well-described, conventionally-titled, appropriately-sized PRs |
| D2 | **Post-Merge Health** | 27.8% | Changes that stay stable — no reverts, no cross-author corrective fixes |
| D3 | **Requirement-Aligned Tests** | 16.7% | Bug-fix PRs that ship tests; PRs linked to tracked issues |
| D4 | **Code Reduction & Cleanup** | 16.7% | Net code removal and dead-code cleanup |
| D5 | **Process Influence** | 5.6% | Reviews given on others' PRs + review-graph centrality (PageRank) |

Weights are **re-normalized** over these five because two PRD dimensions — *Issue Discovery* (D6) and *Dependency Hygiene* (D7) — can't be computed honestly from PR metadata alone and are marked **"not measured"** rather than faked.

### How scoring works (deterministic — no LLM in the loop)

1. Each sub-metric is computed per engineer from real PR data.
2. Small-sample rates are regressed toward the cohort mean via **empirical-Bayes shrinkage (K = 20)** — so a lucky handful of PRs can't outrank a large body of work, and neither can sheer volume.
3. Each sub-metric is **percentile-ranked** across the active cohort.
4. Dimension score = weighted mean of its sub-metric percentiles; **impact score** = weighted sum of dimensions, scaled to 0–100.

Scores are **relative** to PostHog's active cohort over 90 days — a standing on PR-visible signals, **not** an absolute grade of a person.

### Two signals worth calling out

- **Cross-author corrective churn** counts a PR as "churned" only when a *different human engineer's* PR explicitly references it (`#N`) with a fix within 30 days. Same-file coincidences (≈ 62% noise in this monorepo), self-fixes, and bot/org fixers are deliberately excluded.
- **Bot & org exclusion** is type-based + blocklist-based. Login patterns aren't enough — accounts like `greptile-apps` (an AI reviewer with thousands of reviews) register as a GitHub `User`, so they're filtered explicitly across authors, reviewers, the review graph, and churn attribution.

## Integrity rules

- **No fabricated, estimated, or imputed numbers.** If a signal can't be computed, it's shown as *"not measured"* and excluded from the total.
- **Every number drills down to real PRs** (links to github.com).
- **Bots and organization accounts are excluded** everywhere.
- A **data-freshness timestamp** and the cohort size are always shown.
- A low rank is **not** "a low-value engineer" — the dashboard's honesty panel lists what PR metrics cannot see (architecture, mentorship, on-call, technical direction).

---

## How it works

A three-stage Python pipeline produces a static JSON bundle the page reads with **zero runtime API calls**:

```
fetch.py     →  data/raw/        # cache all merged PRs in the 90-day window (idempotent)
classify.py  →  data/raw/accounts.json   # classify every author/reviewer account (User/Org/Bot)
analyze.py   →  web/dashboard.json + web/profiles.json   # scores, evidence, drill-down data
web/         →  static dashboard that reads the JSON
```

- **`fetch.py`** enumerates `PostHog/posthog` merged PRs via the GraphQL API (ordered by `UPDATED_AT` so the `mergedAt ≥ cutoff` window is complete), pulling per-PR detail (files, reviews, review threads, labels, timeline cross-refs, body). Responses are cached page-by-page to `data/raw/` and **treated as a cache** — re-runs never re-hit the API unless you pass `--refresh`. The whole window costs only ~300 GraphQL rate-limit points.
- **`classify.py`** looks up the real GitHub account *type* for every distinct author and reviewer and caches it, so bots/orgs can be excluded reliably.
- **`analyze.py`** computes the dimension scores, plain-English evidence lines (each citing real PR numbers), the reviewer→author graph, and per-engineer drill-down profiles.

### Project structure

```
blameless/
├─ fetch.py                 # collect + cache raw PRs            → data/raw/
├─ classify.py              # account-type classification        → data/raw/accounts.json
├─ analyze.py               # scoring + evidence + profiles       → web/dashboard.json, web/profiles.json
├─ lib/
│  ├─ auth.py               # token resolution (env → gh keyring; never printed)
│  ├─ github.py             # GraphQL client w/ rate-limit awareness + backoff
│  ├─ bots.py               # bot/org/app account filtering
│  ├─ dataset.py            # clean, in-window, human-only dataset loader
│  ├─ scoring.py            # median / percentile-rank / shrinkage helpers
│  └─ signals.py            # PR signal detectors (tests, bugfix, revert, deps, ...)
├─ web/                     # single static site (zero runtime API calls)
│  ├─ index.html / app.js / styles.css      # top-5 + supporting table + "how we measure" intro
│  ├─ engineer-profile.html / .js           # per-engineer drill-down (every PR, real)
│  ├─ methodology.html / .js                # full methodology + honesty panel
│  ├─ dashboard.json                        # precomputed ranking + evidence
│  └─ profiles.json                         # precomputed per-engineer PR-level data
├─ .github/workflows/refresh.yml            # daily re-fetch → re-score → redeploy
├─ docs/PRD.md                              # the scoring model + build brief
├─ .env.example
└─ .gitignore               # excludes .env and data/raw/
```

---

## Running it locally

**Requirements:** Python 3.11+ and a read-only GitHub token.

A classic PAT with `public_repo` scope is enough (PostHog is public). The scripts read `GITHUB_TOKEN` from the environment first, and otherwise fall back to the [`gh` CLI](https://cli.github.com/) keyring (`gh auth token`) — so an authenticated `gh` install needs no `.env` at all. The token is never printed, logged, or written to disk.

```bash
# 1. install the only two third-party deps
pip install requests certifi

# 2. provide a token (either of these)
export GITHUB_TOKEN=ghp_xxx        # ...or just `gh auth login` once

# 3. run the pipeline
python fetch.py        # caches merged PRs → data/raw/ (idempotent; --refresh to force)
python classify.py     # classifies accounts → data/raw/accounts.json
python analyze.py      # writes web/dashboard.json + web/profiles.json

# 4. serve the static page
python -m http.server 8000 --directory web
# open http://127.0.0.1:8000
```

Re-running `fetch.py` is a no-op once the cache exists, so you can iterate on scoring and the UI for free.

## Deploying (GitHub Pages)

The site is a static bundle, so any static host works. To publish to GitHub Pages from this repo:

```bash
git add -A && git commit -m "Deploy BlameLess"
git push origin main
# publish the web/ folder at the site root via the gh-pages branch:
git push origin "$(git subtree split --prefix web main)":gh-pages --force
# then enable Pages → Source: deploy from branch → gh-pages → / (root)
```

### Daily auto-refresh

`.github/workflows/refresh.yml` runs daily (and on demand from the **Actions** tab): it re-fetches the latest 90-day window, re-scores, and force-pushes the regenerated `web/` to `gh-pages`. It uses the built-in `GITHUB_TOKEN`; if you ever hit Actions rate limits, add a PAT secret as noted in the workflow header. The page fetches its JSON with a cache-busting query so visitors always see the latest scores.

---

## Tech stack

- **Pipeline:** Python 3 — standard library + `requests`/`certifi` for the GraphQL client. No ORM, no framework.
- **Frontend:** vanilla HTML / CSS / JavaScript. No build step, no runtime API calls; radar charts and the review-graph are hand-rolled SVG.
- **Data:** GitHub GraphQL + REST APIs, cached locally.

## Notes & limitations

This model deliberately scores only what shows up in pull requests. It **cannot** see architectural leadership, mentorship, incident response, design decisions made in docs/Slack, or work in other repositories. Read the rankings as *"high on these PR-visible signals vs. peers,"* not as a verdict on an engineer's overall value — the in-app honesty panel says exactly this.
