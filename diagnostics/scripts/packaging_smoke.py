#!/usr/bin/env python3
"""Task 006 packaging smoke test: build, inspect, install, run OUTSIDE the
repository.

  python3 diagnostics/scripts/packaging_smoke.py [--editable]
                                                 [--no-build-isolation]

Steps (each failure exits 1 with a message):

 1. Build a wheel from diagnostics/ with pip.
 2. Inspect the wheel: it may contain only spark_refine_diagnostics/*.py
    and *.dist-info metadata. No tests/, fixtures/, scripts/, obj/,
    .sarif/.spark/.ali/.toml data. Record its size.
 3. Create an isolated venv in a temporary directory, install the wheel
    (or, with --editable, `pip install -e diagnostics/`).
 4. From a temporary directory unrelated to the repository run the
    installed console script:
      spark-refine --version
      spark-refine rules / rules --format json
      spark-refine explain <absolute fixture path> --format json
      spark-refine explain            (discovery in a scratch project)
      spark-refine explain            (zero candidates -> exit 2)
      spark-refine analyze <absolute fixture path> --format json
      spark-refine compare-provers --run ... --format json
      python -m spark_refine_diagnostics rules
      spark-refine prove -P fake.gpr --dry-run   (Task 008; also --format
                                     json via python -m)
      spark-refine prove ...        (fake GNATprove: stale result refused;
                                     fresh result diagnosed, exit preserved)
    and check that the package is imported from the venv, not the repo.
 5. For a wheel install: check the installed files (package size, no
    fixture data in site-packages).

Standard library only; needs network only for pip's build isolation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

DIAGNOSTICS = Path(__file__).resolve().parents[1]
REPO = DIAGNOSTICS.parent
FIXTURES = DIAGNOSTICS / "tests" / "fixtures"
PACKAGE = "spark_refine_diagnostics"
DATA_SUFFIXES = (".sarif", ".spark", ".ali", ".toml", ".json", ".adb",
                 ".ads")


class SmokeError(Exception):
    pass


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise SmokeError(msg)
    print(f"  ok: {msg}")


def run(cmd: list, cwd: Path, env: dict | None = None,
        expect: int = 0) -> subprocess.CompletedProcess:
    print(f"$ (cd {cwd} && {' '.join(map(str, cmd))})", flush=True)
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env,
                          capture_output=True, text=True)
    if proc.returncode != expect:
        raise SmokeError(f"exit {proc.returncode} (expected {expect}):\n"
                         f"{proc.stdout}\n{proc.stderr}")
    return proc


def wheel_disallowed(names: list[str]) -> list[str]:
    """Wheel members outside the allow-list (package .py + dist-info)."""
    bad = []
    for n in names:
        top = n.split("/", 1)[0]
        if top.endswith(".dist-info"):
            if n.endswith(DATA_SUFFIXES[:3]):
                bad.append(n)
            continue
        if top != PACKAGE or not n.endswith(".py") or n.count("/") != 1:
            bad.append(n)
    return bad


def build_wheel(dest: Path, isolation: bool) -> Path:
    cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q",
           "-w", dest, DIAGNOSTICS]
    if not isolation:
        cmd.insert(4, "--no-build-isolation")
    run(cmd, cwd=dest)
    wheels = sorted(dest.glob("spark_refine-*.whl"))
    if len(wheels) != 1:
        raise SmokeError(f"expected one wheel, got {wheels}")
    return wheels[0]


def inspect_wheel(whl: Path) -> None:
    print(f"== wheel {whl.name}: {whl.stat().st_size} bytes")
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        unpacked = sum(i.file_size for i in z.infolist())
        ep = next(n for n in names if n.endswith("entry_points.txt"))
        entry_points = z.read(ep).decode()
        meta = z.read(next(n for n in names
                           if n.endswith("METADATA"))).decode()
    check(not wheel_disallowed(names),
          f"wheel holds only {PACKAGE}/*.py + metadata "
          f"({len(names)} members, {unpacked} bytes unpacked)")
    check(not any("fixtures" in n or "tests/" in n for n in names),
          "no tests/ or fixtures/ in the wheel")
    check("spark-refine = spark_refine_diagnostics.cli:main"
          in entry_points, "console script spark-refine declared")
    check("Requires-Dist" not in meta, "no runtime dependencies")
    for module in ("cli", "discovery", "orchestration"):
        check(f"{PACKAGE}/{module}.py" in names,
              f"{PACKAGE}/{module}.py is in the wheel")
    check(unpacked < 1_000_000,
          "wheel payload well below the 5.5 MB fixture corpus")


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / "python"


def installed_cli_checks(venv: Path, work: Path, editable: bool) -> None:
    bindir = venv_python(venv).parent
    exe = bindir / "spark-refine"
    check(exe.is_file(), f"console script installed: {exe}")
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    outside = work / "unrelated"
    outside.mkdir()
    check(not outside.resolve().is_relative_to(REPO),
          f"working directory {outside} is outside the repository")

    py = venv_python(venv)
    where = Path(run([py, "-c", f"import {PACKAGE} as m; print(m.__file__)"],
                     cwd=outside, env=env).stdout.strip())
    if editable:
        check(where.is_relative_to(DIAGNOSTICS),
              f"editable install imports from the checkout ({where})")
    else:
        check(where.is_relative_to(venv) and not where.is_relative_to(REPO),
              f"package imported from the venv, not the repo ({where})")

    run([exe, "--version"], cwd=outside, env=env)
    # Task 009: the core install has no libadalang; --semantic degrades,
    # never fails, and leaves the base report intact
    sem_fixture = DIAGNOSTICS / "tests" / "semantic_fixtures" / \
        "ring_no_is_full_post" / "results"
    no_lal = run([py, "-c", "import importlib.util as u; "
                  "print(u.find_spec('libadalang') is None)"],
                 cwd=outside, env=env).stdout.strip()
    if no_lal == "True":
        doc = json.loads(run([exe, "explain", sem_fixture, "--semantic",
                              "-P", "x.gpr", "--format", "json"],
                             cwd=outside, env=env).stdout)
        sem = doc["analysis"]["semantic"]
        check(sem["evaluated"] is False and "not importable" in
              sem["reason"] and doc["summary"]["by_code"]["SRD002"] == 2,
              "core install: --semantic without libadalang degrades "
              "(exit 0, base SRD002 kept, evaluated=false)")
    out = run([exe, "rules"], cwd=outside, env=env).stdout
    check(all(c in out for c in ("SRD001", "SRD002", "SRD003")),
          "spark-refine rules lists SRD001-SRD003")
    rules = json.loads(run([exe, "rules", "--format", "json"], cwd=outside,
                           env=env).stdout)["rules"]
    check({c: r["action"] for c, r in rules.items()} == {
        "SRD001": "fix_invariant_then_reprove",
        "SRD002": "validate_client_goal_then_review_public_contracts",
        "SRD003": "preserve_portfolio_or_strengthen_proof"},
        "rules --format json carries the action identifiers")

    p5 = (FIXTURES / "pool_p5").resolve()
    doc = json.loads(run([exe, "explain", p5, "--format", "json"],
                         cwd=outside, env=env).stdout)
    check(doc["format_version"] == 1 and
          [(d["code"], d["category"], d["action"])
           for d in doc["diagnostics"]] ==
          [("SRD001", "proof_context", "fix_invariant_then_reprove")] and
          doc["summary"]["by_code"]["SRD001"] == 1,
          "explain <absolute fixture path> --format json: one SRD001")
    ana = run([exe, "analyze", p5, "--format", "json"], cwd=outside,
              env=env).stdout
    check(json.loads(ana) == doc, "analyze alias output == explain output")

    gap = (FIXTURES / "pool_spec_no_count_posts").resolve()
    doc = json.loads(run([exe, "explain", gap / "gnatprove.sarif",
                          "--format", "json"], cwd=outside, env=env).stdout)
    check(doc["summary"]["by_code"]["SRD002"] == 2 and
          doc["analysis"]["rules"]["SRD002"]["dependency_source"] == "ali",
          "explain <gnatprove.sarif>: two SRD002 (dependencies from .ali)")

    runs = []
    for prover in ("cvc5", "z3", "altergo"):
        runs += ["--run",
                 f"{prover}={(FIXTURES / f'pool_prover_{prover}').resolve()}"]
    doc = json.loads(run([exe, "compare-provers", *runs, "--format", "json"],
                         cwd=outside, env=env).stdout)
    check(doc["summary"]["by_code"]["SRD003"] == 6 and
          all(d["action"] == "preserve_portfolio_or_strengthen_proof"
              for d in doc["diagnostics"]),
          "compare-provers: six SRD003 with the portfolio action")


    # discovery in a scratch project, outside the repository
    project = work / "project"
    result = project / "obj" / "proof" / "gnatprove"
    result.mkdir(parents=True)
    for f in p5.iterdir():
        if f.name != "fixture.json":
            shutil.copy(f, result / f.name)
    doc = json.loads(run([exe, "explain", "--format", "json"], cwd=project,
                         env=env).stdout)
    check(doc["analysis"]["input"] == {"path": "obj/proof/gnatprove",
                                       "discovered": True} and
          doc["summary"]["diagnostic_count"] == 1,
          "explain (no PATH) discovers the single result set")
    proc = run([exe, "explain"], cwd=outside, env=env, expect=2)
    check(proc.stdout == "" and
          "No GNATprove result set found." in proc.stderr,
          "explain with zero candidates exits 2, no report")
    shutil.copytree(result, project / "obj" / "other" / "gnatprove")
    proc = run([exe, "explain"], cwd=project, env=env, expect=2)
    check(proc.stdout == "" and
          "  obj/other/gnatprove\n  obj/proof/gnatprove\n" in proc.stderr,
          "explain with two candidates exits 2, sorted candidate list")

    run([py, "-m", PACKAGE, "rules"], cwd=outside, env=env)
    check(True, "python -m spark_refine_diagnostics rules works")

    prove_checks(exe, py, work, env, p5)


FAKE_GNATPROVE = """#!{python}
import os, shutil, sys
print("fake gnatprove stdout: Phase 1 of 3 {{not json")
print("fake gnatprove stderr", file=sys.stderr)
if os.environ.get("FAKE_WRITE"):
    dest = os.path.join("obj", "fresh", "gnatprove")
    os.makedirs(dest, exist_ok=True)
    for n in sorted(os.listdir(os.environ["FAKE_WRITE"])):
        if n != "fixture.json":
            shutil.copy(os.path.join(os.environ["FAKE_WRITE"], n), dest)
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


