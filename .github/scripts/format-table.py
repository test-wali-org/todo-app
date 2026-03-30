#!/usr/bin/env python3
"""
Parse TruffleHog NDJSON output and write a markdown findings table with GitHub links.

Usage:
  python3 format-table.py <input.ndjson> [output.md]

Env vars used for link generation (auto-set in GitHub Actions):
  GITHUB_SERVER_URL   e.g. https://github.com
  GITHUB_REPOSITORY   e.g. owner/repo

Appends to GITHUB_STEP_SUMMARY if the env var is set.
Exits 1 if any secrets were found.
"""
import json
import os
import sys

SERVER_URL = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")


def blob_url(commit: str, file: str, line: int) -> str:
    if not REPOSITORY or not commit or not file:
        return ""
    fragment = f"#L{line}" if line else ""
    return f"{SERVER_URL}/{REPOSITORY}/blob/{commit}/{file.lstrip('/')}{fragment}"


def file_link(commit: str, file: str, line: int) -> str:
    url   = blob_url(commit, file, line)
    label = f"{file}{'#L' + str(line) if line else ''}"
    return f"[{label}]({url})" if url else f"`{label}`"


def redact(raw: str) -> str:
    raw = raw[:50]
    return f"{raw[:6]}...{raw[-4:]}" if len(raw) > 10 else raw


def load_findings(path: str) -> list[dict]:
    findings = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        findings.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return findings


def build_table(findings: list[dict]) -> str:
    if not findings:
        return "**No secrets detected.** ✅\n"

    lines = [
        f"**{len(findings)} secret(s) found** 🚨\n",
        "| # | Type | File | Branch | Commit | Verified | Value (redacted) |",
        "|---|------|------|--------|--------|----------|-----------------|",
    ]

    for i, f in enumerate(findings, 1):
        meta     = (f.get("SourceMetadata") or {}).get("Data", {})
        git      = meta.get("Git", {})
        fs       = meta.get("Filesystem", {})
        detector = f.get("DetectorName", "unknown")
        verified = "✅ yes" if f.get("Verified") else "no"
        value    = redact(f.get("Raw") or "")
        commit   = git.get("commit") or ""
        file     = git.get("file") or fs.get("file") or "unknown"
        branch   = git.get("branch", "—")
        line_no  = git.get("line", 0)
        short_sha = commit[:8] or "—"
        link     = file_link(commit, file, line_no)

        lines.append(
            f"| {i} | {detector} | {link} | {branch} | `{short_sha}` | {verified} | `{value}` |"
        )

    return "\n".join(lines) + "\n"


def main():
    input_file  = sys.argv[1] if len(sys.argv) > 1 else "trufflehog-results.ndjson"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    findings = load_findings(input_file)
    table    = build_table(findings)

    if output_file:
        with open(output_file, "w") as f:
            f.write(table)
    else:
        print(table)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"\n## Secret Detection Results\n\n{table}\n")

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
