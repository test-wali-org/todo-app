#!/usr/bin/env python3
"""
Deduplicate TruffleHog NDJSON findings by raw secret value.
Reads:   all-findings.ndjson
Writes:  findings-deduped.json
"""
import json

seen: set = set()
deduped: list = []

with open("all-findings.ndjson") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            key = obj.get("Raw") or obj.get("RawV2") or ""
            if key and key not in seen:
                seen.add(key)
                deduped.append(obj)
        except json.JSONDecodeError:
            pass

with open("findings-deduped.json", "w") as f:
    json.dump(deduped, f, indent=2)

print(f"[cron-dedup] {len(deduped)} unique finding(s) written to findings-deduped.json")
