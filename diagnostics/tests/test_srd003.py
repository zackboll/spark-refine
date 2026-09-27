"""SRD003 (prover-portfolio dependency) on the real single-prover runs of
the Task 003/004 prover matrices."""

from __future__ import annotations

import unittest
from dataclasses import replace

import json
import random
import tempfile
from pathlib import Path

import support
from spark_refine_diagnostics import (compare_provers, compare_provers_report,
                                      load_run)
from spark_refine_diagnostics.model import (Check, Location, ProofRun,
                                            Severity, Status)
from spark_refine_diagnostics.render import to_json
from spark_refine_diagnostics.srd003 import match_checks


def runs(prefix):
    return [replace(support.run_of(f"{prefix}_{p}"), name=p)
            for p in ("cvc5", "z3", "altergo")]


def results(d):
    return dict(dict(d.data)["results"])


class Srd003OnPool(unittest.TestCase):
    def test_manual_pool_matrix(self):
        ref = replace(support.run_of("pool_positive"), name="portfolio")
        diags, notes = compare_provers(runs("pool_prover"), ref)
        self.assertEqual(notes, [])
        got = sorted((dict(d.data)["rule"], d.entity) for d in diags)
        # the prover matrix in BASELINE_METRICS / LIBRARY_METRICS: CVC5
        # alone fails 6, Z3 alone fails the lemma assert, Alt-Ergo none
        self.assertEqual(got, [
            ("VC_ASSERT", "Fixed_Pool.Lemma_Universe_Bound"),
            ("VC_INVARIANT_CHECK", "Fixed_Pool.Allocate"),
            ("VC_INVARIANT_CHECK", "Fixed_Pool.Release"),
            ("VC_POSTCONDITION", "Fixed_Pool.Allocate"),
            ("VC_POSTCONDITION", "Fixed_Pool.Initialize"),
            ("VC_PRECONDITION", "Fixed_Pool.Free_Model")])
        lemma = next(d for d in diags
                     if d.entity == "Fixed_Pool.Lemma_Universe_Bound")
        self.assertEqual(results(lemma), {
            "cvc5": "unproved", "z3": "unproved", "altergo": "proved",
            "portfolio (reference)": "proved"})
        self.assertEqual(lemma.primary_location,
                         Location("fixed_pool.adb", 45, 22))
        for d in diags:
            self.assertEqual(d.severity, Severity.NOTE)
            self.assertEqual(results(d)["altergo"], "proved")
            self.assertEqual(results(d)["portfolio (reference)"], "proved")

    def test_library_backed_matrix(self):
        ref = replace(support.run_of("pool_lib_positive"), name="portfolio")
        diags, _ = compare_provers(runs("pool_lib_prover"), ref)
        z3_fail = [d for d in diags if results(d)["z3"] == "unproved"]
        self.assertEqual([(d.entity, d.primary_location.file)
                          for d in z3_fail],
                         [("Fixed_Pool.Free_Prefix.Model",
                           "spark_refine_prefix_sets.ads")])
        self.assertEqual(len(diags), 5)

    def test_every_single_prover_failure_is_reported(self):
        """Completeness on the fixtures: every unproved check of a
        single-prover run appears in exactly one SRD003 (altergo proves
        all, so each is proved somewhere)."""
        for prefix in ("pool_prover", "pool_lib_prover"):
            rs = runs(prefix)
            diags, _ = compare_provers(rs)
            reported = {(dict(d.data)["rule"], d.entity) for d in diags}
            for r in rs:
                for c in r.unproved:
                    self.assertIn((c.rule, c.entity), reported)

    def test_wording(self):
        diags, _ = compare_provers(runs("pool_prover"))
        for d in diags:
            text = (d.explanation + d.recommendation).lower()
            self.assertIn("not unsoundness", text)
            self.assertIn("pinned", text)


class Srd003Negative(unittest.TestCase):
    def test_ring_buffer_proves_with_every_prover(self):
        diags, _ = compare_provers(runs("ring_prover"))
        self.assertEqual(diags, [])

    def test_needs_two_runs(self):
        self.assertEqual(compare_provers(runs("pool_prover")[:1])[0], [])

    def test_identical_runs_give_nothing(self):
        r = support.run_of("pool_prover_cvc5")
        diags, _ = compare_provers([replace(r, name="a"),
                                    replace(r, name="b")])
        self.assertEqual(diags, [])

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValueError):
            compare_provers([support.run_of("pool_prover_z3")] * 2)


def synthetic_run(name, checks):
    """A minimal run for matching edge cases no real fixture contains."""
    return ProofRun(name=name, source="", tool_version="FSF 16.1.0",
                    command_line="", exit_code=None, checks=list(checks))


