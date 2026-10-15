#!/usr/bin/env python3
"""Check Git-bound files for local artifacts and likely credentials.

This is a small guardrail, not a replacement for reviewing a commit or for a
dedicated secret scanner. Findings print locations only, never secret values.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

BLOCKED_PARTS = {
    ".aws",
    ".idea",
    ".kube",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    ".venv",
    "__pycache__",
    "reports",
}
BLOCKED_SUFFIXES = {
    ".db",
    ".key",
    ".log",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".tfstate",
}
SECRET_PATTERNS = {
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "AWS access key ID": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "kubeconfig client key": re.compile(r"client-key-data:\s*[A-Za-z0-9+/=]{40,}"),
}
ASSIGNED_SECRET = re.compile(
    r"(?i)\b(?:password|secret|token|api[_-]?key|access[_-]?key)\b"
    r"\s*[=:]\s*['\"]?([A-Za-z0-9_!@#$%^&*+/=-]{16,})"
)
CREDENTIAL_URL = re.compile(
    r"(?:postgres(?:ql)?(?:\+asyncpg)?|redis|rediss|amqp|mongodb(?:\+srv)?)"
    r"://[^\s/:@]+:([^\s@]+)@"
)
PLACEHOLDER_PREFIXES = (
    "changeme",
    "dummy",
    "example",
    "generated",
    "load-test",
    "placeholder",
    "test",
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def path_issue(path: str) -> str | None:
    item = PurePosixPath(path)
    name = item.name.lower()
    if any(part in BLOCKED_PARTS for part in item.parts):
        return "local or generated directory"
    if name == ".ds_store" or name.startswith(".env") and name != ".env.example":
        return "local or environment file"
    if name in {"id_rsa", "id_ed25519", "kubeconfig"}:
        return "credential file"
    if item.suffix.lower() in BLOCKED_SUFFIXES or name.endswith(".tfvars"):
        return "credential, state, log, or database file"
    if (
        path.startswith("deploy/charts/")
        and "/charts/" in path
        and name.endswith(".tgz")
    ):
        return "generated Helm chart archive"
    return None


def content_issues(data: bytes) -> list[tuple[int, str]]:
    if b"\0" in data:
        return []
    issues: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        data.decode("utf-8", errors="replace").splitlines(), 1
    ):
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                issues.append((line_number, label))
        for match in ASSIGNED_SECRET.finditer(line):
            value = match.group(1).lower()
            if not value.startswith(PLACEHOLDER_PREFIXES):
                issues.append((line_number, "possible hard-coded secret"))
        for match in CREDENTIAL_URL.finditer(line):
            value = match.group(1).lower()
            if not value.startswith(("<", "${", "$", *PLACEHOLDER_PREFIXES)):
                issues.append((line_number, "credential in connection URL"))
    return issues


def staged_files() -> list[tuple[str, bytes]]:
    paths = git("ls-files", "--cached", "-z").split(b"\0")
    return [
        (decode_path(raw), git("show", ":" + decode_path(raw))) for raw in paths if raw
    ]


def working_files() -> list[tuple[str, bytes]]:
    from pathlib import Path

    paths = set(
        git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    )
    files = []
    for raw in sorted(paths):
        if not raw:
            continue
        path = decode_path(raw)
        file = Path(path)
        if file.is_file() and not file.is_symlink():
            files.append((path, file.read_bytes()))
    return files


def pushed_files() -> list[tuple[str, bytes]]:
    commits: set[str] = set()
    received_ref = False
    for line in sys.stdin:
        received_ref = True
        fields = line.split()
        if len(fields) != 4 or set(fields[1]) == {"0"}:
            continue
        commits.update(git("rev-list", fields[1]).decode().splitlines())
    if not commits and not received_ref:
        try:
            commits.update(git("rev-list", "HEAD").decode().splitlines())
        except subprocess.CalledProcessError:
            return []

    blobs: dict[tuple[str, str], bytes] = {}
    for commit in commits:
        for raw in git("ls-tree", "-r", "-z", commit).split(b"\0"):
            if not raw:
                continue
            metadata, raw_path = raw.split(b"\t", 1)
            _, kind, object_id = metadata.split()
            if kind != b"blob":
                continue
            path = decode_path(raw_path)
            key = (path, object_id.decode())
            if key not in blobs:
                blobs[key] = git("cat-file", "blob", key[1])
    return [(path, data) for (path, _), data in blobs.items()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--working-tree", action="store_true")
    mode.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()

    files = (
        staged_files()
        if args.staged
        else working_files()
        if args.working_tree
        else pushed_files()
    )
    found = False
    for path, data in files:
        issue = path_issue(path)
        if issue:
            print(f"{path}: {issue}", file=sys.stderr)
            found = True
        for line_number, label in content_issues(data):
            print(f"{path}:{line_number}: {label}", file=sys.stderr)
            found = True
    if found:
        print(
            "Git content check failed. Review these files before committing "
            "or pushing.",
            file=sys.stderr,
        )
        return 1
    print(f"Git content check passed ({len(files)} file versions scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
