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

Task 008 adds two cases in which `spark-refine prove` itself launches
GNATprove (no --results; a stale decoy result set, the committed ring_b3
fixture, is placed first under obj/e2e_stale_decoy/ and must be ignored,
as must every result set left by earlier cases):

  E2E-D  prove   ring buffer A positive baseline: GNATprove exit 0,
                 fresh_discovery selects obj/baseline/gnatprove, fully
                 proved, no diagnostics
  E2E-E  prove   ring buffer B3 (materialised with the benchmark's own
                 apply_fault): GNATprove exit 1, prove exits 1 and still
                 reports the E2E-A SRD001 from the fresh result set

Only structural fields of the JSON report are checked (codes, entities,
rules, statuses, locations, confidence, data fields). English diagnostic
prose is never checked. The total number of SRD003 findings is NOT gated
(it is not intrinsically stable); only the known Z3-timeout check is.

Task 009 adds (needs an importable libadalang, e.g. the bundle built by
scripts/setup_libadalang.sh on PYTHONPATH; not part of the default set):

  E2E-F  SRD002 + semantic: fresh no_is_full_post ablation, then
                 `explain --semantic -P ring_buffer.gpr -X...` with the
                 materialised ablated source; every Push precondition
                 failure must resolve exactly to Ring_Buffer.Push with
                 Pre `not Is_Full (B)`, failed_conjunct null

  python3 diagnostics/scripts/e2e_fresh.py [srd001] [srd002] [srd003]
                                           [prove] [prove_negative]
                                           [semantic]