def chk(rule, line, col, status, entity="P.Op", file="p.adb"):
    return Check(rule=rule, status=status, location=Location(file, line,
                                                             col),
                 entity=entity, message="")


P, U = Status.PROVED, Status.UNPROVED


class MatchingPolicy(unittest.TestCase):
    def test_real_matrices_match_confidently(self):
        for prefix, exact, unique in (("pool_prover", 130, 2),
                                      ("pool_lib_prover", 155, 2),
                                      ("ring_prover", 112, 0)):
            with self.subTest(prefix=prefix):
                res = match_checks(runs(prefix))
                c = res.counts()
                self.assertEqual((c["exact"], c["unique_entity"]),
                                 (exact, unique))
                self.assertEqual(c["fingerprint"], 0)
                # the only duplicate identity: a container aggregate check
                # reported 4x per run, identical outcomes; never paired
                self.assertEqual(c["duplicate_identity"], 1)
                self.assertEqual(c["ambiguous_candidates"], 0)
                self.assertEqual(c["unmatched"], 0)
                self.assertEqual(res.unresolved[0].key[0],
                                 "VC_CONTAINER_AGGR_CHECK")
                self.assertFalse(res.unresolved[0].outcomes_differ())

    def test_unique_entity_matches_are_the_documented_ones(self):
        diags, _ = compare_provers(runs("pool_prover"))
        got = sorted((d.entity, d.match_quality) for d in diags
                     if d.match_quality == "unique_entity")
        # proved at the aspect (39:17 / 45:17), unproved at the failing
        # conjunct (41:24 / 46:21): one such check per entity per run
        self.assertEqual(got, [("Fixed_Pool.Allocate", "unique_entity"),
                               ("Fixed_Pool.Initialize", "unique_entity")])

    def test_case_a_duplicate_identity_is_not_paired(self):
        """Two checks with identical (rule, file, line, column, entity) and
        different outcomes/order across runs: no pairing, no SRD003,
        ambiguity reported in the analysis metadata."""
        a = synthetic_run("a", [chk("VC_ASSERT", 5, 7, P),
                                chk("VC_ASSERT", 5, 7, U)])
        b = synthetic_run("b", [chk("VC_ASSERT", 5, 7, U),
                                chk("VC_ASSERT", 5, 7, P)])
        c = synthetic_run("c", [chk("VC_ASSERT", 5, 7, P),
                                chk("VC_ASSERT", 5, 7, P)])
        rep = compare_provers_report([a, b, c])
        self.assertEqual(rep.diagnostics, [])
        m = rep.analysis["srd003_matching"]
        self.assertEqual(m["counts"]["duplicate_identity"], 1)
        u = m["unresolved"][0]
        self.assertEqual(u["reason"], "duplicate_identity")
        self.assertTrue(u["outcomes_differ"])
        self.assertEqual([x["candidate"] for x in u["candidates"]["a"]],
                         ["1 of 2", "2 of 2"])
        self.assertTrue(any("could not be matched confidently" in n
                            for n in rep.notes))

    def test_ambiguous_leftovers_are_not_paired_by_source_order(self):
        """Same (rule, file, entity), two checks per run at shifted lines:
        the old ordered fallback would pair them; now they stay unpaired."""
        a = synthetic_run("a", [chk("VC_ASSERT", 5, 7, P),
                                chk("VC_ASSERT", 9, 7, U)])
        b = synthetic_run("b", [chk("VC_ASSERT", 6, 7, U),
                                chk("VC_ASSERT", 10, 7, P)])
        rep = compare_provers_report([a, b])
        self.assertEqual(rep.diagnostics, [])
        self.assertEqual(rep.analysis["srd003_matching"]["counts"]
                         ["ambiguous_candidates"], 1)

    def test_one_run_without_candidate_is_unmatched(self):
        a = synthetic_run("a", [chk("VC_ASSERT", 5, 7, P)])
        b = synthetic_run("b", [chk("VC_RANGE_CHECK", 5, 7, U)])
        res = match_checks([a, b])
        self.assertEqual(res.matched, [])
        self.assertEqual(sorted(u.reason for u in res.unresolved),
                         ["unmatched", "unmatched"])

    def test_case_b_unique_normal_check(self):
        a = synthetic_run("a", [chk("VC_ASSERT", 5, 7, P),
                                chk("VC_ASSERT", 9, 7, P)])
        b = synthetic_run("b", [chk("VC_ASSERT", 5, 7, U),
                                chk("VC_ASSERT", 9, 7, P)])
        diags, _ = compare_provers([a, b])
        self.assertEqual([(d.primary_location, d.match_quality)
                          for d in diags],
                         [(Location("p.adb", 5, 7), "exact")])

    def test_shifted_lines_are_no_longer_paired(self):
        """Every check of fixed_pool.adb moved one line down in one run:
        identities that are unique per (rule, file, entity) still match
        (unique_entity); the rest become ambiguous, never paired by order."""
        a, b = runs("pool_prover")[:2]
        shifted = replace(b, checks=[
            replace(c, location=replace(c.location,
                                        line=(c.location.line or 0) + 1))
            if c.location.file == "fixed_pool.adb" else c
            for c in b.checks])
        rep = compare_provers_report([a, shifted])
        for d in rep.diagnostics:
            self.assertIn(d.match_quality, ("exact", "unique_entity"))
        c = rep.analysis["srd003_matching"]["counts"]
        self.assertGreater(c["ambiguous_candidates"], 0)


