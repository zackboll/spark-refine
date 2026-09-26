#!/usr/bin/env python3
"""Ablation study: is each fixed-pool proof artifact actually necessary?

For each case, a scratch copy of src/ is made under obj/ablation_src/<case>,
one proof artifact is removed (or, for "alt_*"/"weak_*" cases, replaced by a
weaker or alternative form), GNATprove is run with the project's normal
proof switches, and the unproved (rule, entity) pairs are read back from
SARIF. Results are written to obj/ablation_summary[_<switches>].json.

"mask_*" cases remove the representation invariant from a negative fixture
to expose functional failures that an invariant failure may mask (Task 002
observation R3, re-checked here per Task 003 section 23).

This is a measurement tool for BASELINE_METRICS.md, not a CI gate.

  python3 scripts/ablate_proof_support.py [--only CASE ...]
                                          [--extra-switch=--prover=z3 ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib

import check_proof_results as g

ADS, ADB = "fixed_pool.ads", "fixed_pool.adb"

INVARIANT = ("   end record\n"
             "   with Type_Invariant =>\n"
             "     (for all I in 1 .. Pool.Top =>\n"
             "        (for all J in 1 .. I - 1 =>\n"
             "           Pool.Free_Stack (I) /= Pool.Free_Stack (J)));\n")
NO_INVARIANT = "   end record;\n"
TOP_DEFAULT = "      Top        : Pool_Count := 0;\n"
TOP_NO_DEFAULT = "      Top        : Pool_Count;\n"

RP_LENGTH = ("     Id_Sets.Length (Free_Model'Result) = To_Big_Integer (P.Top)\n"
             "     and (for all Id in Object_Id =>\n")
RP_MEMBER = ("     and (for all Id in Object_Id =>\n"
             "            Id_Sets.Contains (Free_Model'Result, Id)\n"
             "            = (for some I in 1 .. P.Top => P.Free_Stack (I) = Id))\n")
RP_ALL = ("   with Refined_Post =>\n"
          "     Id_Sets.Length (Free_Model'Result) = To_Big_Integer (P.Top)\n"
          + RP_MEMBER)
LI_LENGTH = ("         pragma Loop_Invariant (Id_Sets.Length (R) = "
             "To_Big_Integer (I));\n")
LI_MEMBER = ("         pragma Loop_Invariant\n"
             "           (for all Id in Object_Id =>\n"
             "              Id_Sets.Contains (R, Id)\n"
             "              = (for some K in 1 .. I => P.Free_Stack (K) = Id));\n")
LEMMA_CALL = "      Lemma_Universe_Bound (Id_Sets.Add (Free_Model (P), Id));\n"
LEMMA_ASSERT = ("      pragma Assert (Id_Sets.Num_Overlaps (S, U) = "
                "Id_Sets.Length (S));\n")
LEMMA_BODY_DECLS = (
    "      U : constant Id_Sets.Set :=\n"
    "        Free_Model ((Free_Stack => [for I in Object_Id => I],\n"
    "                     Top        => Max_Objects));\n"
    "   begin\n" + LEMMA_ASSERT)

# case name -> list of (file, find, replace)
CASES: dict[str, list] = {
    "baseline": [],
    # ---- representation invariant (uniqueness) --------------------------
    "no_uniqueness_invariant": [(ADS, INVARIANT, NO_INVARIANT)],
    "no_top_default": [(ADS, TOP_DEFAULT, TOP_NO_DEFAULT)],
    "alt_dynamic_predicate": [
        (ADS, "   with Type_Invariant =>\n", "   with Dynamic_Predicate =>\n")],
    # ---- Free_Model refinement relation --------------------------------
    "no_refined_post": [(ADB, RP_ALL, "")],
    "no_refined_post_cardinality": [
        (ADB, RP_LENGTH, "     (for all Id in Object_Id =>\n")],
    "no_refined_post_membership": [(ADB, RP_MEMBER, "")],
    "weak_membership_prefix_in_model": [
        (ADB, RP_MEMBER,
         "     and (for all I in 1 .. P.Top =>\n"
         "            Id_Sets.Contains (Free_Model'Result, P.Free_Stack (I)))\n"),
        (ADB, LI_MEMBER,
         "         pragma Loop_Invariant\n"
         "           (for all K in 1 .. I =>\n"
         "              Id_Sets.Contains (R, P.Free_Stack (K)));\n")],
    # ---- model-construction loop invariants -----------------------------
    "no_loop_invariant_cardinality": [(ADB, LI_LENGTH, "")],
    "no_loop_invariant_membership": [(ADB, LI_MEMBER, "")],
    "no_loop_invariants": [(ADB, LI_LENGTH, ""), (ADB, LI_MEMBER, "")],
    # ---- finite-universe bound lemma -----------------------------------
    "no_lemma_call": [(ADB, LEMMA_CALL, "")],
    "no_lemma_assert": [(ADB, LEMMA_ASSERT, "      null;\n")],
    "no_lemma_universe_witness": [
        (ADB, LEMMA_BODY_DECLS, "   begin\n      null;\n")],
    # ---- authoritative-spec clauses (measured only; not mechanical) ------
    "spec_no_public_model_bound": [
        (ADS, "   with Ghost,\n        Post => Id_Sets.Length (Free_Model'Result)\n"
              "                <= To_Big_Integer (Max_Objects);\n",
         "   with Ghost;\n")],
    "spec_no_count_posts": [
        (ADS, "\n                and Free_Count (P) = Free_Count (P)'Old - 1;\n",
         ";\n"),
        (ADS, "\n                and Free_Count (P) = Free_Count (P)'Old + 1;\n",
         ";\n")],
}


def fixture_edits(name: str) -> list:
    spec = tomllib.loads((g.NEGATIVE / name / "fault.toml").read_text(
        encoding="utf-8"))
    return [(e["file"], e["find"], e["replace"]) for e in spec["edit"]]


def mask_cases() -> dict:
    """Every negative fixture whose normal failure includes an invariant
    check, re-run with the representation invariant removed."""
    out = {}
    for path in sorted(g.NEGATIVE.glob("*/fault.toml")):
        spec = tomllib.loads(path.read_text(encoding="utf-8"))
        if any(e["rule"] == "VC_INVARIANT_CHECK" for e in spec["expect"]):
            out[f"mask_{spec['name']}"] = (
                fixture_edits(path.parent.name)
                + [(ADS, INVARIANT, NO_INVARIANT)])
    return out


def run_case(name: str, edits: list, extra: list[str]) -> dict:
    dest = g.OBJ / "ablation_src" / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in g.SRC.glob("*.ad[sb]"):
        shutil.copy2(f, dest / f.name)
    for file, find, replace in edits:
        path = dest / file
        text = path.read_text(encoding="utf-8")
        if text.count(find) != 1:
            raise g.GateError(f"{name}: anchor not found exactly once in "
                              f"{file}: {find!r}")
        path.write_text(text.replace(find, replace), encoding="utf-8")
    variant = f"ablation_{name}"
    old = g.gnatprove_cmd
    g.gnatprove_cmd = lambda v, i: old(v, i) + extra
    try:
        run = g.run_gnatprove(variant, dest.relative_to(g.EXAMPLE).as_posix())
    finally:
        g.gnatprove_cmd = old
    try:
        res = g.load_results(run["out_dir"])
        unproved = sorted({f"{u['rule']}@{u['entity']}"
                           for u in res["unproved"]})
        n_unproved = len(res["unproved"])
        proved = len(res["proved"])
    except g.GateError as exc:
        unproved, n_unproved, proved = [f"ANALYSIS_FAILED: {exc}"], -1, 0
    return {"case": name, "returncode": run["returncode"], "proved": proved,
            "unproved_count": n_unproved, "unproved": unproved,
            "wall_seconds": round(run["wall_seconds"], 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-switch", action="append", default=[],
                    help="additional gnatprove switch, e.g. --prover=z3")
    ap.add_argument("--only", nargs="*", help="case names to run")
    args = ap.parse_args()
    cases = {**CASES, **mask_cases()}
    results = []
    for name, edits in cases.items():
        if args.only and name not in args.only:
            continue
        r = run_case(name, edits, args.extra_switch)
        results.append(r)
        print(f"{name:34} rc={r['returncode']} proved={r['proved']:3} "
              f"unproved={r['unproved_count']} {r['unproved']}", flush=True)
    suffix = "".join(s.strip("-").replace("=", "") for s in args.extra_switch)
    out = g.OBJ / f"ablation_summary{('_' + suffix) if suffix else ''}.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
