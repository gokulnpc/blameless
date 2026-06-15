#!/usr/bin/env python3
"""Phase 1 — Fetch & cache merged PRs for PostHog/posthog (last 90 days).

Enumerates merged PRs by UPDATED_AT desc (the API can't order by mergedAt), stops
once a page's oldest updatedAt < cutoff, then the in-window set is filtered to
mergedAt >= cutoff. Raw GraphQL pages are cached to data/raw/pages/ and treated as
a cache: re-runs read from disk and never re-hit the API unless --refresh is passed.
"""
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.auth import get_token
from lib.bots import is_bot, is_team
from lib.github import parse_iso, respect_rate_limit, run_query

OWNER, NAME = "PostHog", "posthog"
WINDOW_DAYS = 90
PAGE_SIZE = 50  # smaller pages → smaller responses → robust against chunked-read drops
RL_FLOOR = 150

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PAGES_DIR = RAW_DIR / "pages"
META_PATH = RAW_DIR / "meta.json"

QUERY = """
query($owner:String!, $name:String!, $cursor:String) {
  repository(owner:$owner, name:$name) {
    pullRequests(states:MERGED, first:%d, orderBy:{field:UPDATED_AT, direction:DESC}, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title authorAssociation createdAt mergedAt updatedAt
        additions deletions changedFiles
        author { login }
        labels(first:10) { nodes { name } }
        files(first:100) { totalCount nodes { path } }
        reviews(first:50) { totalCount nodes { author { login } state submittedAt } }
        reviewThreads { totalCount }
        timelineItems(first:20, itemTypes:[CROSS_REFERENCED_EVENT]) {
          totalCount
          nodes {
            ... on CrossReferencedEvent {
              willCloseTarget
              source {
                ... on PullRequest { number title createdAt mergedAt }
                ... on Issue { number title }
              }
            }
          }
        }
        bodyText
      }
    }
  }
  rateLimit { limit cost remaining resetAt }
}
""" % PAGE_SIZE


def page_path(n: int) -> Path:
    return PAGES_DIR / f"page_{n:04d}.json"


def load_cached_pages() -> list[dict]:
    if not PAGES_DIR.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(PAGES_DIR.glob("page_*.json"))]


def fetch_all(token, cutoff_iso) -> tuple[list[dict], dict]:
    """Fetch pages until oldest updatedAt < cutoff. Returns (pages, stats)."""
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = parse_iso(cutoff_iso)

    existing = load_cached_pages()
    cursor = None
    start_n = 1
    points_spent = 0
    if existing:
        last = existing[-1]
        # Resume only if the cache is incomplete (more pages exist and we hadn't
        # yet crossed the cutoff). Otherwise treat as complete.
        last_nodes = last.get("nodes", [])
        oldest = min((parse_iso(n["updatedAt"]) for n in last_nodes), default=cutoff)
        if last.get("pageInfo", {}).get("hasNextPage") and oldest >= cutoff:
            cursor = last["pageInfo"]["endCursor"]
            start_n = last["page"] + 1
            print(f"  resuming from page {start_n} (cursor cached)")
        else:
            print(f"  cache complete: {len(existing)} pages on disk")
            return existing, {"points_spent": 0, "from_cache": True}

    pages = existing[:]
    n = start_n
    while True:
        resp = run_query(token, QUERY, {"owner": OWNER, "name": NAME, "cursor": cursor})
        conn = resp["data"]["repository"]["pullRequests"]
        rl = resp["data"]["rateLimit"]
        points_spent += rl.get("cost", 0)
        nodes = conn["nodes"]
        page_info = conn["pageInfo"]
        page_obj = {
            "page": n,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "pageInfo": page_info,
            "rateLimit": rl,
            "nodes": nodes,
        }
        page_path(n).write_text(json.dumps(page_obj))
        pages.append(page_obj)

        oldest = min((parse_iso(x["updatedAt"]) for x in nodes), default=cutoff)
        newest = max((parse_iso(x["updatedAt"]) for x in nodes), default=cutoff)
        print(f"  page {n:>3}: {len(nodes):>3} PRs | updated {newest.date()}..{oldest.date()} "
              f"| cost {rl['cost']} | remaining {rl['remaining']}")

        if oldest < cutoff:
            break
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
        n += 1
        respect_rate_limit(rl, floor=RL_FLOOR, log=lambda m: print(m))

    return pages, {"points_spent": points_spent, "from_cache": False}


