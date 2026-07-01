#!/usr/bin/env python3
"""Small staged-file secret scanner used by the local pre-commit hook."""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_TEXT_BYTES = 2_000_000

ALLOWLIST_COMMENT_RE = re.compile(
    r"(?i)(allowlist secret|pragma:\s*allowlist secret|gitleaks:allow|secret_scan:ignore)"
)

SPECIFIC_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
        "possible Telegram bot token",
    ),
    (
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
        "possible OpenAI API key",
    ),
    (
        re.compile(r"\bsk-ant-api[0-9A-Za-z_-]{20,}\b"),
        "possible Anthropic API key",
    ),
    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b"),
        "possible GitHub token",
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "possible AWS access key id",
    ),
    (
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "possible Google API key",
    ),
    (
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
        "possible Slack token",
    ),
    (
        re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{24,}\b"),
        "possible Stripe secret key",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "possible JWT",
    ),
    (
        re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
        "private key material",
    ),
    (
        re.compile(r"(?i)\bpostgres(?:ql)?(?:\+asyncpg)?://[^:\s/@]+:[^@\s]+@"),
        "database URL with inline password",
    ),
)

SECRET_ASSIGNMENT_RE = re.compile(
    r"""
    (?P<name>
        [A-Z0-9_.-]*
        (?:
            API[_-]?KEY
            | ACCESS[_-]?KEY
            | APP[_-]?HMAC[_-]?SECRET
            | LLM[_-]?API[_-]?KEY
            | PASSWORD
            | PASSWD
            | PRIVATE[_-]?KEY
            | POSTGRES[_-]?PASSWORD
            | SECRET
            | TELEGRAM[_-]?TOKEN
            | TOKEN(?!S)
            | TURNSTILE[_-]?SECRET
            | WEB[_-]?SESSION[_-]?SECRET
        )
        [A-Z0-9_.-]*
    )
    \s*[:=]\s*
    (?P<quote>["']?)
    (?P<value>[^\s"',#]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

PLACEHOLDER_WORDS = (
    "change-me",
    "changeme",
    "development",
    "dummy",
    "example",
    "fake",
    "fixture",
    "local",
    "mock",
    "placeholder",
    "replace",
    "sample",
    "test",
    "todo",
    "user:pass",
    "your-",
    "your_",
)

PLACEHOLDER_VALUES = {
    "",
    "0",
    "1",
    "false",
    "none",
    "null",
    "true",
    "xxx",
    "xxxx",
}

TEMPLATE_MARKERS = ("$", "<", ">", "{", "}", "(", ")", "[", "]", "*")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan staged or tracked files for leaked secrets.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="scan staged files from the Git index")
    mode.add_argument("--all", action="store_true", help="scan all tracked files from the worktree")
    args = parser.parse_args()

    try:
        repo_root = get_repo_root()
        files = staged_paths() if args.staged or not args.all else tracked_paths()
        if not files:
            print("avvalo secret scan: no files to scan")
            return 0

        findings: list[Finding] = []
        for path in files:
            findings.extend(path_findings(path))
            data = (
                read_staged_file(path)
                if args.staged or not args.all
                else read_worktree_file(repo_root, path)
            )
            if data is None or is_binary(data):
                continue
            findings.extend(scan_text(path, decode_text(data)))
    except SecretScanError as exc:
        print(f"avvalo secret scan failed: {exc}", file=sys.stderr)
        return 1

    if findings:
        print("avvalo secret scan blocked this commit:")
        for finding in findings:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            print(f"  - {location}: {finding.reason}")
        print()
        print(
            "Remove the secret, replace it with a placeholder, "
            "or keep runtime secrets out of Git."
        )
        print("For a verified false positive only, add 'secret_scan:ignore' on that line.")
        return 1

    print(f"avvalo secret scan: checked {len(files)} file(s), no secrets found")
    return 0


def get_repo_root() -> Path:
    result = git(["rev-parse", "--show-toplevel"])
    return Path(result.stdout.decode("utf-8", errors="replace").strip())


def staged_paths() -> list[str]:
    result = git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    return split_nul_paths(result.stdout)


def tracked_paths() -> list[str]:
    result = git(["ls-files", "-z"])
    return split_nul_paths(result.stdout)


def split_nul_paths(data: bytes) -> list[str]:
    return [path.decode("utf-8", errors="replace") for path in data.split(b"\0") if path]


def read_staged_file(path: str) -> bytes | None:
    result = git(["show", f":{path}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout[:MAX_TEXT_BYTES]


def read_worktree_file(repo_root: Path, path: str) -> bytes | None:
    file_path = repo_root / Path(path)
    if not file_path.is_file():
        return None
    try:
        return file_path.read_bytes()[:MAX_TEXT_BYTES]
    except OSError as exc:
        raise SecretScanError(f"cannot read {path}: {exc}") from exc


def git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["git", *args], check=False, capture_output=True)
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise SecretScanError(message or f"git {' '.join(args)} failed")
    return result


def path_findings(path: str) -> list[Finding]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = PurePosixPath(lower).name
    findings: list[Finding] = []

    if is_runtime_env_file(lower):
        findings.append(Finding(path, 0, "runtime .env file must not be committed"))

    if lower.startswith("secrets/") and name not in {".gitkeep", "readme.md"}:
        findings.append(Finding(path, 0, "files under secrets/ must not be committed"))

    if is_private_key_path(lower):
        findings.append(Finding(path, 0, "private key or certificate bundle path"))

    if is_service_account_path(lower):
        findings.append(Finding(path, 0, "service account JSON must not be committed"))

    return findings


def is_runtime_env_file(lower_path: str) -> bool:
    name = PurePosixPath(lower_path).name
    if not name.startswith(".env"):
        return False
    return not name.endswith((".example", ".sample", ".template"))


def is_private_key_path(lower_path: str) -> bool:
    name = PurePosixPath(lower_path).name
    if "example" in lower_path or "sample" in lower_path or "public" in lower_path:
        return False
    return name in {"id_rsa", "id_ed25519", "id_ecdsa"} or lower_path.endswith(
        (".pem", ".p12", ".pfx", ".key")
    )


def is_service_account_path(lower_path: str) -> bool:
    name = PurePosixPath(lower_path).name
    if "example" in lower_path or "sample" in lower_path:
        return False
    return name in {"gcv.json", "service-account.json"} or (
        name.endswith(".json") and "service-account" in name
    )


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:4096]


def decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ALLOWLIST_COMMENT_RE.search(line):
            continue

        for pattern, reason in SPECIFIC_SECRET_PATTERNS:
            if pattern.search(line) and not line_looks_like_placeholder(line):
                findings.append(Finding(path, line_number, reason))
                break

        assignment = SECRET_ASSIGNMENT_RE.search(line)
        if assignment and value_looks_secret(assignment.group("value")):
            name = assignment.group("name")
            findings.append(
                Finding(path, line_number, f"secret-looking value assigned to {name}")
            )

    return findings


def line_looks_like_placeholder(line: str) -> bool:
    lowered = line.lower()
    if "${" in line or "$(" in line:
        return True
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def value_looks_secret(value: str) -> bool:
    cleaned = value.strip().strip(",;")
    lowered = cleaned.lower()

    if lowered in PLACEHOLDER_VALUES:
        return False
    if any(marker in cleaned for marker in TEMPLATE_MARKERS):
        return False
    if any(word in lowered for word in PLACEHOLDER_WORDS):
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", cleaned):
        return False
    if cleaned.startswith(("/", "./", "../")):
        return False
    if len(cleaned) < 12:
        return False

    has_alpha = any(char.isalpha() for char in cleaned)
    has_digit = any(char.isdigit() for char in cleaned)
    has_secret_punctuation = any(char in cleaned for char in "_-.:/+=~")

    if len(cleaned) >= 24 and has_alpha and (has_digit or has_secret_punctuation):
        return True

    return len(cleaned) >= 16 and entropy(cleaned) >= 3.2 and has_alpha


def entropy(value: str) -> float:
    if not value:
        return 0.0
    return -sum(
        (value.count(char) / len(value)) * math.log2(value.count(char) / len(value))
        for char in set(value)
    )


class SecretScanError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
