#!/usr/bin/env python3
"""
Parse TruffleHog output and write a markdown findings table with GitHub links.

Accepts two input formats:
  - NDJSON (.ndjson)  : raw TruffleHog output, one JSON object per line
  - JSON array (.json): deduplicated output from cron-dedup.py,
                        each entry has 'branches' and 'occurrences' lists

Usage:
  python3 format-table.py <input-file> [output.md]

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
    """Return a GitHub permalink to a specific file and line."""
    if not REPOSITORY or not commit or not file:
        return ""
    fragment = f"#L{line}" if line else ""
    return f"{SERVER_URL}/{REPOSITORY}/blob/{commit}/{file.lstrip('/')}{fragment}"


def file_link(commit: str, file: str, line: int) -> str:
    """Markdown link for a file, falls back to plain text if URL can't be built."""
    url = blob_url(commit, file, line)
    label = f"{file}{'#L' + str(line) if line else ''}"
    return f"[{label}]({url})" if url else f"`{label}`"


def redact(raw: str) -> str:
    raw = raw[:50]
    return f"{raw[:6]}...{raw[-4:]}" if len(raw) > 10 else raw


def load_findings(path: str) -> list[dict]:
    try:
        with open(path) as f:
            content = f.read().strip()
        if content.startswith("["):
            return json.loads(content)
        # NDJSON
        findings = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return findings
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def build_table_ndjson(findings: list[dict]) -> str:
    """Table for raw PR scan output — one row per finding, file linked to exact line."""
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


def build_table_deduped(findings: list[dict]) -> str:
    """Table for cron deduplicated output — branches column has per-branch links."""
    lines = [
        f"**{len(findings)} unique secret(s) found** 🚨\n",
        "| # | Type | Branches (linked to file:line) | Verified | Value (redacted) | Occurrences |",
        "|---|------|-------------------------------|----------|-----------------|-------------|",
    ]
    for i, f in enumerate(findings, 1):
        detector = f.get("DetectorName", "unknown")
        verified = "✅ yes" if f.get("Verified") else "no"
        value    = redact(f.get("Raw") or "")
        occs     = f.get("occurrences", [])

        # Each occurrence becomes a linked branch label
        branch_links = []
        for o in occs:
            branch = o.get("branch", "unknown")
            file   = o.get("file",   "unknown")
            commit = o.get("commit", "")
            line_no = o.get("line", 0)
            url    = blob_url(commit, file, line_no)
            label  = f"{branch} (`{file}{'#L' + str(line_no) if line_no else ''}`)"
            branch_links.append(f"[{label}]({url})" if url else label)

        branches_cell = "<br>".join(branch_links) if branch_links else "—"

        lines.append(
            f"| {i} | {detector} | {branches_cell} | {verified} | `{value}` | {len(occs)} |"
        )
    return "\n".join(lines) + "\n"


def build_table(findings: list[dict]) -> str:
    if not findings:
        return "**No secrets detected.** ✅\n"
    if "occurrences" in findings[0]:
        return build_table_deduped(findings)
    return build_table_ndjson(findings)


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
