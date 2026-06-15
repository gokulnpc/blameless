# PRD — "BlameLess": Engineering Impact Dashboard

**One-liner:** Identify the **5 most impactful engineers** on `PostHog/posthog` over the
**last 90+ days**, and show _why_ on a **single, fast, fully auditable** page.

**Why "BlameLess":** the goal is not to blame engineers. We use Git history, PR structure,
review behavior, and post-merge signals to find engineers whose changes are **intentional,
reviewable, and durable**.

### How to read this PRD

- **Part A — Scoring model (the "what"):** the impact definition + the 7-dimension model. The north star.
- **Part B — Build brief (the "how"):** data collection, computation, dashboard, hosting.
- **Part C — Feasibility & integrity:** which signals are real vs. out of scope, and the rules that keep every number honest.
- **Appendix — Setup checklist:** env vars, repo layout, what you must provide.

---

---

# PART A — SCORING MODEL

## A.1 Working thesis

The dashboard must **not** rank engineers by raw activity. It identifies engineers who make
the codebase and the engineering process **healthier**:

> Impactful engineers ship intentional, reviewable changes that are easy to understand,
> remain healthy after merge, and improve the team's ability to build safely.

Three ideas are the signature feature: **(1) PR Reviewability, (2) Developer Intent,
(3) Post-Merge Code Health.** Supporting dimensions round out the ranking but must not clutter the UI.

## A.2 Core scoring model

|   # | Dimension                                | Weight | Simple question                                                | Why it matters                                                                                     |
| --: | ---------------------------------------- | -----: | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
|   1 | PR Reviewability & Developer Intent      |    30% | Was the change focused, intentional, and easy to review?       | Most distinctive signal. Detects noisy diffs, oversized PRs, unnecessary rewrites, AI-style churn. |
|   2 | Code Ownership & Post-Merge Health       |    25% | What happened after the code merged?                           | Goes beyond merge-time activity: did the change stay stable or cause follow-up churn?              |
|   3 | Requirement-Aligned Test Quality         |    15% | Do the tests prove the actual requirement/bug fix?             | Avoids rewarding meaningless coverage; focuses on tests that protect behavior.                     |
|   4 | Simplicity, Readability & Design Quality |    15% | Did the engineer make code easier to understand and maintain?  | Great engineers reduce complexity, not just add code.                                              |
|   5 | Engineering Process Influence            |     5% | Did they improve work via review, design input, clarification? | Captures non-code engineering impact.                                                              |
|   6 | Issue Discovery, Triage & Resolution     |     5% | Did they help find, understand, prioritize, resolve problems?  | The problem-solving layer before and after PRs.                                                    |
|   7 | Dependency & Duplication Hygiene         |     5% | Did they keep the codebase lean?                               | Detects bloat, duplicate logic, unnecessary dependencies.                                          |

## A.3 Dimension 1 — PR Reviewability & Developer Intent

**Definition:** measures whether changes are focused, intentional, and safe to review — what
changed, why, and how reviewers can validate it. _Not_ the same as rewarding small PRs; some
important work is large. Reward appropriately-scoped PRs; penalize mixed/noisy/oversized ones.

| Metric                           | Positive                                              | Negative                                   | GitHub evidence                                  |
| -------------------------------- | ----------------------------------------------------- | ------------------------------------------ | ------------------------------------------------ |
| Manageable PR size               | Small/medium focused, or large but clearly structured | Huge with no review path                   | additions, deletions, changed files, description |
| Scope focus                      | Files align to one purpose                            | Bugfix + refactor + formatting + cleanup   | title, description, labels, changed paths        |
| Diff intent clarity              | PR explains _why_                                     | Large diff, vague title, no description    | body, linked issue, review comments              |
| Low noisy-churn                  | Functional changes easy to isolate                    | Renames/formatting/moves with little value | file diffs, repeated delete/add blocks           |
| Mechanical/functional separation | Cleanup separated from logic                          | Formatting mixed into feature/bugfix       | changed files, commits, body                     |
| Review friction                  | Few clarification comments                            | Reviewers ask to split/simplify/explain    | review comments                                  |
| AI-style low-signal rewrite      | Small targeted changes                                | Whole-function rewrites for tiny changes   | similar old/new blocks, diff patterns            |
| Reviewability explanation        | Testing/screenshot/migration/risk notes               | No validation details for risky changes    | body, checklist, linked issue                    |

