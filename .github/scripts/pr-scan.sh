#!/usr/bin/env bash
# Scan ONLY the lines added/changed in this PR — not pre-existing file content.
# Uses git diff to extract added lines, scans them with trufflehog filesystem,
# then maps temp-file line numbers back to the real HEAD line numbers.
#
# Inputs (env vars):  BASE_SHA, HEAD_SHA
# Outputs:            trufflehog-results.ndjson  +  GITHUB_OUTPUT findings_count
set -euo pipefail

: "${BASE_SHA:?BASE_SHA env var required}"
: "${HEAD_SHA:?HEAD_SHA env var required}"

CONFIG_ARG=""
[[ -f ".trufflehog.yaml" ]] && CONFIG_ARG="--config .trufflehog.yaml"

TRUFFLEHOG_CONFIG="$CONFIG_ARG" \
python3 - <<'PYEOF'
import subprocess, json, os, re, sys, tempfile

base_sha = os.environ["BASE_SHA"]
head_sha = os.environ["HEAD_SHA"]
config   = os.environ.get("TRUFFLEHOG_CONFIG", "").split() or []

# ── Get files added/modified in this PR ───────────────────────────────────
res = subprocess.run(
    ["git", "diff", "--name-only", "--diff-filter=ACM", base_sha, head_sha],
    capture_output=True, text=True,
)
changed_files = [f for f in res.stdout.strip().split("\n") if f]

if not changed_files:
    print("[pr-scan] No changed files", file=sys.stderr)
    gh = os.environ.get("GITHUB_OUTPUT", "")
    if gh:
        open(gh, "a").write("findings_count=0\n")
    sys.exit(0)

print(f"[pr-scan] {len(changed_files)} changed file(s)", file=sys.stderr)

all_findings = []

for filepath in changed_files:
    # ── Extract added lines + their real line numbers in HEAD ──────────────
    diff = subprocess.run(
        ["git", "diff", base_sha, head_sha, "--unified=0", "--", filepath],
        capture_output=True, text=True,
    ).stdout

    added = []          # [(line_no_in_head, line_content), ...]
    new_lineno = 0
    for dl in diff.splitlines():
        if dl.startswith("@@"):
            m = re.search(r"\+(\d+)", dl)
            if m:
                new_lineno = int(m.group(1)) - 1
        elif dl.startswith("+") and not dl.startswith("+++"):
            new_lineno += 1
            added.append((new_lineno, dl[1:]))
        elif not dl.startswith("-") and not dl.startswith("\\"):
            new_lineno += 1

    if not added:
        continue

    # ── Write added lines to a temp file for trufflehog ───────────────────
    ext = os.path.splitext(filepath)[1] or ".txt"
    with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        for _, content in added:
            tmp.write(content + "\n")

    try:
        cmd = ["trufflehog", "filesystem", tmp_path, "--json", "--no-update"] + config
        scan = subprocess.run(cmd, capture_output=True, text=True)

        for raw_line in scan.stdout.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
                # Map temp-file line number → real HEAD line number
                tmp_lineno = (
                    (obj.get("SourceMetadata") or {})
                    .get("Data", {})
                    .get("Filesystem", {})
                    .get("line", 0)
                )
                real_lineno = (
                    added[tmp_lineno - 1][0]
                    if 0 < tmp_lineno <= len(added)
                    else tmp_lineno
                )
                obj["SourceMetadata"] = {
                    "Data": {
                        "Git": {
                            "commit": head_sha,
                            "file":   filepath,
                            "line":   real_lineno,
                            "branch": "",
                        }
                    }
                }
                all_findings.append(obj)
            except Exception:
                pass
    finally:
        os.unlink(tmp_path)

# ── Write output ──────────────────────────────────────────────────────────
with open("trufflehog-results.ndjson", "w") as out:
    for f in all_findings:
        out.write(json.dumps(f) + "\n")

count = len(all_findings)
print(f"[pr-scan] {count} finding(s) across added lines", file=sys.stderr)

gh = os.environ.get("GITHUB_OUTPUT", "")
if gh:
    with open(gh, "a") as f:
        f.write(f"findings_count={count}\n")
PYEOF
