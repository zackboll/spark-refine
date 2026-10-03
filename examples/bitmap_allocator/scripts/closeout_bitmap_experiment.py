#!/usr/bin/env python3
"""Bind reviewed metadata to current files; no proof reproduction or Ada parser."""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = "docs/evidence/task019-bitmap-set-proof-pattern.json"
BASE = "examples/bitmap_allocator/"
INPUT_HASHES = {
    BASE + "evidence/library_minimization.json": "6655666c27ad24322dd1719d7b46e13e24005d6dd40dd9abae3842520da28cb6",
    BASE + "evidence/manual_inventory.json": "219556259161cfab72a8b34af680b50ab689f091195d98d8d8aad53a5848e51d",
    BASE + "evidence/manual_proof.json": "bd4416ea7686a1391bd6818f94d5ab0a69c806ec1a9c876538eb22cd91f13595",
    BASE + "evidence/library_minimization_timings.json": "5518b7c7f0bc36fca350dbb690c74eee287bf67bece36c15a25fa01e1b2e0370",
}
CAMPAIGNS = [
    "Independent generic-instance campaign",
    "Other word widths and identity kinds",
    "Invalid-configuration rejection tests",
    "Complete M1–M8 campaign, manual and library variants",
    "Masking experiments",
    "Complete single-prover comparison",
    "Final controlled performance comparison",
    "Dedicated hosted bitmap proof gate",
]


class VerificationError(ValueError):
    """Recorded evidence or bound source is inconsistent."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def verify_hash(root, path, expected):
    require(hashlib.sha256((root / path).read_bytes()).hexdigest() == expected,
            f"SHA-256 mismatch: {path}")


def economics(p, r, independent_validation=None):
    if p is None or r is None:
        return {"decision": "UNKNOWN", "support_saved": None,
                "R_gt_20": None, "reduction_lt_30_percent": None}
    require(type(p) is int and p > 0 and type(r) is int and r >= 0,
            "Invalid support counts")
    saved = p - r
    size = r > 20
    reduction = 100 * saved < 30 * p
    return {
        "support_saved": saved,
        "reduction": {"numerator": 100 * saved, "denominator": p,
                      "displayed_percentage": f"{Decimal(100 * saved) / Decimal(p):.6f}%"},
        "R_gt_20": size,
        "reduction_lt_30_percent": reduction,
        "decision": "DO_NOT_ADOPT_BITMAP_PATTERN" if size or reduction else
                    "ADOPTION_NOT_ESTABLISHED",
        "independent_validation": independent_validation,
    }


def verify_totals(snapshot):
    counts = Counter(row["category"] for f in snapshot["current"]["files"].values()
                     for row in f["lines"])
    require(dict(counts) == snapshot["current"]["totals"], "Inventory totals mismatch")
    require(counts["local_mechanical_support"] == snapshot["R_final_for_this_continuation"],
            "R inventory mismatch")
    require(counts["reusable_library"] == snapshot["L_current"], "L inventory mismatch")
    require(sum(snapshot["residual_breakdown"].values()) == counts["local_mechanical_support"],
            "Residual breakdown mismatch")


def build(root=ROOT):
    for path, digest in INPUT_HASHES.items():
        verify_hash(root, path, digest)
    def load(name):
        return json.loads((root / BASE / "evidence" / name).read_text(encoding="utf-8"))
    snapshot = load("library_minimization.json")
    manual = load("manual_inventory.json")
    proof = load("manual_proof.json")
    timings = load("library_minimization_timings.json")
    verify_totals(snapshot)
    require(sum(s["sloc"] for s in manual["spans"] if s["class"] == "mechanical")
            == manual["P"] == snapshot["P"], "Manual P mismatch")
    for path, digest in manual["source_sha256"].items():
        verify_hash(root, BASE + path, digest)
    identities = {path: data["sha256"] for path, data in snapshot["current"]["files"].items()}
    identities.update(snapshot["candidate_configuration_sha256"])
    for path, digest in identities.items():
        verify_hash(root, path, digest)
    for name in ("stable-1", "stable-2", "stable-3"):
        for path, digest in snapshot["observations"][name]["source_sha256"].items():
            require(identities.get(path) == digest, f"Stable proof source identity mismatch: {name}: {path}")
    result = economics(manual["P"], snapshot["R_final_for_this_continuation"])
    require(result["support_saved"] == snapshot["support_saved"], "Savings mismatch")
    return {
        "format_version": 1,
        "checkpoints": {
            "preregistration": "a3265d455d2420daf435a02127455af1ee07a9d0",
            "manual_baseline": "029f2907c7993da3854ed72583c166de4b79faa5",
            "first_green": snapshot["input_checkpoint"],
            "measured_candidate": "ce13e839259e3e8b7c265678db4e119f8b4152ce",
        },
        "input_evidence_sha256": INPUT_HASHES,
        "measured_source_sha256": identities,
        "counts": {"P": manual["P"], "R": snapshot["R_final_for_this_continuation"],
                   "L": snapshot["L_current"], "A": snapshot["A_current"],
                   "R_start_unminimized": snapshot["R_start"], "generic_manual_support": manual["generic_P"]},
        "economics": result,
        "decision_scope": "Measured packed allocator, preserved production interface, recorded proof architecture and bounded minimization alternatives; not a global minimum or impossibility claim.",
        "recorded_local_coverage": {
            "manual": snapshot["regressions"]["manual"],
            "manual_runtime": proof["runtime"],
            "candidate_runtime": snapshot["regressions"]["runtime"],
            "candidate_clean_proofs": [
                {k: snapshot["observations"][name][k] for k in
                 ("total", "passes", "justified", "failures", "agreement")}
                for name in ("stable-1", "stable-2", "stable-3")],
            "candidate_clean_wall_seconds": [timings[n] for n in ("stable-1", "stable-2", "stable-3")],
            "padding": snapshot["regressions"]["padding"],
            "padding_sloc": snapshot["standalone_padding_validation_sloc"],
            "padding_scope": "One arbitrary-raw-storage representation relationship, not three independent generic instances.",
            "production_lines": snapshot["current"]["totals"]["production"],
            "public_API_equivalence": snapshot["regressions"]["API_equivalence"],
            "assertions_scope": snapshot["regressions"]["assertions_scope"],
            "reproduction_claim": "Recorded local observations only; this helper verifies integrity, not proofs.",
        },
        "campaigns": {name: "not performed before economic closeout; no result claimed" for name in CAMPAIGNS},
        "documented_stopping_decision": {
            "execution": "closed early after economic rejection; not all planned campaigns completed",
            "timing": "post-measurement review decision, not a preregistered early-stopping plan",
            "rationale": "Passing remaining checks would not change measured R or satisfy the frozen economic criteria; review elected not to pursue them.",
            "verification_limit": "Human authorization is a documented input, not independently verified by software.",
        },
    }


def serialize(data):
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only evidence verification")
    args = parser.parse_args()
    try:
        content = serialize(build())
        if args.check:
            require((ROOT / OUTPUT).read_bytes() == content, "Closeout evidence differs")
        else:
            (ROOT / OUTPUT).write_bytes(content)
    except (VerificationError, OSError, KeyError, ValueError) as exc:
        parser.exit(1, f"Closeout verification failed: {exc}\n")
    print("Closeout evidence integrity verified; no proof reproduction claimed.")


if __name__ == "__main__":
    main()