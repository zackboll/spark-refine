#!/usr/bin/env python3
"""Ablation study: is each manual proof artifact actually necessary?

For each case, a scratch copy of the selected implementation is made under
obj/ablation_src/<variant>/<case>, one proof artifact is removed (or, for
"alt_*" cases, replaced by an alternative mechanism), GNATprove is run with
the project's normal proof switches, and the unproved (rule, entity) pairs
are read back from SARIF. Results are written to
obj/ablation_summary[_<variant>][_<switches>].json and printed.

This is a measurement tool for BASELINE_METRICS.md / REFACTOR_METRICS.md,
not a CI gate.

  python3 scripts/ablate_proof_support.py [--variant head_tail_count]
                                          [--extra-switch=--level=0 ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys

import check_proof_results as g

LI_LAST = "         pragma Loop_Invariant (Sequences.Last (R) = J);\n"
LI_ELEM = ("         pragma Loop_Invariant\n"
           "           (for all K in 1 .. J =>\n"
           "              Sequences.Get (R, K)\n"
           "              = B.Content (Physical_Index (B.First, K - 1)));\n")
REFINED_POST = (
    "   with Refined_Post =>\n"
    "     Sequences.Last (Model'Result) = B.Length\n"
    "     and then (for all K in 1 .. B.Length =>\n"
    "                 Sequences.Get (Model'Result, K)\n"
    "                 = B.Content (Physical_Index (B.First, K - 1)))\n")
MODEL_BOUND = ("   with Ghost,\n"
               "        Post => Sequences.Last (Model'Result) <= Max_Size;")
EMPTY_POST = ("\n   with Post => Is_Empty'Result = "
              "(Sequences.Last (Model (B)) = 0);")
FULL_POST = ("\n   with Post => Is_Full'Result = "
             "(Sequences.Last (Model (B)) = Max_Size);")

# case name -> list of (file, find, replace)
# Representation A (Task 001, src/). Names and output paths are unchanged.
CASES = {
    "baseline": [],
    "no_loop_invariant_length": [("ring_buffer.adb", LI_LAST, "")],
    "no_loop_invariant_elements": [("ring_buffer.adb", LI_ELEM, "")],
    "no_loop_invariants": [("ring_buffer.adb", LI_LAST, ""),
                           ("ring_buffer.adb", LI_ELEM, "")],
    "no_refined_post": [("ring_buffer.adb", REFINED_POST, "")],
    "no_public_model_bound": [("ring_buffer.ads", MODEL_BOUND,
                               "   with Ghost;")],
    "no_is_empty_post": [("ring_buffer.ads", EMPTY_POST, "")],
    "no_is_full_post": [("ring_buffer.ads", FULL_POST, "")],
}

# Representation B (Task 002, variants/head_tail_count/).
B_LI_ELEM = LI_ELEM.replace("B.First", "B.Head")
B_REFINED_POST = (REFINED_POST.replace("B.Length", "B.Count")
                  .replace("B.First", "B.Head"))
B_INVARIANT = ("   end record\n"
               "   with Type_Invariant =>\n"
               "     Buffer.Tail = Physical_Index (Buffer.Head, Buffer.Count);\n")
B_CLEAR = ("      B.Head  := Storage_Index'First;\n"
           "      B.Tail  := Storage_Index'First;\n"
           "      B.Count := 0;\n")
B_PUSH = ("      B.Tail  := Physical_Index (B.Tail, 1);\n"
          "      B.Count := B.Count + 1;\n")
B_POP = ("      B.Head  := Physical_Index (B.Head, 1);\n"
         "      B.Count := B.Count - 1;\n")
# Dynamic_Predicate variant: a component-wise update would transiently
# violate the predicate, so the three mutators must assign whole records.
B_DP = [
    ("ring_buffer.ads", "   with Type_Invariant =>\n",
     "   with Dynamic_Predicate =>\n"),
    ("ring_buffer.adb", B_CLEAR,
     "      B := (B with delta Head  => Storage_Index'First,\n"
     "                         Tail  => Storage_Index'First,\n"
     "                         Count => 0);\n"),
    ("ring_buffer.adb", B_PUSH,
     "      B := (B with delta Tail  => Physical_Index (B.Tail, 1),\n"
     "                         Count => B.Count + 1);\n"),
    ("ring_buffer.adb", B_POP,
     "      B := (B with delta Head  => Physical_Index (B.Head, 1),\n"
     "                         Count => B.Count - 1);\n"),
]
B_CASES = {
    "baseline": [],
    # mechanical proof support
    "no_type_invariant": [("ring_buffer.ads", B_INVARIANT,
                           "   end record;\n")],
    "no_loop_invariant_length": [("ring_buffer.adb", LI_LAST, "")],
    "no_loop_invariant_elements": [("ring_buffer.adb", B_LI_ELEM, "")],
    "no_loop_invariants": [("ring_buffer.adb", LI_LAST, ""),
                           ("ring_buffer.adb", B_LI_ELEM, "")],
    "no_refined_post": [("ring_buffer.adb", B_REFINED_POST, "")],
    # authoritative public specification (for parity with A; not support)
    "no_public_model_bound": [("ring_buffer.ads", MODEL_BOUND,
                               "   with Ghost;")],
    "no_is_empty_post": [("ring_buffer.ads", EMPTY_POST, "")],
    "no_is_full_post": [("ring_buffer.ads", FULL_POST, "")],
    # alternative invariant mechanisms
    "alt_dynamic_predicate": B_DP[:1],
    "alt_dynamic_predicate_whole_record": B_DP,
    # control: is the invariant needed only because Push consumes Tail?
    # (Push computes the slot from Head/Count, ignoring Tail - NOT the
    # production design, which must use Tail.)
    "control_push_ignores_tail_no_invariant": [
        ("ring_buffer.ads", B_INVARIANT, "   end record;\n"),
        ("ring_buffer.adb", "B.Content (B.Tail) := E;",
         "B.Content (Physical_Index (B.Head, B.Count)) := E;")],
}

VARIANT_CASES = {"first_length": CASES, "head_tail_count": B_CASES}


def fix_semicolons(text: str) -> str:
    # Removing a trailing "with Post => ...;" aspect leaves the function
    # declaration without its terminating semicolon; restore it.
    return text.replace("return Boolean\n\n", "return Boolean;\n\n")


def run_case(name: str, edits: list, extra: list[str],
             variant_name: str = "first_length") -> dict:
    # first_length keeps the Task 001 paths (obj/ablation_src/<case>).
    tag = "" if variant_name == "first_length" else "htc_"
    dest = g.OBJ / "ablation_src" / f"{tag}{name}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    impl = g.EXAMPLE / g.VARIANTS[variant_name]["impl"]
    for f in impl.glob("*.ad[sb]"):
        shutil.copy2(f, dest / f.name)
    for file, find, replace in edits:
        path = dest / file
        text = path.read_text(encoding="utf-8")
        if text.count(find) != 1:
            raise g.GateError(f"{name}: anchor not found exactly once in {file}")
        path.write_text(fix_semicolons(text.replace(find, replace)),
                        encoding="utf-8")
    variant = f"ablation_{tag}{name}"
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
        proved = len(res["proved"])
    except g.GateError as exc:
        unproved, proved = [f"ANALYSIS_FAILED: {exc}"], 0
    return {"case": name, "returncode": run["returncode"], "proved": proved,
            "unproved": unproved, "wall_seconds": round(run["wall_seconds"], 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-switch", action="append", default=[],
                    help="additional gnatprove switch, e.g. --level=0")
    ap.add_argument("--variant", choices=tuple(VARIANT_CASES),
                    default="first_length")
    ap.add_argument("--only", nargs="*", help="case names to run")
    args = ap.parse_args()
    results = []
    for name, edits in VARIANT_CASES[args.variant].items():
        if args.only and name not in args.only:
            continue
        r = run_case(name, edits, args.extra_switch, args.variant)
        results.append(r)
        print(f"{name:30} rc={r['returncode']} proved={r['proved']:3} "
              f"unproved={r['unproved']}", flush=True)
    suffix = "".join(s.strip("-").replace("=", "") for s in args.extra_switch)
    vtag = "" if args.variant == "first_length" else f"_{args.variant}"
    out = (g.OBJ / f"ablation_summary{vtag}"
           f"{('_' + suffix) if suffix else ''}.json")
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