**Sub-scores:** PR size appropriateness 20% · Scope focus 20% · Diff intent clarity 20% ·
Low noisy churn 20% · Review friction 10% · Testing/validation notes 10%.
**Cautions:** large PRs aren't always bad (penalize only when unjustified/unreviewable);
small PRs aren't always good; reward explained/isolated/tested refactors; never _claim_ AI
use — detect low-signal rewrite patterns instead.

## A.4 Dimension 2 — Code Ownership & Post-Merge Health

**Definition:** what happens _after_ merge — follow-up changes, reverts, fix chains, ownership.
Framing: "after an engineer changes important code, what happens to that area next?" **A health
signal, never personal blame.**

| Metric                     | Positive                             | Negative                                       | GitHub evidence                       |
| -------------------------- | ------------------------------------ | ---------------------------------------------- | ------------------------------------- |
| Stability after merge      | No quick corrective follow-up        | Same area gets bugfix/hotfix/revert soon after | PR file list, later PRs on same files |
| Corrective churn window    | No corrective change in 7/14/30 days | Later PR says fix/bug/regression/hotfix/revert | titles, labels, changed files         |
| Fix-forward impact         | Fixes bugs/regressions/flaky tests   | (positive credit only)                         | labels, titles, linked issues         |
| Durable simplification     | Simplification survives, built upon  | Removed logic quickly restored                 | later diffs, same-file history        |
| Fragile-area stabilization | Repeatedly stabilizes risky areas    | Creates repeated churn in fragile areas        | file history, labels, issue links     |
| Revert relationship        | No revert/rollback needed            | Direct revert soon after merge                 | revert PR title, linked refs          |
| Blame overlap confidence   | Weak/no overlap with later bugfix    | Later fix touches same blamed lines/function   | blame, diff, commit history           |

**Sub-scores:** No corrective churn 30% · Fix-forward 25% · Durable simplification 15% ·
Fragile-area stabilization 15% · Revert avoidance 10% · Blame-overlap confidence 5%.
**Confidence tiers for linking an original PR to a later fix:** Low = same file(s);
Medium = same file + bugfix language within 14–30d; High = references the PR / same function /
overlapping blamed lines; Very high = explicitly says it fixes a regression from that PR.
**Cautions:** same-file follow-up ≠ fault; high-risk areas churn more (reward stabilization);
reverts can be responsible release safety; blame is technically noisy.

## A.5 Dimension 3 — Requirement-Aligned Test Quality

**Definition:** tests tied to real behavior/requirements/bugfixes. Does **not** reward coverage by itself.

| Metric                           | Positive                                    | Negative                                   |
| -------------------------------- | ------------------------------------------- | ------------------------------------------ |
| Requirement linkage              | Test maps to linked issue/requirement       | Test doesn't validate requested behavior   |
| Regression coverage              | Bugfix PR includes regression test          | Bugfix has no/shallow test                 |
| Behavior-focused assertions      | Validates user-visible/domain behavior      | Only checks calls/snapshots without intent |
| Edge-case coverage               | Boundary/failure/permission/migration cases | Only happy path                            |
| Test naming quality              | Names describe expected behavior            | Vague names                                |
| Reviewer-driven test improvement | Reviewer asks, author adds                  | Asked but none added                       |

**Sub-scores:** Requirement linkage 25% · Regression coverage 25% · Behavior assertions 20% ·
Edge cases 15% · Naming 5% · Reviewer-driven 10%.
**Cautions:** more tests ≠ better; coverage can be gamed; reward snapshots only when they protect behavior.

## A.6 Dimension 4 — Simplicity, Readability & Design Quality

**Definition:** does the engineer make code easier to understand, modify, and maintain?

