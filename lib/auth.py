"""GitHub token resolution.

Order: GITHUB_TOKEN env var first, else fall back to `gh auth token` (keyring).
The token is never printed, logged, or written to disk.
"""
import os
import subprocess


def get_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    try:
        out = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, check=True,
        )
        tok = out.stdout.strip()
        if tok:
            return tok
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    raise SystemExit(
        "No GitHub token available. Set GITHUB_TOKEN or run `gh auth login`."
    )
