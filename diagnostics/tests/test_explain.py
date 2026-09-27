"""Task 006: `explain` command, result-set discovery, agent-facing JSON
(category / action / summary) and backward compatibility.

Everything here runs on the committed fixtures; no toolchain needed.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support
from spark_refine_diagnostics import RULES
from spark_refine_diagnostics.cli import main
from spark_refine_diagnostics.discovery import (DiscoveryError, discover,
                                                find_result_sets)
from spark_refine_diagnostics.render import summary_to_dict

EXPECTED_CATEGORY = {"SRD001": "proof_context",
                     "SRD002": "abstraction_boundary",
                     "SRD003": "prover_portfolio"}
EXPECTED_ACTION = {
    "SRD001": "fix_invariant_then_reprove",
    "SRD002": "validate_client_goal_then_review_public_contracts",
    "SRD003": "preserve_portfolio_or_strengthen_proof"}


def call(*argv, cwd: Path | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as st:
        if cwd is not None:
            st.enter_context(contextlib.chdir(cwd))
        st.enter_context(contextlib.redirect_stdout(out))
        st.enter_context(contextlib.redirect_stderr(err))
        rc = main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def place(fixture: str, dest: Path, with_ali: bool = True) -> Path:
    """Copy a fixture's GNATprove result files into `dest` (a fake
    obj/.../gnatprove directory)."""
    dest.mkdir(parents=True)
    for p in support.fixture(fixture).iterdir():
        if p.name == "fixture.json":
            continue
        if p.suffix == ".ali" and not with_ali:
            continue
        shutil.copy(p, dest / p.name)
    return dest


class Discovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name) / "project"
        self.project.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_one_candidate_is_discovered(self):
        place("pool_p5", self.project / "obj" / "proof" / "gnatprove")
        (self.project / "src").mkdir()
        self.assertEqual(discover(self.project),
                         Path("obj/proof/gnatprove"))
        rc, out, err = call("explain", "--format", "json",
                            cwd=self.project)
        self.assertEqual(rc, 0, err)
        doc = json.loads(out)
        self.assertEqual(doc["analysis"]["input"],
                         {"path": "obj/proof/gnatprove", "discovered": True})
        self.assertEqual([d["code"] for d in doc["diagnostics"]],
                         ["SRD001"])
        # same diagnostics as an explicit path on the same results
        rc2, out2, _ = call("explain", "obj/proof/gnatprove", "--format",
                            "json", cwd=self.project)
        self.assertEqual(rc2, 0)
        doc2 = json.loads(out2)
        self.assertNotIn("input", doc2["analysis"])
        self.assertEqual(doc["diagnostics"], doc2["diagnostics"])
        self.assertEqual(doc["summary"], doc2["summary"])

    def test_one_candidate_text_mentions_discovery_and_freshness(self):
        place("pool_p5", self.project / "obj" / "gnatprove")
        rc, out, _ = call("explain", cwd=self.project)
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("results: obj/gnatprove "
                                       "(auto-discovered;"))
        self.assertIn("only if GNATprove was just run", out)
        self.assertIn("summary: SRD001=1", out)

    def test_zero_candidates(self):
        # a SARIF without any .spark file is not a result set
        (self.project / "obj" / "gnatprove").mkdir(parents=True)
        shutil.copy(support.fixture("pool_p5") / "gnatprove.sarif",
                    self.project / "obj" / "gnatprove")
        for fmt in ("text", "json"):
            with self.subTest(format=fmt):
                rc, out, err = call("explain", "--format", fmt,
                                    cwd=self.project)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")  # nothing pretending success
                self.assertIn("No GNATprove result set found.", err)
                self.assertIn("Run GNATprove first or pass the result "
                              "path explicitly.", err)

    def test_multiple_candidates_sorted_never_guessed(self):
        # created in non-sorted order, with differing sizes and mtimes
        for name, fx in (("z3", "pool_prover_z3"),
                         ("altergo", "pool_prover_altergo"),
                         ("cvc5", "pool_prover_cvc5")):
            place(fx, self.project / "obj" / name / "gnatprove")
        place("pool_p5", self.project / "gnatprove")
        rc, out, err = call("explain", "--format", "json",
                            cwd=self.project)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        listed = [ln.strip() for ln in err.splitlines()
                  if ln.startswith("  ")]
        expected = ["gnatprove", "obj/altergo/gnatprove",
                    "obj/cvc5/gnatprove", "obj/z3/gnatprove"]
        self.assertEqual(listed, expected)
        self.assertIn("refusing to guess", err)
        with self.assertRaises(DiscoveryError) as ctx:
            discover(self.project)
        self.assertEqual([c.as_posix() for c in ctx.exception.candidates],
                         expected)


    def test_explicit_path_wins_over_multiple_candidates(self):
        place("pool_prover_z3", self.project / "obj" / "z3" / "gnatprove")
        place("pool_p5", self.project / "obj" / "p5" / "gnatprove")
        self.assertEqual(len(find_result_sets(self.project)), 2)
        for arg in ("obj/p5/gnatprove", "obj/p5",
                    "obj/p5/gnatprove/gnatprove.sarif"):
            with self.subTest(path=arg):
                rc, out, err = call("explain", arg, "--format", "json",
                                    cwd=self.project)
                self.assertEqual(rc, 0, err)
                doc = json.loads(out)
                self.assertEqual([d["code"] for d in doc["diagnostics"]],
                                 ["SRD001"])
                self.assertNotIn("input", doc["analysis"])

    def test_explicit_missing_path_does_not_fall_back(self):
        place("pool_p5", self.project / "obj" / "gnatprove")
        rc, out, err = call("explain", "obj/typo", cwd=self.project)
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("obj/typo", err)

    def test_hidden_and_alire_dirs_are_not_searched(self):
        place("pool_p5", self.project / "obj" / "gnatprove")
        place("pool_positive",
              self.project / "alire" / "cache" / "dep" / "obj" / "gnatprove")
        place("pool_positive", self.project / ".git" / "x" / "gnatprove")
        self.assertEqual(find_result_sets(self.project),
                         [Path("obj/gnatprove")])

    def test_symlinked_dirs_are_not_followed(self):
        place("pool_p5", self.project / "obj" / "gnatprove")
        other = Path(self._tmp.name) / "elsewhere"
        place("pool_positive", other / "gnatprove")
        (self.project / "link").symlink_to(other, target_is_directory=True)
        self.assertEqual(find_result_sets(self.project),
                         [Path("obj/gnatprove")])

    def test_discovery_keeps_ali_conservatism(self):
        """A discovered result set without .ali: SRD002 is skipped, even
        when .ali files for the same units exist elsewhere in the tree."""
        place("pool_spec_no_count_posts",
              self.project / "obj" / "gnatprove", with_ali=False)
        stray = self.project / "obj" / "stray_ali"
        stray.mkdir()
        for p in support.fixture("pool_spec_no_count_posts").glob("*.ali"):
            shutil.copy(p, stray / p.name)
        rc, out, _ = call("explain", "--format", "json", cwd=self.project)
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        srd002 = doc["analysis"]["rules"]["SRD002"]
        self.assertFalse(srd002["evaluated"])
        self.assertEqual(srd002["dependency_source"], "none")
        self.assertEqual(doc["summary"]["by_code"]["SRD002"], 0)
        self.assertTrue(any(n.startswith("SRD002 not evaluated")
                            for n in doc["notes"]))
        # with its own .ali (explicit fixture) the rule does fire
        _, out, _ = call("explain", str(support.fixture(
            "pool_spec_no_count_posts")), "--format", "json")
        self.assertEqual(json.loads(out)["summary"]["by_code"]["SRD002"], 2)


class ExplainAnalyzeCompatibility(unittest.TestCase):
    def test_explain_and_analyze_identical_for_explicit_paths(self):
        for name in support.manifest():
            path = str(support.fixture(name))
            with self.subTest(fixture=name):
                for fmt in ("json", "text"):
                    self.assertEqual(call("analyze", path, "--format", fmt),
                                     call("explain", path, "--format", fmt))

    def test_analyze_still_requires_path(self):
        with self.assertRaises(SystemExit) as ctx, \
                contextlib.redirect_stderr(io.StringIO()):
            main(["analyze"])
        self.assertEqual(ctx.exception.code, 2)

    def test_fail_on_with_explain(self):
        rc, _, _ = call("explain", str(support.fixture("ring_b3")),
                        "--fail-on", "SRD001")
        self.assertEqual(rc, 1)

    def test_module_invocations_still_work(self):
        f = support.fixture
        for argv in (["rules"],
                     ["analyze", str(f("pool_p5")), "--format", "json"],
                     ["explain", str(f("pool_p5")), "--format", "json"],
                     ["compare-provers",
                      "--run", f"cvc5={f('pool_prover_cvc5')}",
                      "--run", f"z3={f('pool_prover_z3')}"]):
            with self.subTest(argv=argv[0]):
                proc = subprocess.run(
                    [sys.executable, "-m", "spark_refine_diagnostics",
                     *argv], cwd=support.DIAGNOSTICS, capture_output=True,
                    text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_version(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as ctx, \
                contextlib.redirect_stdout(out):
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertTrue(out.getvalue().startswith("spark-refine "))



class AgentJson(unittest.TestCase):
    def test_rule_catalogue_category_and_action(self):
        self.assertEqual({c: r.category for c, r in RULES.items()},
                         EXPECTED_CATEGORY)
        self.assertEqual({c: r.action for c, r in RULES.items()},
                         EXPECTED_ACTION)
        rc, out, _ = call("rules", "--format", "json")
        self.assertEqual(rc, 0)
        rules = json.loads(out)["rules"]
        for code in RULES:
            self.assertEqual(rules[code]["category"],
                             EXPECTED_CATEGORY[code])
            self.assertEqual(rules[code]["action"], EXPECTED_ACTION[code])
            self.assertTrue(rules[code]["action_description"])
        _, text, _ = call("rules")
        for code in RULES:
            self.assertIn(f"category: {EXPECTED_CATEGORY[code]}   "
                          f"action: {EXPECTED_ACTION[code]}", text)

    def test_identifiers_are_short_and_workflow_level(self):
        for r in RULES.values():
            for ident in (r.category, r.action):
                self.assertRegex(ident, r"^[a-z][a-z_]*[a-z]$")
                self.assertLessEqual(len(ident), 60)
            # never a concrete edit location
            self.assertIsNone(re.search(r"\bline\b|\d",
                                        r.action_description))

    def _docs(self):
        f = support.fixture
        for name in support.manifest():
            yield name, json.loads(call("explain", str(f(name)),
                                        "--format", "json")[1])
        yield "compare", json.loads(call(
            "compare-provers", "--run", f"cvc5={f('pool_prover_cvc5')}",
            "--run", f"z3={f('pool_prover_z3')}",
            "--run", f"altergo={f('pool_prover_altergo')}",
            "--format", "json")[1])

    def test_every_diagnostic_has_category_and_action(self):
        seen = set()
        for name, doc in self._docs():
            self.assertEqual(doc["format_version"], 1)
            for d in doc["diagnostics"]:
                with self.subTest(fixture=name, code=d["code"]):
                    self.assertEqual(d["category"],
                                     EXPECTED_CATEGORY[d["code"]])
                    self.assertEqual(d["action"],
                                     EXPECTED_ACTION[d["code"]])
                    seen.add(d["code"])
        self.assertEqual(seen, set(RULES))

    def test_summary_is_derived_from_diagnostics(self):
        for name, doc in self._docs():
            with self.subTest(fixture=name):
                diags, s = doc["diagnostics"], doc["summary"]
                self.assertEqual(s["diagnostic_count"], len(diags))
                self.assertEqual(list(s["by_code"]), list(RULES))
                self.assertEqual(list(s["by_confidence"]),
                                 ["high", "medium", "low"])
                for key, field in (("by_code", "code"),
                                   ("by_confidence", "confidence"),
                                   ("by_category", "category"),
                                   ("by_action", "action")):
                    counts = {k: 0 for k in s[key]}
                    for d in diags:
                        counts[d[field]] += 1
                    self.assertEqual(s[key], counts, key)

    def test_summary_known_values(self):
        _, out, _ = call("explain", str(support.fixture(
            "pool_spec_no_count_posts")), "--format", "json")
        s = json.loads(out)["summary"]
        self.assertEqual(s["diagnostic_count"], 2)
        self.assertEqual(s["by_code"], {"SRD001": 0, "SRD002": 2,
                                        "SRD003": 0})
        empty = summary_to_dict([])
        self.assertEqual(empty["diagnostic_count"], 0)
        self.assertEqual(set(empty["by_code"].values()), {0})

    def test_json_is_additive_and_deterministic(self):
        path = str(support.fixture("ring_b3"))
        outs = {call("explain", path, "--format", "json")[1]
                for _ in range(2)}
        self.assertEqual(len(outs), 1)
        doc = json.loads(outs.pop())
        # every Task 005 key is still present, unchanged in meaning
        for key in ("format_version", "tool", "rules", "runs", "notes",
                    "analysis", "diagnostics"):
            self.assertIn(key, doc)
        self.assertEqual(doc["tool"], "spark_refine_diagnostics")
        for key in ("code", "severity", "confidence", "title", "entity",
                    "primary_location", "related", "evidence",
                    "explanation", "recommendation", "data"):
            self.assertIn(key, doc["diagnostics"][0])


if __name__ == "__main__":
    unittest.main()

