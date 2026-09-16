"""No real credential may enter the repository.

Scans every git-tracked text file for credential shapes. Test fixtures need
realistic-looking tokens, so a match is allowed only when the value carries an
obvious fake marker — which also forces anyone adding a fixture to make it
obviously fake, rather than pasting something real "just for a minute".
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

PATTERNS = {
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
}

# A credential shape is tolerated only if the value itself says it is fake.
FAKE_MARKERS = ("test", "example", "fake", "placeholder", "dummy", "demo", "xxx", "your-", "redacted")

SKIP_SUFFIXES = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2"}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    return [REPO_ROOT / line for line in out.splitlines() if line]


def scannable() -> list[Path]:
    return [
        path
        for path in tracked_files()
        if path.is_file() and path.suffix.lower() not in SKIP_SUFFIXES and path.name != Path(__file__).name
    ]


def test_there_are_files_to_scan():
    assert len(scannable()) > 10, "scanner found almost nothing; it would pass vacuously"


def test_no_tracked_file_contains_credential_shaped_strings():
    """One test over every file, not one test per file: the suite total should count
    behaviours covered, not how many files the repo happens to have."""
    findings: list[str] = []
    for path in scannable():
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: nothing a credential would hide in as text

        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                value = match.group(0)
                if any(marker in value.lower() for marker in FAKE_MARKERS):
                    continue
                line = content[: match.start()].count("\n") + 1
                rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
                findings.append(f"{rel}:{line} looks like a {label}")

    assert not findings, (
        "Possible credentials committed:\n  "
        + "\n  ".join(findings)
        + f"\nIf a hit is a fixture, put an obvious marker ({', '.join(FAKE_MARKERS[:4])}) in the value. "
        "If it is real, rotate it now — git history keeps it even after you delete the line."
    )


@pytest.mark.parametrize(
    ("label", "sample"),
    [
        ("GitHub token", "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"),
        ("GitHub fine-grained token", "github_pat_" + "11ABCDEFG0" + "a" * 30),
        ("Telegram bot token", "123456789" + ":" + "AA" + "b" * 33),
        ("AWS access key", "AKIA" + "ABCDEFGHIJKLMNOP"),
        ("Slack token", "xoxb-" + "123456789012-abcdefghijkl"),
    ],
)
def test_patterns_detect_realistic_credentials(label, sample):
    """Without this, a regex that never matches anything would look like a clean repo."""
    assert PATTERNS[label].search(sample), f"{label} pattern failed to match a realistic value"
    assert not any(marker in sample.lower() for marker in FAKE_MARKERS), "sample would be excused as a fixture"


def test_env_file_is_ignored_and_untracked():
    tracked = {p.name for p in tracked_files()}
    assert ".env" not in tracked
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore


def test_env_example_carries_names_without_values():
    example = (REPO_ROOT / "projects" / "01-mcp-server" / ".env.example").read_text(encoding="utf-8")
    for line in example.splitlines():
        if line.startswith(("GITHUB_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")):
            assert line.split("=", 1)[1].strip() == "", f"{line.split('=')[0]} must ship empty"