| Metric                  | Positive                              | Negative                                 |
| ----------------------- | ------------------------------------- | ---------------------------------------- |
| Safe code reduction     | Less code, same/better behavior       | Deletion with no explanation/test safety |
| Duplicate logic removal | Repeated paths → clear shared helper  | Over-abstraction that hurts              |
| Dead code cleanup       | Removes unused flags/obsolete APIs    | Removes active behavior accidentally     |
| Naming clarity          | Better variable/function/module names | Cosmetic renames with no value           |
| Simple control flow     | Less nesting, fewer special cases     | More nested branches                     |
| Design fit              | Uses established patterns             | Introduces unnecessary new patterns      |
| Useful comments         | Explain _why_/risk                    | Repeat obvious code                      |

**Sub-scores:** Safe reduction 20% · Duplicate removal 20% · Dead-code cleanup 15% ·
Naming/readability 15% · Simple control flow 15% · Design fit 10% · Useful comments 5%.
**Cautions:** simpler ≠ shorter; abstractions can help or hurt; renames can be noisy.

## A.7 Dimension 5 — Engineering Process Influence

**Definition:** meaningful non-code contributions that shape work before/during/after implementation.

| Metric                      | Positive                                         | Negative                             |
| --------------------------- | ------------------------------------------------ | ------------------------------------ |
| Substantive review comments | Identify bugs/risks/edge cases/better designs    | LGTM-only / shallow                  |
| Design input                | Suggests simpler/safer design that's adopted     | Vague opinion, no effect             |
| Edge-case detection         | Catches failure/permission/migration/scale cases | No specific technical content        |
| Test strategy influence     | Suggests specific tests that get added           | Generic "add tests"                  |
| Requirement clarification   | Clarifies expected behavior/constraints          | Adds confusion                       |
| Unblocking others           | Answers questions, provides context              | Comment volume with no useful action |

**Sub-scores:** Substantive comments 30% · Design input 20% · Edge-case detection 20% ·
Test strategy 15% · Clarification 10% · Unblocking 5%.
**Cautions:** score usefulness not volume; short comments can be valuable; long comments can be low value.

## A.8 Dimension 6 — Issue Discovery, Triage & Resolution

**Definition:** helping the team discover, understand, prioritize, route, and resolve problems.

| Metric                      | Positive                                  | Negative                        |
| --------------------------- | ----------------------------------------- | ------------------------------- |
| High-quality issue creation | Clear problem, repro, expected vs actual  | Vague, no useful detail         |
| Bug reproduction            | Adds repro/logs/screenshots/env           | No diagnostic progress          |
| Triage quality              | Correct labels/owner/priority/dup links   | Mislabels, stale, unclear owner |
| Issue→PR linkage            | Issue linked to fixing PR                 | Closed without explanation      |
| Resolution efficiency       | Quick useful response, linked PR, closure | Long delay, no action           |
| Reopen/recurrence           | Closed stays closed                       | Reopened/repeated soon after    |
| Cross-team coordination     | Links product/support/FE/BE/infra context | Siloed, missing context         |

**Sub-scores:** Issue creation 20% · Repro/diagnosis 20% · Triage 15% · Issue→PR 15% ·
Resolution efficiency 15% · Reopen handling 10% · Cross-team 5%.
**Cautions:** closing many issues ≠ impact; opener ≠ resolver (split credit); some issues are naturally long-running.

## A.9 Dimension 7 — Dependency & Duplication Hygiene

**Definition:** keeping the codebase lean — avoid unnecessary deps, remove unused packages, reduce duplication.

| Metric                         | Positive                                   | Negative                                        |
| ------------------------------ | ------------------------------------------ | ----------------------------------------------- |
| Dependency justification       | New dep solves a real, explained problem   | Adds package for trivial/existing functionality |
| Unused dependency removal      | Removes obsolete packages                  | Leaves unused deps                              |
| Overlapping library avoidance  | Uses existing project library              | Adds duplicate library                          |
| Duplicate logic reduction      | Consolidates duplication                   | Repeats similar functions                       |
| Security/maintenance awareness | Handles vulnerable/outdated deps carefully | Adds risky dep without explanation              |
| Lockfile discipline            | Lockfile matches dependency intent         | Huge lockfile churn w/o clear change            |

