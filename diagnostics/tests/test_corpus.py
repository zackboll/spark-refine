"""Corpus-wide checks: fixture set = manifest = expectations, exact
expected diagnostics for every fixture, determinism, stable IDs, and the
CLI."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

import support
from spark_refine_diagnostics import RULES
from spark_refine_diagnostics.cli import main
from spark_refine_diagnostics.render import to_json, to_text


class Corpus(unittest.TestCase):
    def test_fixture_dirs_manifest_and_expectations_agree(self):
        dirs = {p.name for p in support.FIXTURES.iterdir() if p.is_dir()}
        self.assertEqual(dirs, set(support.manifest()))
        self.assertEqual(set(support.expectations()), dirs)

    def test_fixtures_are_real_pinned_gnatprove_output(self):
        for name in support.manifest():
            run = support.run_of(name)
            self.assertEqual(run.tool_version, "FSF 16.1.0", name)
            self.assertTrue(run.command_line.startswith("gnatprove -P "),
                            name)
            self.assertTrue(run.checks, name)

    def test_expected_diagnostics(self):
        for name in support.manifest():
            with self.subTest(fixture=name):
                _, diags, notes = support.analyzed(name)
                self.assertEqual(
                    sorted(f"{d.code}:{d.entity}" for d in diags),
                    sorted(support.expected(name)["diagnostics"]))
                self.assertEqual(notes, [])

    def test_required_corpus_members(self):
        m = support.manifest()
        for name in ("ring_b3", "ring_b4", "pool_p1", "pool_p5", "pool_l1",
                     "pool_l5", "ring_b1", "ring_b2", "ring_b6", "pool_p4",
                     "pool_l4", "ring_no_public_model_bound",
                     "ring_no_is_empty_post", "ring_no_is_full_post",
                     "pool_spec_no_count_posts", "pool_false_client_assert"):
            self.assertIn(name, m)

    def test_fixture_provenance(self):
        """Every fixture records its toolchain; the .ali producer is GNAT
        16.1.0 (the only ALI version the adapter has seen)."""
        import json
        for name in support.manifest():
            with self.subTest(fixture=name):
                prov = json.loads((support.fixture(name) / "fixture.json")
                                  .read_text("utf-8"))["provenance"]
                self.assertEqual(prov["gnatprove_version"], "FSF 16.1.0")
                self.assertEqual(prov["gnat_version"], "16.1.0")
                self.assertEqual(prov["ali_producer"], "GNAT 16.1.0")
                self.assertEqual(prov["ali_version_header"],
                                 ["GNAT Lib v16"])
                for key in ("benchmark", "variant", "case",
                            "prover_configuration", "source_ref",
                            "command_line"):
                    self.assertTrue(prov[key], key)
                self.assertNotIn(str(support.REPO), json.dumps(prov))

    def test_fixture_only_sources_do_not_touch_benchmarks(self):
        spec = support.manifest()["pool_false_client_assert"]
        for rel in spec["extra_sources"]:
            src = support.DIAGNOSTICS / rel
            names = {p.name for p in src.glob("*.ad[sb]")}
            self.assertEqual(names, {"fixed_pool_false_client.ads",
                                     "fixed_pool_false_client.adb"})
            for n in names:
                # obj/ holds git-ignored scratch copies made by capture
                self.assertFalse([p for p in support.REPO.glob(
                    f"examples/**/{n}") if "obj" not in p.parts], n)


class Stability(unittest.TestCase):
    def test_rule_ids(self):
        self.assertEqual(list(RULES), ["SRD001", "SRD002", "SRD003"])

    def test_deterministic_output(self):
        for name in ("pool_p5", "pool_spec_no_count_posts"):
            outs = []
            for _ in range(2):
                support.analyzed.cache_clear()
                support.run_of.cache_clear()
                run, diags, notes = support.analyzed(name)
                outs.append((to_text([run], diags, notes),
                             to_json([run], diags, notes)))
            self.assertEqual(outs[0], outs[1])


class Cli(unittest.TestCase):
    def call(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(list(argv))
        return rc, buf.getvalue()

    def test_analyze_text(self):
        rc, out = self.call("analyze", str(support.fixture("pool_p5")))
        self.assertEqual(rc, 0)
        self.assertIn("SRD001: failed invariant may mask downstream "
                      "postconditions", out)
        self.assertIn("fixed_pool.ads:52:17 VC_POSTCONDITION [proved]", out)
        self.assertIn("summary: SRD001=1", out)

    def test_analyze_json_and_fail_on(self):
        rc, out = self.call("analyze", str(support.fixture("ring_b3")),
                            "--format", "json", "--fail-on", "SRD001")
        self.assertEqual(rc, 1)
        doc = json.loads(out)
        self.assertEqual(doc["format_version"], 1)
        self.assertEqual([d["code"] for d in doc["diagnostics"]],
                         ["SRD001"])
        rc, _ = self.call("analyze", str(support.fixture("ring_positive")),
                          "--fail-on", "SRD001")
        self.assertEqual(rc, 0)

    def test_sarif_file_input(self):
        rc, out = self.call("analyze", str(support.fixture("pool_spec_"
                                                           "no_count_posts")
                                           / "gnatprove.sarif"))
        self.assertEqual(rc, 0)
        self.assertIn("summary: SRD002=2", out)

    def test_compare_provers(self):
        f = support.fixture
        rc, out = self.call(
            "compare-provers",
            "--run", f"cvc5={f('pool_prover_cvc5')}",
            "--run", f"z3={f('pool_prover_z3')}",
            "--run", f"altergo={f('pool_prover_altergo')}",
            "--reference", f"portfolio={f('pool_positive')}")
        self.assertEqual(rc, 0)
        self.assertIn("summary: SRD003=6", out)

    def test_input_error(self):
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc, _ = self.call("analyze", "/nonexistent")
        self.assertEqual(rc, 2)
        self.assertIn("error:", err.getvalue())

    def test_module_entry_point(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spark_refine_diagnostics", "rules"],
            cwd=support.DIAGNOSTICS, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SRD003", proc.stdout)

    def test_rules_catalogue_matches_behaviour(self):
        rc, out = self.call("rules")
        self.assertEqual(rc, 0)
        self.assertIn("SRD001  [confidence high, single run]", out)
        self.assertIn("SRD002  [confidence dynamic, single run]  Client-only "
                      "proof gap; public abstraction may be insufficient",
                      out)
        self.assertIn("medium for VC_PRECONDITION, low for VC_ASSERT", out)
        self.assertIn("SRD003  [confidence high, multiple runs]", out)
        self.assertIn("confidently matched", out)
        self.assertNotIn("likely", out.lower())

    def test_json_rules_and_srd002_example(self):
        rc, out = self.call("analyze", str(support.fixture(
            "pool_false_client_assert")), "--format", "json")
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual(doc["rules"]["SRD002"]["confidence"], "dynamic")
        self.assertIn("confidence_policy", doc["rules"]["SRD002"])
        self.assertTrue(doc["analysis"]["rules"]["SRD002"]["evaluated"])
        self.assertEqual(doc["analysis"]["rules"]["SRD002"]["ali_versions"],
                         ["GNAT Lib v16"])
        d = doc["diagnostics"][0]
        self.assertEqual((d["code"], d["severity"], d["confidence"]),
                         ("SRD002", "warning", "low"))
        self.assertEqual(d["data"]["client_rules"], ["VC_ASSERT"])
        self.assertEqual(d["data"]["implementation_failures"], 0)


if __name__ == "__main__":
    unittest.main()
