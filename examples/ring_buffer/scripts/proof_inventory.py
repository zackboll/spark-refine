#!/usr/bin/env python3
"""Reproducible proof-support inventory for the Task 001 baseline.

Reads proof_inventory.toml, validates every classified line range against
its anchor text, and reports source LOC (non-blank, non-comment lines) per
group/category plus structural counts (ghost declarations, loop invariants,
lemmas, public contracts, assertions in the client proof).

  python3 scripts/proof_inventory.py            # human-readable table
  python3 scripts/proof_inventory.py --json     # machine-readable output

Task 002 can point the same script at generated output to compare
generated versus manual support without reconstructing numbers by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
INVENTORY = EXAMPLE / "proof_inventory.toml"
SOURCES = ("src/ring_buffer.ads", "src/ring_buffer.adb")
CLIENT = ("proof/ring_buffer_client_proof.ads",
          "proof/ring_buffer_client_proof.adb")
TESTS = ("tests/ring_buffer_runtime_tests.adb",)

MECH_CATEGORIES = (
    "model_construction", "representation_predicate", "proof_index_mapping",
    "helper_lemma", "loop_invariant", "operation_refinement_contract",
    "proof_only_state_update", "other",
)


def is_code(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("--")


def sloc(path: Path) -> int:
    return sum(is_code(l) for l in
               path.read_text(encoding="utf-8").splitlines())


def count(rx: str, texts: list[str]) -> int:
    pattern = re.compile(rx, re.I | re.M)
    return sum(len(pattern.findall(t)) for t in texts)


def strip_comments(text: str) -> str:
    return "\n".join(l.split("--", 1)[0] for l in text.splitlines())


def classify(inv: dict, files: dict) -> tuple[list, dict, list]:
    owner: dict[tuple[str, int], str] = {}
    errors: list[str] = []
    artifacts = []
    for art in inv["artifact"]:
        lines = files[art["file"]]
        lo, hi = art["lines"]
        if not (1 <= lo <= hi <= len(lines)):
            errors.append(f"{art['name']}: range {lo}-{hi} out of bounds")
            continue
        if art["anchor"] not in lines[lo - 1]:
            errors.append(f"{art['name']}: anchor {art['anchor']!r} not on "
                          f"{art['file']}:{lo} "
                          f"(found {lines[lo - 1].strip()!r})")
        loc = 0
        for n in range(lo, hi + 1):
            key = (art["file"], n)
            if key in owner:
                errors.append(f"{art['name']}: line {n} already classified "
                              f"as {owner[key]}")
            owner[key] = art["name"]
            if is_code(lines[n - 1]):
                loc += 1
            else:
                errors.append(f"{art['name']}: {art['file']}:{n} is blank "
                              "or comment-only; ranges must cover code only")
        if (art["group"] == "mechanical"
                and art.get("category") not in MECH_CATEGORIES):
            errors.append(f"{art['name']}: unknown category "
                          f"{art.get('category')}")
        artifacts.append({**art, "loc": loc})
    return artifacts, owner, errors


def build() -> dict:
    inv = tomllib.loads(INVENTORY.read_text(encoding="utf-8"))
    files = {f: (EXAMPLE / f).read_text(encoding="utf-8").splitlines()
             for f in SOURCES}
    artifacts, owner, errors = classify(inv, files)

    production = sum(1 for f, lines in files.items()
                     for n, line in enumerate(lines, 1)
                     if is_code(line) and (f, n) not in owner)
    spec_loc = sum(a["loc"] for a in artifacts
                   if a["group"] == "specification")
    mech = {c: {"loc": 0, "artifacts": []} for c in MECH_CATEGORIES}
    for a in artifacts:
        if a["group"] == "mechanical":
            mech[a["category"]]["loc"] += a["loc"]
            if a["name"] not in mech[a["category"]]["artifacts"]:
                mech[a["category"]]["artifacts"].append(a["name"])

    src_text = [strip_comments("\n".join(files[f])) for f in SOURCES]
    ads = strip_comments("\n".join(files["src/ring_buffer.ads"]))
    client_text = [strip_comments((EXAMPLE / f).read_text(encoding="utf-8"))
                   for f in CLIENT]
    structure = {
        "ghost_declarations": count(r"\bGhost\b", src_text),
        "lemmas": count(r"procedure\s+Lemma_\w+", src_text),
        "loop_invariants": count(r"pragma\s+Loop_Invariant", src_text),
        "loop_variants": count(r"pragma\s+Loop_Variant", src_text),
        "assertions_in_package": count(r"pragma\s+Assert\b", src_text),
        "refined_postconditions": count(r"Refined_Post\s*=>", src_text),
        "type_invariants_or_predicates": count(
            r"(Type_Invariant|Dynamic_Predicate|Static_Predicate)\s*=>",
            src_text),
        "public_preconditions": count(r"\bPre\s*=>", [ads]),
        "public_postconditions": count(r"\bPost\s*=>", [ads]),
        "client_proof_assertions": count(r"pragma\s+Assert\b", client_text),
    }
    totals = {
        "production_loc": production,
        "specification_loc": spec_loc,
        "mechanical_loc": sum(v["loc"] for v in mech.values()),
        "package_total_loc": sum(sloc(EXAMPLE / f) for f in SOURCES),
        "client_proof_loc": sum(sloc(EXAMPLE / f) for f in CLIENT),
        "runtime_tests_loc": sum(sloc(EXAMPLE / f) for f in TESTS),
    }
    if (totals["production_loc"] + totals["specification_loc"]
            + totals["mechanical_loc"]) != totals["package_total_loc"]:
        errors.append("classification does not partition the package SLOC")
    keep = ("name", "group", "category", "entity", "file", "lines", "loc",
            "generic", "application_specific", "why")
    return {"errors": errors, "totals": totals, "mechanical": mech,
            "structure": structure,
            "artifacts": [{k: a[k] for k in keep if k in a}
                          for a in artifacts]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = build()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("SLOC = non-blank, non-comment source lines")
        for k, v in data["totals"].items():
            print(f"  {k:30} {v}")
        print("mechanical proof support by category (SLOC):")
        for c, v in data["mechanical"].items():
            print(f"  {c:30} {v['loc']:3}  {'; '.join(v['artifacts'])}")
        print("structure:")
        for k, v in data["structure"].items():
            print(f"  {k:30} {v}")
    for e in data["errors"]:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if data["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