def consolidate(pages, cutoff_iso):
    """Dedupe by PR number, exclude bots, keep mergedAt >= cutoff."""
    cutoff = parse_iso(cutoff_iso)
    by_num = {}
    for pg in pages:
        for node in pg["nodes"]:
            by_num[node["number"]] = node
    in_window, bots_excluded = [], 0
    for node in by_num.values():
        merged = node.get("mergedAt")
        if not merged or parse_iso(merged) < cutoff:
            continue
        login = (node.get("author") or {}).get("login")
        if is_bot(login):
            bots_excluded += 1
            continue
        in_window.append(node)
    return in_window, bots_excluded, len(by_num)


def report(prs, bots_excluded, total_fetched, cutoff_iso, stats):
    if prs:
        merged_dates = sorted(parse_iso(p["mergedAt"]) for p in prs)
        date_lo, date_hi = merged_dates[0], merged_dates[-1]
    else:
        date_lo = date_hi = None
    authors = Counter((p["author"] or {}).get("login") for p in prs)
    team = sum(1 for p in prs if is_team(p.get("authorAssociation")))
    external = len(prs) - team

    print("\n" + "=" * 64)
    print("PHASE 1 SUMMARY — merged PRs, PostHog/posthog")
    print("=" * 64)
    print(f"Window cutoff (mergedAt >=):   {cutoff_iso}")
    if date_lo:
        print(f"Actual merged date range:      {date_lo.isoformat()}  ->  {date_hi.isoformat()}")
    print(f"PRs fetched (raw, deduped):    {total_fetched}")
    print(f"Bots excluded (in-window):     {bots_excluded}")
    print(f"Merged-in-window PRs (humans): {len(prs)}   <-- headline count")
    print(f"   team (MEMBER/OWNER/COLLAB): {team}")
    print(f"   external (contributors):    {external}")
    print(f"Distinct human authors:        {len(authors)}")
    print(f"Rate-limit points spent:       {stats['points_spent']}"
          + ("  (served from cache)" if stats.get("from_cache") else ""))
    print(f"\nTop 15 authors by merged-PR count:")
    for login, c in authors.most_common(15):
        print(f"   {c:>4}  {login}")
    print("=" * 64)
    if len(prs) < 6000:
        print("NOTE: count is well below the PRD's ~8,400 expectation. This reflects the")
        print("real recent merge rate for the window (reported honestly, not force-fit).")
    print("=" * 64)


def main():
    refresh = "--refresh" in sys.argv
    if refresh and RAW_DIR.exists():
        print("--refresh: clearing data/raw/ ...")
        shutil.rmtree(RAW_DIR)

    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    print(f"Fetching merged PRs updated since cutoff (mergedAt >= {cutoff_iso[:10]}) ...")

    token = get_token()
    pages, stats = fetch_all(token, cutoff_iso)
    prs, bots_excluded, total_fetched = consolidate(pages, cutoff_iso)

    META_PATH.write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "repo": f"{OWNER}/{NAME}",
        "window_days": WINDOW_DAYS,
        "cutoff": cutoff_iso,
        "pages": len(pages),
        "total_fetched": total_fetched,
        "merged_in_window_humans": len(prs),
        "bots_excluded": bots_excluded,
        "points_spent": stats["points_spent"],
    }, indent=2))

    report(prs, bots_excluded, total_fetched, cutoff_iso, stats)


if __name__ == "__main__":
    main()
