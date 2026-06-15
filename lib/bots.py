"""Bot-account filtering and team/external classification."""

# Known automation accounts (lower-cased, without the [bot] suffix where applicable).
# NOTE: some automation registers as a GitHub `User` (e.g. greptile-apps had 4,690 reviews),
# so account-type filtering alone is insufficient -- this blocklist + the suffix patterns below
# catch app/AI accounts that the type filter misses.
KNOWN_BOTS = {
    # generic CI / dependency / housekeeping bots
    "dependabot", "dependabot-preview", "github-actions", "renovate",
    "renovate-bot", "posthog-bot", "posthog-contributions-bot", "snyk-bot",
    "codecov", "codecov-io", "greenkeeper", "sentry-io", "imgbot",
    "allcontributors", "pre-commit-ci", "mergify", "stale",
    # AI code-review / agent accounts that register as Users or Orgs
    "greptile-apps", "greptile", "coderabbitai", "coderabbit", "sourcery-ai",
    "sourcery", "codium-ai", "codiumai", "sweep-ai", "devin-ai-integration",
    "cursor", "graphite-app", "copilot-pull-request-reviewer",
    "chatgpt-codex-connector", "veria-ai", "hex-security-app", "inkeep",
    # PostHog-internal automation accounts
    "stamphog", "tests-posthog", "scheduled-actions-posthog",
    "clickhouse-sync-posthog", "posthog-js-upgrader",
}

# Login suffixes that indicate a GitHub App / service account, not a person.
BOT_SUFFIXES = ("[bot]", "-bot", "-app", "-apps")

TEAM_ASSOCIATIONS = {"MEMBER", "OWNER", "COLLABORATOR"}


def is_bot(login: str | None) -> bool:
    if not login:  # ghost / deleted author
        return True
    low = login.lower()
    if low in KNOWN_BOTS:
        return True
    return any(low.endswith(sfx) for sfx in BOT_SUFFIXES)


def is_team(association: str | None) -> bool:
    return (association or "").upper() in TEAM_ASSOCIATIONS