**Sub-scores:** Justification 20% · Unused removal 20% · Overlap avoidance 15% ·
Duplicate reduction 20% · Security awareness 15% · Lockfile discipline 10%.
**Cautions:** new deps aren't always bad; small duplication can beat a bad abstraction; security data only when available.

## A.10 Evidence model

Each metric must produce a small amount of **explainable evidence** — no mysterious scores.
Example dashboard lines: "Submitted 8 focused PRs with low noisy-churn and clear testing
notes." · "Only 1 of 9 merged PRs had likely corrective follow-up within 14 days." · "Fixed 3
bug/regression PRs in high-risk ingestion paths." · "Review comments led to added edge-case
tests in 4 PRs."

## A.11 Dashboard structure (one laptop screen)

**Header:** "Engineering Impact Dashboard — Reviewable Diffs & Post-Merge Code Health."
Subtitle: ranking by intentional PRs, post-merge stability, meaningful tests, simplicity, and
influence — _not_ raw code volume.
**Top-5 card:** rank · engineer · impact score (e.g. 86/100) · primary strength · 3–4 evidence
lines · score breakdown (e.g. Reviewability 29, Post-Merge 21, Tests 13, Simplicity 12, Other 11).
**Supporting table:** next engineers with per-dimension columns.

## A.12 Anti-patterns the dashboard must avoid

Ranking by **commits**, **lines of code**, **PR count**, **comment count**, or **coverage
alone**; using **git blame as personal blame**; **penalizing all large PRs**; **calling out AI
usage directly** (detect low-signal rewrites instead).

## A.13 Recommended focus for the take-home

Make **PR Reviewability**, **Developer Intent**, and **Post-Merge Health** the visible
differentiators (most dashboards ignore what happens after merge). Supporting dimensions
improve the ranking but stay out of the way. Top-5 cards explain the result in plain English.

> Positioning: this dashboard identifies engineers who don't just produce code, but produce
> changes that are reviewable, intentional, stable after merge, and helpful to the broader system.

---

---

# PART B — BUILD BRIEF (how to build it for real)

## B.1 Audience & format constraints

Audience: a **busy engineering leader** who won't read code or PR descriptions. Everything must
be understandable _at a glance_ and _validatable_. **Single page, fits one laptop screen, loads
< 10s.**

## B.2 Definition of done (this mirrors the grading rubric — optimize against it)

- [ ] Clearly answers "who are the 5 most impactful engineers, and why."
- [ ] **Every number drills down to the real PRs/reviews** behind it — no black-box scores.
- [ ] Real, **complete** data for **≥ 90 days**; bots excluded; data-freshness timestamp shown.
- [ ] **No fabricated or imputed dimensions** (see Part C).
- [ ] Methodology visible on the page.
- [ ] Loads < 10s, single page, no console errors, **deployed to a public URL**.

## B.3 Target & data reality

- **Repo:** `PostHog/posthog`. **Window:** rolling last 90 days (compute cutoff at runtime).
- **Volume:** ~**8,400 merged PRs / 90 days** — high. Design for scale, caching, rate limits
  from the start; a naïve per-PR REST loop will not finish.
- **Auth:** a read-only GitHub token is provided as `GITHUB_TOKEN`. **Use it** (5,000 REST/hr +
  GraphQL). Fail loudly if missing or under-scoped.

## B.4 Data collection (do this first; cache aggressively)

**Prefer GraphQL** — one query pulls a PR with everything: `author{login}`, `authorAssociation`,
`title`, `bodyText`, `labels`, `createdAt`, `mergedAt`, `additions`, `deletions`, `changedFiles`,
`files(first:100){path}`, `reviews(first:50){author{login} state}`, `reviewThreads{totalCount}`,
and `timelineItems(... CROSS_REFERENCED_EVENT ...)` for revert↔original links. Include
`rateLimit{remaining cost resetAt}` every query.
**Enumerate** via `repository.pullRequests(states:MERGED, orderBy:{field:CREATED_AT,
direction:DESC})` with cursors; stop when `createdAt < cutoff`. (Avoids the Search API's
1,000-result cap. If you must use Search, window by date.)
**Required robustness:**

