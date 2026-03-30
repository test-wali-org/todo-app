#!/usr/bin/env bash
set -euo pipefail

curl -sSfL \
  https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \
  | sh -s -- -b /usr/local/bin

trufflehog --version
