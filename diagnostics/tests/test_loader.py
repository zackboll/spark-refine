"""Loader: SARIF/.spark merge on real fixtures, unit attribution, and
agreement with the benchmark gates' own result reader (parity)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from spark_refine_diagnostics.loader import load_run, unit_from_entity
from spark_refine_diagnostics.sarif import InputError


def _gate(example: str):
    path = support.REPO / "examples" / example / "scripts" / \
        "check_proof_results.py"
    spec = importlib.util.spec_from_file_location(f"gate_{example}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATES = {"ring_buffer": _gate("ring_buffer"),
         "fixed_pool": _gate("fixed_pool")}


class ParityWithBenchmarkGates(unittest.TestCase):
    """The diagnostics parser must not reinterpret GNATprove output: on
    every committed fixture, its proved/unproved/justified/warning split
    equals load_results() of the gate of the example it came from."""

    def test_every_fixture(self):
        for name, spec in support.manifest().items():
            with self.subTest(fixture=name):
                gate = GATES[spec["example"]]
                ref = gate.load_results(support.fixture(name))
                run = support.run_of(name)
                key = lambda i: (i["rule"], i["file"], i["line"],  # noqa
                                 i["entity"])
                ours = lambda cs: sorted(  # noqa: E731
                    (c.rule, c.location.file, c.location.line, c.entity)
                    for c in cs)
                self.assertEqual(ours(run.proved),
                                 sorted(map(key, ref["proved"])))
                self.assertEqual(ours(run.unproved),
                                 sorted(map(key, ref["unproved"])))
                self.assertEqual(ours(run.justified),
                                 sorted(map(key, ref["justified"])))
                self.assertEqual(sum(w.allowed for w in run.warnings),
                                 len(ref["allowed_warnings"]))
                self.assertEqual(sum(not w.allowed for w in run.warnings),
                                 len(ref["warnings"]))
                self.assertEqual(sum(u.pragma_assume for u in run.units
                                     if u.name in gate.GATED_UNITS),
                                 ref["pragma_assume"])
                self.assertEqual(sum(u.unproved_entries for u in run.units
                                     if u.name in gate.GATED_UNITS),
                                 ref["spark_unproved"])
                self.assertEqual(run.tool_version, ref["tool"])
                self.assertEqual(run.tool_version, "FSF 16.1.0")


class MergeTests(unittest.TestCase):
    def test_every_fixture_merges_without_disagreement(self):
        for name in support.manifest():
            with self.subTest(fixture=name):
                run = support.run_of(name)
                self.assertEqual(run.consistency_issues, [])
                self.assertEqual(run.unit_attribution, "spark")
                self.assertTrue(all(c.unit for c in run.checks))
                self.assertTrue(run.complete)

    def test_generic_instance_checks_belong_to_instantiating_unit(self):
        lib = [c for c in support.run_of("pool_l5").checks
               if c.location.file.startswith("spark_refine_prefix_sets")]
        self.assertTrue(lib)
        self.assertEqual({c.unit for c in lib}, {"fixed_pool"})

    def test_prover_stats_are_attached(self):
        run = support.run_of("pool_prover_altergo")
        provers = {s.prover for c in run.checks for s in c.prover_stats}
        self.assertIn("altergo", {p.lower().replace("-", "")
                                  for p in provers})

    def test_sarif_only_input_falls_back_to_entity_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(support.fixture("pool_p5") / "gnatprove.sarif",
                        Path(tmp) / "gnatprove.sarif")
            run = load_run(Path(tmp) / "gnatprove.sarif")
        self.assertEqual(run.unit_attribution, "entity")
        self.assertEqual(run.units, [])
        self.assertEqual(len(run.checks),
                         len(support.run_of("pool_p5").checks))
        self.assertEqual(unit_from_entity("Fixed_Pool.Release"),
                         "fixed_pool")

    def test_status_disagreement_is_reported_not_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in support.fixture("pool_p5").iterdir():
                shutil.copy(p, Path(tmp) / p.name)
            spark = Path(tmp) / "fixed_pool.spark"
            data = json.loads(spark.read_text("utf-8"))
            for e in data["proof"]:
                e["severity"] = "info"
            spark.write_text(json.dumps(data), "utf-8")
            run = load_run(Path(tmp))
        self.assertTrue(any("status disagreement" in i
                            for i in run.consistency_issues))
        self.assertFalse(run.complete)
        # SARIF stays authoritative for status
        self.assertEqual(len(run.unproved), 1)
        self.assertEqual([c.rule for c in run.checks if c.disputed],
                         ["VC_INVARIANT_CHECK"])
        self.assertEqual(run.disputed_units, {"fixed_pool"})

    def test_disagreement_surfaces_and_is_not_overclaimed(self):
        """SARIF says the Release invariant is unproved, .spark says it is
        proved: the analysis completes, the disagreement is a note, and
        SRD001 (which relies on that status) is reported at medium, not
        high, confidence with the reason in its evidence."""
        from spark_refine_diagnostics import analyze_path
        from spark_refine_diagnostics.model import Confidence
        with tempfile.TemporaryDirectory() as tmp:
            for p in support.fixture("pool_p5").iterdir():
                shutil.copy(p, Path(tmp) / p.name)
            spark = Path(tmp) / "fixed_pool.spark"
            data = json.loads(spark.read_text("utf-8"))
            for e in data["proof"]:
                if e["rule"] == "VC_INVARIANT_CHECK":
                    e["severity"] = "info"
            spark.write_text(json.dumps(data), "utf-8")
            _, diags, notes = analyze_path(Path(tmp))
        self.assertTrue(any(n.startswith("consistency: status disagreement")
                            for n in notes))
        self.assertEqual([(d.code, d.confidence) for d in diags],
                         [("SRD001", Confidence.MEDIUM)])
        self.assertTrue(any("status disagreement" in e
                            for e in diags[0].evidence))

    def test_missing_input(self):
        with self.assertRaises(InputError):
            load_run(Path("/nonexistent/gnatprove"))


if __name__ == "__main__":
    unittest.main()
