#!/usr/bin/env python3
"""Fresh end-to-end diagnostics gate (Task 005 corrective).

The committed fixture corpus (tests/fixtures, 49 runs) is the primary,
detailed regression suite. This script is a SMALL complementary smoke test:
it runs the pinned toolchain (Alire 2.1.1, FSF GNATprove 16.1.0, GNAT
16.1.0) NOW, through the benchmarks' own unchanged scripts, and analyses
the fresh, unsanitized SARIF / .spark / .ali output with the real CLI
(`python3 -m spark_refine_diagnostics ... --format json`, in a subprocess).

  E2E-A  SRD001  ring buffer B, fault B3 head_advances_wrong
                 (check_proof_results.py negative --variant head_tail_count
                  --only head_advances_wrong)
  E2E-B  SRD002  ring buffer A, public-contract ablation no_is_full_post
                 (ablate_proof_support.py --only no_is_full_post); exercises
                 fresh GNAT .ali -> ali.py -> transitive closure -> SRD002
  E2E-C  SRD003  library-backed fixed pool, single-prover runs
                 (prover_matrix.py --variant library_backed: cvc5, z3,
                  altergo), then compare-provers

Only structural fields of the JSON report are checked (codes, entities,
rules, statuses, locations, confidence, data fields). English diagnostic
prose is never checked. The total number of SRD003 findings is NOT gated
(it is not intrinsically stable); only the known Z3-timeout check is.

  python3 diagnostics/scripts/e2e_fresh.py [srd001] [srd002] [srd003]

No argument runs all three. Exit 0 only if every selected case passes.
Writes diagnostics/obj/e2e/<case>.json (analyzer report) and
diagnostics/obj/e2e/summary.json (merged across invocations; git-ignored).
The script never modifies committed sources: the benchmark scripts
materialise their edited copies under examples/*/obj/.

Environment: GNATPROVE_EXEC as for the benchmark scripts (default
"alr -n exec --", run inside each example's Alire crate).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAGNOSTICS = REPO / "diagnostics"
EXAMPLES = REPO / "examples"
OUT = DIAGNOSTICS / "obj" / "e2e"

GNATPROVE_VERSION = "FSF 16.1.0"
ALI_VERSION = "GNAT Lib v16"


class E2EError(Exception):
    pass


def _require(cond: bool, msg: str, problems: list[str]) -> None:
    if not cond:
        problems.append(msg)


def _data(diag: dict) -> dict:
    return diag.get("data") or {}


def _check_runs(report: dict, problems: list[str]) -> None:
    runs = report.get("runs", [])
    _require(bool(runs), "report has no runs", problems)
    for run in runs:
        _require(run.get("gnatprove") == GNATPROVE_VERSION,
                 f"run {run.get('name')}: GNATprove "
                 f"{run.get('gnatprove')!r}, expected {GNATPROVE_VERSION!r}",
                 problems)
        _require(run.get("unit_attribution") == "spark",
                 f"run {run.get('name')}: .spark files not used", problems)


# --------------------------------------------------------------------------
# Checkers: pure functions over an analyzer JSON report. They are also run
# on the committed fixtures by tests/test_e2e_checks.py, so the gate's own
# logic is covered without a toolchain.
# --------------------------------------------------------------------------

SRD001_ENTITY = "Ring_Buffer.Pop"


def check_srd001(report: dict) -> list[str]:
    """SRD001 present for the expected entity, high confidence unless the
    report records a real SARIF/.spark disagreement, and at least one
    proved postcondition listed as potentially affected."""
    problems: list[str] = []
    _check_runs(report, problems)
    diags = [d for d in report.get("diagnostics", [])
             if d.get("code") == "SRD001" and d.get("entity") == SRD001_ENTITY]
    _require(len(diags) == 1, f"expected one SRD001 for {SRD001_ENTITY}, "
             f"got {len(diags)}", problems)
    disagreement = any(n.startswith("consistency:")
                       for n in report.get("notes", []))
    for d in diags:
        if d.get("confidence") != "high":
            _require(disagreement, f"SRD001 confidence "
                     f"{d.get('confidence')!r} without a recorded "
                     "SARIF/.spark disagreement", problems)
        failed = [r for r in d.get("related", [])
                  if r.get("role") == "failed"
                  and r.get("rule") == "VC_INVARIANT_CHECK"
                  and r.get("status") == "unproved"]
        affected = [r for r in d.get("related", [])
                    if r.get("role") == "potentially affected"
                    and r.get("rule") == "VC_POSTCONDITION"
                    and r.get("status") == "proved"
                    and r.get("entity") == SRD001_ENTITY]
        _require(bool(failed), "SRD001 cites no unproved invariant check",
                 problems)
        _require(bool(affected), "SRD001 lists no proved postcondition as "
                 "potentially affected", problems)
    return problems


SRD002_CLIENT_UNIT = "ring_buffer_client_proof"
SRD002_IMPL_UNITS = ["ring_buffer"]
# expected client entity -> rules that must appear among its failures
SRD002_EXPECTED = {
    "Ring_Buffer_Client_Proof.Push_Push_Pop": {"VC_PRECONDITION",
                                               "VC_ASSERT"},
    "Ring_Buffer_Client_Proof.Rotate": {"VC_PRECONDITION"},
}


def check_srd002(report: dict) -> list[str]:
    """SRD002 present for the expected client entities and rules, the
    implementation dependency closure green, dependencies from .ali."""
    problems: list[str] = []
    _check_runs(report, problems)
    meta = report.get("analysis", {}).get("rules", {}).get("SRD002", {})
    _require(meta.get("evaluated") is True, "SRD002 not evaluated: "
             f"{meta.get('reason', '')}", problems)
    _require(meta.get("dependency_source") == "ali",
             f"dependency_source {meta.get('dependency_source')!r}",
             problems)
    _require(meta.get("ali_status") == "ok",
             f"ali_status {meta.get('ali_status')!r}", problems)
    _require(meta.get("ali_versions") == [ALI_VERSION],
             f"ali_versions {meta.get('ali_versions')!r}", problems)
    got = {d.get("entity"): d for d in report.get("diagnostics", [])
           if d.get("code") == "SRD002"}
    for entity, rules in SRD002_EXPECTED.items():
        d = got.get(entity)
        if d is None:
            problems.append(f"no SRD002 for {entity}")
            continue
        data = _data(d)
        client_rules = set(data.get("client_rules", []))
        _require(rules <= client_rules, f"{entity}: client_rules "
                 f"{sorted(client_rules)}, expected {sorted(rules)}",
                 problems)
        _require(client_rules <= {"VC_PRECONDITION", "VC_ASSERT"},
                 f"{entity}: unexpected client_rules "
                 f"{sorted(client_rules)}", problems)
        _require(data.get("client_unit") == SRD002_CLIENT_UNIT,
                 f"{entity}: client_unit {data.get('client_unit')!r}",
                 problems)
        _require(list(data.get("implementation_units", []))
                 == SRD002_IMPL_UNITS,
                 f"{entity}: implementation_units "
                 f"{data.get('implementation_units')!r}", problems)
        _require(data.get("implementation_failures") == 0
                 and (data.get("implementation_checks") or 0) > 0,
                 f"{entity}: implementation closure not green "
                 f"({data.get('implementation_checks')} checks, "
                 f"{data.get('implementation_failures')} failures)",
                 problems)
        _require(data.get("dependency_source") == "ali",
                 f"{entity}: dependency_source "
                 f"{data.get('dependency_source')!r}", problems)
        failures = [r for r in d.get("related", [])
                    if r.get("role") == "client failure"]
        _require(bool(failures) and all(
            r.get("status") == "unproved" and r.get("entity") == entity
            and r.get("rule") in rules | client_rules
            for r in failures), f"{entity}: client failures malformed",
            problems)
    for run in report.get("runs", []):
        _require(run.get("justified") == 0,
                 f"run {run.get('name')}: justified checks", problems)
    return problems


# The known prover-sensitive check (examples/fixed_pool/LIBRARY_METRICS.md
# prover matrix): the reusable library's Model postcondition. Z3 alone
# times out on it, Alt-Ergo alone proves it (CVC5 alone also fails it).
SRD003_RULE = "VC_POSTCONDITION"
SRD003_ENTITY = "Fixed_Pool.Free_Prefix.Model"
SRD003_FILE = "spark_refine_prefix_sets.ads"
SRD003_LINE = 93
SRD003_OUTCOMES = {"z3": "unproved", "altergo": "proved"}


def check_srd003(report: dict) -> list[str]:
    """The known SRD003 is present with an exact or unique_entity match and
    the known per-prover outcomes. The total count is not gated."""
    problems: list[str] = []
    _check_runs(report, problems)
    names = {r.get("name") for r in report.get("runs", [])}
    _require(set(SRD003_OUTCOMES) <= names,
             f"runs {sorted(names)} lack {sorted(SRD003_OUTCOMES)}",
             problems)
    known = [d for d in report.get("diagnostics", [])
             if d.get("code") == "SRD003"
             and d.get("entity") == SRD003_ENTITY
             and _data(d).get("rule") == SRD003_RULE
             and (d.get("primary_location") or {}).get("file") == SRD003_FILE
             and (d.get("primary_location") or {}).get("line") == SRD003_LINE]
    _require(len(known) == 1, f"expected one SRD003 for {SRD003_RULE} "
             f"{SRD003_ENTITY} ({SRD003_FILE}:{SRD003_LINE}), got "
             f"{len(known)}", problems)
    for d in known:
        _require(d.get("match_quality") in ("exact", "unique_entity"),
                 f"match_quality {d.get('match_quality')!r}", problems)
        outcomes = dict(_data(d).get("results", []))
        for prover, outcome in SRD003_OUTCOMES.items():
            _require(outcomes.get(prover) == outcome,
                     f"{prover}: {outcomes.get(prover)!r}, expected "
                     f"{outcome!r}", problems)
    for d in report.get("diagnostics", []):
        if d.get("code") == "SRD003":
            _require(d.get("match_quality") in ("exact", "unique_entity"),
                     f"SRD003 {d.get('entity')}: match_quality "
                     f"{d.get('match_quality')!r}", problems)
    return problems



# --------------------------------------------------------------------------
# Driver: fresh GNATprove runs through the benchmark scripts, then the CLI
# --------------------------------------------------------------------------

def _show_logs(obj_dirs: list[Path]) -> None:
    """On failure, print the tail of each GNATprove log the benchmark
    script wrote (obj/<variant>/gnatprove.log), so CI shows the cause."""
    for d in obj_dirs:
        log = d / "gnatprove.log"
        if not log.is_file():
            print(f"   (no {log.relative_to(REPO)})", flush=True)
            continue
        lines = log.read_text("utf-8", errors="replace").splitlines()
        print(f"   --- tail of {log.relative_to(REPO)} ---", flush=True)
        for line in lines[-40:]:
            print(f"   | {line}", flush=True)


def _run(cmd: list[str], cwd: Path, obj_dirs: list[Path]) -> None:
    print(f"$ (cd {cwd.relative_to(REPO)} && "
          f"python3 {' '.join(cmd[1:])})", flush=True)
    proc = subprocess.run(cmd, cwd=cwd)
    if proc.returncode != 0:
        _show_logs(obj_dirs)
        raise E2EError(f"{' '.join(cmd[1:])}: exit {proc.returncode}")


def _fresh(out_dir: Path, since: float) -> None:
    """The output must have been written by THIS run (the benchmark
    scripts delete obj/<variant>/ first; checked anyway) and contain the
    SARIF, .spark and .ali files the analyzer reads."""
    sarif = out_dir / "gnatprove.sarif"
    problem = None
    if not sarif.is_file():
        problem = f"{sarif}: missing (GNATprove did not run?)"
    elif sarif.stat().st_mtime < since:
        problem = f"{sarif}: stale (older than this E2E run)"
    else:
        for ext in ("spark", "ali"):
            if not any(out_dir.glob(f"*.{ext}")):
                problem = f"{out_dir}: no .{ext} files produced"
    if problem:
        _show_logs([out_dir.parent])
        raise E2EError(problem)


def _cli(args: list[str], name: str) -> dict:
    cmd = [sys.executable, "-m", "spark_refine_diagnostics", *args,
           "--format", "json"]
    print(f"$ (cd diagnostics && python3 {' '.join(cmd[1:])})", flush=True)
    proc = subprocess.run(cmd, cwd=DIAGNOSTICS, capture_output=True,
                          text=True)
    if proc.returncode != 0:
        raise E2EError(f"analyzer exit {proc.returncode}: {proc.stderr}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(proc.stdout, encoding="utf-8")
    return json.loads(proc.stdout)


def e2e_srd001() -> dict:
    ex = EXAMPLES / "ring_buffer"
    since = time.time() - 1
    # the benchmark's own negative gate: materialises B3, runs GNATprove
    # and exits 0 only if the fault is detected where expected
    out = ex / "obj" / "negative_htc_head_advances_wrong" / "gnatprove"
    _run([sys.executable, "scripts/check_proof_results.py", "negative",
          "--variant", "head_tail_count", "--only", "head_advances_wrong"],
         ex, [out.parent])
    _fresh(out, since)
    return _cli(["analyze", str(out), "--name", "fresh_ring_b3"], "srd001")


def e2e_srd002() -> dict:
    ex = EXAMPLES / "ring_buffer"
    since = time.time() - 1
    # the Task 001 ablation script (measurement: exits 0 whatever the
    # proof outcome); first_length is its default variant
    out = ex / "obj" / "ablation_no_is_full_post" / "gnatprove"
    _run([sys.executable, "scripts/ablate_proof_support.py", "--only",
          "no_is_full_post"], ex, [out.parent])
    _fresh(out, since)
    return _cli(["analyze", str(out), "--name", "fresh_no_is_full_post"],
                "srd002")


def e2e_srd003() -> dict:
    ex = EXAMPLES / "fixed_pool"
    since = time.time() - 1
    # the Task 004 prover matrix: one --prover=<p> run per prover
    outs = {p: ex / "obj" / f"prover_library_backed_{p}" / "gnatprove"
            for p in ("cvc5", "z3", "altergo")}
    _run([sys.executable, "scripts/prover_matrix.py", "--variant",
          "library_backed"], ex, [o.parent for o in outs.values()])
    runs = []
    for prover, out in outs.items():
        _fresh(out, since)
        runs += ["--run", f"{prover}={out}"]
    return _cli(["compare-provers", *runs], "srd003")


CASES = {
    "srd001": ("E2E-A SRD001 ring buffer B3 head_advances_wrong",
               e2e_srd001, check_srd001),
    "srd002": ("E2E-B SRD002 ring buffer no_is_full_post",
               e2e_srd002, check_srd002),
    "srd003": ("E2E-C SRD003 library-backed pool, cvc5/z3/altergo",
               e2e_srd003, check_srd003),
}


def main(argv: list[str]) -> int:
    selected = argv or list(CASES)
    unknown = [a for a in selected if a not in CASES]
    if unknown:
        print(__doc__)
        print(f"unknown case(s): {unknown}", file=sys.stderr)
        return 2
    summary, failed = {}, False
    for key in selected:
        title, produce, check = CASES[key]
        print(f"== {title}", flush=True)
        start = time.monotonic()
        try:
            problems = check(produce())
        except (E2EError, json.JSONDecodeError, OSError) as exc:
            problems = [f"error: {exc}"]
        summary[key] = {"title": title, "passed": not problems,
                        "problems": problems,
                        "wall_seconds": round(time.monotonic() - start, 1)}
        for p in problems:
            print(f"   FAIL: {p}", flush=True)
        print(f"   {'PASS' if not problems else 'FAIL'}: {title}",
              flush=True)
        failed |= bool(problems)
    # merged across invocations (CI runs one case per step)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    try:
        merged = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        merged = {}
    merged.update(summary)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    passed = sum(v["passed"] for v in summary.values())
    print(f"fresh E2E diagnostics: {passed}/{len(summary)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