- Honor `rateLimit`; sleep until `resetAt` when low; retry 403/429/5xx with exponential backoff.
- **Persist raw responses to `data/raw/` and treat fetch as a cache** — re-runs must not re-hit
  the API. Do this early; it lets you iterate on scoring/UI for free.
- **Exclude bots** (`*[bot]`, `dependabot`, `github-actions`, `renovate`, `posthog-bot`); flag
  team vs external via `authorAssociation` (MEMBER/OWNER/COLLABORATOR = team).
- Sanity-check the merged-PR count lands near ~8.4k.

## B.5 Operationalizing the dimensions (compute from real signals)

- **Reviewability/Intent (D1):** size (`additions+deletions`, `changedFiles`); **scope focus** =
  # distinct top-level dirs touched; has-description (`bodyText` length); conventional-commit-typed
  title. Use medians; reward _appropriate_ scope, don't blanket-penalize large PRs.
- **Post-Merge Health (D2):** **revert detection** — titles `Revert "...(#1234)"` / body
  `Reverts ...#1234` / timeline cross-refs → exact, high-confidence link. **Corrective churn** —
  later PRs touching same files within 7/14/30d with fix/bug/regression/hotfix titles →
  confidence-tiered (Part A.4). **Fix-forward credit** for shipping those fixes.
- **Process Influence (D5):** reviews _given_; `CHANGES_REQUESTED` that led to follow-up commits.
  Build the **reviewer→author directed graph**; compute weighted PageRank / in-degree to surface
  engineers central to review flow. A small network viz is a strong, non-obvious highlight.
- **Test Quality (D3):** detect test-file paths (`test`,`spec`,`__tests__`,`.test.`) co-occurring
  with bug/feature PRs; reward bugfixes that ship tests.
- **Simplicity (D4):** net-negative diffs that aren't reverts; dead-code/stale-flag removal.
- **Dependency hygiene (D7):** `package.json`/`requirements*`/lockfile changes; reward removals.
- **Breadth & consistency:** distinct areas (labels or top-level dirs) + active weeks.

## B.6 Scoring math

Within the cohort of **active** engineers (e.g. ≥ 3 merged PRs in window), **percentile-rank**
each dimension, weight-combine per A.2, scale to 0–100. **Always render sub-scores**, so "86" is
explained by its parts. Reward per-PR quality, not raw volume; show totals _and_ per-PR averages.

## B.7 Dashboard requirements

- **Precompute everything to a single `dashboard.json` at build time** → the page makes **zero**
  runtime API calls → instant load.
- **Top-5 cards** with auto-generated plain-English evidence (real data + PR links) and sub-score breakdown.
- **Drill-down:** clicking a score expands evidence + the math + links to actual PRs.
- **Methodology panel** + **honesty panel** ("what we measured / confidence levels / out of scope").
- Supporting table for the next ~10. Keep it light and fast.

## B.8 Structure, stack, build order

```
fetch.(py|ts)    # collect + cache raw PRs/reviews -> data/raw/   (idempotent, cached)
analyze.(py|ts)  # compute scores + evidence -> web/dashboard.json
web/             # single static page that reads dashboard.json
```

Stack: your choice, **minimal** — Python (raw GraphQL via `requests`) + a static frontend
(vanilla JS or small React/Vite; D3/Chart.js only for the network viz). **Build order — ship a
vertical slice first:** fetch (cached) → minimal scoring → bare top-5 page → **deploy** → _then_
enrich dimensions and polish. Don't gold-plate one dimension while others are missing.

## B.9 Hosting

Static site → **Vercel / Netlify / Cloudflare Pages / GitHub Pages**. If deploy creds exist, run
the deploy and print the public URL; otherwise output the exact deploy commands.

## B.10 Validation before "done"

