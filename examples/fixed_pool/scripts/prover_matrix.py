#!/usr/bin/env python3
"""Single-prover measurement of the positive fixed-pool baseline (Task 003).

Under --level=2 -j0 the three provers race and the losers are killed, so the
winner (and thus reported step counts) varies between runs (Task 002). This
script re-runs the positive baseline once per prover with --prover=<p> and
otherwise the project's normal switches (timeout/steps from --level=2 are
NOT raised), and records for each: all checks proved?, unproved list, max
steps, slowest check, wall time. Output: obj/prover_matrix.json.

Measurement only; not a CI gate.
"""

from __future__ import annotations

import json
import sys

import check_proof_results as g

PROVERS = ("cvc5", "z3", "altergo")


def effort(out_dir) -> dict:
    worst_steps, worst_time = (0, ""), (0.0, "")
    for unit in g.GATED_UNITS:
        data = json.loads((out_dir / f"{unit}.spark").read_text(
            encoding="utf-8"))
        for entry in data.get("proof", []):
            where = f"{entry['rule']} {entry['file']}:{entry['line']}"
            for st in (entry.get("stats") or {}).values():
                if st.get("max_steps", 0) > worst_steps[0]:
                    worst_steps = (st["max_steps"], where)
                if st.get("max_time", 0.0) > worst_time[0]:
                    worst_time = (st["max_time"], where)
    return {"max_steps": worst_steps[0], "max_steps_check": worst_steps[1],
            "slowest_check_seconds": round(worst_time[0], 3),
            "slowest_check": worst_time[1]}


def main() -> int:
    results = []
    for prover in PROVERS:
        old = g.gnatprove_cmd
        g.gnatprove_cmd = lambda v, i: old(v, i) + [f"--prover={prover}"]
        try:
            run = g.run_gnatprove(f"prover_{prover}", "src")
        finally:
            g.gnatprove_cmd = old
        res = g.load_results(run["out_dir"])
        row = {"prover": prover, "returncode": run["returncode"],
               "total": len(res["proved"]) + len(res["unproved"])
                        + len(res["justified"]),
               "proved": len(res["proved"]),
               "unproved": sorted(f"{u['rule']}@{u['entity']}"
                                  for u in res["unproved"]),
               "all_proved": not res["unproved"] and run["returncode"] == 0,
               "wall_seconds": round(run["wall_seconds"], 2),
               **effort(run["out_dir"])}
        results.append(row)
        print(json.dumps(row), flush=True)
    (g.OBJ / "prover_matrix.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
