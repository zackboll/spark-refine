#!/usr/bin/env python3
"""Task 017 research-only, read-only normalization of fresh external proofs."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from external_validation import canonical, clean_identity, inventory, sha256

SHAS = {"failing": "5fa2c0cee62deb86368fcc84a8d3b06726028276",
        "control": "aeb809456846935ef126df1b5ec1c3d79a83fab1"}
COMMAND = "alr exec -- gnatprove -P crdt.gpr -j 30 --steps 10000 --no-loop-unrolling"
CATEGORIES = frozenset({"externally_corroborated_structure", "mechanically_supported_only",
                        "control_pattern_persists", "not_comparable",
                        "artifact_or_toolchain_limitation"})
CHANGES = frozenset({"unchanged", "contract_changed", "implementation_changed",
                     "both_changed", "deleted_or_moved", "not_comparable"})


def state(rule: dict, count: int) -> dict:
    return {"evaluated": rule["evaluated"],
            "count": count if rule["evaluated"] else None,
            "reason": rule.get("reason")}


def key(check) -> tuple:
    loc = check.location
    return check.rule, check.entity, loc.file, loc.line, loc.column


def pair(check, controls: list) -> tuple[str, object | None]:
    """Only unique exact or unique entity/rule matches; never source order."""
    exact = [c for c in controls if key(c) == key(check)]
    if len(exact) == 1:
        return "exact", exact[0]
    if exact:
        return "not_comparable", None
    unique = [c for c in controls if (c.rule, c.entity) == (check.rule, check.entity)]
    if len(unique) == 1 and check.entity:
        return "unique_entity_rule", unique[0]
    return "not_comparable", None


def srd001_pattern(invariant: bool, post: bool, same_identity: bool) -> str:
    if not same_identity:
        return "source_identity_changed"
    if not invariant:
        return "failing_invariant_disappears"
    if not post:
        return "related_postcondition_disappears"
    return "same_structural_pattern_persists"


def srd002_pattern(client: bool, implementation_proved: bool,
                   closure_complete: bool) -> str:
    if not closure_complete:
        return "not_comparable"
    return "same_structural_pattern_persists" if client and implementation_proved else "client_only_pattern_disappears"


def category(mechanical: bool, disappears: bool, changed: str,
             comparable: bool = True, compatible: bool = True) -> str:
    if changed not in CHANGES:
        raise ValueError("unknown upstream change")
    if not compatible:
        return "artifact_or_toolchain_limitation"
    if not comparable:
        return "not_comparable"
    if not mechanical:
        return "artifact_or_toolchain_limitation"
    if not disappears:
        return "control_pattern_persists"
    if changed in {"contract_changed", "implementation_changed", "both_changed", "deleted_or_moved"}:
        return "externally_corroborated_structure"
    return "mechanically_supported_only"


def estimate(occurrences: int, conjuncts: int, unique_prefixes: int) -> dict:
    return {"naive_observations": occurrences * conjuncts,
            "unique_prefix_programs": unique_prefixes,
            "additional_runs_after_baseline": max(unique_prefixes - 1, 0)}


def summary(text: str) -> dict:
    """Parse the Total row's numeric columns; never read prover message prose."""
    rows = [line for line in text.splitlines() if line.startswith("Total ")]
    if len(rows) != 1:
        raise ValueError("expected exactly one Total row")
    # GNATprove layout: total, flow proved, proof proved, justified, unproved.
    # Dot denotes zero. Read columns at fixed widths from the header instead.
    line = rows[0]
    parts = re.split(r"\s{2,}", line.strip())
    if len(parts) != 6:
        raise ValueError("unsupported Total layout")
    values = [int(p.split()[0]) if p != "." else 0 for p in parts[1:]]
    total, flow, proof, justified, unproved = values
    if total != flow + proof + justified + unproved:
        raise ValueError("inconsistent upstream total")
    return {"checks": total, "proved": flow + proof,
            "unproved": unproved, "justified": justified}


def row(check) -> dict:
    return {"rule": check.rule, "entity": check.entity,
            "location": {"file": check.location.file, "line": check.location.line,
                         "column": check.location.column}, "status": check.status.value,
            "disputed": check.disputed}


