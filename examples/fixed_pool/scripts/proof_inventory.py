#!/usr/bin/env python3
"""Reproducible proof-support inventory for the fixed-pool benchmark.

Reads proof_inventory.toml, validates every classified line range against
its anchor text, checks that the classification partitions the package
SLOC, and reports production / specification / mechanical (P) SLOC,
mechanical SLOC per Task 003 category, generic mechanical SLOC and the
generic fraction G, and structural counts.

  python3 scripts/proof_inventory.py          # human-readable
  python3 scripts/proof_inventory.py --json   # machine-readable

Exit status is nonzero if any range drifts, overlaps, covers blank/comment
text, uses an unknown category, lacks a required field, or if the
partition does not add up.
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
SOURCES = ("src/fixed_pool.ads", "src/fixed_pool.adb")
CLIENT = ("proof/fixed_pool_client_proof.ads",
          "proof/fixed_pool_client_proof.adb")
TESTS = ("tests/fixed_pool_runtime_tests.adb",)

MECH_CATEGORIES = (
    "model_construction", "representation_invariant", "membership_mapping",
    "cardinality_relation", "helper_lemma", "loop_invariant",
    "operation_refinement_contract", "proof_assertion", "proof_only_helper",
    "proof_only_state_update", "other",
)
MECH_REQUIRED = ("entity", "generic", "application_specific", "why",
                 "ablation")


def is_code(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("--")


def sloc(path: Path) -> int:
    return sum(is_code(l) for l in
               path.read_text(encoding="utf-8").splitlines())


def strip_comments(text: str) -> str:
    return "\n".join(l.split("--", 1)[0] for l in text.splitlines())


def count(rx: str, texts: list[str]) -> int:
    pattern = re.compile(rx, re.I | re.M)
    return sum(len(pattern.findall(t)) for t in texts)


def check_artifact(art, files, owner, errors) -> int:
    lines = files[art["file"]]
    lo, hi = art["lines"]
    if not (1 <= lo <= hi <= len(lines)):
        errors.append(f"{art['name']}: range {lo}-{hi} out of bounds")
        return 0
    if art["anchor"] not in lines[lo - 1]:
        errors.append(f"{art['name']}: anchor {art['anchor']!r} not on "
                      f"{art['file']}:{lo} (found {lines[lo - 1].strip()!r})")
    loc = 0
    for n in range(lo, hi + 1):
        key = (art["file"], n)
        if key in owner:
            errors.append(f"{art['name']}: line {n} already classified as "
                          f"{owner[key]}")
        owner[key] = art["name"]
        if is_code(lines[n - 1]):
            loc += 1
        else:
            errors.append(f"{art['name']}: {art['file']}:{n} is blank or "
                          "comment-only; ranges must cover code only")
    if art["group"] not in ("specification", "mechanical"):
        errors.append(f"{art['name']}: unknown group {art['group']!r}")
    if art["group"] == "mechanical":
        if art.get("category") not in MECH_CATEGORIES:
            errors.append(f"{art['name']}: unknown category "
                          f"{art.get('category')!r}")
        for k in MECH_REQUIRED:
            if k not in art:
                errors.append(f"{art['name']}: missing field {k!r}")
        if art.get("generic") == art.get("application_specific"):
            errors.append(f"{art['name']}: generic and application_specific "
                          "must differ")
    return loc


def build() -> dict:
    inv = tomllib.loads(INVENTORY.read_text(encoding="utf-8"))
    files = {f: (EXAMPLE / f).read_text(encoding="utf-8").splitlines()
             for f in SOURCES}
    owner: dict[tuple[str, int], str] = {}
    errors: list[str] = []
    arts = []
    for art in inv["artifact"]:
        if art["file"] not in files:
            errors.append(f"{art['name']}: unknown file {art['file']}")
            continue
        arts.append({**art, "loc": check_artifact(art, files, owner, errors)})

    spec_loc = sum(a["loc"] for a in arts if a["group"] == "specification")
    mech = {c: {"loc": 0, "artifacts": []} for c in MECH_CATEGORIES}
    generic_loc = 0
    for a in arts:
        if a["group"] != "mechanical" or a.get("category") not in mech:
            continue
        mech[a["category"]]["loc"] += a["loc"]
        if a["name"] not in mech[a["category"]]["artifacts"]:
            mech[a["category"]]["artifacts"].append(a["name"])
        if a.get("generic"):
            generic_loc += a["loc"]
    mech_loc = sum(v["loc"] for v in mech.values())
    package_loc = sum(sloc(EXAMPLE / f) for f in SOURCES)
    classified = sum(1 for (f, n) in owner if is_code(files[f][n - 1]))
    production = package_loc - classified
    if production + spec_loc + mech_loc != package_loc:
        errors.append("classification does not partition the package SLOC")

    src_text = [strip_comments("\n".join(files[f])) for f in SOURCES]
    client_text = [strip_comments((EXAMPLE / f).read_text(encoding="utf-8"))
                   for f in CLIENT]
    structure = {
        "ghost_declarations": count(r"\bGhost\b", src_text),
        "lemmas": count(r"procedure\s+Lemma_\w+", src_text),
        "loop_invariants": count(r"pragma\s+Loop_Invariant", src_text),
        "assertions_in_package": count(r"pragma\s+Assert\b", src_text),
        "refined_postconditions": count(r"Refined_Post\s*=>", src_text),
        "type_invariants_or_predicates": count(
            r"(Type_Invariant|Dynamic_Predicate|Static_Predicate)\s*=>",
            src_text),
        "public_preconditions": count(r"\bPre\s*=>", src_text[:1]),
        "public_postconditions": count(r"\bPost\s*=>", src_text[:1]),
        "client_proof_assertions": count(r"pragma\s+Assert\b", client_text),
    }
    totals = {
        "production_loc": production,
        "specification_loc": spec_loc,
        "mechanical_loc_P": mech_loc,
        "generic_mechanical_loc": generic_loc,
        "generic_fraction_G": (round(generic_loc / mech_loc, 4)
                               if mech_loc else 0.0),
        "package_total_loc": package_loc,
        "client_proof_loc": sum(sloc(EXAMPLE / f) for f in CLIENT),
        "runtime_tests_loc": sum(sloc(EXAMPLE / f) for f in TESTS),
    }
    keep = ("name", "group", "category", "entity", "file", "lines", "loc",
            "generic", "application_specific", "ablation", "why")
    return {"inventory": INVENTORY.name, "errors": errors, "totals": totals,
            "mechanical": mech, "structure": structure,
            "artifacts": [{k: a[k] for k in keep if k in a} for a in arts]}


def report(data: dict) -> None:
    print(f"== fixed_pool ({data['inventory']}) ==")
    print("SLOC = non-blank, non-comment source lines")
    for k, v in data["totals"].items():
        print(f"  {k:30} {v}")
    print("mechanical proof support by category (SLOC):")
    for c, v in data["mechanical"].items():
        print(f"  {c:30} {v['loc']:3}  {'; '.join(v['artifacts'])}")
    print("structure:")
    for k, v in data["structure"].items():
        print(f"  {k:30} {v}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = build()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        report(data)
    for e in data["errors"]:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if data["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
