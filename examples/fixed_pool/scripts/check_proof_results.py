#!/usr/bin/env python3
"""Machine-checked GNATprove gate for the fixed-pool benchmark (Task 003).

Sub-commands:

  positive    Run GNATprove on src/ (+ proof/) from a clean output directory
              and require: total checks > 0, zero unproved checks, zero
              justified checks, zero pragma Assume and no unexpected
              warnings. Writes obj/baseline/proof_summary.json.
  negative    For every fixture in negative/*/fault.toml: materialise a copy
              of src/ with exactly that fault applied, run GNATprove, and
              require that each expected (rule, entity) obligation is
              reported unproved. A nonzero exit status alone is not
              accepted. Writes obj/negative_summary.json.
  trust-scan  Scan src/, proof/, tests/ and every negative fault patch for
              forbidden trust-affecting constructs.
  all         trust-scan, positive, negative (in that order).

Results are read from GNATprove's SARIF output (gnatprove.sarif) and
cross-checked against the per-unit .spark JSON files. English message text
is never used to decide whether a check passed; it is only used for the
documented allow-list of toolchain warnings (currently empty for this
benchmark's own sources).

The structure mirrors examples/ring_buffer/scripts/check_proof_results.py so
that both benchmarks are gated identically; the two scripts are kept
independent so that neither benchmark can silently change the other's gate.

Environment:
  GNATPROVE_EXEC  Command prefix used to run gnatprove. Default:
                  "alr -n exec --". Set to "" to call gnatprove from PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
SRC = EXAMPLE / "src"
NEGATIVE = EXAMPLE / "negative"
OBJ = EXAMPLE / "obj"

VARIANTS = {
    "baseline": {
        "impl": "src", "obj_name": "baseline", "negative": NEGATIVE,
        "min_fixtures": 6, "neg_prefix": "negative_",
        "neg_src": OBJ / "negative_src",
        "neg_summary": "negative_summary.json",
    },
}

GATED_UNITS = ("fixed_pool", "fixed_pool_client_proof")

TRUST_SCAN_GLOBS = ("src/*.ad[sb]", "proof/*.ad[sb]", "tests/*.ad[sb]",
                    "fixed_pool.gpr")
FAULT_GLOBS = ("negative/*/fault.toml",)

FORBIDDEN_PATTERNS = {
    "pragma Assume": re.compile(r"pragma\s+Assume\b", re.I),
    "Assume aspect": re.compile(r"\bAssume\s*=>", re.I),
    "proof justification annotation": re.compile(
        r"(False_Positive|Intentional)", re.I),
    "imported (bodyless) declaration": re.compile(
        r"\bImport\s*(=>|;|,)|pragma\s+Import\b", re.I),
    "warning suppression": re.compile(r"pragma\s+Warnings\s*\(|-gnatw[.]?s\b"
                                      r"|--warnings=(off|continue)", re.I),
    "run-time check suppression": re.compile(r"pragma\s+Suppress\b|-gnatp\b",
                                             re.I),
    "SPARK_Mode Off": re.compile(r"SPARK_Mode\s*(=>\s*)?\(?\s*Off", re.I),
    "Skip_Proof / Skip_Flow_And_Proof": re.compile(r"Skip_(Flow_And_)?Proof",
                                                   re.I),
    "Why3 axiom": re.compile(r"\baxiom\b", re.I),
    "external axiomatization": re.compile(r"External_Axiomatization", re.I),
    "spark-refine trust-me": re.compile(r"spark-refine:\s*trust-me", re.I),
}

# The executable test driver is intentionally SPARK_Mode => Off: it is not a
# proof artefact and is excluded from proof. All other rules still apply.
TRUST_EXEMPTIONS = {
    ("tests/fixed_pool_runtime_tests.adb", "SPARK_Mode Off"),
}

# Toolchain warnings that belong to the documented external proof foundation.
# Matched on SARIF rule id, file and message prefix; anything else that is
# not a passing check fails the positive gate. Same entry as the ring-buffer
# benchmark: the Big_Integers Is_Valid intrinsic reached through SPARKlib
# Length. It is only accepted if GNATprove actually reports it.
ALLOWED_WARNINGS = (
    ("error", "a-nbnbin.ads", "function Is_Valid is assumed to return True"),
)


class GateError(Exception):
    pass


# --------------------------------------------------------------------------
# Running GNATprove
# --------------------------------------------------------------------------

def exec_prefix() -> list[str]:
    return shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))


def gnatprove_cmd(variant: str, impl_dir: str) -> list[str]:
    # All proof switches (mode, level, -U, report) live in fixed_pool.gpr
    # package Prove so that interactive and gated runs are identical.
    return exec_prefix() + [
        "gnatprove", "-P", "fixed_pool.gpr", "-j0",
        f"-XFIXED_POOL_SRC={impl_dir}",
        f"-XFIXED_POOL_VARIANT={variant}",
    ]


def run_gnatprove(variant: str, impl_dir: str) -> dict:
    variant_obj = OBJ / variant
    if variant_obj.exists():
        shutil.rmtree(variant_obj)  # never trust stale prover output
    variant_obj.mkdir(parents=True)
    cmd = gnatprove_cmd(variant, impl_dir)
    start = time.monotonic()
    proc = subprocess.run(cmd, cwd=EXAMPLE, capture_output=True, text=True)
    wall = time.monotonic() - start
    log = variant_obj / "gnatprove.log"
    log.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return {"cmd": cmd, "returncode": proc.returncode, "wall_seconds": wall,
            "out_dir": variant_obj / "gnatprove", "log": log}


# --------------------------------------------------------------------------
# Reading results
# --------------------------------------------------------------------------

def is_allowed_warning(rule: str, uri: str, text: str) -> bool:
    return any(rule == r and uri == f and text.startswith(m)
               for r, f, m in ALLOWED_WARNINGS)


def load_results(out_dir: Path) -> dict:
    """Classify every SARIF result and cross-check with the .spark files."""
    sarif_path = out_dir / "gnatprove.sarif"
    if not sarif_path.is_file():
        raise GateError(f"missing SARIF output {sarif_path} "
                        "(compilation or analysis did not complete)")
    sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
    run = sarif["runs"][0]

    proved, justified, unproved, warnings, allowed = [], [], [], [], []
    for res in run["results"]:
        loc = res["locations"][0]
        phys = loc["physicalLocation"]
        uri = phys["artifactLocation"]["uri"]
        region = phys.get("region", {})
        entity = (loc.get("logicalLocations") or [{}])[0].get("name", "")
        item = {"rule": res["ruleId"], "kind": res["kind"],
                "level": res.get("level", ""), "file": uri,
                "line": region.get("startLine"), "entity": entity,
                "message": res["message"]["text"]}
        suppressions = res.get("suppressions") or []
        if res["kind"] == "pass":
            proved.append(item)
        elif is_allowed_warning(item["rule"], uri, item["message"]):
            allowed.append(item)
        elif any(s.get("kind") == "inSource" for s in suppressions):
            justified.append(item)
        elif item["level"] in ("warning", "note"):
            warnings.append(item)
        else:
            unproved.append(item)

    spark_unproved = 0
    pragma_assume = 0
    for unit in GATED_UNITS:
        spark_path = out_dir / f"{unit}.spark"
        if not spark_path.is_file():
            raise GateError(f"missing {spark_path}: unit was not analysed")
        data = json.loads(spark_path.read_text(encoding="utf-8"))
        if data.get("stop_reason") != "STOP_REASON_NONE":
            raise GateError(f"{unit}: analysis stopped early: "
                            f"{data.get('stop_reason')}")
        pragma_assume += len(data.get("pragma_assume", []))
        for entry in data.get("proof", []) + data.get("flow", []):
            if entry.get("severity") in ("low", "medium", "high", "error"):
                spark_unproved += 1

    inv = run.get("invocations") or [{}]
    return {"proved": proved, "justified": justified, "unproved": unproved,
            "warnings": warnings, "allowed_warnings": allowed,
            "spark_unproved": spark_unproved, "pragma_assume": pragma_assume,
            "command_line": inv[0].get("commandLine", ""),
            "tool": run["tool"]["driver"].get("version", "")}



def prover_effort(out_dir: Path) -> dict:
    """Measurement only (never a pass/fail criterion): the largest per-check
    step count and time in GNATprove's own per-check "stats" (the prover
    that won each check), from the gated units' .spark files.

    Under --level=2 with -j0 the three provers race and the losers are
    killed, so which prover wins, and therefore the reported steps, varies
    between identical runs. Treat these numbers as indicative only; for a
    deterministic comparison run a single prover (--prover=...), see
    BASELINE_METRICS.md."""
    worst = []
    for unit in GATED_UNITS:
        data = json.loads((out_dir / f"{unit}.spark").read_text(
            encoding="utf-8"))
        for entry in data.get("proof", []):
            for prover, st in (entry.get("stats") or {}).items():
                worst.append((st.get("max_steps", 0),
                              st.get("max_time", 0.0),
                              f"{entry['rule']} {entry['file']}:"
                              f"{entry['line']} ({prover})"))
    worst.sort(reverse=True)
    return {"max_prover_steps": worst[0][0] if worst else 0,
            "max_check_seconds": round(max((w[1] for w in worst),
                                           default=0.0), 3),
            "most_expensive_checks": [f"{s} steps: {w}"
                                      for s, _, w in worst[:3]]}


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------

def gate_positive(args) -> None:
    var = VARIANTS[args.variant]
    print(f"== positive {args.variant} ({var['impl']}) ==")
    run = run_gnatprove(var["obj_name"], var["impl"])
    res = load_results(run["out_dir"])
    by_rule: dict[str, int] = {}
    for item in res["proved"]:
        by_rule[item["rule"]] = by_rule.get(item["rule"], 0) + 1
    summary = {
        "variant": args.variant,
        "implementation": var["impl"],
        "gnatprove": res["tool"],
        "command_line": res["command_line"],
        "returncode": run["returncode"],
        "wall_seconds": round(run["wall_seconds"], 2),
        "total_checks": (len(res["proved"]) + len(res["justified"])
                         + len(res["unproved"])),
        "proved": len(res["proved"]),
        "justified": len(res["justified"]),
        "unproved": len(res["unproved"]),
        "unexpected_warnings": len(res["warnings"]),
        "allowed_foundation_warnings": len(res["allowed_warnings"]),
        "pragma_assume": res["pragma_assume"],
        "proved_by_rule": dict(sorted(by_rule.items())),
        **prover_effort(run["out_dir"]),
    }
    (OBJ / var["obj_name"] / "proof_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "proved_by_rule"}, indent=2))

    problems = []
    if run["returncode"] != 0:
        problems.append(f"gnatprove exited with {run['returncode']} "
                        f"(see {run['log']})")
    for item in res["unproved"]:
        problems.append(f"unproved: {item['rule']} {item['entity']} "
                        f"{item['file']}:{item['line']}: {item['message']}")
    for item in res["warnings"]:
        problems.append(f"unexpected warning: {item['rule']} {item['file']}:"
                        f"{item['line']}: {item['message']}")
    if res["spark_unproved"]:
        problems.append(f".spark files report {res['spark_unproved']} "
                        "unproved checks")
    if res["pragma_assume"]:
        problems.append(f"{res['pragma_assume']} pragma Assume analysed")
    if res["justified"]:
        problems.append(f"{len(res['justified'])} justified checks "
                        "(none are permitted)")
    if summary["total_checks"] == 0:
        problems.append("no checks found; proof did not run")
    if problems:
        raise GateError(f"positive {args.variant} FAILED:\n  "
                        + "\n  ".join(problems))
    print(f"positive {args.variant}: PASS ({summary['proved']} proved, "
          "0 unproved, 0 justified)")


def apply_fault(spec: dict, dest: Path, impl: Path = SRC) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in impl.glob("*.ad[sb]"):
        shutil.copy2(f, dest / f.name)
    for edit in spec["edit"]:
        target = dest / edit["file"]
        text = target.read_text(encoding="utf-8")
        count = text.count(edit["find"])
        if count != 1:
            raise GateError(f"{spec['name']}: fault anchor occurs {count} "
                            f"times in {edit['file']} (expected exactly 1); "
                            "the baseline changed, update the fixture")
        target.write_text(text.replace(edit["find"], edit["replace"]),
                          encoding="utf-8")



def gate_negative(args) -> None:
    var = VARIANTS[args.variant]
    fixtures = sorted(var["negative"].glob("*/fault.toml"))
    if args.only:
        fixtures = [f for f in fixtures if f.parent.name in args.only]
    elif len(fixtures) < var["min_fixtures"]:
        raise GateError(f"expected at least {var['min_fixtures']} negative "
                        f"fixtures for {args.variant}, "
                        f"found {len(fixtures)}")
    report, failures = [], []
    for path in fixtures:
        spec = tomllib.loads(path.read_text(encoding="utf-8"))
        name = spec["name"]
        variant = f"{var['neg_prefix']}{name}"
        impl = var["neg_src"] / name
        apply_fault(spec, impl, EXAMPLE / var["impl"])
        print(f"== {spec['id']} {name} ==")
        run = run_gnatprove(variant, impl.relative_to(EXAMPLE).as_posix())
        try:
            res = load_results(run["out_dir"])
        except GateError as exc:
            failures.append(f"{spec['id']} {name}: {exc}")
            continue
        if res["pragma_assume"]:
            failures.append(f"{spec['id']} {name}: contains pragma Assume")
        if run["returncode"] == 0 or not res["unproved"]:
            failures.append(f"{spec['id']} {name}: proof unexpectedly "
                            "SUCCEEDED")
        missing = []
        for exp in spec["expect"]:
            if not any(u["rule"] == exp["rule"]
                       and u["entity"] == exp["entity"]
                       for u in res["unproved"]):
                missing.append(f"{exp['rule']} in {exp['entity']}")
        if missing:
            failures.append(f"{spec['id']} {name}: expected unproved "
                            f"obligation(s) not reported: "
                            f"{', '.join(missing)}")
        observed = sorted({(u["rule"], u["entity"])
                           for u in res["unproved"]})
        for rule, entity in observed:
            print(f"   unproved: {rule} @ {entity}")
        report.append({
            "id": spec["id"], "name": name,
            "returncode": run["returncode"],
            "wall_seconds": round(run["wall_seconds"], 2),
            "proved": len(res["proved"]),
            "unproved": len(res["unproved"]),
            "expected": [f"{e['rule']}@{e['entity']}" for e in spec["expect"]],
            "observed_unproved": [f"{r}@{e}" for r, e in observed],
            "detected": not missing and bool(res["unproved"]),
        })
    OBJ.mkdir(exist_ok=True)
    (OBJ / var["neg_summary"]).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise GateError("negative fixtures FAILED:\n  "
                        + "\n  ".join(failures))
    print(f"negative fixtures ({args.variant}): PASS ({len(report)} "
          "fixtures detected as expected)")


def gate_trust(_args) -> None:
    print("== trust scan ==")
    problems = []
    scanned = 0
    for pattern in TRUST_SCAN_GLOBS:
        for path in sorted(EXAMPLE.glob(pattern)):
            rel = path.relative_to(EXAMPLE).as_posix()
            scanned += 1
            lines = path.read_text(encoding="utf-8").splitlines()
            for lineno, line in enumerate(lines, 1):
                code = line.split("--", 1)[0]
                for label, rx in FORBIDDEN_PATTERNS.items():
                    if rx.search(code) and (rel, label) not in TRUST_EXEMPTIONS:
                        problems.append(f"{rel}:{lineno}: {label}: "
                                        f"{line.strip()}")
    for path in sorted(p for g in FAULT_GLOBS for p in EXAMPLE.glob(g)):
        scanned += 1
        spec = tomllib.loads(path.read_text(encoding="utf-8"))
        for edit in spec.get("edit", []):
            for label, rx in FORBIDDEN_PATTERNS.items():
                if rx.search(edit["replace"]):
                    problems.append(f"{path.relative_to(EXAMPLE)}: {label}")
    if problems:
        raise GateError("trust scan FAILED:\n  " + "\n  ".join(problems))
    print(f"trust scan: PASS ({scanned} files, 0 forbidden constructs)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command",
                        choices=("positive", "negative", "trust-scan", "all"))
    parser.add_argument("--only", nargs="*",
                        help="negative fixture directory names to run")
    parser.add_argument("--variant", choices=tuple(VARIANTS),
                        default="baseline", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.command in ("trust-scan", "all"):
            gate_trust(args)
        if args.command in ("positive", "all"):
            gate_positive(args)
        if args.command in ("negative", "all"):
            gate_negative(args)
    except GateError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
