"""Load the cached raw PRs into a clean, in-window, human-only dataset.

Single source of truth shared by the Phase-1 report and Phase-2 analysis:
- dedupe by PR number
- keep mergedAt >= cutoff (the confirmed window basis)
- exclude any author whose GitHub account type is not 'User' (drops Organization
  and Bot accounts such as posthog, mendral-app, dependabot, renovate, ...)
"""
import json
from pathlib import Path

from .bots import is_bot
from .github import parse_iso

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PAGES = RAW / "pages"


def load_accounts() -> dict:
    p = RAW / "accounts.json"
    return json.loads(p.read_text()) if p.exists() else {}


def load_meta() -> dict:
    return json.loads((RAW / "meta.json").read_text())


def account_type(accounts, login) -> str:
    rec = accounts.get(login)
    if isinstance(rec, dict):
        return rec.get("type", "Unknown")
    return rec or "Unknown"        # tolerate older string-only cache


def is_human(login, accounts) -> bool:
    # Must be a GitHub `User` AND not match the automation blocklist/patterns -- some apps
    # (e.g. greptile-apps) register as Users and slip past the account-type check alone.
    return bool(login) and account_type(accounts, login) == "User" and not is_bot(login)


def is_posthog_company(accounts, login) -> bool:
    rec = accounts.get(login)
    company = (rec.get("company") if isinstance(rec, dict) else None) or ""
    return "posthog" in company.lower()


def load_prs(human_only: bool = True):
    """Return (prs, meta, accounts). prs are in-window merged PR node dicts."""
    meta = load_meta()
    cutoff = parse_iso(meta["cutoff"])
    accounts = load_accounts()

    by_num = {}
    for p in sorted(PAGES.glob("page_*.json")):
        for node in json.loads(p.read_text())["nodes"]:
            by_num[node["number"]] = node

    prs = []
    for node in by_num.values():
        merged = node.get("mergedAt")
        if not merged or parse_iso(merged) < cutoff:
            continue
        login = (node.get("author") or {}).get("login")
        if human_only and not is_human(login, accounts):
            continue
        prs.append(node)
    return prs, meta, accounts
