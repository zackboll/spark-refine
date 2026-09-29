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
    "docs/tasks/004-prefix-set-proof-library.md",
    "examples/fixed_pool/LIBRARY_METRICS.md",
    "examples/fixed_pool/proof_inventory_library_backed.toml",
    "examples/fixed_pool/variants/library_backed/fixed_pool.ads",
    "examples/fixed_pool/variants/library_backed/fixed_pool.adb",
    "proof_patterns/src/spark_refine_prefix_sets.ads",
    "proof_patterns/src/spark_refine_prefix_sets.adb",
    "docs/tasks/005-proof-diagnostics-mvp.md",
    "diagnostics/README.md",
    "diagnostics/DIAGNOSTICS_METRICS.md",
    "diagnostics/spark_refine_diagnostics/__main__.py",
    "diagnostics/tests/expectations.toml",
    "diagnostics/tests/fixtures/manifest.toml",
    "docs/tasks/006-explain-cli-productization.md",
    "docs/AGENT_INTEGRATION.md",
    "docs/history/ORIGINAL_README.md",
    "diagnostics/pyproject.toml",
    "diagnostics/LICENSE",
    "diagnostics/spark_refine_diagnostics/discovery.py",
    "diagnostics/scripts/packaging_smoke.py",
    "docs/adr/0005-library-and-diagnostics-first.md",
    "docs/tasks/007-documentation-realignment.md",
    "diagnostics/spark_refine_diagnostics/orchestration.py",
    "docs/tasks/008-proof-run-orchestration.md",
    "diagnostics/spark_refine_diagnostics/semantic.py",
    "diagnostics/spark_refine_diagnostics/semantic_lal.py",
    "diagnostics/scripts/setup_libadalang.sh",
    "docs/tasks/009-libadalang-srd002-enrichment.md",
    "diagnostics/spark_refine_diagnostics/semantic_groups.py",
    "docs/tasks/010-srd002-semantic-groups.md",
    "diagnostics/spark_refine_diagnostics/semantic_shape.py",
    "docs/tasks/011-defensive-semantic-rendering.md",
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
