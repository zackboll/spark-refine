#!/usr/bin/env python3
"""Task 018: pure pre-proof qualification; never reads proof or diagnostic output."""
from __future__ import annotations

import json
import re
from pathlib import Path

REJECTIONS = frozenset({
    "REJECT_UNCOMMITTED_FAILURE", "REJECT_WRONG_VC_SHAPE",
    "REJECT_IMPLEMENTATION_NOT_PROVED", "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE",
    "REJECT_TOOLCHAIN_VERSION", "REJECT_NOT_REPRODUCIBLE_PREPROOF",
    "REJECT_ALREADY_TESTED", "REJECT_OTHER",
})
QUALIFIED = frozenset({"QUALIFIED_SRD001", "QUALIFIED_SRD002"})
CATEGORIES = REJECTIONS | QUALIFIED
FORBIDDEN = frozenset({"diagnostics", "diagnostic_count", "spark_refine_output",
                       "proof_output", "result", "observed_checks"})


def qualify(c: dict) -> str:
    """Require independent upstream documentation, not source-diff inference."""
    if FORBIDDEN.intersection(c):
        raise ValueError("selection cannot use diagnostic or functional proof output")
    if c.get("already_tested"):
        return "REJECT_ALREADY_TESTED"
    if not c.get("committed_failure"):
        return "REJECT_UNCOMMITTED_FAILURE"
    if c.get("gnatprove_major") != 16:
        return "REJECT_TOOLCHAIN_VERSION"
    if not c.get("reproducible_preproof"):
        return "REJECT_NOT_REPRODUCIBLE_PREPROOF"
    if c.get("vc") not in {"VC_INVARIANT", "VC_PRECONDITION", "VC_ASSERT"}:
        return "REJECT_WRONG_VC_SHAPE"
    if not c.get("documented_failed_vc") or not c.get("upstream_reference"):
        return "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE"
    if c["vc"] == "VC_INVARIANT":
        return ("QUALIFIED_SRD001" if c.get("same_entity_post_documented")
                and c.get("same_entity_post") and c.get("correction_documented") else
                "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")
    if not c.get("implementation_proved_documented"):
        return "REJECT_IMPLEMENTATION_NOT_PROVED"
    return ("QUALIFIED_SRD002" if c.get("caller_callee_documented")
            and c.get("public_boundary_fix_documented")
            and c.get("public_boundary_fix") else
            "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")


def select(candidates: list[dict]) -> dict | None:
    """Stable selection: exact version, PR/issue, direct pair, smaller scope."""
    eligible = [c for c in candidates if qualify(c) in QUALIFIED]
    return min(eligible, key=lambda c: (
        c.get("gnatprove_version") != "16.1.0",
        c.get("evidence_kind") != "issue_pr",
        not c.get("direct_pair", False),
        c.get("scope_units", float("inf")), c["repository"],
        c["failing_sha"])) if eligible else None


def canonical(document: dict) -> bytes:
    """Portable deterministic evidence; reject paths and ephemeral/proof fields."""
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in FORBIDDEN or key in {"timestamp", "prover_message"}:
                    raise ValueError("forbidden evidence field: " + key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            if re.search(r"(?:^|\s)(?:/[^\s]+|[A-Za-z]:\\[^\s]+)", value):
                raise ValueError("absolute path in evidence")
    walk(document)
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


if __name__ == "__main__":
    import sys
    # Evidence source is a checked-in survey, never functional proof output.
    source = Path(__file__).resolve().parents[2] / "docs/evidence/task018-external-positive-candidate.json"
    sys.stdout.buffer.write(canonical(json.loads(source.read_text())))