No argument runs all five. Exit 0 only if every selected case passes.
Writes diagnostics/obj/e2e/<case>.json (analyzer report) and
diagnostics/obj/e2e/summary.json (merged across invocations; git-ignored).
The script never modifies committed sources: the benchmark scripts
materialise their edited copies under examples/*/obj/.

Environment: GNATPROVE_EXEC as for the benchmark scripts (default
"alr -n exec --", run inside each example's Alire crate).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
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


# E2E-D / E2E-E: `spark-refine prove` (Task 008). The CLI itself runs
# GNATprove; the report must identify the result set THAT run wrote.
PROVE_PROJECT = "ring_buffer.gpr"
PROVE_BASELINE_PATH = "obj/baseline/gnatprove"
PROVE_DECOY = "obj/e2e_stale_decoy/gnatprove"
PROVE_B3_VARIANT = "e2e_prove_b3"
PROVE_B3_PATH = f"obj/{PROVE_B3_VARIANT}/gnatprove"
PROVE_B3_SRC = "obj/negative_src/head_tail_count/head_advances_wrong"


def _check_orchestration(report: dict, command: list[str], exit_code: int,
                         path: str, problems: list[str]) -> None:
    o = report.get("analysis", {}).get("orchestration") or {}
    _require(report.get("format_version") == 1,
             f"format_version {report.get('format_version')!r}", problems)
    _require(o.get("command") == command,
             f"command {o.get('command')!r}, expected {command!r}", problems)
    _require(o.get("gnatprove_exit_code") == exit_code,
             f"gnatprove_exit_code {o.get('gnatprove_exit_code')!r}, "
             f"expected {exit_code}", problems)
    _require(o.get("fresh") is True, f"fresh {o.get('fresh')!r}", problems)
    _require(o.get("result_selection") == "fresh_discovery",
             f"result_selection {o.get('result_selection')!r}", problems)
    _require(o.get("result_path") == path,
             f"result_path {o.get('result_path')!r}, expected {path!r}",
             problems)
    stale = o.get("stale_result_sets_ignored") or []
    _require(PROVE_DECOY in stale, f"stale decoy {PROVE_DECOY} not listed "
             f"as ignored ({len(stale)} ignored)", problems)
    _require(path not in stale, "selected path also listed as stale",
             problems)


def check_prove_positive(report: dict) -> list[str]:
    """E2E-D: fresh positive ring-buffer baseline chosen by fresh
    discovery among stale result sets; GNATprove 0; fully proved."""
    problems: list[str] = []
    _check_runs(report, problems)
    _check_orchestration(report, ["gnatprove", "-P", PROVE_PROJECT, "-j0"],
                         0, PROVE_BASELINE_PATH, problems)
    for run in report.get("runs", []):
        for key in ("unproved", "justified", "pragma_assume"):
            _require(run.get(key) == 0, f"run {run.get('name')}: {key} = "
                     f"{run.get(key)!r}", problems)
        _require((run.get("checks") or 0) > 0 and
                 run.get("proved") == run.get("checks"),
                 f"run {run.get('name')}: {run.get('proved')}/"
                 f"{run.get('checks')} proved", problems)
        _require({"ring_buffer", "ring_buffer_client_proof"}
                 <= set(run.get("units", [])),
                 f"units {run.get('units')!r}", problems)
    _require(report.get("diagnostics") == [],
             f"{len(report.get('diagnostics', []))} diagnostics on the "
             "positive baseline", problems)
    return problems


def check_prove_negative(report: dict) -> list[str]:
    """E2E-E: GNATprove exits nonzero on B3, and prove still reports the
    same SRD001 as E2E-A from the fresh result set of that run."""
    problems = check_srd001(report)
    _check_orchestration(report, [
        "gnatprove", "-P", PROVE_PROJECT, "-j0",
        f"-XRING_BUFFER_SRC={PROVE_B3_SRC}",
        f"-XRING_BUFFER_VARIANT={PROVE_B3_VARIANT}"],
        1, PROVE_B3_PATH, problems)
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


def _place_decoy(ex: Path) -> None:
    """A valid but STALE result set (the committed ring_b3 fixture) that
    `explain` would analyse and that `prove` must ignore."""
    decoy = ex / PROVE_DECOY
    if decoy.exists():
        shutil.rmtree(decoy)
    decoy.mkdir(parents=True)
    fixture = DIAGNOSTICS / "tests" / "fixtures" / "ring_b3"
    for f in fixture.iterdir():
        if f.name != "fixture.json":
            shutil.copy(f, decoy / f.name)


def _prove(ex: Path, passthrough: list[str], name: str,
           expect_exit: int) -> dict:
    """Run `spark-refine prove` itself (it launches GNATprove) inside the
    crate's Alire environment, WITHOUT --results."""
    prefix = shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))
    cmd = [*prefix, sys.executable, "-m", "spark_refine_diagnostics",
           "prove", "-P", PROVE_PROJECT, "--format", "json", "--",
           *passthrough]
    env = dict(os.environ, PYTHONPATH=str(DIAGNOSTICS))
    print(f"$ (cd {ex.relative_to(REPO)} && {shlex.join(cmd)})", flush=True)
    proc = subprocess.run(cmd, cwd=ex, env=env, stdout=subprocess.PIPE,
                          text=True)   # GNATprove output: our stderr
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != expect_exit:
        raise E2EError(f"spark-refine prove exit {proc.returncode}, "
                       f"expected {expect_exit}")
    return json.loads(proc.stdout)   # stdout must be the JSON report only


def e2e_prove() -> dict:
    ex = EXAMPLES / "ring_buffer"
    _place_decoy(ex)
    # obj/baseline/gnatprove may already exist (stale); prove must pick it
    # only because THIS GNATprove run rewrote it
    return _prove(ex, ["-j0"], "prove", 0)


def e2e_prove_negative() -> dict:
    ex = EXAMPLES / "ring_buffer"
    _place_decoy(ex)
    gate = _load_script(ex / "scripts" / "check_proof_results.py")
    fault = tomllib.loads((ex / "variants" / "head_tail_count" / "negative"
                           / "head_advances_wrong" / "fault.toml")
                          .read_text(encoding="utf-8"))
    gate.apply_fault(fault, ex / PROVE_B3_SRC,
                     ex / "variants" / "head_tail_count")
    return _prove(ex, ["-j0", f"-XRING_BUFFER_SRC={PROVE_B3_SRC}",
                       f"-XRING_BUFFER_VARIANT={PROVE_B3_VARIANT}"],
                  "prove_negative", 1)


SEMANTIC_ABLATION = "no_is_full_post"
SEMANTIC_PUSH_CALLS = {(9, 7): "Push (Q, A)", (10, 7): "Push (Q, B)",
                       (25, 7): "Push (Q, X)"}


def e2e_semantic() -> dict:
    """Task 009 E2E-F: fresh ablation run, then `explain --semantic` on the
    fresh result WITH the materialised (ablated) source it was proved from,
    selected through the same -X scenario values GNATprove used."""
    ex = EXAMPLES / "ring_buffer"
    since = time.time() - 1
    out = ex / "obj" / f"ablation_{SEMANTIC_ABLATION}" / "gnatprove"
    _run([sys.executable, "scripts/ablate_proof_support.py", "--only",
          SEMANTIC_ABLATION], ex, [out.parent])
    _fresh(out, since)
    prefix = shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))
    cmd = [*prefix, sys.executable, "-m", "spark_refine_diagnostics",
           "explain", str(out.relative_to(ex)), "--semantic",
           "-P", "ring_buffer.gpr",
           f"-XRING_BUFFER_SRC=obj/ablation_src/{SEMANTIC_ABLATION}",
           f"-XRING_BUFFER_VARIANT=ablation_{SEMANTIC_ABLATION}",
           "--format", "json"]
    pp = os.pathsep.join(p for p in (str(DIAGNOSTICS),
                                     os.environ.get("PYTHONPATH")) if p)
    print(f"$ (cd {ex.relative_to(REPO)} && {shlex.join(cmd)})", flush=True)
    proc = subprocess.run(cmd, cwd=ex, env=dict(os.environ, PYTHONPATH=pp),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise E2EError(f"explain --semantic exit {proc.returncode}: "
                       f"{proc.stderr}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "semantic.json").write_text(proc.stdout, encoding="utf-8")
    return json.loads(proc.stdout)


def check_semantic(report: dict) -> list[str]:
    """E2E-B's SRD002 criteria, plus: Libadalang evaluated, every Push
    precondition failure resolved exactly to Ring_Buffer.Push with its
    explicit Pre recovered, failed conjunct not claimed, the VC_ASSERT
    given assertion context only."""
    problems = check_srd002(report)
    meta = report.get("analysis", {}).get("semantic", {})
    _require(meta.get("evaluated") is True and
             meta.get("backend") == "libadalang",
             f"semantic not evaluated: {meta.get('reason')!r}", problems)
    checks = {}
    for d in report.get("diagnostics", []):
        if d.get("code") != "SRD002":
            continue
        sem = d.get("semantic")
        _require(isinstance(sem, dict), f"{d.get('entity')}: no semantic "
                 "block", problems)
        for c in (sem or {}).get("checks", []):
            loc = c.get("location", {})
            checks[(loc.get("line"), loc.get("column"))] = c
    for pos, text in SEMANTIC_PUSH_CALLS.items():
        c = checks.get(pos)
        if c is None:
            problems.append(f"no semantic entry for {pos}")
            continue
        pre = c.get("precondition") or {}
        decl = (c.get("callee") or {}).get("declaration") or {}
        _require(c.get("resolution") == "exact", f"{pos}: resolution "
                 f"{c.get('resolution')!r} ({c.get('reason')})", problems)
        _require((c.get("call") or {}).get("text") == text,
                 f"{pos}: call {c.get('call')!r}", problems)
        _require((c.get("callee") or {}).get("name") == "Ring_Buffer.Push",
                 f"{pos}: callee {c.get('callee')!r}", problems)
        _require(decl.get("file") == f"obj/ablation_src/{SEMANTIC_ABLATION}"
                 "/ring_buffer.ads" and decl.get("start_line") == 36,
                 f"{pos}: declaration {decl!r}", problems)
        _require(pre.get("text") == "not Is_Full (B)" and
                 (pre.get("location") or {}).get("start_line") == 37,
                 f"{pos}: Pre {pre.get('text')!r}", problems)
        _require(pre.get("failed_conjunct") is None and
                 pre.get("attribution") == "not_provided_by_gnatprove",
                 f"{pos}: failed conjunct claimed", problems)
    a = checks.get((16, 43), {})
    _require(a.get("resolution") == "exact" and "assertion" in a
             and "callee" not in a and "precondition" not in a,
             "VC_ASSERT 16:43: not assertion-only context", problems)
    return problems


def _load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CASES = {
    "srd001": ("E2E-A SRD001 ring buffer B3 head_advances_wrong",
               e2e_srd001, check_srd001),
    "srd002": ("E2E-B SRD002 ring buffer no_is_full_post",
               e2e_srd002, check_srd002),
    "srd003": ("E2E-C SRD003 library-backed pool, cvc5/z3/altergo",
               e2e_srd003, check_srd003),
    "prove": ("E2E-D spark-refine prove, fresh ring buffer baseline",
              e2e_prove, check_prove_positive),
    "prove_negative": ("E2E-E spark-refine prove, GNATprove exit 1 on B3",
                       e2e_prove_negative, check_prove_negative),
    "semantic": ("E2E-F SRD002 + Libadalang semantic enrichment, "
                 "ring buffer no_is_full_post",
                 e2e_semantic, check_semantic),
}


def main(argv: list[str]) -> int:
    selected = argv or [k for k in CASES if k != "semantic"]
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