def prove_checks(exe: Path, py: Path, work: Path, env: dict,
                 fixture: Path) -> None:
    """Task 008: `spark-refine prove` from the installed package, with a
    fake GNATprove (no Ada toolchain), outside the repository."""
    project = work / "prove project"
    project.mkdir()
    proc = run([exe, "prove", "-P", "fake.gpr", "--dry-run"], cwd=project,
               env=env)
    check("gnatprove -P fake.gpr" in proc.stderr and
          "dry run" in proc.stdout,
          "prove -P fake.gpr --dry-run shows the command, runs nothing")
    doc = json.loads(run([py, "-m", PACKAGE, "prove", "-P", "fake.gpr",
                          "--dry-run", "--format", "json", "--",
                          "--level=2"], cwd=project, env=env).stdout)
    check(doc["orchestration"]["command"] ==
          ["gnatprove", "-P", "fake.gpr", "--level=2"],
          "python -m ... prove --dry-run --format json: orchestration plan")

    fake = work / "fake bin" / "gnatprove"
    fake.parent.mkdir()
    fake.write_text(FAKE_GNATPROVE.format(python=sys.executable),
                    encoding="utf-8")
    fake.chmod(0o755)
    # a stale, valid result set must never be analysed by prove
    stale = project / "obj" / "stale" / "gnatprove"
    shutil.copytree(fixture, stale,
                    ignore=shutil.ignore_patterns("fixture.json"))
    proc = run([exe, "prove", "-P", "fake.gpr", "--gnatprove", fake,
                "--format", "json"], cwd=project, env=env, expect=2)
    check(proc.stdout == "" and "stale" in proc.stderr,
          "prove refuses a stale result set (exit 2, no report)")
    proc = run([exe, "prove", "-P", "fake.gpr", "--gnatprove", fake,
                "--format", "json"], cwd=project,
               env={**env, "FAKE_WRITE": str(fixture), "FAKE_EXIT": "1"},
               expect=1)
    doc = json.loads(proc.stdout)
    o = doc["analysis"]["orchestration"]
    check(o["result_path"] == "obj/fresh/gnatprove" and
          o["gnatprove_exit_code"] == 1 and o["fresh"] is True and
          o["stale_result_sets_ignored"] == ["obj/stale/gnatprove"] and
          doc["summary"]["by_code"]["SRD001"] == 1 and
          "fake gnatprove stdout" in proc.stderr,
          "prove with fake GNATprove (exit 1): fresh result diagnosed, "
          "exit code preserved, GNATprove output on stderr, JSON stdout")


