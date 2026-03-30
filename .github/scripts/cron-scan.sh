#!/usr/bin/env bash
# Scan all remote branches with TruffleHog.
# Inputs (env vars):  BRANCH_FILTER (optional pattern)
# Outputs:            all-findings.ndjson
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

# ── Scan each branch, inject branch name (TruffleHog omits it) ────────────
BRANCH_COUNT=0
while IFS= read -r branch; do
  [[ -z "$branch" ]] && continue
  echo "[cron-scan] Scanning branch: $branch"
  BRANCH_COUNT=$((BRANCH_COUNT + 1))

  trufflehog git "file://." \
    --branch "origin/$branch" \
    --json \
    --no-update \
    2>/dev/null \
  | python3 -c "
import sys, json
branch = '$branch'
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        obj.setdefault('SourceMetadata', {}).setdefault('Data', {}).setdefault('Git', {})['branch'] = branch
        print(json.dumps(obj))
    except Exception:
        pass
" >> "$ALL_FINDINGS_FILE" || true
done <<< "$BRANCHES"

COUNT=$(grep -c '"DetectorName"' "$ALL_FINDINGS_FILE" 2>/dev/null || true)
COUNT=${COUNT:-0}
echo "total_findings=$COUNT"      >> "$GITHUB_OUTPUT"
echo "branch_count=$BRANCH_COUNT" >> "$GITHUB_OUTPUT"
echo "[cron-scan] $BRANCH_COUNT branch(es) scanned, $COUNT finding(s)"
