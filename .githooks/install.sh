#!/usr/bin/env bash
# Run once after cloning to activate git hooks for this repo.
#   bash .githooks/install.sh
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${BOLD}Setting up git hooks…${NC}"

# ── 1. Point git at .githooks ─────────────────────────────────────────────
git config core.hooksPath .githooks
echo -e "  ${GREEN}✔${NC}  core.hooksPath → .githooks"

# ── 2. Ensure hook files are executable ──────────────────────────────────
chmod +x "$(git rev-parse --show-toplevel)/.githooks/pre-commit"
echo -e "  ${GREEN}✔${NC}  pre-commit hook is executable"

# ── 3. Check TruffleHog ───────────────────────────────────────────────────
if command -v trufflehog >/dev/null 2>&1; then
  echo -e "  ${GREEN}✔${NC}  TruffleHog $(trufflehog --version 2>&1 | head -1)"
else
  echo -e "  ${YELLOW}⚠${NC}  TruffleHog not found — install it to enable secret scanning:"
  echo -e "       brew install trufflehog"
  echo -e "       ${YELLOW}Commits will be allowed through until TruffleHog is installed.${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}Done.${NC} Secret detection pre-commit hook is active for this repo."
echo ""
