#!/usr/bin/env python3
"""Reproducible proof-support inventory for the fixed-pool benchmark.

Reads proof_inventory.toml, validates every classified line range against
its anchor text, checks that the classification partitions the package
SLOC, and reports production / specification / mechanical (P) SLOC,
mechanical SLOC per Task 003 category, generic mechanical SLOC and the
generic fraction G, and structural counts.

  python3 scripts/proof_inventory.py          # human-readable
  python3 scripts/proof_inventory.py --json   # machine-readable
  python3 scripts/proof_inventory.py --variant library_backed
      Task 004: classifies variants/library_backed/ with
      proof_inventory_library_backed.toml; its mechanical total is the
      residual per-instance support R. Also reports the reusable library
      size L (proof_patterns/src) and the generic actual count A.
  python3 scripts/proof_inventory.py --all    # both variants (CI)

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
REPO = EXAMPLE.parents[1]
VARIANTS = {
    # Task 003 manual baseline (unchanged)
    "baseline": {"inventory": EXAMPLE / "proof_inventory.toml",
                 "sources": ("src/fixed_pool.ads", "src/fixed_pool.adb")},
    # Task 004 library-backed variant
    "library_backed": {
        "inventory": EXAMPLE / "proof_inventory_library_backed.toml",
        "sources": ("variants/library_backed/fixed_pool.ads",
                    "variants/library_backed/fixed_pool.adb")},
}
VARIANT_ALIASES = {"manual": "baseline"}
LIBRARY_SOURCES = ("proof_patterns/src/spark_refine_prefix_sets.ads",
                   "proof_patterns/src/spark_refine_prefix_sets.adb")
VALIDATION_DIR = "proof_patterns/validation/src"
CLIENT = ("proof/fixed_pool_client_proof.ads",
          "proof/fixed_pool_client_proof.adb")
TESTS = ("tests/fixed_pool_runtime_tests.adb",)

MECH_CATEGORIES = (
    "model_construction", "representation_invariant", "membership_mapping",
    "cardinality_relation", "helper_lemma", "loop_invariant",
    "operation_refinement_contract", "proof_assertion", "proof_only_helper",
    "proof_only_state_update", "library_configuration", "other",
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


def build(variant: str = "baseline") -> dict:
    INVENTORY = VARIANTS[variant]["inventory"]
    SOURCES = VARIANTS[variant]["sources"]
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
    if variant == "library_backed":
        totals["residual_mechanical_loc_R"] = mech_loc
    return {"variant": variant, "inventory": INVENTORY.name,
            "errors": errors, "totals": totals,
            "mechanical": mech, "structure": structure,
            "artifacts": [{k: a[k] for k in keep if k in a} for a in arts]}


def library_metrics(errors: list[str]) -> dict:
    """Size L of the reusable proof library and the number A of semantic
    generic actuals a caller supplies. Every library line is proof-only
    (all entities are Ghost), so library SLOC == library proof-only SLOC."""
    spec, body = (REPO / f for f in LIBRARY_SOURCES)
    texts = [strip_comments(p.read_text(encoding="utf-8"))
             for p in (spec, body)]
    head, sep, rest = texts[0].partition("package SPARK_Refine_Prefix_Sets")
    if not sep:
        errors.append("library spec: package header not found")
    formals = re.findall(r"^\s*(type\s+\w+|with\s+package\s+\w+|"
                         r"with\s+function\s+\w+)", head, re.M)
    public_api = len(re.findall(r"^\s*(function|procedure|subtype)\s+\w+",
                                rest, re.M))
    val = sorted((REPO / VALIDATION_DIR).glob("*.ad[sb]"))
    return {
        "library_loc_L": sloc(spec) + sloc(body),
        "library_spec_loc": sloc(spec),
        "library_body_loc": sloc(body),
        "library_proof_only_loc": sloc(spec) + sloc(body),
        "library_generic_formal_part_loc": sum(
            is_code(l) for l in head.splitlines()),
        "generic_actuals_A": len(formals),
        "generic_formals": [" ".join(f.split()) for f in formals],
        "library_public_ghost_entities": public_api,
        "library_helper_lemmas": count(r"procedure\s+Lemma_\w+", texts[1:]),
        "library_loop_invariants": count(r"pragma\s+Loop_Invariant", texts),
        "library_assertions": count(r"pragma\s+Assert\b", texts),
        "validation_instances_loc": sum(sloc(p) for p in val),
        "validation_instance_units": len(
            [p for p in val if p.name.startswith("validate_")]),
    }


def report(data: dict) -> None:
    print(f"== fixed_pool {data['variant']} ({data['inventory']}) ==")
    print("SLOC = non-blank, non-comment source lines")
    for k, v in data["totals"].items():
        print(f"  {k:30} {v}")
    print("mechanical proof support by category (SLOC):")
    for c, v in data["mechanical"].items():
        print(f"  {c:30} {v['loc']:3}  {'; '.join(v['artifacts'])}")
    print("structure:")
    for k, v in data["structure"].items():
        print(f"  {k:30} {v}")
    if "library" in data:
        print("reusable proof library (proof_patterns/src, not in R):")
        for k, v in data["library"].items():
            print(f"  {k:30} {v}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--variant", default="baseline",
                    choices=tuple(VARIANTS) + tuple(VARIANT_ALIASES))
    ap.add_argument("--all", action="store_true",
                    help="check and report every variant")
    args = ap.parse_args()
    names = (tuple(VARIANTS) if args.all
             else (VARIANT_ALIASES.get(args.variant, args.variant),))
    failed = False
    out = []
    for name in names:
        data = build(name)
        if name == "library_backed":
            data["library"] = library_metrics(data["errors"])
        out.append(data)
        if not args.json:
            report(data)
        for e in data["errors"]:
            print(f"ERROR ({name}): {e}", file=sys.stderr)
        failed |= bool(data["errors"])
    if args.json:
        print(json.dumps(out if args.all else out[0], indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
