#!/usr/bin/env python3
"""
Deduplicate TruffleHog NDJSON findings by raw secret value.
Instead of discarding duplicates, group them and collect every branch
(+ file and commit) where that secret was seen.

Reads:   all-findings.ndjson
Writes:  findings-deduped.json  (JSON array with a merged 'branches' list)
"""
import json
from collections import defaultdict

# key → first full finding object (used for metadata like DetectorName, Verified)
first_occurrence: dict[str, dict] = {}
# key → list of {branch, file, commit} dicts (one per occurrence)
occurrences: dict[str, list] = defaultdict(list)

with open("all-findings.ndjson") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        key = obj.get("Raw") or obj.get("RawV2") or ""
        if not key:
            continue

        git = (obj.get("SourceMetadata") or {}).get("Data", {}).get("Git", {})
        entry = {
            "branch": git.get("branch", "unknown"),
            "file":   git.get("file",   "unknown"),
            "commit": (git.get("commit") or "")[:8],
        }

        if key not in first_occurrence:
            first_occurrence[key] = obj

        # Only append if this branch+file combo hasn't been recorded yet
        if entry not in occurrences[key]:
            occurrences[key].append(entry)

# Build merged output
deduped = []
for key, base in first_occurrence.items():
    merged = dict(base)
    all_branches = sorted({o["branch"] for o in occurrences[key]})
    merged["branches"]    = all_branches
    merged["occurrences"] = occurrences[key]
    deduped.append(merged)

with open("findings-deduped.json", "w") as f:
    json.dump(deduped, f, indent=2)

print(f"[cron-dedup] {len(deduped)} unique secret(s) across "
      f"{sum(len(v) for v in occurrences.values())} total occurrence(s)")
