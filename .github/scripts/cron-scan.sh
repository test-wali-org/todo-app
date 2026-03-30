#!/usr/bin/env bash
# Scan all remote branches with TruffleHog, then deduplicate findings.
# Inputs (env vars):  BRANCH_FILTER (optional glob/pattern)
# Outputs:            all-findings.ndjson, findings-deduped.json
#                     GITHUB_OUTPUT  →  total_findings, branch_count
set -euo pipefail

BRANCH_FILTER="${BRANCH_FILTER:-}"
ALL_FINDINGS_FILE="all-findings.ndjson"
touch "$ALL_FINDINGS_FILE"

# ── Collect branch names ───────────────────────────────────────────────────
if [[ -n "$BRANCH_FILTER" ]]; then
  BRANCHES=$(git branch -r | grep -v HEAD | grep "origin/$BRANCH_FILTER" \
             | sed 's|origin/||' | tr -d ' ' || true)
else
  BRANCHES=$(git branch -r | grep -v HEAD | sed 's|origin/||' | tr -d ' ')
fi

# ── Scan each branch ──────────────────────────────────────────────────────
BRANCH_COUNT=0
while IFS= read -r branch; do
  [[ -z "$branch" ]] && continue
  echo "[cron-scan] Scanning branch: $branch"
  BRANCH_COUNT=$((BRANCH_COUNT + 1))
  trufflehog git "file://." \
    --branch "origin/$branch" \
    --json \
    --no-update \
    2>/dev/null >> "$ALL_FINDINGS_FILE" || true
done <<< "$BRANCHES"

echo "[cron-scan] Scanned $BRANCH_COUNT branch(es)"

# ── Deduplicate by raw secret value ───────────────────────────────────────
python3 .github/scripts/cron-dedup.py

TOTAL=$(python3 -c "import json; print(len(json.load(open('findings-deduped.json'))))" 2>/dev/null || echo "0")
echo "total_findings=$TOTAL"      >> "$GITHUB_OUTPUT"
echo "branch_count=$BRANCH_COUNT" >> "$GITHUB_OUTPUT"
echo "[cron-scan] $TOTAL unique finding(s) after dedup"
