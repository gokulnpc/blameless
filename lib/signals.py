"""Deterministic signal detectors over PR metadata (titles, bodies, labels, file paths).

Every detector is a pure function of real PR data. Nothing here invents values.
"""
import re

# --- File-path classification -------------------------------------------------
_TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|specs?|e2e|cypress|playwright)(/|$)"
    r"|(^|/)test_[^/]*\.py$"
    r"|_test\.(py|go|ts|tsx|js|jsx)$"
    r"|\.(test|spec)\.(ts|tsx|js|jsx|py)$",
    re.IGNORECASE,
)
_DEP_FILE = re.compile(
    r"(^|/)(package\.json|package-lock\.json|yarn\.lock|pnpm-lock\.yaml"
    r"|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|Pipfile(\.lock)?"
    r"|go\.mod|go\.sum|Cargo\.(toml|lock))$",
    re.IGNORECASE,
)


def is_test_path(path: str) -> bool:
    return bool(_TEST_PATH.search(path or ""))


def is_dep_path(path: str) -> bool:
    return bool(_DEP_FILE.search(path or ""))


def top_level_dir(path: str) -> str:
    parts = (path or "").split("/")
    return parts[0] if len(parts) > 1 else "(root)"


# --- Title / body classification ----------------------------------------------
_CONV = re.compile(r"^([a-zA-Z]+)(\([^)]*\))?(!)?:\s")
_REVERT_TITLE = re.compile(r"^\s*revert\b", re.IGNORECASE)
_BUGWORD = re.compile(r"\b(bug|bugfix|hotfix|regression|regress|flaky|broken|crash|hotpatch)\b",
                      re.IGNORECASE)
_LINK = re.compile(r"\b(fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)",
                   re.IGNORECASE)
_HASHREF = re.compile(r"#(\d+)")
_REVERT_REF = re.compile(r"revert(?:s|ed)?\b[^\n]*?#(\d+)|this reverts[^\n]*?#(\d+)", re.IGNORECASE)


def conventional_type(title: str):
    m = _CONV.match(title or "")
    return m.group(1).lower() if m else None


def has_conventional_title(title: str) -> bool:
    return conventional_type(title) is not None


def label_names(pr) -> list[str]:
    return [n["name"].lower() for n in ((pr.get("labels") or {}).get("nodes") or [])]


def is_bugfix(pr) -> bool:
    """True if the PR is a bug/regression/hotfix (conventional type, keywords, or label)."""
    title = pr.get("title", "") or ""
    ctype = conventional_type(title)
    if ctype in {"fix", "bugfix", "hotfix", "revert"}:
        return True
    if _BUGWORD.search(title):
        return True
    labs = label_names(pr)
    return any("bug" in l or "regression" in l or "hotfix" in l for l in labs)


def is_revert_pr(pr) -> bool:
    return bool(_REVERT_TITLE.match(pr.get("title", "") or ""))


def revert_target(pr):
    """For a revert PR, the PR number it reverts (from title `(#N)` or body `Reverts #N`)."""
    title = pr.get("title", "") or ""
    body = pr.get("bodyText", "") or ""
    m = _REVERT_REF.search(body) or _REVERT_REF.search(title)
    if m:
        return int(next(g for g in m.groups() if g))
    # GitHub auto-revert title: Revert "... (#1234)"
    nums = _HASHREF.findall(title)
    if nums:
        return int(nums[-1])
    return None


def references(pr) -> set[int]:
    """All PR/issue numbers this PR references (title + body + timeline cross-refs)."""
    refs = set()
    for txt in (pr.get("title", ""), pr.get("bodyText", "")):
        refs.update(int(n) for n in _HASHREF.findall(txt or ""))
    for item in ((pr.get("timelineItems") or {}).get("nodes") or []):
        src = item.get("source") or {}
        if src.get("number"):
            refs.add(int(src["number"]))
    return refs


def requirement_linked(pr) -> bool:
    """Issue/PR linkage: the body references a tracked item (#N).

    PostHog rarely uses the 'fixes/closes #N' keyword form (~1% of PRs), but ~23% of
    PRs reference a tracked issue/PR via #N, which is the real discriminating signal.
    """
    return bool(_HASHREF.search(pr.get("bodyText", "") or ""))


def closes_issue(pr) -> bool:
    """Stronger form: body explicitly says fix/close/resolve #N."""
    return bool(_LINK.search(pr.get("bodyText", "") or ""))


def files_of(pr) -> list[str]:
    return [f["path"] for f in ((pr.get("files") or {}).get("nodes") or [])]