def reordered_copy(name: str, tmp: Path, seed: int) -> Path:
    """Copy a real fixture, shuffling the SARIF `results` array (and the
    .spark proof entries): an equivalent GNATprove output whose only
    difference is result-list order."""
    src = support.fixture(name)
    dest = tmp / name
    dest.mkdir()
    rng = random.Random(seed)
    for p in src.iterdir():
        text = p.read_text("utf-8")
        if p.name == "gnatprove.sarif" or p.suffix == ".spark":
            data = json.loads(text)
            if p.suffix == ".sarif":
                rng.shuffle(data["runs"][0]["results"])
            else:
                rng.shuffle(data["proof"])
            text = json.dumps(data)
        (dest / p.name).write_text(text, "utf-8")
    return dest


class ReorderingStability(unittest.TestCase):
    def test_case_c_reordered_results_give_identical_output(self):
        for prefix, ref_name in (("pool_prover", "pool_positive"),
                                 ("pool_lib_prover", "pool_lib_positive")):
            with self.subTest(prefix=prefix), \
                    tempfile.TemporaryDirectory() as tmp:
                outs = []
                for seed in (None, 1, 2):
                    rs = []
                    for i, p in enumerate(("cvc5", "z3", "altergo")):
                        n = f"{prefix}_{p}"
                        if seed is None:
                            path = support.fixture(n)
                        else:
                            base = Path(tmp) / str(seed)
                            base.mkdir(exist_ok=True)
                            path = reordered_copy(n, base, 10 * seed + i)
                        rs.append(load_run(path, name=p))
                    ref = load_run(support.fixture(ref_name),
                                   name="portfolio")
                    rep = compare_provers_report(rs, ref)
                    # run.source differs (temp path); compare the analysis
                    for r in rep.runs:
                        r.source = ""
                    outs.append(to_json(rep.runs, rep.diagnostics,
                                        rep.notes, rep.analysis))
                self.assertEqual(outs[0], outs[1])
                self.assertEqual(outs[0], outs[2])
                self.assertIn('"match_quality"', outs[0])

    def test_reordered_run_list_gives_same_findings(self):
        rs = runs("pool_prover")
        a = compare_provers(rs)[0]
        b = compare_provers(list(reversed(rs)))[0]
        key = lambda ds: sorted((d.entity, d.primary_location,  # noqa
                                 d.match_quality) for d in ds)
        self.assertEqual(key(a), key(b))


class MatchQualityJson(unittest.TestCase):
    def test_every_srd003_has_a_confident_match_quality(self):
        rep = compare_provers_report(runs("pool_prover"))
        doc = json.loads(to_json(rep.runs, rep.diagnostics, rep.notes,
                                 rep.analysis))
        qualities = [d["match_quality"] for d in doc["diagnostics"]]
        self.assertEqual(len(qualities), 6)
        self.assertEqual(sorted(set(qualities)), ["exact", "unique_entity"])
        self.assertNotIn("ambiguous", qualities)
        self.assertEqual(doc["analysis"]["srd003_matching"]["policy"],
                         ["exact", "fingerprint", "unique_entity"])
        self.assertIn("not available",
                      doc["analysis"]["srd003_matching"]
                      ["fingerprint_support"])

    def test_single_run_diagnostics_have_no_match_quality(self):
        from spark_refine_diagnostics.render import diagnostic_to_dict
        for name in ("pool_p5", "pool_spec_no_count_posts"):
            for d in support.analyzed(name)[1]:
                self.assertNotIn("match_quality", diagnostic_to_dict(d))


if __name__ == "__main__":
    unittest.main()
