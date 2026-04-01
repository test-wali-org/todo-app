#!/usr/bin/env bash
# Run once after cloning: bash setup-hooks.sh
set -euo pipefail

git config core.hooksPath .githooks
echo "✅ Git hooks configured. TruffleHog pre-commit hook is active."

if ! command -v trufflehog >/dev/null 2>&1; then
  echo "⚠️  TruffleHog not found. Install it:"
  echo "     brew install trufflehog"
fi