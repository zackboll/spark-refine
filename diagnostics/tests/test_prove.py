"""Task 008: `spark-refine prove` orchestration.

Command construction, freshness selection, subprocess / exit semantics,
JSON stdout cleanliness and stale safety. A fake GNATprove (a small Python
script driven by a JSON plan) stands in for the real tool: no Ada
toolchain is needed. The real pinned GNATprove 16.1.0 is exercised by
E2E-D in scripts/e2e_fresh.py (CI job diagnostics-e2e).
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from spark_refine_diagnostics import cli, orchestration as orch
from spark_refine_diagnostics.discovery import SARIF_NAME
from test_explain import call, place

FAKE = """#!{python}
import json, os, shutil, sys
plan = json.load(open(os.environ["FAKE_GNATPROVE_PLAN"], encoding="utf-8"))
with open(plan["argv_log"], "w", encoding="utf-8") as f:
    json.dump(sys.argv[1:], f)
sys.stdout.write(plan.get("stdout", "")); sys.stdout.flush()
sys.stderr.write(plan.get("stderr", "")); sys.stderr.flush()
for src, dest in plan.get("copy", []):
    os.makedirs(dest, exist_ok=True)
    for n in sorted(os.listdir(src)):
        if n != "fixture.json":
            shutil.copy(os.path.join(src, n), os.path.join(dest, n))
for path in plan.get("rewrite", []):
    data = open(path, "rb").read()
    open(path, "wb").write(data + b"\\n")
if plan.get("signal"):
    os.kill(os.getpid(), plan["signal"])
sys.exit(plan.get("exit", 0))
"""

NOISE_OUT = "Phase 1 of 3: {not json\n"
NOISE_ERR = "gnatprove: unproved check messages considered as errors\n"


def rewrite(result_dir: Path) -> None:
    """Rewrite a result set's SARIF (new bytes; new stamp)."""
    sarif = result_dir / SARIF_NAME
    sarif.write_bytes(sarif.read_bytes() + b" ")


