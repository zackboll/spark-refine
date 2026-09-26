#!/usr/bin/env python3
"""Representation-refactor churn: first_length (A) -> head_tail_count (B).

Measurement tool for REFACTOR_METRICS.md (not a proof gate). It diffs the
code lines (non-blank, non-comment) of src/ring_buffer.ad[sb] against
variants/head_tail_count/ring_buffer.ad[sb] and attributes every removed
line to its representation-A classification and every added line to its
representation-B classification (proof_inventory*.toml). A changed line
counts once as removed and once as added.

It also reports whether the representation-independent files differ from
the reviewed Task 002 base commit (the controls of the experiment):

  public API       visible part of ring_buffer.ads, A vs B (token level,
                   same normalisation as check_public_api_equivalence.py)
  client proof     proof/ring_buffer_client_proof.ad[sb]   (git diff BASE)
  runtime tests    tests/ring_buffer_runtime_tests.adb     (git diff BASE)

  python3 scripts/refactor_churn.py [--base 0f6da97...] [--json]
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
import tomllib

import check_public_api_equivalence as api
import proof_inventory as pi

TASK_002_BASE = "0f6da9702ab5683157efa855df80e7c562c53d95"
CONTROLS = {
    "client_proof": ["proof/ring_buffer_client_proof.ads",
                     "proof/ring_buffer_client_proof.adb"],
    "runtime_tests": ["tests/ring_buffer_runtime_tests.adb"],
}


def owners(variant: str) -> tuple[str, dict]:
    inventory, impl = pi.VARIANTS[variant]
    own = {}
    for art in tomllib.loads(inventory.read_text(encoding="utf-8"))["artifact"]:
        lo, hi = art["lines"]
        label = ("specification" if art["group"] == "specification"
                 else f"mechanical:{art['category']}")
        for n in range(lo, hi + 1):
            own[(art["file"].rsplit("/", 1)[-1], n)] = label
    return impl, own


def code_lines(path) -> list[tuple[int, str]]:
    return [(n, line) for n, line in
            enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if pi.is_code(line)]


def churn() -> dict:
    impl_a, own_a = owners("first_length")
    impl_b, own_b = owners("head_tail_count")
    totals: dict[str, dict[str, int]] = {}
    lines = []
    for f in ("ring_buffer.ads", "ring_buffer.adb"):
        a = code_lines(pi.EXAMPLE / impl_a / f)
        b = code_lines(pi.EXAMPLE / impl_b / f)
        sm = difflib.SequenceMatcher(a=[l.strip() for _, l in a],
                                     b=[l.strip() for _, l in b],
                                     autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            for n, l in a[i1:i2]:
                g = own_a.get((f, n), "production")
                totals.setdefault(g, {"removed": 0, "added": 0})["removed"] += 1
                lines.append(f"- [{g}] {f}:{n}: {l.strip()}")
            for n, l in b[j1:j2]:
                g = own_b.get((f, n), "production")
                totals.setdefault(g, {"removed": 0, "added": 0})["added"] += 1
                lines.append(f"+ [{g}] {f}:{n}: {l.strip()}")
    return {"by_group": dict(sorted(totals.items())), "lines": lines}


def git_changed_lines(base: str, paths: list[str]) -> int | None:
    proc = subprocess.run(
        ["git", "diff", "--numstat", base, "--", *paths],
        cwd=pi.EXAMPLE, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    total = 0
    for row in proc.stdout.splitlines():
        added, removed, _ = row.split("\t", 2)
        total += int(added) + int(removed)
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=TASK_002_BASE)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ref = api.visible_part(api.EXAMPLE / api.REFERENCE)
    got = api.visible_part(api.EXAMPLE / api.VARIANTS[0])
    api_diff = sum(1 for d in difflib.ndiff(ref, got) if d[:1] in "+-")
    data = {
        "base": args.base,
        "public_api_token_changes": api_diff,
        "controls_changed_lines_vs_base": {
            k: git_changed_lines(args.base, v) for k, v in CONTROLS.items()},
        **churn(),
    }
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"public API token changes (A vs B): "
              f"{data['public_api_token_changes']}")
        for k, v in data["controls_changed_lines_vs_base"].items():
            shown = "unavailable (base commit not present)" if v is None else v
            print(f"{k} lines changed vs {args.base[:12]}: {shown}")
        print("A -> B code-line churn by classification:")
        for g, v in data["by_group"].items():
            print(f"  {g:45} -{v['removed']:<3} +{v['added']}")
        print("lines:")
        for line in data["lines"]:
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
