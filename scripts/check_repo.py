#!/usr/bin/env python3
"""Lightweight structural checks for the bootstrap repository."""

from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "docs/MOTIVATION.md",
    "docs/LANDSCAPE.md",
    "docs/ARCHITECTURE.md",
    "docs/TRUST_MODEL.md",
    "docs/MVP.md",
    "docs/BENCHMARKS.md",
    "docs/RESEARCH.md",
    "examples/ring_buffer/spark-refine.toml",
    "examples/fixed_pool/BASELINE_METRICS.md",
    "examples/fixed_pool/proof_inventory.toml",
    "docs/tasks/003-fixed-pool-proof-baseline.md",
]

FORBIDDEN_GENERATED_TRUST = [
    "pragma Assume",
    "-- spark-refine: trust-me",
]


def main() -> int:
    failures = []

    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")

    manifest_path = ROOT / "examples/ring_buffer/spark-refine.toml"
    if manifest_path.is_file():
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        if data.get("format_version") != 1:
            failures.append("example manifest format_version must be 1")
        refs = data.get("refinement", [])
        if len(refs) != 1:
            failures.append("example manifest must contain exactly one refinement")
        elif refs[0].get("pattern") != "circular_sequence":
            failures.append("example refinement must use circular_sequence")

    generated = ROOT / "examples/ring_buffer/generated"
    if generated.exists():
        for path in generated.rglob("*.ad[bs]"):
            text = path.read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_GENERATED_TRUST:
                if forbidden.lower() in text.lower():
                    failures.append(f"forbidden generated trust construct in {path}: {forbidden}")

    if failures:
        print("Repository checks FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Repository checks passed.")
    print(f"Checked {len(REQUIRED)} required files and example manifest schema basics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
