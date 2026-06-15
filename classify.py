#!/usr/bin/env python3
"""Phase 1b — classify every distinct author/reviewer login by GitHub account type.

GraphQL `Bot` authors and `Organization` accounts (e.g. `posthog`, `mendral-app`) are
not human engineers and must be excluded. Login-pattern matching is insufficient, so we
look up each account's real type (User / Organization / Bot) via the REST API and cache
it to data/raw/accounts.json (idempotent — only fetches logins not already cached).
"""
import json
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.auth import get_token

ROOT = Path(__file__).resolve().parent
PAGES_DIR = ROOT / "data" / "raw" / "pages"
ACCOUNTS_PATH = ROOT / "data" / "raw" / "accounts.json"


def collect_logins() -> set[str]:
    logins: set[str] = set()
    for p in sorted(PAGES_DIR.glob("page_*.json")):
        for node in json.loads(p.read_text())["nodes"]:
            a = (node.get("author") or {}).get("login")
            if a:
                logins.add(a)
            for r in (node.get("reviews") or {}).get("nodes", []):
                ra = (r.get("author") or {}).get("login")
                if ra:
                    logins.add(ra)
    return logins


def fetch_account(session, token, login) -> dict:
    """Return {type, name, company, avatar} for a login (type Unknown if 404)."""
    delay = 2.0
    for _ in range(5):
        try:
            r = session.get(
                f"https://api.github.com/users/{login}",
                headers={"Authorization": f"bearer {token}",
                         "User-Agent": "blameless-impact-dashboard",
                         "Accept": "application/vnd.github+json"},
                timeout=60,
            )
        except requests.exceptions.RequestException:
            time.sleep(delay + random.uniform(0, 1)); delay = min(delay * 2, 60); continue
        if r.status_code == 404:
            return {"type": "Unknown", "name": None, "company": None, "avatar": None}
        if r.status_code in (403, 429) or r.status_code >= 500:
            ra = r.headers.get("Retry-After")
            time.sleep((float(ra) if ra else delay) + random.uniform(0, 1))
            delay = min(delay * 2, 60); continue
        if r.ok:
            j = r.json()
            return {"type": j.get("type", "Unknown"), "name": j.get("name"),
                    "company": j.get("company"), "avatar": j.get("avatar_url")}
    return {"type": "Unknown", "name": None, "company": None, "avatar": None}


def main():
    accounts = {}
    if ACCOUNTS_PATH.exists():
        accounts = json.loads(ACCOUNTS_PATH.read_text())

    logins = collect_logins()
    # re-fetch any login not yet stored as a full dict (handles older string-only cache)
    todo = sorted(l for l in logins if not isinstance(accounts.get(l), dict))
    print(f"Distinct logins: {len(logins)} | already cached: {len(logins) - len(todo)} | "
          f"to fetch: {len(todo)}")

    token = get_token()
    session = requests.Session()
    for i, login in enumerate(todo, 1):
        accounts[login] = fetch_account(session, token, login)
        if i % 50 == 0 or i == len(todo):
            ACCOUNTS_PATH.write_text(json.dumps(accounts, indent=2, sort_keys=True))
            print(f"  classified {i}/{len(todo)}")
    ACCOUNTS_PATH.write_text(json.dumps(accounts, indent=2, sort_keys=True))

    by_type = {}
    for v in accounts.values():
        t = v.get("type", "Unknown")
        by_type[t] = by_type.get(t, 0) + 1
    print(f"\nAccount types: {by_type}")
    non_user = sorted(l for l, v in accounts.items() if v.get("type") != "User")
    print(f"Non-User accounts excluded ({len(non_user)}): {', '.join(non_user)}")


if __name__ == "__main__":
    main()
