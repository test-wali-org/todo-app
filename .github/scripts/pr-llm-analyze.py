#!/usr/bin/env python3
"""
LLM-based contextual analysis for a PR diff.

Inputs (env vars): ANTHROPIC_API_KEY, BASE_SHA, HEAD_SHA
Reads:             trufflehog-results.ndjson  (written by pr-scan.sh)
Outputs:           GITHUB_OUTPUT  →  llm_result, verdict
"""
import json
import os
import re
import subprocess
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BASE_SHA = os.environ.get("BASE_SHA", "")
HEAD_SHA = os.environ.get("HEAD_SHA", "")
GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "")

FALLBACK = json.dumps({
    "verdict": "unknown",
    "summary": "LLM analysis failed — manual review required.",
    "findings": [],
    "recommendation": "Review trufflehog-results.ndjson in workflow artifacts.",
})


def set_output(key: str, value: str) -> None:
    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"[output] {key}={value}")


def get_pr_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", BASE_SHA, HEAD_SHA, "--unified=0"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout[:14000]
    except Exception as e:
        print(f"[pr-llm-analyze] Warning: could not get diff: {e}")
        return ""


def get_trufflehog_json() -> str:
    try:
        with open("trufflehog-results.ndjson") as f:
            return f.read(3000)
    except FileNotFoundError:
        return ""


def call_claude(prompt: str) -> dict:
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1500,
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[pr-llm-analyze] API error: {e}")
        return {}


def parse_llm_response(response: dict) -> dict:
    try:
        text = response["content"][0]["text"]
        text = re.sub(r"^```json\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        print(f"[pr-llm-analyze] Parse error: {e}")
        return {}


def main():
    if not ANTHROPIC_API_KEY:
        print("[pr-llm-analyze] ANTHROPIC_API_KEY not set — skipping LLM pass")
        set_output("llm_result", FALLBACK)
        set_output("verdict", "unknown")
        return

    diff = get_pr_diff()
    trufflehog_json = get_trufflehog_json()

    prompt = f"""You are a security expert reviewing a git pull request for hardcoded secrets.

TruffleHog findings (JSON, may be empty):
```json
{trufflehog_json}
```

Full PR diff:
```diff
{diff}
```

Rules:
- Flag ONLY genuine secrets (real keys, passwords, tokens with actual entropy).
- Dismiss placeholders, example values, test fixtures, and commented-out code.
- Confirm or dismiss each TruffleHog finding.

Reply with ONLY valid JSON — no markdown fences, no prose:
{{
  "verdict": "clean" | "suspicious" | "confirmed_secrets",
  "summary": "<one sentence>",
  "findings": [
    {{
      "type": "<AWS key | DB password | API token | etc>",
      "severity": "critical" | "high" | "medium" | "low",
      "location": "<filename:line or description>",
      "reason": "<why this is a real secret>",
      "is_false_positive": false
    }}
  ],
  "recommendation": "<action to take>"
}}"""

    response = call_claude(prompt)
    result = parse_llm_response(response)

    if not result:
        set_output("llm_result", FALLBACK)
        set_output("verdict", "unknown")
        return

    result_str = json.dumps(result)
    verdict = result.get("verdict", "unknown")
    set_output("llm_result", result_str)
    set_output("verdict", verdict)
    print(f"[pr-llm-analyze] verdict={verdict}")


if __name__ == "__main__":
    main()
