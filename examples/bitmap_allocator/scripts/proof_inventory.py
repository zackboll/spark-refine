#!/usr/bin/env python3
"""Check complete, disjoint physical Ada SLOC classifications; emit stable JSON."""
import collections
import hashlib
import json
from pathlib import Path
import tomllib

root = Path(__file__).resolve().parents[1]
inventory = tomllib.loads((root / "proof_inventory.toml").read_text())
files = {}
totals = collections.Counter()
generic = 0
spans = []
for span in inventory["span"]:
    path = root / span["file"]
    files.setdefault(span["file"], {"text": path.read_text(), "covered": set()})
    data = files[span["file"]]
    lines = data["text"].splitlines()
    indices = set(range(span["start"], span["end"] + 1))
    if indices & data["covered"] or min(indices) < 1 or max(indices) > len(lines):
        raise ValueError(f"Overlapping or out-of-range span: {span}")
    data["covered"].update(indices)
    active = [n for n in sorted(indices) if lines[n - 1].split("--", 1)[0].strip()]
    count = len(active)
    totals[span["class"]] += count
    if span["class"] == "mechanical" and span["generic"]:
        generic += count
    spans.append(dict(span, sloc=count, active_lines=active))
for file, data in files.items():
    expected = {i for i, line in enumerate(data["text"].splitlines(), 1)
                if line.split("--", 1)[0].strip()}
    if not expected <= data["covered"]:
        raise ValueError(f"Unclassified lines: {file}: {expected - data['covered']}")
actual = {str(p.relative_to(root)) for p in (root / "variants/manual").glob("*.ad?")}
if set(files) != actual:
    raise ValueError("Source inventory missing a file")
p = totals["mechanical"]
tests = root / "tests/bitmap_allocator_runtime_tests.adb"
result = {"format_version": 1, "totals": dict(totals), "P": p,
          "generic_P": generic, "application_specific_P": p - generic,
          "G_percent": round(100 * generic / p, 6),
          "library_gate": "PASS" if p >= 15 and 2 * generic >= p else "MANUAL_SUPPORT_TOO_SMALL",
          "source_sha256": {file: hashlib.sha256(data["text"].encode()).hexdigest()
                            for file, data in files.items()},
          "runtime_test_sloc_excluded": sum(bool(line.split("--", 1)[0].strip())
                                            for line in tests.read_text().splitlines()),
          "spans": spans}
print(json.dumps(result, indent=2, sort_keys=True))