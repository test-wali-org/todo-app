#!/usr/bin/env python3
"""
Send a formatted Slack Block Kit notification with the secret scan report.

Inputs (env vars):
  SLACK_WEBHOOK_URL, LLM_REPORT, TOTAL_FINDINGS,
  BRANCH_COUNT, STATUS, REPO, RUN_URL
"""
import json
import os
import urllib.request
import urllib.error

WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
LLM_REPORT = os.environ.get("LLM_REPORT", "{}")
TOTAL = int(os.environ.get("TOTAL_FINDINGS", "0"))
BRANCHES = int(os.environ.get("BRANCH_COUNT", "0"))
STATUS = os.environ.get("STATUS", "unknown")
REPO = os.environ.get("REPO", "unknown")
RUN_URL = os.environ.get("RUN_URL", "#")

SEV_ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}


def main():
    if not WEBHOOK:
        print("[slack-notify] SLACK_WEBHOOK_URL not set — skipping")
        return

    try:
        report = json.loads(LLM_REPORT)
    except json.JSONDecodeError:
        report = {}

    is_clean = STATUS == "clean"
    stats = report.get("stats", {})
    summary = report.get("executive_summary", "Automated scan complete.")
    priorities = report.get("top_priorities", [])[:5]
    steps = report.get("remediation_steps", [])
    fp_est = report.get("false_positive_estimate", "N/A")

    sev_bar = (
        f"🔴 {stats.get('critical', 0)} critical  "
        f"🟠 {stats.get('high', 0)} high  "
        f"🟡 {stats.get('medium', 0)} medium  "
        f"🔵 {stats.get('low', 0)} low"
    )
    if stats.get("verified_live", 0):
        sev_bar += f"  ⚡ {stats['verified_live']} *VERIFIED LIVE*"

    prio_lines = ""
    for p in priorities:
        icon = SEV_ICONS.get(p.get("severity", "low"), "⚪")
        prio_lines += (
            f"{icon} *{p.get('type', '?')}* — "
            f"`{p.get('file', '?')}` ({p.get('branch', '?')}) "
            f"→ _{p.get('action', 'review')}_\n"
        )

    remediation = (
        "\n".join(f"• {s}" for s in steps)
        if steps
        else "• Review the workflow artifacts for full details."
    )

    header_text = (
        "✅ Secret Scan — All Clear"
        if is_clean
        else "🚨 Secret Scan — Action Required"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text, "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"✅ *Secret Scan Complete — No secrets found in `{REPO}`*"
                    if is_clean
                    else f"🚨 *Secret Scan Alert — Potential secrets detected in `{REPO}`*"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Repository*\n`{REPO}`"},
                {"type": "mrkdwn", "text": f"*Branches Scanned*\n{BRANCHES}"},
                {"type": "mrkdwn", "text": f"*Unique Findings*\n{TOTAL}"},
                {"type": "mrkdwn", "text": f"*FP Estimate*\n{fp_est}"},
            ],
        },
    ]

    if not is_clean:
        blocks += [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Severity breakdown*\n{sev_bar}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Summary*\n{summary}"}},
        ]
        if prio_lines:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Top Priorities*\n{prio_lines}"},
            })
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Remediation Steps*\n{remediation}"},
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Full Report", "emoji": True},
                    "url": RUN_URL,
                    "style": "danger" if not is_clean else "default",
                }
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Scanned by TruffleHog v3 + Claude AI · <{RUN_URL}|Workflow run>"}
            ],
        },
    ]

    data = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[slack-notify] HTTP {resp.status} — notification sent")
    except urllib.error.HTTPError as e:
        print(f"[slack-notify] Error: {e.code} {e.reason}")
        raise


if __name__ == "__main__":
    main()