def collect(root: Path) -> dict:
    from spark_refine_diagnostics.ali import load_ali_deps
    from spark_refine_diagnostics.loader import load_run

    output = {}
    runs = {}
    for name, commit in SHAS.items():
        checkout = root / name
        identity = clean_identity(checkout, commit)
        results = checkout / "obj/gnatprove"
        start = int((root / (name + "-start")).read_text().strip())
        hashes = {}
        for suffix in (".sarif", ".spark", ".ali"):
            files = sorted(results.glob("*" + suffix))
            if not files or any(p.stat().st_mtime < start for p in files):
                raise ValueError("missing or stale " + suffix)
            hashes[suffix] = {"inventory": inventory(results, suffix),
                              "files": {p.name: sha256(p) for p in files}}
        run = load_run(results)
        runs[name] = run
        report = json.loads((root / (name + "-core.json")).read_text())
        if report["runs"][0]["gnatprove"] != run.tool_version:
            raise ValueError("report/proof version mismatch")
        rules = report["analysis"]["rules"]
        units = run.dependency_unit_names()
        ali = load_ali_deps(results, units)
        if rules["SRD002"].get("ali_status") != ali.status:
            raise ValueError("ALI status mismatch")
        by_rule = {}
        for rule in sorted({c.rule for c in run.checks}):
            by_rule[rule] = dict(sorted(Counter(c.status.value for c in run.checks
                                                if c.rule == rule).items()))
        meta = dict(line.split("=", 1) for line in
                    (root / (name + "-proof.meta")).read_text().splitlines())
        output[name] = {
            "identity": identity, "proof": {"command": COMMAND, "exit": int(meta["exit"]),
                "result_directory": "obj/gnatprove", "gnatprove": run.tool_version,
                "upstream": summary((results / "gnatprove.out").read_text()),
                "gnatprove_command_line": run.command_line},
            "sarif": {"summary": run.summary(), "by_rule": by_rule,
                      "unproved": [row(c) for c in run.unproved],
                      "consistency_issues": run.consistency_issues,
                      "disputed_units": sorted(run.disputed_units)},
            "task016": {"authoritative_dependency_units": units,
                        "requested_ali_units": units, "ali_status": ali.status,
                        "ali_versions": sorted(ali.versions),
                        "ali_problems": [p.split(":", 1)[0] for p in ali.problems],
                        "fallback_only_units": sorted(set(run.unit_names()) - set(units))},
            "core": {"json_exit": int((root / (name + "-core.exit")).read_text()),
                     "text_exit": int((root / (name + "-text.exit")).read_text()),
                     "parsed": True, "notes": report["notes"],
                     "rules": {k: state(rules[k], report["summary"]["by_code"][k])
                               for k in ("SRD001", "SRD002")},
                     "diagnostics": [{k: d[k] for k in ("code", "entity", "confidence")}
                                     for d in report["diagnostics"]],
                     "confidence_distribution": report["summary"]["by_confidence"]},
            "hashes": hashes}
    fail, control = runs["failing"], runs["control"]
    comparisons = []
    for check in fail.unproved:
        quality, matched = pair(check, control.checks)
        comparisons.append({"failing": row(check), "pairing": quality,
                            "control": row(matched) if matched else None})
    output["comparison"] = {"raw_failure_pairs": comparisons,
        "diagnostic_comparisons": [], "review_categories": {c: 0 for c in sorted(CATEGORIES)},
        "source_change_near_diagnostics": [],
        "limitation": "child changes multiple source regions; no edit is assigned as a VC cause"}
    count = len(fail.unproved)
    core = output["failing"]["core"]
    evaluated = all(core["rules"][code]["evaluated"] for code in ("SRD001", "SRD002"))
    output["outcome"] = ("EXTERNAL_FAILING_REVISION_NOT_REPRODUCIBLE" if not count else
        "EXTERNAL_POSITIVE_VALIDATION_BLOCKED_BY_COMPATIBILITY" if not evaluated else
        "POSITIVE_EXTERNAL_VALIDATION_COMPLETED" if core["diagnostics"] else
        "EXTERNAL_FAILURE_REPRODUCED_NO_MATCHING_DIAGNOSTIC")
    output["states"] = {"failing_revision_reproduced": count > 0,
        "control_revision_reproduced": not control.unproved,
        "core_analysis": True, "srd001_evaluated": core["rules"]["SRD001"]["evaluated"],
        "srd001_count": core["rules"]["SRD001"]["count"],
        "srd002_evaluated": core["rules"]["SRD002"]["evaluated"],
        "srd002_count": core["rules"]["SRD002"]["count"],
        "semantic_evaluated": False, "grouping_available": False,
        "externally_corroborated_structure_count": 0,
        "mechanically_supported_only_count": 0, "not_comparable_count": 0,
        "raw_unproved_not_covered_count": count}
    output["semantic"] = {"evaluated": False, "reason": "no SRD002 diagnostic to enrich",
        "exact": 0, "ambiguous": 0, "unresolved": 0, "unavailable": 0,
        "grouping": None, "triage_consolidation": None}
    output["probe_opportunities"] = {"eligible_groups": [], "estimate": estimate(0, 0, 0),
                                     "executed": False}
    output["starting_main"] = "0b2aa64d148c4defb8e9739322c4ca5a25c73f2b"
    output["preregistration"] = "4b2dce69046d0ea902739c02e54e599ab1d1a8cf"
    output["external_repository"] = "https://github.com/bladeacer/Ada_CRDT.git"
    output["alire"] = "2.1.1"
    output["covex_procedure_version"] = "1.48.0"
    return output


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: positive_external_validation.py RAW_ROOT EVIDENCE_JSON")
    Path(sys.argv[2]).write_text(canonical(collect(Path(sys.argv[1]))))