#!/usr/bin/env python3
"""
Generate a structured LLM security report from deduplicated TruffleHog findings.

Inputs (env vars): ANTHROPIC_API_KEY, TOTAL_FINDINGS, BRANCH_COUNT, REPO, RUN_URL
Reads:             findings-deduped.json
Outputs:           GITHUB_OUTPUT  →  llm_report, status
"""
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TOTAL = int(os.environ.get("TOTAL_FINDINGS", "0"))
BRANCHES = int(os.environ.get("BRANCH_COUNT", "0"))
REPO = os.environ.get("REPO", "unknown")
RUN_URL = os.environ.get("RUN_URL", "#")
GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "")
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def set_output(key: str, value: str) -> None:
    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"[output] {key}={value}")


def fallback_report() -> dict:
    return {
        "status": "issues_found" if TOTAL > 0 else "clean",
        "executive_summary": (
            f"Scan complete. {TOTAL} unique finding(s) detected across "
            f"{BRANCHES} branch(es). Manual review required."
        ),
        "stats": {"critical": 0, "high": 0, "medium": 0, "low": 0, "verified_live": 0},
        "top_priorities": [],
        "remediation_steps": [
            "Review findings-deduped.json in workflow artifacts.",
            "Rotate any confirmed secrets immediately.",
        ],
        "false_positive_estimate": "unknown",
    }


def load_findings_sample() -> list:
    try:
        with open("findings-deduped.json") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    simplified = []
    for finding in data[:50]:
        meta = (finding.get("SourceMetadata") or {}).get("Data", {}).get("Git", {})
        simplified.append({
            "detector": finding.get("DetectorName", "unknown"),
            "raw_truncated": (finding.get("Raw") or "")[:60],
            "file": meta.get("file", "unknown"),
            "branch": meta.get("branch", "unknown"),
            "commit": meta.get("commit", "")[:8],
            "verified": finding.get("Verified", False),
        })
    return simplified


def call_claude(prompt: str) -> dict:
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[cron-llm-report] API error: {e}")
        return {}


def parse_response(response: dict) -> dict:
    try:
        text = response["content"][0]["text"]
        text = re.sub(r"^```json\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        print(f"[cron-llm-report] Parse error: {e}")
        return {}


def main():
    if not ANTHROPIC_API_KEY:
        print("[cron-llm-report] ANTHROPIC_API_KEY not set — using fallback report")
        report = fallback_report()
        set_output("llm_report", json.dumps(report))
        set_output("status", report["status"])
        return

    sample = load_findings_sample()

    prompt = f"""You are a security engineer reviewing automated secret scan results for repository '{REPO}'.

Scan metadata:
- Date: {DATE}
- Branches scanned: {BRANCHES}
- Total unique findings (after dedup): {TOTAL}
- Findings sample (up to 50): {json.dumps(sample, indent=2)}

Tasks:
1. Categorize findings by severity: critical (verified live secrets), high (likely real), medium (probable), low (possibly FP).
2. Identify the most urgent items requiring immediate action.
3. Group by secret type (AWS, DB credentials, API tokens, etc.).
4. Flag any verified=true findings — these are confirmed live secrets.
5. Provide a concise remediation priority list.

Reply with ONLY valid JSON — no markdown fences, no prose:
{{
  "status": "clean" | "issues_found",
  "executive_summary": "<2-3 sentences for non-technical stakeholders>",
  "stats": {{
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "verified_live": 0
  }},
  "top_priorities": [
    {{
      "rank": 1,
      "type": "<secret type>",
      "severity": "critical|high|medium|low",
      "branch": "<branch>",
      "file": "<file>",
      "action": "<immediate action to take>"
    }}
  ],
  "remediation_steps": ["<step 1>", "<step 2>"],
  "false_positive_estimate": "<percentage estimate>"
}}"""

    response = call_claude(prompt)
    report = parse_response(response)

    if not report:
        report = fallback_report()

    set_output("llm_report", json.dumps(report))
    set_output("status", report.get("status", "unknown"))
    print(f"[cron-llm-report] status={report.get('status')}")


if __name__ == "__main__":
    main()
