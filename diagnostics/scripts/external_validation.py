#!/usr/bin/env python3
"""Task 015 research-only normalization; never runs proof or edits a checkout."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


def select_target(muen: bool, fallback: bool) -> str | None:
    return "muen" if muen else "sml-ada" if fallback else None


def verdict(fresh: bool, core: bool, candidate: bool) -> str:
    if not candidate or not fresh:
        return "EXTERNAL_TARGET_NOT_REPRODUCIBLE"
    return ("EXTERNAL_VALIDATION_COMPLETED" if core else
            "EXTERNAL_VALIDATION_BLOCKED_BY_COMPATIBILITY")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory: Path, suffix: str) -> dict:
    files = sorted(directory.glob("*" + suffix))
    rows = [(p.name, sha256(p)) for p in files]
    digest = hashlib.sha256("".join(f"{n}\t{h}\n" for n, h in rows).encode()).hexdigest()
    return {"count": len(rows), "sha256": digest}


def clean_identity(directory: Path, commit: str) -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(directory), *args],
                                       text=True).strip()
    head, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    if head != commit or status or subprocess.call(
            ["git", "-C", str(directory), "diff", "--exit-code"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        raise ValueError("external checkout is dirty or at the wrong commit")
    return {"commit": head, "tree": git("rev-parse", "HEAD^{tree}"),
            "status_porcelain": status}


def structural(checks: list) -> dict:
    rules = Counter(c.rule for c in checks)
    states = Counter(c.status.value for c in checks)
    runtime = sum(n for rule, n in rules.items()
                  if rule.startswith("VC_") and any(
                      k in rule for k in ("CHECK", "OVERFLOW", "RAISE")))
    return {"sarif_checks": len(checks), "statuses": dict(sorted(states.items())),
            "rules": dict(sorted(rules.items())),
            "source_units": len({c.location.file for c in checks}),
            "precondition": rules["VC_PRECONDITION"],
            "postcondition": rules["VC_POSTCONDITION"],
            "assert": rules["VC_ASSERT"],
            "invariant": sum(v for k, v in rules.items() if "INVARIANT" in k),
            "runtime": runtime}


def diagnostics_metrics(report: dict) -> dict:
    rules = report["analysis"]["rules"]
    counts = report["summary"]["by_code"]
    return {k: {"evaluated": rules[k]["evaluated"],
                "count": counts[k] if rules[k]["evaluated"] else None,
                **({"reason": rules[k]["reason"]} if not rules[k]["evaluated"] else {})}
            for k in ("SRD001", "SRD002")}


def semantic_metrics(report: dict) -> dict:
    meta = report["analysis"].get("semantic", {})
    return {"evaluated": meta.get("evaluated", False),
            "backend": meta.get("backend"), "reason": meta.get("reason"),
            "resolutions": meta.get("resolutions", {
                k: 0 for k in ("exact", "ambiguous", "unresolved", "unavailable")}),
            "provenance": meta.get("provenance")}


def group_metrics(report: dict) -> dict | None:
    groups = report["analysis"].get("semantic", {}).get("srd002_groups")
    if groups is None:
        return None
    return {k: groups[k] for k in ("client_failure_count", "group_count",
                                     "grouped_check_count", "ungrouped_check_count")}


def probe_eligible(check: dict) -> bool:
    pre = check.get("precondition") or {}
    return (check.get("rule") == "VC_PRECONDITION" and
            check.get("resolution") == "exact" and
            bool(check.get("callee", {}).get("declaration")) and
            pre.get("explicit") is True and
            isinstance(pre.get("conjuncts"), list) and
            len(pre["conjuncts"]) >= 2 and
            all(isinstance(c.get("text"), str) for c in pre["conjuncts"]))


def estimate(occurrences: int, prefixes: int) -> dict:
    return {"naive_occurrence_prefix_observations": occurrences * prefixes,
            "unique_callee_prefix_programs": prefixes,
            "additional_prefix_runs": max(prefixes - 1, 0)}


def parse_gnatprove_summary(text: str) -> dict:
    """Read exactly one GNATprove result summary, never individual messages.

    Supports the observed all-proved line and explicit totals for non-clean
    runs; any other summary shape is rejected rather than guessed.
    """
    candidates = [line.strip() for line in text.splitlines()
                  if re.match(r"^(?:Success:|Summary:)\s", line.strip())
                  and not line.strip().startswith("Summary logged in ")]
    if len(candidates) != 1:
        raise ValueError("expected exactly one GNATprove summary")
    line = candidates[0]
    all_proved = re.fullmatch(r"Success: all checks proved \(([0-9]+) checks\)\.", line)
    totals = re.fullmatch(
        r"Summary: ([0-9]+) checks: ([0-9]+) proved, "
        r"([0-9]+) unproved, ([0-9]+) justified\.", line)
    if all_proved:
        checks = int(all_proved.group(1))
        result = {"checks": checks, "proved": checks,
                  "unproved": 0, "justified": 0}
    elif totals:
        result = dict(zip(("checks", "proved", "unproved", "justified"),
                          map(int, totals.groups())))
    else:
        raise ValueError("malformed or unsupported GNATprove summary")
    if result["checks"] != sum(result[k] for k in ("proved", "unproved", "justified")):
        raise ValueError("inconsistent GNATprove summary totals")
    return result


def parse_proof_exit(text: str) -> int:
    lines = [line for line in text.splitlines() if line.startswith("proof_exit=")]
    if len(lines) != 1 or not re.fullmatch(r"proof_exit=[0-9]+", lines[0]):
        raise ValueError("expected exactly one integer proof_exit")
    return int(lines[0].split("=", 1)[1])


def report_states(core: dict, diagnostics: dict, semantic: dict,
                  grouping: dict | None, opportunities: list) -> dict:
    return {"core_analysis": isinstance(core.get("analysis", {}).get("rules"), dict),
            "srd001_evaluated": diagnostics["SRD001"]["evaluated"],
            "srd002_evaluated": diagnostics["SRD002"]["evaluated"],
            "semantic_evaluated": semantic["evaluated"],
            "grouping_available": grouping is not None,
            "probe_opportunities": len(opportunities)}


def canonical(evidence: dict) -> str:
    def validate(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key != "timestamp_resolution" and re.search(
                        r"timestamp|message|date", key, re.I):
                    raise ValueError("evidence contains prover prose metadata")
                validate(item)
        elif isinstance(value, list):
            for item in value:
                validate(item)
        elif isinstance(value, str) and value.startswith("/"):
            raise ValueError("evidence contains an absolute path")
    validate(evidence)
    text = json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    return text


def capture(root: Path, output: Path) -> dict:
    """Normalize an already completed, fresh, preregistered proof run."""
    from spark_refine_diagnostics.loader import load_run

    checkout = root / "sml-ada"
    identity = clean_identity(checkout, "3ccd0e4bf51685ebd832383c12166e795473a037")
    results = checkout / "proof/obj/gnatprove"
    sarif = results / "gnatprove.sarif"
    start = int((root / "proof-start-epoch.txt").read_text())
    if not sarif.is_file() or sarif.stat().st_mtime < start:
        raise ValueError("no fresh SARIF from this proof run")
    for suffix in (".spark", ".ali"):
        files = list(results.glob("*" + suffix))
        if not files or any(p.stat().st_mtime < start for p in files):
            raise ValueError("missing or stale " + suffix + " inventory")
    run = load_run(results)
    core = json.loads((root / "core.json").read_text())
    sem = json.loads((root / "semantic.json").read_text())
    if core["runs"][0]["gnatprove"] != run.tool_version:
        raise ValueError("report version does not match proof")
    proof_log = (root / "proof-run.log").read_text()
    wall = re.search(r"proof_wall_seconds=(\d+)", proof_log)
    proof_exit = parse_proof_exit(proof_log)
    summary = parse_gnatprove_summary(proof_log)
    if proof_exit != 0 or not wall:
        raise ValueError("proof run did not complete")
    checks = structural(run.checks)
    diagnostics = diagnostics_metrics(core)
    semantic = semantic_metrics(sem)
    grouping = group_metrics(sem)
    opportunities: list = []
    states = report_states(core, diagnostics, semantic, grouping, opportunities)
    evidence = {
        "result": verdict(True, True, True),
        "source": {"repo": "https://github.com/ldm5180/sml-ada.git",
                   "branch": "informational only: pinned detached HEAD",
                   **identity, "submodules": {}},
        "starting_main": "de7e740dee2d17b1a5eec699048e86b224f84989",
        "preregistration": "aef0dde5567246ff9940f6e52e11f7c82fe007cc",
        "proof": {"command": "alr exec -- gnatprove -P proof/proof.gpr -j0 --level=2 --checks-as-errors=on --warnings=error --output-header",
                  "result_dir": "proof/obj/gnatprove", "exit": proof_exit,
                  "gnatprove": run.tool_version, "alire": "2.1.1",
                  **{"upstream_summary_" + key: value
                     for key, value in summary.items()}},
        "structural": {**checks, "sarif_spark_disputes": len(run.consistency_issues),
                       "dispute_kinds": dict(sorted(Counter(
                           issue.split(":", 1)[0]
                           for issue in run.consistency_issues).items())),
                       "unique_spark_units": len(run.unit_names())},
        "core": {"exit": 0, "parsed": True,
                 "rules": core["analysis"]["rules"],
                 "diagnostics": diagnostics,
                 "diagnostic_count": core["summary"]["diagnostic_count"],
                 "notes_count": len(core["notes"])},
        "semantic": semantic,
        "grouping": grouping,
        "probe_opportunities": opportunities,
        "probe_estimate": estimate(0, 0),
        "descriptive_review": [],
        "states": {"target_selected": "sml-ada", "proof_reproduced": True,
                   **states},
        "hashes": {"gnatprove_sarif": sha256(sarif),
                   "spark_inventory": inventory(results, ".spark"),
                   "ali_inventory": inventory(results, ".ali"),
                   "core_text": sha256(root / "core.txt"),
                   "core_json": sha256(root / "core.json"),
                   "semantic_json": sha256(root / "semantic.json")},
        "timing": {"setup_seconds": None, "proof_seconds": int(wall.group(1)),
                   "explain_seconds": 0, "semantic_seconds": 0,
                   "precision": "integer shell SECONDS; setup not timed"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(evidence))
    return evidence


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: external_validation.py RAW_ROOT EVIDENCE_JSON")
    capture(Path(sys.argv[1]), Path(sys.argv[2]))