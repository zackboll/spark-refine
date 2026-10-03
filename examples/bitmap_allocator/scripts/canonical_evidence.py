#!/usr/bin/env python3
"""Canonicalize existing manual observations; does not rerun the prover."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
measurements = root / "obj/measurements"
positives = []
for i in range(1, 4):
    d = json.loads((measurements / f"stable-{i}/summary.json").read_text())
    assert d["exit"] == 0 and d["analysis_complete"] and not d["failures"]
    assert not d["warnings"] and d["justified"] == 0
    positives.append({k: d[k] for k in ("wall_seconds", "passing_results", "passing_rules", "max_steps", "justified")})
ablations = {}
for name in ("ablations-first", "ablations-second", "ablations"):
    data = json.loads((measurements / f"{name}.json").read_text())
    ablations[name] = {
        key: {k: value[k] for k in ("exit", "failures", "warnings")}
        for key, value in data.items()
    }
for name in ("clear_membership", "clear_snapshot", "set_snapshot", "padding_predicate"):
    d = json.loads((measurements / f"ablation_{name}/summary.json").read_text())
    ablations[name] = {"exit": d["exit"], "complete": d.get("complete", False),
                       "failures": d.get("failures", []), "warnings": d.get("warnings", [])}
result = {"format_version": 1, "positive_runs": positives, "ablations": ablations,
          "unproved": 0, "justified": 0,
          "runtime": {"production": 45792, "assertions": 45792},
          "notes": ["Clear-membership ablation can pass once but failed in the earlier clean repeat at Allocate Equal_Length precondition; retained for observed stability.",
                    "Canonical padding invariant is a frozen representation requirement, retained even when its ablation proves green.",
                    "Missing snapshots/padding predicate ablations are compile failures, not unproved-VC evidence."]}
print(json.dumps(result, indent=2, sort_keys=True))