Spot-check 2–3 engineers' evidence against the live GitHub UI so findings validate. Confirm:
< 10s load, no console errors, every score drills to real PRs, freshness timestamp present, bots excluded.

---

---

# PART C — FEASIBILITY MAP & INTEGRITY RULES

## C.1 What's computable (with the token) vs. out of scope

The model in Part A is the ideal. Real GitHub data makes most of it computable, but some signals
need code-level/semantic analysis that's slow or fuzzy. Build the **Strong** tier first; treat
**Best-effort** as optional polish; **never invent** the rest.

| Signal group                                                                            | Source                       | Feasibility                              |
| --------------------------------------------------------------------------------------- | ---------------------------- | ---------------------------------------- |
| Typed shipping (feat/fix/perf via titles+labels), breadth, consistency, cycle time      | search/metadata              | **Strong**                               |
| PR size, scope focus, has-description, changed-files                                    | GraphQL per-PR (token)       | **Strong**                               |
| Reviews given/received, states, **reviewer→author graph & centrality**                  | GraphQL reviews (token)      | **Strong**                               |
| **Revert detection + revert↔original link**                                             | titles/body/timeline         | **Strong** (exact)                       |
| Corrective churn (same-file fix within N days)                                          | files + later PRs (token)    | **Partial** (confidence-tiered)          |
| Test-file presence in bug/feature PRs                                                   | file paths (token)           | **Partial**                              |
| Dependency/lockfile changes                                                             | file paths (token)           | **Partial**                              |
| Review _friction_ / substantive comments                                                | review thread counts (token) | **Partial** (counts, not semantics)      |
| Issue triage/diagnosis quality, requirement clarification                               | issue comment text           | **Best-effort** (needs NLP/LLM judgment) |
| "Behavior-focused assertions", "useful comments", "AI-style rewrite", git-blame overlap | deep diff/blame analysis     | **Best-effort / likely skip in 1.5h**    |

## C.2 Integrity rules (non-negotiable — this is what wins the grade)

1. **Never fabricate, estimate, or impute a score.** If a signal can't be computed, show it as
   **"not measured"** and exclude it from the total. A visible gap beats an invented "Test Quality: 13."
2. **Every dashboard number must drill down to real PRs** (links to github.com).
3. **Use the confidence tiers** (A.4) for any inferred revert/fix linkage; show the tier in the UI.
4. **Post-merge "health" is a signal, not blame** — frame as "what happened to this area next."
5. **Normalize fairly** — reward per-PR quality, not raw volume; a high-volume account must not win automatically.
6. If a dimension ends up mostly **Best-effort/skipped**, **re-normalize the visible weights** and
   say so in the methodology panel, rather than padding with fake numbers.

---

# APPENDIX — SETUP CHECKLIST

## What YOU must provide

1. **GitHub token** → `.env` as `GITHUB_TOKEN`. A classic PAT with **`public_repo`** scope is
   enough (PostHog is public); a fine-grained token with read access to contents, pull requests,
   and issues also works. Read-only — no write scopes needed.
2. **(Optional) deploy credentials** if you want Claude Code to auto-deploy (e.g. `VERCEL_TOKEN`
   or `NETLIFY_AUTH_TOKEN`). Otherwise it will output manual deploy steps.
3. **Node 18+ and/or Python 3.11+** available in the environment (depending on the stack it picks).

## Recommended repo layout

```
project-root/
├─ CLAUDE.md           # you add — Claude Code reads this automatically
├─ .env                # you add — contains GITHUB_TOKEN (gitignored)
├─ .env.example        # provided
├─ .gitignore          # provided
└─ docs/
   ├─ PRD.md           # THIS document
   └─ assignment.md    # recommended: paste the original take-home text here
```

Claude Code will create `data/`, the fetch/analyze scripts, and `web/` itself.

## What to put in `docs/`

- **`PRD.md`** (this file) — the only spec it strictly needs; everything is inlined.
- **`assignment.md`** — _recommended_: paste the original take-home description (the rubric +
  red-flags list) so Claude Code optimizes against the real grading criteria.
- You do **not** need the separate parameters file anymore — its full content is inlined in Part A.
