#!/usr/bin/env bash
# Scan only the files changed in this PR using trufflehog filesystem mode.
# This avoids scanning pre-existing secrets in unchanged files.
#
# Inputs (env vars):  BASE_SHA, HEAD_SHA
# Outputs:            trufflehog-results.ndjson  +  GITHUB_OUTPUT findings_count
set -euo pipefail

: "${BASE_SHA:?BASE_SHA env var required}"
: "${HEAD_SHA:?HEAD_SHA env var required}"

# ── Get files added/changed in this PR ────────────────────────────────────
CHANGED_FILES=$(git diff --name-only --diff-filter=ACM "$BASE_SHA" "$HEAD_SHA" 2>/dev/null || true)

if [[ -z "$CHANGED_FILES" ]]; then
  echo "[pr-scan] No changed files in this PR"
  echo "findings_count=0" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "[pr-scan] Changed files:"
echo "$CHANGED_FILES" | sed 's/^/  /'

# ── Extract those files at HEAD to a temp dir ─────────────────────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  mkdir -p "$TMP_DIR/$(dirname "$file")"
  git show "$HEAD_SHA:$file" > "$TMP_DIR/$file" 2>/dev/null || true
done <<< "$CHANGED_FILES"

# ── Scan with filesystem mode + inject commit for GitHub links ────────────
CONFIG_FLAG=""
[[ -f ".trufflehog.yaml" ]] && CONFIG_FLAG="--config .trufflehog.yaml"

trufflehog filesystem "$TMP_DIR" \
  --json \
  --no-update \
  $CONFIG_FLAG \
  2>/dev/null \
| python3 -c "
import sys, json

tmp      = '$TMP_DIR'
head_sha = '$HEAD_SHA'

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj     = json.loads(line)
        fs      = (obj.get('SourceMetadata') or {}).get('Data', {}).get('Filesystem', {})
        fs_file = fs.get('file', '')
        line_no = fs.get('line', 0)
        clean   = fs_file.replace(tmp + '/', '').replace(tmp, '') if fs_file else 'unknown'
        # Rewrite to Git-style metadata so format-table.py can build blob links
        obj['SourceMetadata'] = {
            'Data': {
                'Git': {
                    'commit': head_sha,
                    'file':   clean,
                    'line':   line_no,
                    'branch': '',
                }
            }
        }
        print(json.dumps(obj))
    except Exception:
        pass
" > trufflehog-results.ndjson || true

COUNT=$(grep -c '"DetectorName"' trufflehog-results.ndjson 2>/dev/null || true)
COUNT=${COUNT:-0}
echo "findings_count=$COUNT" >> "$GITHUB_OUTPUT"
echo "[pr-scan] TruffleHog: $COUNT finding(s) across $(echo "$CHANGED_FILES" | wc -l | tr -d ' ') changed file(s)"