class FakeProject(unittest.TestCase):
    """A temporary project directory plus a fake GNATprove executable
    in a directory whose name contains a space."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.project = base / "project"
        self.project.mkdir()
        bindir = base / "fake bin"
        bindir.mkdir()
        self.fake = bindir / "gnatprove"
        self.fake.write_text(FAKE.format(python=sys.executable),
                             encoding="utf-8")
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IXUSR)
        self.plan_file = base / "plan.json"
        self.argv_log = base / "argv.json"
        env = mock.patch.dict(os.environ, {
            "FAKE_GNATPROVE_PLAN": str(self.plan_file)})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def plan(self, **kw) -> None:
        kw["argv_log"] = str(self.argv_log)
        self.plan_file.write_text(json.dumps(kw), encoding="utf-8")

    def old(self, fixture: str, rel: str) -> Path:
        return place(fixture, self.project / rel)

    def prove(self, *extra, passthrough=()) -> tuple[int, str, str]:
        argv = ["prove", "-P", "p.gpr", "--gnatprove", str(self.fake),
                *extra]
        if passthrough:
            argv += ["--", *passthrough]
        return call(*argv, cwd=self.project)

    def invoked_argv(self) -> list[str] | None:
        if not self.argv_log.is_file():
            return None
        return json.loads(self.argv_log.read_text(encoding="utf-8"))

    def fixture_src(self, name: str) -> str:
        return str(support.fixture(name))


# --------------------------------------------------------------------------
# Command construction
# --------------------------------------------------------------------------

class CommandConstruction(unittest.TestCase):
    def test_default_executable(self):
        self.assertEqual(orch.build_command("p.gpr"),
                         ["gnatprove", "-P", "p.gpr"])

    def test_custom_executable_and_passthrough_order(self):
        self.assertEqual(
            orch.build_command("p.gpr", ["--prover=z3", "-j0"],
                               "/opt/gnat/bin/gnatprove"),
            ["/opt/gnat/bin/gnatprove", "-P", "p.gpr", "--prover=z3",
             "-j0"])

    def test_split_passthrough_only_for_prove(self):
        self.assertEqual(cli.split_passthrough(
            ["prove", "-P", "p.gpr", "--", "-j0", "--", "x"]),
            (["prove", "-P", "p.gpr"], ["-j0", "--", "x"]))
        self.assertEqual(cli.split_passthrough(["explain", "--", "x"]),
                         (["explain", "--", "x"], []))
        self.assertEqual(cli.split_passthrough(["prove", "-P", "p"]),
                         (["prove", "-P", "p"], []))

    def test_display_is_deterministic_shell_escaping(self):
        argv = orch.build_command("my project.gpr",
                                  ["--level=2", "a;b", "$HOME"])
        shown = orch.display_command(argv)
        self.assertEqual(shown, "gnatprove -P 'my project.gpr' --level=2 "
                         "'a;b' '$HOME'")
        self.assertEqual(shlex.split(shown), argv)
        self.assertEqual(shown, orch.display_command(list(argv)))

    def test_popen_is_called_with_argv_and_no_shell(self):
        argv = ["gnatprove", "-P", "p.gpr", "a b;c"]
        with mock.patch.object(orch.subprocess, "Popen") as popen:
            popen.return_value.stdout.readline.return_value = b""
            popen.return_value.wait.return_value = 0
            self.assertEqual(orch.run_gnatprove(argv), 0)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], argv)
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)

    def test_shell_true_never_appears_in_the_package(self):
        pkg = support.DIAGNOSTICS / "spark_refine_diagnostics"
        for src in sorted(pkg.glob("*.py")):
            with self.subTest(file=src.name):
                self.assertNotIn("shell=True", src.read_text("utf-8"))

    def test_signal_exit_code_normalization(self):
        self.assertEqual(orch.normalize_returncode(0), 0)
        self.assertEqual(orch.normalize_returncode(3), 3)
        self.assertEqual(orch.normalize_returncode(-signal.SIGKILL),
                         128 + signal.SIGKILL)

    def test_exit_precedence(self):
        self.assertEqual(orch.exit_status(0, False), 0)
        self.assertEqual(orch.exit_status(0, True), 1)
        self.assertEqual(orch.exit_status(3, False), 3)
        self.assertEqual(orch.exit_status(3, True), 3)


class PassThroughLiteral(FakeProject):
    def test_metacharacters_reach_gnatprove_literally(self):
        self.plan()
        weird = ["--level=2", "has space", "-j0", "--prover=z3;rm -rf /",
                 "$HOME", "`id`", "a|b", "--", "*"]
        self.prove(passthrough=weird)
        self.assertEqual(self.invoked_argv(), ["-P", "p.gpr", *weird])

    def test_project_with_space_is_one_argument(self):
        self.plan()
        call("prove", "-P", "my project.gpr", "--gnatprove",
             str(self.fake), cwd=self.project)
        self.assertEqual(self.invoked_argv(), ["-P", "my project.gpr"])

    def test_command_shown_on_stderr_before_execution(self):
        self.plan(stderr="FAKE-RAN\n")
        _rc, _out, err = self.prove(passthrough=["a b"])
        exe = shlex.quote(str(self.fake))
        shown = f"GNATprove command:\n  {exe} -P p.gpr 'a b'\n"
        self.assertIn(shown, err)
        self.assertLess(err.index(shown), err.index("FAKE-RAN"))


class DryRun(FakeProject):
    def test_dry_run_executes_nothing_and_ignores_stale_results(self):
        self.old("ring_b3", "obj/old/gnatprove")
        self.plan()
        rc, out, err = self.prove("--dry-run", passthrough=["-j0"])
        self.assertEqual(rc, 0)
        self.assertIsNone(self.invoked_argv())
        self.assertIn("dry run", out)
        self.assertNotIn("SRD001", out)
        self.assertNotIn("obj/old", out + err)

    def test_dry_run_json_plan(self):
        self.plan()
        rc, out, _ = self.prove("--dry-run", "--format", "json",
                                passthrough=["--prover=z3"])
        self.assertEqual(rc, 0)
        self.assertIsNone(self.invoked_argv())
        self.assertEqual(json.loads(out), {
            "format_version": 1, "tool": "spark_refine_diagnostics",
            "orchestration": {
                "command": [str(self.fake), "-P", "p.gpr", "--prover=z3"],
                "dry_run": True, "result_selection": "fresh_discovery",
                "result_path": None}})
        self.assertEqual(out, self.prove("--dry-run", "--format", "json",
                                         passthrough=["--prover=z3"])[1])

    def test_dry_run_with_missing_executable_still_exits_0(self):
        rc, _out, _err = call("prove", "-P", "p.gpr", "--gnatprove",
                              "/nonexistent/gnatprove", "--dry-run",
                              cwd=self.project)
        self.assertEqual(rc, 0)


# --------------------------------------------------------------------------
# Freshness (pure filesystem; the "GNATprove run" is simulated between the
# snapshot and the selection)
# --------------------------------------------------------------------------

class FreshnessSelection(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def put(self, rel: str, fixture: str = "pool_p5") -> Path:
        return place(fixture, self.root / rel)

    def test_a_new_result_selected(self):
        f = orch.Freshness(self.root)
        self.put("obj/proof/gnatprove")
        sel = f.select()
        self.assertEqual(sel.path, Path("obj/proof/gnatprove"))
        self.assertEqual(sel.method, orch.FRESH_DISCOVERY)
        self.assertEqual(sel.stale_ignored, [])

    def test_b_unchanged_old_result_rejected(self):
        self.put("obj/proof/gnatprove")
        f = orch.Freshness(self.root)
        with self.assertRaises(orch.FreshnessError) as cm:
            f.select()
        self.assertIn("refusing to analyse stale results", str(cm.exception))
        self.assertIn("  obj/proof/gnatprove", str(cm.exception))

    def test_c_rewritten_old_result_selected(self):
        old = self.put("obj/proof/gnatprove")
        f = orch.Freshness(self.root)
        rewrite(old)
        self.assertEqual(f.select().path, Path("obj/proof/gnatprove"))

    def test_c2_same_bytes_new_metadata_is_a_change(self):
        # repeated GNATprove runs within one second can write identical
        # bytes; the new mtime/ctime still marks the file as rewritten
        old = self.put("obj/proof/gnatprove")
        f = orch.Freshness(self.root)
        sarif = old / SARIF_NAME
        st = sarif.stat()
        os.utime(sarif, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        self.assertEqual(f.select().path, Path("obj/proof/gnatprove"))

    def test_d_one_of_several_rewritten_selected(self):
        for v in ("a", "b", "c"):
            self.put(f"obj/{v}/gnatprove")
        f = orch.Freshness(self.root)
        rewrite(self.root / "obj/b/gnatprove")
        sel = f.select()
        self.assertEqual(sel.path, Path("obj/b/gnatprove"))
        self.assertEqual(sel.stale_ignored, [Path("obj/a/gnatprove"),
                                             Path("obj/c/gnatprove")])

    def test_e_two_rewritten_is_ambiguous(self):
        for v in ("c", "a", "b"):
            self.put(f"obj/{v}/gnatprove")
        f = orch.Freshness(self.root)
        rewrite(self.root / "obj/c/gnatprove")
        rewrite(self.root / "obj/a/gnatprove")
        with self.assertRaises(orch.FreshnessError) as cm:
            f.select()
        self.assertEqual(cm.exception.candidates,
                         [Path("obj/a/gnatprove"), Path("obj/c/gnatprove")])
        self.assertIn("  obj/a/gnatprove\n  obj/c/gnatprove\n",
                      str(cm.exception))

    def test_e2_new_plus_rewritten_is_ambiguous(self):
        self.put("obj/old/gnatprove")
        f = orch.Freshness(self.root)
        rewrite(self.root / "obj/old/gnatprove")
        self.put("obj/new/gnatprove")
        with self.assertRaises(orch.FreshnessError) as cm:
            f.select()
        self.assertEqual(cm.exception.candidates,
                         [Path("obj/new/gnatprove"),
                          Path("obj/old/gnatprove")])

    def test_old_sarif_that_merely_becomes_valid_is_not_fresh(self):
        # a directory with an OLD gnatprove.sarif but no .spark before the
        # run is not "newly created" just because a .spark appears
        d = self.put("obj/proof/gnatprove")
        moved = [(p, p.read_bytes()) for p in sorted(d.glob("*.spark"))]
        for p, _ in moved:
            p.unlink()
        f = orch.Freshness(self.root)
        for p, data in moved:
            p.write_bytes(data)
        with self.assertRaises(orch.FreshnessError):
            f.select()


    def test_f_explicit_rewritten_selected(self):
        old = self.put("out/gnatprove")
        f = orch.Freshness(self.root, Path("out/gnatprove"))
        rewrite(old)
        sel = f.select()
        self.assertEqual((sel.path, sel.method),
                         (Path("out/gnatprove"), orch.EXPLICIT))

    def test_f2_explicit_sarif_file_path_accepted(self):
        old = self.put("out/gnatprove")
        f = orch.Freshness(self.root, Path("out/gnatprove") / SARIF_NAME)
        rewrite(old)
        self.assertEqual(f.select().path, Path("out/gnatprove"))

    def test_g_explicit_unchanged_rejected_no_fallback(self):
        self.put("out/gnatprove")
        f = orch.Freshness(self.root, Path("out/gnatprove"))
        self.put("obj/elsewhere/gnatprove")   # fresh, but not requested
        with self.assertRaises(orch.FreshnessError) as cm:
            f.select()
        self.assertIn(orch.NOT_FRESH_EXPLICIT, str(cm.exception))
        self.assertNotIn("elsewhere", str(cm.exception))

    def test_h_explicit_absent_then_created_selected(self):
        f = orch.Freshness(self.root, Path("out/gnatprove"))
        self.put("out/gnatprove")
        self.assertEqual(f.select().path, Path("out/gnatprove"))

    def test_explicit_absolute_path_preserved(self):
        where = self.root / "abs" / "gnatprove"
        f = orch.Freshness(self.root, where)
        self.put("abs/gnatprove")
        self.assertEqual(f.select().path, where)

    def test_explicit_never_written_is_invalid(self):
        f = orch.Freshness(self.root, Path("out/gnatprove"))
        with self.assertRaises(orch.FreshnessError) as cm:
            f.select()
        self.assertIn(orch.NOT_VALID_EXPLICIT, str(cm.exception))

    def test_hidden_and_alire_dirs_are_ignored_as_in_discovery(self):
        f = orch.Freshness(self.root)
        self.put("alire/cache/gnatprove")
        self.put(".git/x/gnatprove")
        self.put("obj/gnatprove")
        self.assertEqual(f.select().path, Path("obj/gnatprove"))



# --------------------------------------------------------------------------
# Subprocess / exit semantics with a fake GNATprove
# --------------------------------------------------------------------------

class ExitSemantics(FakeProject):
    def test_zero_with_fresh_results(self):
        self.old("ring_b3", "obj/stale/gnatprove")
        self.plan(copy=[[self.fixture_src("ring_positive"),
                         "obj/baseline/gnatprove"]])
        rc, out, err = self.prove("--format", "json")
        self.assertEqual(rc, 0, err)
        doc = json.loads(out)
        self.assertEqual(doc["format_version"], 1)
        self.assertEqual(doc["analysis"]["orchestration"], {
            "command": [str(self.fake), "-P", "p.gpr"],
            "gnatprove_exit_code": 0,
            "result_path": "obj/baseline/gnatprove",
            "result_selection": "fresh_discovery",
            "fresh": True,
            "stale_result_sets_ignored": ["obj/stale/gnatprove"]})
        self.assertEqual(doc["diagnostics"], [])
        self.assertIn("GNATprove exit: 0", err)

    def test_nonzero_with_fresh_results_still_diagnoses(self):
        self.plan(exit=1, copy=[[self.fixture_src("ring_b3"),
                                 "obj/b3/gnatprove"]])
        rc, out, _ = self.prove("--format", "json")
        self.assertEqual(rc, 1)
        doc = json.loads(out)
        self.assertEqual(doc["analysis"]["orchestration"]
                         ["gnatprove_exit_code"], 1)
        self.assertEqual([(d["code"], d["entity"])
                          for d in doc["diagnostics"]],
                         [("SRD001", "Ring_Buffer.Pop")])

    def test_nonzero_exit_code_is_preserved_exactly(self):
        self.plan(exit=7, copy=[[self.fixture_src("ring_b3"),
                                 "obj/b3/gnatprove"]])
        self.assertEqual(self.prove()[0], 7)

    def test_nonzero_without_results_preserves_code_and_no_report(self):
        self.old("ring_b3", "obj/stale/gnatprove")
        self.plan(exit=4, stderr="compilation error\n")
        rc, out, err = self.prove("--format", "json")
        self.assertEqual(rc, 4)
        self.assertEqual(out, "")
        self.assertIn("compilation error", err)
        self.assertIn("GNATprove failed (exit 4) before usable fresh "
                      "result output was found", err)

    def test_signal_termination_maps_to_128_plus_n(self):
        self.plan(signal=int(signal.SIGTERM),
                  copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]])
        rc, out, _ = self.prove("--format", "json")
        self.assertEqual(rc, 128 + signal.SIGTERM)
        meta = json.loads(out)["analysis"]["orchestration"]
        self.assertEqual(meta["gnatprove_exit_code"], 128 + signal.SIGTERM)
        self.assertEqual(meta["gnatprove_raw_returncode"], -signal.SIGTERM)

    def test_launch_failure_exits_2_without_report(self):
        rc, out, err = call("prove", "-P", "p.gpr", "--gnatprove",
                            str(self.project / "no-such-gnatprove"),
                            cwd=self.project)
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("could not launch", err)


    def test_fail_on_when_gnatprove_succeeded(self):
        # GNATprove 0 with unproved checks (allowed by its configuration)
        self.plan(copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]])
        rc, _, _ = self.prove("--fail-on", "SRD001")
        self.assertEqual(rc, 1)
        self.plan(copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]],
                  rewrite=["obj/b3/gnatprove/gnatprove.sarif"])
        rc2, _, _ = self.prove("--fail-on", "SRD002")
        self.assertEqual(rc2, 0)

    def test_fail_on_when_gnatprove_already_failed(self):
        self.plan(exit=3, copy=[[self.fixture_src("ring_b3"),
                                 "obj/b3/gnatprove"]])
        rc, _, _ = self.prove("--fail-on", "SRD001")
        self.assertEqual(rc, 3)

    def test_zero_exit_with_unproved_checks_is_not_overridden(self):
        self.plan(copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]])
        rc, out, _ = self.prove("--format", "json")
        self.assertEqual(rc, 0)
        notes = json.loads(out)["notes"]
        self.assertTrue(any("does not override GNATprove's exit status" in n
                            for n in notes))

    def test_explicit_results_unchanged_exit_2(self):
        self.old("ring_b3", "out/gnatprove")
        self.plan()
        rc, out, err = self.prove("--results", "out/gnatprove")
        self.assertEqual((rc, out), (2, ""))
        self.assertIn(orch.NOT_FRESH_EXPLICIT, err)

    def test_multiple_fresh_exit_2_sorted_list(self):
        self.plan(copy=[[self.fixture_src("ring_b3"), "obj/z/gnatprove"],
                        [self.fixture_src("ring_b3"), "obj/a/gnatprove"]])
        rc, out, err = self.prove()
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("  obj/a/gnatprove\n  obj/z/gnatprove\n", err)

    def test_text_report_shows_provenance_first(self):
        self.plan(exit=1, copy=[[self.fixture_src("ring_b3"),
                                 "obj/b3/gnatprove"]])
        rc, out, _ = self.prove(passthrough=["--level=2"])
        self.assertEqual(rc, 1)
        exe = shlex.quote(str(self.fake))
        self.assertTrue(out.startswith(
            f"proof command: {exe} -P p.gpr --level=2\n"
            "GNATprove exit: 1\n"
            "fresh results: obj/b3/gnatprove\n"
            "selection: fresh_discovery\n"), out)
        self.assertIn("SRD001: ", out)


# --------------------------------------------------------------------------
# JSON cleanliness, stale safety, unchanged diagnostics
# --------------------------------------------------------------------------

class JsonCleanliness(FakeProject):
    def test_gnatprove_output_never_reaches_stdout_in_process(self):
        self.plan(stdout=NOISE_OUT, stderr=NOISE_ERR, exit=1,
                  copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]])
        _rc, out, err = self.prove("--format", "json")
        json.loads(out)
        self.assertNotIn("Phase 1 of 3", out)
        self.assertIn(NOISE_OUT, err)
        self.assertIn(NOISE_ERR, err)

    def test_real_subprocess_stdout_is_json_only(self):
        # the whole CLI in a child process: real file descriptors
        self.plan(stdout=NOISE_OUT * 50, stderr=NOISE_ERR * 50,
                  copy=[[self.fixture_src("ring_b3"), "obj/b3/gnatprove"]])
        env = dict(os.environ, PYTHONPATH=str(support.DIAGNOSTICS))
        proc = subprocess.run(
            [sys.executable, "-m", "spark_refine_diagnostics", "prove",
             "-P", "p.gpr", "--gnatprove", str(self.fake), "--format",
             "json"], cwd=self.project, env=env, capture_output=True,
            text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["analysis"]["orchestration"]["result_path"],
                         "obj/b3/gnatprove")
        self.assertNotIn("Phase 1 of 3", proc.stdout)
        self.assertIn(NOISE_OUT, proc.stderr)
        self.assertIn(NOISE_ERR, proc.stderr)


class StaleSafety(FakeProject):
    def test_old_valid_result_is_never_analysed_by_prove(self):
        """The central Task 008 safety test."""
        self.old("ring_b3", "obj/proof/gnatprove")
        # explain happily analyses it...
        rc, out, _ = call("explain", "--format", "json", cwd=self.project)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["summary"]["by_code"]["SRD001"], 1)
        # ...but prove, after a GNATprove that exits 0 and writes nothing,
        # refuses it
        self.plan(exit=0)
        for fmt in ("text", "json"):
            with self.subTest(format=fmt):
                rc, out, err = self.prove("--format", fmt)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertIn("refusing to analyse stale results", err)
                self.assertIn("  obj/proof/gnatprove", err)


class DiagnosticsUnchanged(FakeProject):
    def test_prove_equals_explain_apart_from_orchestration(self):
        for fixture in ("ring_b3", "pool_spec_no_count_posts",
                        "ring_positive"):
            with self.subTest(fixture=fixture):
                dest = f"obj/{fixture}/gnatprove"
                self.plan(copy=[[self.fixture_src(fixture), dest]])
                _rc, out, _ = self.prove("--format", "json", "--name", "r")
                proved = json.loads(out)
                _rc, out2, _ = call("explain", dest, "--format", "json",
                                    "--name", "r", cwd=self.project)
                explained = json.loads(out2)
                orch_meta = proved["analysis"].pop("orchestration")
                self.assertEqual(orch_meta["result_path"], dest)
                proved["notes"] = [n for n in proved["notes"]
                                   if "does not override" not in n]
                self.assertEqual(proved, explained)


if __name__ == "__main__":
    unittest.main()

