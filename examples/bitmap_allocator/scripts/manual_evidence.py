#!/usr/bin/env python3
"""Sequential Task 019 manual proof runs and structural result inventory.

Generated logs/summaries stay in obj; English prose is not a proof gate.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "variants/manual"
OUT = ROOT / "obj/manual/gnatprove"


def trust_scan() -> None:
    patterns = {
        "assume": r"\bpragma\s+Assume\b|\bAssume\s*=>",
        "axiom": r"\bAxiom\b|External_Axiomatization",
        "justification": r"False_Positive|Intentional",
        "suppression": r"Skip_(Flow_And_)?Proof|pragma\s+(Suppress|Warnings)\b|--warnings=(off|continue)|-gnatp\b|-gnatw[.]?s\b",
        "import": r"pragma\s+Import\b|\bImport\s*(=>|;|,)",
        "unchecked_conversion": r"Unchecked_Conversion",
        "spark_off": r"SPARK_Mode\s*=>\s*Off",
    }
    failures = []
    for path in [*SRC.glob("*.ad?"), * (ROOT / "tests").glob("*.adb"), ROOT / "bitmap_allocator.gpr"]:
        text = "\n".join(line.split("--", 1)[0] for line in path.read_text().splitlines())
        for label, pattern in patterns.items():
            if label == "spark_off" and path.parent.name == "tests":
                continue  # Executable runtime driver is explicitly outside proof.
            if re.search(pattern, text, re.I):
                failures.append(f"{path.relative_to(ROOT)}: {label}")
    if failures:
        raise ValueError("Trust scan failed: " + "; ".join(failures))


def run(name: str) -> dict:
    shutil.rmtree(ROOT / "obj/manual", ignore_errors=True)
    start = time.monotonic()
    proc = subprocess.run(
        ["alr", "-n", "exec", "--", "gnatprove", "-P", "bitmap_allocator.gpr",
         "-j0", "--output-header", "--output=oneline"],
        cwd=ROOT, capture_output=True, text=True)
    dest = ROOT / "obj/measurements" / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "run.log").write_text(proc.stdout + proc.stderr)
    result = {"exit": proc.returncode, "wall_seconds": round(time.monotonic() - start, 3)}
    if not (OUT / "gnatprove.sarif").exists():
        result["complete"] = False
    else:
        shutil.copytree(OUT, dest / "gnatprove", dirs_exist_ok=True)
        sarif = json.loads((OUT / "gnatprove.sarif").read_text())
        failures = []
        warnings = []
        counts = collections.Counter()
        rules = collections.Counter()
        for r in sarif["runs"][0]["results"]:
            loc = r.get("locations", [{}])[0]
            phys = loc.get("physicalLocation", {})
            file = phys.get("artifactLocation", {}).get("uri", "")
            rule = r["ruleId"]
            if r.get("kind") != "pass":
                # Existing external Big_Integers foundation, not user proof support.
                if (rule == "error" and Path(file).name == "a-nbnbin.ads"
                        and r.get("message", {}).get("text", "").startswith(
                            "function Is_Valid is assumed to return True")):
                    continue
                item = {"rule": rule, "file": Path(file).name,
                        "line": phys.get("region", {}).get("startLine"),
                        "column": phys.get("region", {}).get("startColumn"),
                        "entity": loc.get("logicalLocations", [{}])[0].get("name", ""),
                        "kind": r.get("kind")}
                (failures if rule.startswith("VC_") else warnings).append(item)
            else:
                counts["application" if Path(file).name.startswith("bitmap_allocator")
                       else "sparklib"] += 1
                rules[rule] += 1
        units = {}
        steps = 0
        structural_unproved = []
        justified = 0
        for p in OUT.glob("*.spark"):
            data = json.loads(p.read_text())
            units[p.name] = {k: data.get(k) for k in
                            ("progress", "stop_reason", "pragma_assume", "skip_proof", "skip_flow_proof")}
            for check in data.get("proof", []):
                if check.get("severity") != "info":
                    structural_unproved.append((check["rule"], check["file"], check["line"], check["col"]))
                if check.get("how_proved") == "justified":
                    justified += 1
                for s in check.get("stats", {}).values():
                    steps = max(steps, s.get("max_steps", 0))
        result.update(complete=True, failures=failures, warnings=warnings,
                      passing_results=dict(counts), passing_rules=dict(rules),
                      max_steps=steps, units=units, justified=justified,
                      spark_unproved=structural_unproved)
        result["analysis_complete"] = all(
            u["progress"] == "PROGRESS_PROOF" and u["stop_reason"] == "STOP_REASON_NONE"
            and not u["pragma_assume"] and not u["skip_proof"] and not u["skip_flow_proof"]
            for u in units.values())
        sarif_unproved = sorted((r["rule"], r["file"], r["line"], r["column"]) for r in failures)
        if sarif_unproved != sorted(structural_unproved):
            raise ValueError("SARIF/.spark unproved VC mismatch")
    (dest / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(name, result["exit"], len(result.get("failures", [])), flush=True)
    return result


def ablate() -> None:
    ads = SRC / "bitmap_allocator.ads"
    adb = SRC / "bitmap_allocator.adb"
    original = {ads: ads.read_text(), adb: adb.read_text()}
    cases = {
        "membership_contract": (ads, "        Post => (for all Id in Object_Id =>\n          Id_Sets.Contains (Bitmap_Model'Result, Id) = Bitmap_Contains (Words, Id))\n          and ", "        Post => "),
        "capacity_bound": (ads, "          and Id_Sets.Length (Bitmap_Model'Result) <= Capacity\n", ""),
        "full_iff": (ads, "          and ((Id_Sets.Length (Bitmap_Model'Result) = Capacity)\n            = (for all Id in Object_Id => Bitmap_Contains (Words, Id)))\n", ""),
        "empty_iff": (ads, "          and ((Id_Sets.Length (Bitmap_Model'Result) = 0)\n            = (for all Id in Object_Id => not Bitmap_Contains (Words, Id)))", ""),
        "padding_invariant": (ads, "     Padding_Is_Canonical (Pool.Words)\n     and ", "     "),
        "count_invariant": (ads, "\n     and To_Big_Integer (Pool.Count) = Id_Sets.Length (Bitmap_Model (Pool.Words))", ""),
        "model_membership_loop": (adb, "         pragma Loop_Invariant\n           (for all J in Object_Id => Id_Sets.Contains (Result, J)\n             = (J < Id and then Bitmap_Contains (Words, J)));\n", ""),
        "model_bound_loop": (adb, "         pragma Loop_Invariant (Id_Sets.Length (Result) <= To_Big_Integer (Id));\n", ""),
        "model_full_loop": (adb, "         pragma Loop_Invariant\n           ((Id_Sets.Length (Result) = To_Big_Integer (Id))\n             = (for all J in Object_Id'First .. Id - 1 => Bitmap_Contains (Words, J)));\n", ""),
        "scan_model_loop": (adb, "         pragma Loop_Invariant (Bitmap_Model (P.Words) = Old_Model);\n", ""),
        "scan_count_loop": (adb, "         pragma Loop_Invariant (P.Count = Old_Count);\n", ""),
        "scan_prefix_loop": (adb, "         pragma Loop_Invariant\n           (for all J in Object_Id'First .. Candidate - 1 => not Bitmap_Contains (P.Words, J));\n", ""),
        "clear_equality_assert": (adb, "            pragma Assert (Bitmap_Model (P.Words) = Id_Sets.Remove (Old_Model, Id));\n", ""),
        "clear_length_call": (adb, "            Equal_Length (Bitmap_Model (P.Words), Id_Sets.Remove (Old_Model, Id));\n", ""),
        "set_membership_assert": (adb, "      pragma Assert\n        (for all J in Object_Id => Bitmap_Contains (P.Words, J)\n          = (J = Id or else Bitmap_Contains (Old_Words, J)));\n", ""),
        "set_equality_assert": (adb, "      pragma Assert (Bitmap_Model (P.Words) = Id_Sets.Add (Old_Model, Id));\n", ""),
        "set_length_call": (adb, "      Equal_Length (Bitmap_Model (P.Words), Id_Sets.Add (Old_Model, Id));\n", ""),
        "equal_length_assert": (adb, "      pragma Assert (Id_Sets.Num_Overlaps (Left, Right) = Id_Sets.Length (Left));", "      null;"),
        "equal_length_post": (adb, "   with Ghost, Pre => Left = Right,\n        Post => Id_Sets.Length (Left) = Id_Sets.Length (Right)", "   with Ghost, Pre => Left = Right"),
        "clear_membership": (adb, "            pragma Assert\n              (for all J in Object_Id => Bitmap_Contains (P.Words, J)\n                = (J /= Id and then Bitmap_Contains (Old_Words, J)));\n", ""),
        "clear_snapshot": (adb, "      Old_Words : constant Word_Array := P.Words with Ghost;\n   begin\n      Id :=", "   begin\n      Id :="),
        "set_snapshot": (adb, "      Old_Words : constant Word_Array := P.Words with Ghost;\n   begin\n      P.Words", "   begin\n      P.Words"),
        "padding_predicate": (ads, "   function Padding_Is_Canonical (Words : Word_Array) return Boolean is\n     ((Words (2) and not Interfaces.Unsigned_32 (2 ** 6 - 1)) = 0)\n   with Ghost;\n", ""),
    }
    results = {}
    try:
        for name, (file, before, after) in cases.items():
            for p, text in original.items():
                p.write_text(text)
            if before not in original[file] and name in {
                    "scan_model_loop", "scan_count_loop", "clear_equality_assert", "set_equality_assert",
                    "capacity_bound"}:
                continue  # Removed in the first minimization pass.
            if original[file].count(before) != 1:
                raise ValueError(f"Ambiguous or missing ablation: {name}")
            file.write_text(original[file].replace(before, after))
            results[name] = run("ablation_" + name)
    finally:
        for p, text in original.items():
            p.write_text(text)
        (ROOT / "obj/measurements/ablations.json").write_text(
            json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("positive", "ablate", "trust-scan"))
    args = parser.parse_args()
    if args.action == "trust-scan":
        trust_scan()
        print("Trust scan passed; runtime driver SPARK_Mode Off is the sole exemption.")
    elif args.action == "ablate":
        ablate()
    else:
        trust_scan()
        result = run("positive")
        if (result["exit"] or not result.get("complete") or result.get("failures")
                or result.get("warnings") or result.get("justified")
                or not result.get("analysis_complete")
                or "bitmap_allocator.spark" not in result.get("units", {})):
            raise SystemExit(1)