def inspect_installed(venv: Path) -> None:
    py = venv_python(venv)
    site = Path(subprocess.run(
        [py, "-c", f"import {PACKAGE}, pathlib; "
         f"print(pathlib.Path({PACKAGE}.__file__).parent.parent)"],
        capture_output=True, text=True, check=True,
        cwd=venv).stdout.strip())
    pkg = site / PACKAGE
    files = [p for p in pkg.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files
               if "__pycache__" not in p.parts)
    print(f"== installed package {pkg}: {len(files)} files, "
          f"{size} bytes of Python source")
    check(all(p.suffix in (".py", ".pyc") for p in files),
          "installed package holds only Python modules")
    dist = [p for p in site.iterdir()
            if p.name.startswith("spark_refine-") and
            p.name.endswith(".dist-info")]
    check(len(dist) == 1, f"one dist-info directory: {[d.name for d in dist]}")
    stray = [p for p in site.rglob("*")
             if p.suffix in (".sarif", ".spark", ".ali")]
    check(not stray, "no GNATprove fixture data anywhere in site-packages")
    check(not (site / "tests").exists() and not (site / "scripts").exists(),
          "no top-level tests/ or scripts/ installed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--editable", action="store_true",
                    help="test `pip install -e diagnostics/` instead")
    ap.add_argument("--no-build-isolation", action="store_true",
                    help="build with the venv's setuptools (offline use)")
    args = ap.parse_args()
    iso = ["--no-build-isolation"] if args.no_build_isolation else []
    try:
        with tempfile.TemporaryDirectory(prefix="spark-refine-pkg-") as t:
            work = Path(t).resolve()
            venv = work / "venv"
            run([sys.executable, "-m", "venv", venv], cwd=work)
            py = venv_python(venv)
            if iso:
                run([py, "-m", "pip", "install", "-q", "setuptools>=77"],
                    cwd=work)
            if args.editable:
                run([py, "-m", "pip", "install", "-q", *iso, "-e",
                     DIAGNOSTICS], cwd=work)
            else:
                dist = work / "dist"
                dist.mkdir()
                whl = build_wheel(dist, not iso)
                inspect_wheel(whl)
                run([py, "-m", "pip", "install", "-q", whl], cwd=work)
                inspect_installed(venv)
            installed_cli_checks(venv, work, args.editable)
    except SmokeError as exc:
        print(f"PACKAGING SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        # setuptools writes these next to pyproject.toml; keep tree clean
        for junk in ("build", "spark_refine.egg-info"):
            shutil.rmtree(DIAGNOSTICS / junk, ignore_errors=True)
    print("packaging smoke test passed"
          f" ({'editable' if args.editable else 'wheel'} install)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

