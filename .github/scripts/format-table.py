#!/usr/bin/env python3
"""
Parse TruffleHog output and write a markdown findings table.

Accepts two input formats:
  - NDJSON (.ndjson)  : raw TruffleHog output, one JSON object per line
  - JSON array (.json): deduplicated output from cron-dedup.py
    Each entry may have a 'branches' list and 'occurrences' list.

Usage:
  python3 format-table.py <input-file> [output.md]

Appends to GITHUB_STEP_SUMMARY if the env var is set.
Exits 1 if any secrets were found.
"""
import json
import os
import sys


def parse_ndjson(path: str) -> list[dict]:
    findings = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return findings


def parse_json_array(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def load_findings(path: str) -> list[dict]:
    try:
        with open(path) as f:
            first_char = f.read(1)
        if first_char == "[":
            return parse_json_array(path)
        return parse_ndjson(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def redact(raw: str) -> str:
    raw = raw[:50]
    return f"{raw[:6]}...{raw[-4:]}" if len(raw) > 10 else raw


def build_table(findings: list[dict]) -> str:
    if not findings:
        return "**No secrets detected.** ✅\n"

    rows = []
    for f in findings:
        meta = (f.get("SourceMetadata") or {}).get("Data", {})
        git  = meta.get("Git", {})
        fs   = meta.get("Filesystem", {})

        detector = f.get("DetectorName", "unknown")
        verified = "✅ yes" if f.get("Verified") else "no"
        value    = redact(f.get("Raw") or "")

        # Deduplicated (cron) format: has 'branches' and 'occurrences'
        if "occurrences" in f:
            branches_str = ", ".join(f.get("branches", ["unknown"]))
            # Show unique files across all occurrences
            files = sorted({o["file"] for o in f["occurrences"]})
            file_str = ", ".join(f"`{fp}`" for fp in files)
            commit   = "multiple" if len(f["occurrences"]) > 1 else f["occurrences"][0]["commit"]
            rows.append((detector, file_str, branches_str, commit, verified, value,
                         len(f["occurrences"])))
        else:
            # Raw NDJSON format (PR scan): single branch per finding
            file   = git.get("file") or fs.get("file") or "unknown"
            branch = git.get("branch", "—")
            commit = (git.get("commit") or "")[:8] or "—"
            rows.append((detector, f"`{file}`", branch, commit, verified, value, 1))

    is_cron = "occurrences" in findings[0]

    header = (
        "| # | Type | File(s) | Branches | Commit | Verified | Value (redacted) | Occurrences |"
        if is_cron else
        "| # | Type | File | Branch | Commit | Verified | Value (redacted) |"
    )
    separator = (
        "|---|------|---------|----------|--------|----------|-----------------|-------------|"
        if is_cron else
        "|---|------|------|--------|--------|----------|-----------------|"
    )

    lines = [f"**{len(findings)} unique secret(s) found** 🚨\n", header, separator]

    for i, row in enumerate(rows, 1):
        detector, file_str, branch_or_branches, commit, verified, value, count = row
        if is_cron:
            lines.append(
                f"| {i} | {detector} | {file_str} | {branch_or_branches} "
                f"| `{commit}` | {verified} | `{value}` | {count} |"
            )
        else:
            lines.append(
                f"| {i} | {detector} | {file_str} | {branch_or_branches} "
                f"| `{commit}` | {verified} | `{value}` |"
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
