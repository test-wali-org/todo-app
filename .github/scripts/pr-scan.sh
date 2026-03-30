#!/usr/bin/env bash
# Scan only the commits introduced by this PR.
# Inputs (env vars):  BASE_SHA, HEAD_SHA
# Outputs:            trufflehog-results.ndjson  +  GITHUB_OUTPUT findings_count
set -euo pipefail

: "${BASE_SHA:?BASE_SHA env var required}"
: "${HEAD_SHA:?HEAD_SHA env var required}"

trufflehog git "file://." \
  --since-commit "$BASE_SHA" \
  --branch       "$HEAD_SHA" \
  --json \
  --no-update \
  2>/dev/null > trufflehog-results.ndjson || true

COUNT=$(grep -c '"DetectorName"' trufflehog-results.ndjson 2>/dev/null || true)
COUNT=${COUNT:-0}
echo "findings_count=$COUNT" >> "$GITHUB_OUTPUT"
echo "[pr-scan] TruffleHog: $COUNT raw finding(s)"
