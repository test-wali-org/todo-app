#!/usr/bin/env bash
# Scan the current file state of every remote branch with TruffleHog.
# Uses git archive + trufflehog filesystem so each branch is scanned
# independently — shared commits are NOT skipped.
#
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

# ── Scan each branch independently ────────────────────────────────────────
BRANCH_COUNT=0
while IFS= read -r branch; do
  [[ -z "$branch" ]] && continue
  echo "[cron-scan] Scanning branch: $branch"
  BRANCH_COUNT=$((BRANCH_COUNT + 1))

  # Get the HEAD commit SHA for this branch (used in GitHub permalink)
  COMMIT=$(git rev-parse "origin/$branch" 2>/dev/null || echo "")

  # Extract branch contents to a temp dir
  TMP_DIR=$(mktemp -d)

  git archive "origin/$branch" | tar -x -C "$TMP_DIR" 2>/dev/null || true

  # Scan, then inject branch + commit + strip the tmp path from file names
  trufflehog filesystem "$TMP_DIR" \
    --json \
    --no-update \
    2>/dev/null \
  | python3 -c "
import sys, json, os

branch = '$branch'
commit = '$COMMIT'
tmp    = '$TMP_DIR'

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        fs_file = (obj.get('SourceMetadata') or {}).get('Data', {}).get('Filesystem', {}).get('file', '')
        clean_file = fs_file.replace(tmp + '/', '').replace(tmp, '') if fs_file else 'unknown'
        line_no = (obj.get('SourceMetadata') or {}).get('Data', {}).get('Filesystem', {}).get('line', 0)
        # Store in Git-style metadata so format-table.py can build links
        obj['SourceMetadata'] = {
            'Data': {
                'Git': {
                    'branch': branch,
                    'commit': commit,
                    'file':   clean_file,
                    'line':   line_no,
                }
            }
        }
        print(json.dumps(obj))
    except Exception:
        pass
" >> "$ALL_FINDINGS_FILE" || true

  rm -rf "$TMP_DIR"
done <<< "$BRANCHES"

COUNT=$(grep -c '"DetectorName"' "$ALL_FINDINGS_FILE" 2>/dev/null || true)
COUNT=${COUNT:-0}
echo "total_findings=$COUNT"      >> "$GITHUB_OUTPUT"
echo "branch_count=$BRANCH_COUNT" >> "$GITHUB_OUTPUT"
echo "[cron-scan] $BRANCH_COUNT branch(es) scanned, $COUNT finding(s)"
