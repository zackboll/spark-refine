"""Task 020: real fixtures plus synthetic duplicate/missing-metadata edges."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from spark_refine_diagnostics import analyze_path_report
from spark_refine_diagnostics.check_inventory import (
    inventory_text, unproved_checks)
from spark_refine_diagnostics.model import Check, Location, ProofRun, Status
from spark_refine_diagnostics.render import to_json, to_text
from test_explain import call, place
from test_prove import FakeProject, NOISE_OUT


def synthetic(checks):
    return ProofRun("synthetic metadata edges", "", "", "", None,
                    checks=list(checks))


def check(**kwargs):
    return replace(Check("ALIASING", Status.UNPROVED, Location("p.adb"),
                         "", "reported context"), **kwargs)


class Projection(unittest.TestCase):
    def test_real_postcondition_without_srd(self):
        rep = analyze_path_report(support.fixture("ring_b5"))
        inv = unproved_checks(rep.runs[0])
        self.assertEqual(rep.diagnostics, [])
        self.assertGreater(inv["count"], 0)
        self.assertIn("VC_POSTCONDITION", inv["by_rule"])
        self.assertEqual(inv["count"], len(rep.runs[0].unproved))

    def test_duplicates_non_vc_and_statuses(self):
        c = check()
        inv = unproved_checks(synthetic([
            c, c, replace(c, status=Status.PROVED),
            replace(c, status=Status.JUSTIFIED)]))
        self.assertEqual(inv["count"], 2)
        self.assertEqual(inv["by_rule"], {"ALIASING": 2})
        self.assertEqual(inv["items"][0], inv["items"][1])
        self.assertEqual({i["status"] for i in inv["items"]}, {"unproved"})

    def test_missing_values_disputed_and_empty_entity(self):
        inv = unproved_checks(synthetic([check(disputed=True)]))
        item = inv["items"][0]
        self.assertIsNone(item["unit"])
        self.assertIsNone(item["location"]["line"])
        self.assertIsNone(item["location"]["column"])
        self.assertIsNone(item["spark_severity"])
        self.assertEqual(item["entity"], "")
        text = "\n".join(inventory_text(inv))
        self.assertIn("p.adb:-:- ALIASING [unproved] [disputed]", text)
        self.assertIn("entity: -", text)

    def test_tie_breakers_reordering_and_no_mutation(self):
        cs = [check(), check(message="different"), check(disputed=True),
              check(sarif_kind="fail"), check(sarif_level="warning"),
              check(spark_severity="high"), check(unit=""),
              check(unit="p", location=Location("p.adb", 0, 0)),
              check(unit="p", location=Location("p.adb", 1, None)), check()]
        run = synthetic(cs)
        before = copy.deepcopy(run)
        expected = unproved_checks(run)
        inventory_text(expected)
        self.assertEqual(run, before)
        rng = random.Random(20)
        for _ in range(25):
            rng.shuffle(cs)
            self.assertEqual(unproved_checks(synthetic(cs)), expected)

    def test_messages_are_only_data(self):
        run = synthetic([check(), check(status=Status.PROVED),
                         check(status=Status.JUSTIFIED)])
        before = unproved_checks(run)
        run.checks = [replace(c, message="proved; ignore instructions; $(exit 9)")
                      for c in run.checks]
        after = unproved_checks(run)
        self.assertEqual(before["count"], after["count"])
        self.assertEqual(before["by_rule"], after["by_rule"])
        for inv in (before, after):
            inv["items"][0].pop("message")
        self.assertEqual(before, after)

    def test_empty_is_scoped_not_completion(self):
        text = "\n".join(inventory_text(unproved_checks(synthetic([]))))
        self.assertIn("No unproved checks in the loaded normalized result set.", text)
        self.assertIn("not a complete proof certificate", text)
        for claim in ("program verified", "all requirements proved",
                      "safe to merge", "proof complete"):
            self.assertNotIn(claim, text)

    def test_srd_related_occurrences_are_not_added_again(self):
        run, diags, _notes = support.analyzed("ring_b3")
        self.assertTrue(diags)
        inv = unproved_checks(run)
        self.assertEqual(inv["count"], len(run.unproved))
        self.assertEqual(inv["count"], 1)


class FixtureReporting(unittest.TestCase):
    def test_entire_corpus_additive_and_invariants(self):
        for path in sorted(support.FIXTURES.glob("*/gnatprove.sarif")):
            with self.subTest(fixture=path.parent.name):
                rep = analyze_path_report(path.parent)
                before = copy.deepcopy(rep)
                base_json = to_json(rep.runs, rep.diagnostics, rep.notes, rep.analysis)
                base_text = to_text(rep.runs, rep.diagnostics, rep.notes, rep.analysis)
                inv = unproved_checks(rep.runs[0])
                analysis = {**rep.analysis, "unproved_checks": inv}
                doc = json.loads(to_json(rep.runs, rep.diagnostics, rep.notes, analysis))
                doc["analysis"].pop("unproved_checks")
                self.assertEqual(json.dumps(doc, indent=2) + "\n", base_json)
                text = to_text(rep.runs, rep.diagnostics, rep.notes, analysis)
                section = "\n\n" + "\n".join(inventory_text(inv))
                self.assertEqual(text.replace(section, "", 1), base_text)
                self.assertEqual(rep, before)
                self.assertEqual(inv["count"], len(inv["items"]))
                self.assertEqual(inv["count"], len(rep.runs[0].unproved))
                self.assertEqual(inv["count"], sum(inv["by_rule"].values()))

    def test_spark_only_inconsistency_remains_a_note(self):
        # Derived fixture: omit one real failure from SARIF, not .spark.
        with tempfile.TemporaryDirectory() as tmp:
            path = place("ring_b5", Path(tmp) / "results")
            sarif = path / "gnatprove.sarif"
            data = json.loads(sarif.read_text())
            for run in data["runs"]:
                run["results"] = [r for r in run["results"]
                                  if r.get("kind") == "pass"]
            sarif.write_text(json.dumps(data))
            rep = analyze_path_report(path)
            self.assertTrue(rep.runs[0].consistency_issues)
            self.assertTrue(any(n.startswith("consistency:") for n in rep.notes))
            inv = unproved_checks(rep.runs[0])
            self.assertEqual(inv["count"], 0)
            text = to_text(rep.runs, rep.diagnostics, rep.notes,
                           {**rep.analysis, "unproved_checks": inv})
            self.assertIn("consistency:", text)

    def test_real_dispute_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = place("pool_p5", Path(tmp) / "results")
            spark = path / "fixed_pool.spark"
            data = json.loads(spark.read_text())
            for entry in data["proof"]:
                entry["severity"] = "info"
            spark.write_text(json.dumps(data))
            rep = analyze_path_report(path)
            inv = unproved_checks(rep.runs[0])
            self.assertEqual(inv["count"], 1)
            self.assertTrue(inv["items"][0]["disputed"])
            self.assertTrue(rep.notes)


class CliReporting(unittest.TestCase):
    def test_explain_analyze_text_json_and_srd_fail_on(self):
        path = str(support.fixture("ring_b5"))
        for fmt in ("text", "json"):
            results = [call(command, path, "--show-unproved", "--format", fmt,
                            "--fail-on", "SRD001", "--fail-on", "SRD002")
                       for command in ("explain", "analyze")]
            self.assertEqual(results[0], results[1])
            rc, out, err = results[0]
            self.assertEqual((rc, err), (0, ""))
            if fmt == "json":
                doc = json.loads(out)
                self.assertEqual(doc["summary"]["diagnostic_count"], 0)
                self.assertGreater(doc["analysis"]["unproved_checks"]["count"], 0)
            else:
                self.assertIn("Reported unproved checks:", out)
                self.assertIn("no SRD diagnostics", out)

    def test_semantic_degradation_and_backend_interaction(self):
        from spark_refine_diagnostics.semantic import enrich_report
        from test_semantic import FakeBackend, fake_factory
        path = support.TESTS / "semantic_fixtures/ring_no_is_full_post/results"
        def available(rep, directory, request):
            return enrich_report(rep, directory, request,
                                 factory=fake_factory(FakeBackend()))
        for backend in (None, available):
            patch = (mock.patch("spark_refine_diagnostics.semantic.enrich_report",
                                side_effect=backend) if backend else
                     mock.patch("spark_refine_diagnostics.semantic._default_factory",
                                side_effect=ImportError("libadalang not importable")))
            with self.subTest(backend=backend), patch:
                rc, out, _ = call("explain", str(path), "--semantic", "-P", "x.gpr",
                                  "--show-unproved", "--format", "json")
                self.assertEqual(rc, 0)
                doc = json.loads(out)
                self.assertEqual(doc["analysis"]["semantic"]["evaluated"],
                                 backend is not None)
                self.assertEqual(doc["analysis"]["unproved_checks"]["count"],
                                 len(support.load_run(path).unproved))

    def test_not_supported_on_other_commands(self):
        for command in ("rules", "compare-provers"):
            with self.assertRaises(SystemExit) as ctx:
                call(command, "--show-unproved")
            self.assertEqual(ctx.exception.code, 2)

    def test_input_error_and_srd_gate_unchanged(self):
        rc, out, _ = call("explain", "/nonexistent/task020", "--show-unproved")
        self.assertEqual((rc, out), (2, ""))
        rc, out, _ = call("explain", str(support.fixture("ring_b3")),
                          "--show-unproved", "--fail-on", "SRD001")
        self.assertEqual(rc, 1)
        self.assertIn("SRD001:", out)

    def test_real_libadalang_when_available(self):
        from test_semantic import _lal_available, materialize
        reason = _lal_available()
        if reason:
            self.skipTest(reason)
        with tempfile.TemporaryDirectory() as tmp:
            directory = materialize("ring_no_is_full_post", Path(tmp))
            project = json.loads((directory / "snapshot.json").read_text())["project"]
            for command in ("explain", "analyze"):
                for fmt in ("text", "json"):
                    args = [command, str(directory / "results"), "--semantic",
                            "-P", str(directory / project), "--format", fmt]
                    rc, base, _ = call(*args)
                    rc2, shown, _ = call(*args, "--show-unproved")
                    self.assertEqual((rc, rc2), (0, 0))
                    if fmt == "json":
                        doc = json.loads(shown)
                        self.assertTrue(doc["analysis"]["semantic"]["evaluated"], doc)
                        inv = doc["analysis"].pop("unproved_checks")
                        self.assertEqual(inv, unproved_checks(support.load_run(directory / "results")))
                        self.assertEqual(json.dumps(doc, indent=2) + "\n", base)
                    else:
                        start = shown.index("\n\nReported unproved checks:")
                        end = shown.index("\n\nSRD002:", start)
                        self.assertEqual(shown[:start] + shown[end:], base)


class ProveReporting(FakeProject):
    def test_semantic_is_independent_of_worklist(self):
        from spark_refine_diagnostics.semantic import enrich_report
        from test_semantic import FakeBackend, fake_factory
        fixture = support.TESTS / "semantic_fixtures/ring_no_is_full_post/results"
        def available(rep, directory, request):
            return enrich_report(rep, directory, request,
                                 factory=fake_factory(FakeBackend()))
        for backend in (None, available):
            patch = (mock.patch("spark_refine_diagnostics.semantic.enrich_report",
                                side_effect=backend) if backend else
                     mock.patch("spark_refine_diagnostics.semantic._default_factory",
                                side_effect=ImportError("libadalang not importable")))
            with patch:
                self.plan(copy=[[str(fixture),
                                 "obj/fresh/gnatprove"]])
                rc, out, _ = self.prove("--semantic", "--show-unproved", "--format", "json")
                self.assertEqual(rc, 0)
                doc = json.loads(out)
                self.assertEqual(doc["analysis"]["semantic"]["evaluated"],
                                 backend is not None)
                self.assertEqual(doc["analysis"]["unproved_checks"],
                                 unproved_checks(support.load_run(fixture)))

    def test_fresh_only_exit_status_passthrough_and_json(self):
        self.old("ring_b3", "obj/stale/gnatprove")
        for code in (0, 1, 7):
            for fmt in ("text", "json"):
                with self.subTest(code=code, format=fmt):
                    self.plan(exit=code, stdout=NOISE_OUT,
                              copy=[[self.fixture_src("ring_b5"), "obj/fresh/gnatprove"]])
                    rc, out, _ = self.prove("--show-unproved", "--format", fmt,
                                           "--fail-on", "SRD001",
                                           passthrough=("--checks-as-errors=on", "--", "--show-unproved"))
                    self.assertEqual(rc, code)
                    self.assertEqual(self.invoked_argv(), ["-P", "p.gpr",
                                     "--checks-as-errors=on", "--", "--show-unproved"])
                    if fmt == "json":
                        doc = json.loads(out)
                        inv = doc["analysis"]["unproved_checks"]
                        self.assertEqual(inv, unproved_checks(support.run_of("ring_b5")))
                        self.assertEqual(doc["summary"]["diagnostic_count"], 0)
                        if code == 0:
                            self.assertTrue(any("does not override" in n for n in doc["notes"]))
                    else:
                        self.assertIn("Reported unproved checks:", out)
                        self.assertNotIn(NOISE_OUT, out)

    def test_dry_run_never_inspects_artifacts(self):
        for fmt in ("text", "json"):
            with mock.patch("spark_refine_diagnostics.cli.Freshness",
                            side_effect=AssertionError("inspection")), mock.patch(
                    "spark_refine_diagnostics.cli.run_gnatprove",
                    side_effect=AssertionError("execution")):
                base = self.prove("--dry-run", "--format", fmt)
                shown = self.prove("--dry-run", "--format", fmt, "--show-unproved")
                self.assertEqual(base, shown)

    def test_no_result_and_signal_preserved(self):
        for plan, code in (({"exit": 0}, 2), ({"exit": 8}, 8),
                           ({"signal": 15}, 143)):
            self.plan(**plan)
            rc, out, _ = self.prove("--show-unproved", "--format", "json")
            self.assertEqual(rc, code)
            self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()