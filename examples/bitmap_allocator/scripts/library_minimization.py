#!/usr/bin/env python3
"""Inventory candidate Ada and serialize captured Task 019 observations.

No prover is invoked. --capture reads archived runs once; normal regeneration
uses the committed compact observations and verifies every source hash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples/bitmap_allocator"
CHECKPOINT = "fee271fbeaf9fcd1077ede3a9e3a2f276e3ea907"


def inventory(start=False):
    manual = tomllib.loads((EX / "proof_inventory.toml").read_text())
    files = {}
    totals = {}
    for ext in ("ads", "adb"):
        rel = f"examples/bitmap_allocator/variants/library_backed/bitmap_allocator.{ext}"
        text = (subprocess.check_output(["git", "show", f"{CHECKPOINT}:{rel}"], cwd=ROOT).decode()
                if start else (ROOT / rel).read_text())
        source = text.splitlines()
        old = (EX / f"variants/manual/bitmap_allocator.{ext}").read_text().splitlines()
        prod = [old[n-1].strip() for s in manual["span"]
                if s["file"].endswith(ext) and s["class"] == "production"
                for n in range(s["start"], s["end"]+1) if old[n-1].strip()]
        cursor = 0
        rows = []
        private = False
        for n, line in enumerate(source, 1):
            clean = line.split("--", 1)[0].strip()
            if not clean:
                continue
            if clean == "private":
                private = True
            if cursor < len(prod) and clean == prod[cursor]:
                category = "production"
                cursor += 1
            elif ext == "ads" and ((not private and not clean.startswith("private with"))
                                   or clean in ("private", "end Bitmap_Allocator;")):
                category = "authoritative_specification"
            else:
                category = "local_mechanical_support"
            rows.append(dict(line=n, category=category, text=clean))
        assert cursor == len(prod), "Production line identity/order changed"
        files[rel] = dict(sha256=hashlib.sha256(text.encode()).hexdigest(), lines=rows)
    paths = list((ROOT / "proof_patterns/src").glob("spark_refine_bitmap_sets.ad?"))
    if start:
        paths += list((EX / "tests").glob("*.ad?"))
    if not start:
        paths += list((EX / "validation").glob("*.ad?"))
        paths += list((EX / "tests").glob("*.ad?"))
    for path in sorted(paths):
        rel = str(path.relative_to(ROOT))
        text = (subprocess.check_output(["git", "show", f"{CHECKPOINT}:{rel}"], cwd=ROOT).decode()
                if start else path.read_text())
        category = "reusable_library" if "proof_patterns/" in rel else "standalone_validation_test"
        files[rel] = dict(sha256=hashlib.sha256(text.encode()).hexdigest(), lines=[
            dict(line=n, category=category, text=line.split("--", 1)[0].strip())
            for n, line in enumerate(text.splitlines(), 1) if line.split("--", 1)[0].strip()])
    for file in files.values():
        for row in file["lines"]:
            totals[row["category"]] = totals.get(row["category"], 0) + 1
    return dict(files=files, totals=totals)


def capture(directory):
    runs = {}
    timings = {}
    for path in sorted(directory.glob("*/summary.json")):
        data = json.loads(path.read_text())
        timings[path.parent.name] = data.pop("wall")
        runs[path.parent.name] = data
        data["source_sha256"] = json.loads((path.parent / "hashes.json").read_text())
        data["total"] = data["passes"] + len(data["failures"])
    (EX / "evidence/library_minimization_timings.json").write_text(json.dumps(timings, indent=2, sort_keys=True)+"\n")
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    output = EX / "evidence/library_minimization.json"
    previous = json.loads(output.read_text()) if output.exists() else {}
    start, current = inventory(True), inventory()
    r = current["totals"]["local_mechanical_support"]
    data = dict(status="INTERMEDIATE — SINGLE-INSTANCE MINIMIZATION; INDEPENDENT VALIDATION AND FALSIFICATION PENDING",
                input_checkpoint=CHECKPOINT, start=start, current=current,
                R_start=start["totals"]["local_mechanical_support"], R_final_for_this_continuation=r,
                L_start=start["totals"]["reusable_library"], L_current=current["totals"]["reusable_library"],
                A_current=6, P=54, generic_manual_support=52, G="52/54",
                support_saved=54-r, reduction_percentage=100*(54-r)/54,
                observations=capture(args.capture) if args.capture else previous["observations"],
                decisions=previous.get("decisions", {}), regressions=previous.get("regressions", {}),
                outstanding=["independent instances", "configuration rejection", "M1–M8 and masking",
                             "single-prover and final performance", "final Task 019 decision"])
    import re
    body = (EX / "variants/library_backed/bitmap_allocator.adb").read_text()
    data["supporting_counts"] = dict(
        local_helpers=2, model_adapters=1,
        assertions=body.count("pragma Assert"),
        proof_witness_loops=1, production_scan_loops=1,
        loop_invariants=body.count("pragma Loop_Invariant"),
        snapshots=len(re.findall(r"Old_Words : constant", body)),
        mutation_lemma_calls=len(re.findall(r"Bitmap.Lemma_", body)),
        mapping_bridge_calls=len(re.findall(r"Mapping_Bridge \(", body))-1)
    data["standalone_padding_validation_sloc"] = sum(
        len(file["lines"]) for rel, file in current["files"].items() if "/validation/" in rel)
    data["residual_breakdown"] = {
        "private_with_and_instantiation": 3,
        "mapping_bridge_declaration_and_body": 10,
        "model_contract_and_forwarding_body": 21,
        "representation_invariant": 3,
        "Free_Model_adapter": 2,
        "raw_snapshots": 2,
        "scan_prefix_invariant": 2,
        "operation_mapping_calls": 2,
        "physical_delta_assertions": 6,
        "mutation_lemma_calls": 2,
        "clear_membership_assertion": 3}
    assert sum(data["residual_breakdown"].values()) == r
    dispositions = {
        "adapter": "replaced_by_checked_interface", "adapter_run": "inconclusive",
        "clear-length": "removed", "set-length": "removed",
        "clear-post": "retained_required_in_tested_design", "mutation-support": "removed",
        "model-path": "removed", "snapshots": "removed",
        "mapping-loop": "retained_required_in_tested_design", "universe": "removed",
        "scan": "retained_required_in_tested_design",
        "independent": "moved_to_independent_validation", "old-facts": "removed",
        "length-clause": "retained_required_in_tested_design", "input": "inconclusive"}
    data["decisions"] = {name: (dict(disposition=dispositions[name], observation=value)
                               if isinstance(value, str) else value)
                         for name, value in data["decisions"].items()}
    data["candidate_configuration_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (EX / "bitmap_allocator_library.gpr", EX / "bitmap_padding_validation.gpr")}
    for n in range(1, 4):
        run = data["observations"][f"stable-{n}"]
        assert run["exit"] == 0 and not run["failures"] and run["justified"] == 0 and run["agreement"]
        for path, digest in run["source_sha256"].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    output.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)+"\n")
    metrics = ["# Library integration metrics", "", "**"+data["status"]+"**", "",
               "Generated by `scripts/library_minimization.py`; do not edit manually.", "",
               f"Unminimized checkpoint R_start = {data['R_start']}; measured R = {r}.",
               f"L_start = {data['L_start']}; L_current = {data['L_current']}; A_current = 6.",
               f"P = 54; generic manual support = 52; G = 52/54.",
               f"Savings = {54-r}; reduction = {data['reduction_percentage']:.6f}%.",
               f"R <= 15: {'met' if r <= 15 else 'not met'}; reduction >= 50%: {'met' if r <= 27 else 'not met'}.",
               "Current design fails the frozen residual-size criterion (R > 20)." if r > 20 else "", "",
               "## Residual breakdown", "", "| Artifact | SLOC |", "|---|---:|"]
    metrics += [f"| {name} | {count} |" for name, count in data["residual_breakdown"].items()]
    metrics += ["", f"Standalone arbitrary-raw-storage padding validation: {data['standalone_padding_validation_sloc']} Ada SLOC.",
               "Runtime test driver: 54 Ada SLOC, deliberately outside SPARK.",
               "Candidate GPR output isolation uses --subdirs; configuration is unchanged.",
               "The bitmap library is unchanged; no allocator-specific theorem was moved into L.",
               "These are the smallest stable results under the recorded targeted alternatives, not a global minimum.", "",
               "## Complete line inventories", "",
               "Every active line is classified once. Test/validation code is separate from R and L.", ""]
    for rel, file in current["files"].items():
        metrics += [f"### {rel}", "", f"SHA-256: `{file['sha256']}`", "", "| Line | Class | Ada |", "|---:|---|---|"]
        metrics += [f"| {row['line']} | {row['category']} | `{row['text'].replace('|', '&#124;')}` |" for row in file["lines"]]
        metrics += [""]
    (EX / "LIBRARY_METRICS.md").write_text("\n".join(metrics).rstrip()+"\n")
    print(json.dumps({k: data[k] for k in ("R_start", "R_final_for_this_continuation", "L_start", "L_current", "A_current", "support_saved", "reduction_percentage")}, indent=2))


if __name__ == "__main__":
    main()