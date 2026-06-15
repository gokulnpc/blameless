"""Minimal GitHub GraphQL client (via requests) with rate-limit awareness + backoff."""
import random
import time
from datetime import datetime, timezone

import requests

GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "blameless-impact-dashboard"

_session = requests.Session()


class GraphQLError(Exception):
    pass


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _is_transient_gql(errs) -> bool:
    for err in errs:
        msg = (err.get("message", "") or "").lower()
        if err.get("type") == "RATE_LIMITED" or "timeout" in msg or "secondary rate limit" in msg:
            return True
    return False


def run_query(token: str, query: str, variables: dict, max_retries: int = 8) -> dict:
    """Execute a GraphQL query, retrying transient failures (403/429/5xx/network/chunked)."""
    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    payload = {"query": query, "variables": variables}
    delay = 2.0
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = _session.post(GRAPHQL_URL, json=payload, headers=headers, timeout=120)
        except requests.exceptions.RequestException as e:
            # Covers ChunkedEncodingError (IncompleteRead), ConnectionError, Timeout, etc.
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(delay + random.uniform(0, 1.0))
            delay = min(delay * 2, 120)
            continue

        if resp.status_code in (403, 429) or 500 <= resp.status_code < 600:
            last_err = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("Retry-After")
            sleep_s = float(retry_after) if retry_after else delay
            time.sleep(sleep_s + random.uniform(0, 1.0))
            delay = min(delay * 2, 120)
            continue
        if resp.status_code >= 400:
            raise GraphQLError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
        except ValueError as e:
            last_err = f"JSON decode: {e}"
            time.sleep(delay + random.uniform(0, 1.0))
            delay = min(delay * 2, 120)
            continue

        if data.get("errors"):
            errs = data["errors"]
            if _is_transient_gql(errs) and attempt < max_retries - 1:
                time.sleep(delay + random.uniform(0, 1.0))
                delay = min(delay * 2, 120)
                continue
            raise GraphQLError(__import__("json").dumps(errs)[:600])
        return data

    raise GraphQLError(f"max retries exceeded (last error: {last_err})")


def respect_rate_limit(rate_limit: dict, floor: int = 150, log=print) -> None:
    """Sleep until resetAt if remaining points are below floor."""
    if not rate_limit:
        return
    remaining = rate_limit.get("remaining")
    reset_at = rate_limit.get("resetAt")
    if remaining is None or remaining >= floor or not reset_at:
        return
    reset_dt = parse_iso(reset_at)
    now = datetime.now(timezone.utc)
    sleep_s = max(0, (reset_dt - now).total_seconds()) + 2
    log(f"  rate limit low ({remaining}); sleeping {int(sleep_s)}s until {reset_at}")
    time.sleep(sleep_s)
