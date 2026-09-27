#!/usr/bin/env python3
"""Ablation study for the Task 004 library-backed fixed pool.

Measurement only (not a CI gate). Three groups of cases, each run from a
scratch copy under obj/ablation_lib_src/<case>/{app,lib}:

  residual_*   remove / replace one remaining per-instance artifact in
               variants/library_backed (Task 004 section 36). Proves the
               fixed pool.
  lib_*        remove one proof fact inside the reusable library
               (proof_patterns/src, section 37). Proves the fixed pool AND
               the independent validation instances
               (proof_patterns/validation), because a fact may be needed
               only by the pattern's wider contract.
  mask_*       every library-backed negative fixture whose normal failure
               includes VC_INVARIANT_CHECK, re-run with the library-backed
               uniqueness invariant removed (section 29).

Unproved (rule, entity, file:line) triples are read back from SARIF.
Output: obj/ablation_library_backed[_<switches>].json

  python3 scripts/ablate_library_backed.py [--only CASE ...]
                                           [--extra-switch=--prover=z3 ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import tomllib

import check_proof_results as g

APP_DIR = g.EXAMPLE / g.LIBRARY_BACKED
LIB_DIR = g.REPO / "proof_patterns" / "src"
VALIDATION_GPR = (g.REPO / "proof_patterns" / "validation"
                  / "prefix_sets_validation.gpr")
ADS, ADB = "fixed_pool.ads", "fixed_pool.adb"
LADS, LADB = "spark_refine_prefix_sets.ads", "spark_refine_prefix_sets.adb"

INVARIANT = ("   end record\n"
             "   with Type_Invariant => Free_Prefix.Is_Unique "
             "(Pool.Free_Stack, Pool.Top);\n")
NO_INVARIANT = "   end record;\n"
LOCAL_INVARIANT = ("   end record\n"
                   "   with Type_Invariant =>\n"
                   "     (for all I in 1 .. Pool.Top =>\n"
                   "        (for all J in 1 .. I - 1 =>\n"
                   "           Pool.Free_Stack (I) /= Pool.Free_Stack (J)));\n")
TOP_DEFAULT = "      Top        : Pool_Count := 0;\n"
RELEASE_BODY = "   begin\n      P.Top := P.Top + 1;\n"
RELEASE_WITH_LEMMA = ("   begin\n      Free_Prefix.Lemma_Can_Add "
                      "(Free_Model (P), Id);\n      P.Top := P.Top + 1;\n")

MODEL_PRE = "        Pre    => Is_Unique (Storage, Count),\n"
MODEL_POST_CARD = ("          Element_Sets.Length (Model'Result) = "
                   "To_Big_Integer (Integer (Count))\n"
                   "          and (for all E in Element_Type =>\n")
MODEL_POST_CARD_REPL = "          (for all E in Element_Type =>\n"
MODEL_POST_MEMBER = ("          and (for all E in Element_Type =>\n"
                     "                 Element_Sets.Contains (Model'Result, E)\n"
                     "                 = In_Prefix (Storage, Count, E))\n")
MODEL_POST_ROOM = ("                 = In_Prefix (Storage, Count, E))\n"
                   "          and (To_Big_Integer (Integer (Count)) < "
                   "Universe_Size\n"
                   "               or else (for all E in Element_Type =>\n"
                   "                          In_Prefix (Storage, Count, E)));\n")
MODEL_POST_ROOM_REPL = "                 = In_Prefix (Storage, Count, E));\n"
MODEL_LI_CARD = ("         pragma Loop_Invariant\n"
                 "           (Element_Sets.Length (R)\n"
                 "            = To_Big_Integer (Integer ((I - Index_Type'First)"
                 " + 1)));\n")
MODEL_LI_MEMBER = ("         pragma Loop_Invariant\n"
                   "           (for all E in Element_Type =>\n"
                   "              Element_Sets.Contains (R, E)\n"
                   "              = (for some K in Index_Type'First .. I => "
                   "Storage (K) = E));\n")
MODEL_LEMMA_CALL = "      Lemma_Universe_Bound (R);\n"
LEMMA_ASSERT = ("      pragma Assert (Element_Sets.Num_Overlaps (S, U)\n"
                "                     = Element_Sets.Length (S));\n")
UNIVERSE_LI_CARD = ("         pragma Loop_Invariant\n"
                    "           (Element_Sets.Length (U)\n"
                    "            = To_Big_Integer ((Element_Type'Pos (E)\n"
                    "                               - Element_Type'Pos "
                    "(Element_Type'First)) + 1));\n")
UNIVERSE_LI_MEMBER = ("         pragma Loop_Invariant\n"
                      "           (for all X in Element_Type =>\n"
                      "              Element_Sets.Contains (U, X) = "
                      "(X <= E));\n")
CAN_ADD_BODY = "      Lemma_Universe_Bound (S);\n   end Lemma_Can_Add;"
CAN_ADD_NULL = "      null;\n   end Lemma_Can_Add;"

# case -> (application edits, library edits); each edit = (file, find, repl)
CASES: dict[str, tuple[list, list]] = {
    "baseline": ([], []),
    # ---- residual per-instance artifacts (section 36) --------------------
    "residual_no_invariant": ([(ADS, INVARIANT, NO_INVARIANT)], []),
    "residual_no_top_default": (
        [(ADS, TOP_DEFAULT, "      Top        : Pool_Count;\n")], []),
    "residual_local_quantified_invariant": (
        [(ADS, INVARIANT, LOCAL_INVARIANT)], []),
    "residual_with_explicit_lemma_call": (
        [(ADB, RELEASE_BODY, RELEASE_WITH_LEMMA)], []),
    # ---- reusable-library internal facts (section 37) --------------------
    "lib_no_model_precondition": ([], [(LADS, MODEL_PRE, "")]),
    "lib_no_model_post_cardinality": (
        [], [(LADS, MODEL_POST_CARD, MODEL_POST_CARD_REPL)]),
    "lib_no_model_post_membership": ([], [(LADS, MODEL_POST_MEMBER, "")]),
    "lib_no_model_post_room": (
        [], [(LADS, MODEL_POST_ROOM, MODEL_POST_ROOM_REPL)]),
    "lib_no_model_loop_invariant_cardinality": (
        [], [(LADB, MODEL_LI_CARD, "")]),
    "lib_no_model_loop_invariant_membership": (
        [], [(LADB, MODEL_LI_MEMBER, "")]),
    "lib_no_universe_lemma_in_model": ([], [(LADB, MODEL_LEMMA_CALL, "")]),
    "lib_no_num_overlaps_assert": ([], [(LADB, LEMMA_ASSERT, "")]),
    "lib_no_universe_loop_invariants": (
        [], [(LADB, UNIVERSE_LI_CARD, ""), (LADB, UNIVERSE_LI_MEMBER, "")]),
    "lib_no_can_add_body": ([], [(LADB, CAN_ADD_BODY, CAN_ADD_NULL)]),
}


def mask_cases() -> dict:
    neg = g.VARIANTS["library_backed"]["negative"]
    out = {}
    for path in sorted(neg.glob("*/fault.toml")):
        spec = tomllib.loads(path.read_text(encoding="utf-8"))
        if any(e["rule"] == "VC_INVARIANT_CHECK" for e in spec["expect"]):
            edits = [(e["file"], e["find"], e["replace"])
                     for e in spec["edit"]]
            out[f"mask_{spec['name']}"] = (
                edits + [(ADS, INVARIANT, NO_INVARIANT)], [])
    return out


def materialise(src, dest, edits, case) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in src.glob("*.ad[sb]"):
        shutil.copy2(f, dest / f.name)
    for file, find, replace in edits:
        path = dest / file
        text = path.read_text(encoding="utf-8")
        if text.count(find) != 1:
            raise g.GateError(f"{case}: anchor occurs {text.count(find)} "
                              f"times in {file}: {find!r}")
        path.write_text(text.replace(find, replace), encoding="utf-8")


def bad_results(sarif_path) -> list[str] | None:
    """Unproved (rule@entity (file:line)) from a SARIF file, or None."""
    if not sarif_path.is_file():
        return None
    data = json.loads(sarif_path.read_text(encoding="utf-8"))
    bad = set()
    for r in data["runs"][0]["results"]:
        if r["kind"] == "pass":
            continue
        loc = r["locations"][0]
        uri = loc["physicalLocation"]["artifactLocation"]["uri"]
        if g.is_allowed_warning(r["ruleId"], uri, r["message"]["text"]):
            continue
        ent = (loc.get("logicalLocations") or [{}])[0].get("name", "")
        line = loc["physicalLocation"].get("region", {}).get("startLine")
        bad.add(f"{r['ruleId']}@{ent} ({uri}:{line})")
    return sorted(bad)


def run_validation(case, lib_dest, extra) -> dict:
    obj = g.REPO / "proof_patterns" / "validation" / "obj"
    if obj.exists():
        shutil.rmtree(obj)
    cmd = g.exec_prefix() + [
        "gnatprove", "-P", str(VALIDATION_GPR), "-j0",
        f"-XPROOF_PATTERNS_SRC={lib_dest}",
        f"-XPROOF_PATTERNS_VARIANT=ablation_{case}"] + extra
    proc = subprocess.run(cmd, cwd=VALIDATION_GPR.parent,
                          capture_output=True, text=True)
    bad = bad_results(obj / "gnatprove" / "gnatprove.sarif")
    if bad is None:
        bad = ["ANALYSIS_FAILED"]
    return {"returncode": proc.returncode, "unproved_count": len(bad),
            "unproved": bad}


def run_case(name, app_edits, lib_edits, extra) -> dict:
    base = g.OBJ / "ablation_lib_src" / name
    app_dest, lib_dest = base / "app", base / "lib"
    materialise(APP_DIR, app_dest, app_edits, name)
    materialise(LIB_DIR, lib_dest, lib_edits, name)
    lib_switches = [f"-XPROOF_PATTERNS_SRC={lib_dest}",
                    f"-XPROOF_PATTERNS_VARIANT=ablation_{name}"]
    old = g.gnatprove_cmd
    g.gnatprove_cmd = lambda v, i: old(v, i) + lib_switches + extra
    try:
        run = g.run_gnatprove(f"ablation_lib_{name}",
                              app_dest.relative_to(g.EXAMPLE).as_posix())
    finally:
        g.gnatprove_cmd = old
    bad = bad_results(run["out_dir"] / "gnatprove.sarif")
    row = {"case": name, "returncode": run["returncode"],
           "wall_seconds": round(run["wall_seconds"], 2),
           "fixed_pool": {"unproved_count": -1 if bad is None else len(bad),
                          "unproved": bad or (["ANALYSIS_FAILED"]
                                              if bad is None else [])}}
    if lib_edits or name == "baseline":
        row["validation"] = run_validation(name, lib_dest, extra)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-switch", action="append", default=[])
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    results = []
    for name, (app, lib) in {**CASES, **mask_cases()}.items():
        if args.only and name not in args.only:
            continue
        start = time.monotonic()
        r = run_case(name, app, lib, args.extra_switch)
        results.append(r)
        v = r.get("validation")
        print(f"{name:42} pool unproved={r['fixed_pool']['unproved_count']}"
              + (f" | validation unproved={v['unproved_count']}" if v else "")
              + f"  ({time.monotonic() - start:.1f}s)", flush=True)
        for u in r["fixed_pool"]["unproved"]:
            print(f"    pool:       {u}")
        for u in (v or {}).get("unproved", [])[:10]:
            print(f"    validation: {u}")
    suffix = "".join(s.strip("-").replace("=", "") for s in args.extra_switch)
    out = g.OBJ / ("ablation_library_backed"
                   + (f"_{suffix}" if suffix else "") + ".json")
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
