# CLAUDE.md — BlameLess Engineering Impact Dashboard

**Read `docs/PRD.md` first — it is the authoritative spec.** This file is a short pointer.

## Goal

Identify the **top 5 most impactful engineers** on `PostHog/posthog` over the **last 90+ days**
and present _why_ on a **single, fast (<10s), fully auditable** page. Impact is NOT lines of
code / commit count / PR count — see the model in `docs/PRD.md` Part A.

## Hard rules (do not break)

- **No fabricated numbers.** If a signal can't be computed from real data, show "not measured"
  and exclude it from the score. Every number must drill down to real PRs.
- Single page, fits one laptop screen, loads < 10s, deployed to a public URL.
- Exclude bot accounts; show a data-freshness timestamp.

## Workflow (follow this order)

1. **Fetch & cache first.** Pull merged PRs (+ reviews/files) for the last 90 days via the
   **GraphQL API** using `GITHUB_TOKEN`. Persist raw responses to `data/raw/` and treat it as a
   cache — never re-fetch if the cache exists. Confirm the merged-PR count lands near ~8,400,
   then stop and report before analyzing.
2. **Analyze** → compute scores + plain-English evidence → write `web/dashboard.json`.
3. **Build** the static `web/` page that reads `dashboard.json` (zero runtime API calls).
4. **Deploy** to a public URL; print it. (Or output exact deploy steps.)
5. **Validate** 2–3 engineers' evidence against the live GitHub UI.

## Environment

- `GITHUB_TOKEN` — read-only PAT (see `.env`). **Never print or commit it.**
- Optional deploy creds (`VERCEL_TOKEN` / `NETLIFY_AUTH_TOKEN`).

## Constraints

- Keep the stack minimal (Python + raw GraphQL for the pipeline; light static frontend).
- Ship a working vertical slice (fetch→score→bare top-5→deploy) BEFORE enriching dimensions.
- Respect GitHub rate limits (watch `rateLimit.remaining`/`resetAt`; backoff on 403/429/5xx).
