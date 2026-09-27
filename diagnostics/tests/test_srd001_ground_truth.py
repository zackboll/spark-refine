"""SRD001 evaluation against ablation ground truth (task sections 10, 12).

Two concepts are measured separately:
  masking_risk                  what SRD001 promises (structural)
  secondary_failure_confirmed   whether a proved postcondition is really
                                false (from invariant-removal ablations)

The labels in expectations.toml are hand-written; these tests re-derive
them from the committed ablation fixtures so they cannot drift.
"""

from __future__ import annotations

import unittest

import support


def srd001(name):
    return support.by_code(support.analyzed(name)[1], "SRD001")


def unproved_posts(name):
    return {(c.rule, c.entity) for c in support.run_of(name).unproved
            if c.rule == "VC_POSTCONDITION"}


def labelled():
    for name, exp in support.expectations().items():
        if "ground_truth" in exp:
            yield name, exp["ground_truth"]


class GroundTruthLabels(unittest.TestCase):
    def test_masking_risk_labels_match_structure(self):
        for name, gt in labelled():
            with self.subTest(fixture=name):
                run = support.run_of(name)
                inv = {c.entity for c in run.unproved
                       if c.rule == "VC_INVARIANT_CHECK"}
                post = {c.entity for c in run.proved
                        if c.rule == "VC_POSTCONDITION"}
                self.assertEqual(gt["masking_risk"], bool(inv & post))

    def test_secondary_failure_labels_match_ablation(self):
        for name, gt in labelled():
            with self.subTest(fixture=name, basis=gt["basis"]):
                mask = unproved_posts(gt["mask"])
                base = unproved_posts(gt["mask_baseline"])
                proved = {(c.rule, c.entity)
                          for c in support.run_of(name).proved
                          if c.rule == "VC_POSTCONDITION"}
                masked = {tuple(m) for m in gt["masked"]}
                if gt["basis"] == "differential":
                    self.assertEqual(masked, (mask - base) & proved)
                elif gt["basis"] == "differential-negative":
                    self.assertEqual(masked, set())
                    self.assertEqual((mask - base) & proved, set())
                else:
                    self.assertEqual(gt["basis"], "equivalence")
                    # the differential is unusable: the no-fault baseline
                    # already fails the postcondition ...
                    self.assertTrue(masked <= base)
                    self.assertTrue(masked <= mask)
                    # ... so rely on a byte-identical, differentially
                    # confirmed fault
                    ref = support.expected(gt["equivalent_to"])
                    self.assertEqual(ref["ground_truth"]["basis"],
                                     "differential")
                    self.assertEqual(masked, {tuple(m) for m in
                                              ref["ground_truth"]["masked"]})
                    self._assert_identical_fault_edits(
                        name, gt["equivalent_to"])
                self.assertEqual(gt["secondary_failure_confirmed"],
                                 bool(masked))
                self.assertTrue(masked <= proved)

    def _assert_identical_fault_edits(self, a, b):
        import tomllib
        fp = support.REPO / "examples" / "fixed_pool"
        dirs = {"pool_l5": fp / "variants/library_backed/negative/"
                               "l5_release_duplicate",
                "pool_p5": fp / "negative/p5_release_duplicate"}
        edits = [tomllib.loads((dirs[n] / "fault.toml").read_text("utf-8")
                               )["edit"] for n in (a, b)]
        self.assertEqual(edits[0], edits[1])

    def test_required_confirmed_examples(self):
        for name in ("ring_b3", "ring_b4", "pool_p1", "pool_p5", "pool_l1",
                     "pool_l5"):
            self.assertTrue(support.expected(name)["ground_truth"]
                            ["secondary_failure_confirmed"], name)


class Measurement(unittest.TestCase):
    def test_srd001_against_both_concepts(self):
        rows = [(n, gt, bool(srd001(n))) for n, gt in labelled()]

        def confusion(key):
            return (sum(g[key] and s for _, g, s in rows),
                    sum(g[key] and not s for _, g, s in rows),
                    sum(not g[key] and s for _, g, s in rows))

        # masking-risk detection (what SRD001 promises): exact
        self.assertEqual(confusion("masking_risk"), (9, 0, 0))
        # actual secondary failures: 6/6 found; 3 risk warnings (B1, B2,
        # B6) where the proved postcondition is in fact true
        self.assertEqual(confusion("secondary_failure_confirmed"), (6, 0, 3))

    def test_metrics_categories(self):
        """The categories reported in DIAGNOSTICS_METRICS.md. A 'positive'
        for SRD001 is the structural masking-risk pattern, NOT an underlying
        functional defect; the three conservative warnings are therefore
        correct SRD001 output, not errors."""
        rows = [(n, gt, bool(srd001(n))) for n, gt in labelled()]
        structural = sorted(n for n, g, _ in rows if g["masking_risk"])
        detected = sorted(n for n, g, s in rows if g["masking_risk"] and s)
        confirmed = sorted(n for n, g, s in rows
                           if g["secondary_failure_confirmed"] and s)
        conservative = sorted(n for n, g, s in rows
                              if s and g["masking_risk"]
                              and not g["secondary_failure_confirmed"])
        missed = sorted(n for n, g, s in rows if g["masking_risk"] and not s)
        self.assertEqual(len(structural), 9)
        self.assertEqual(detected, structural)              # 9 / 9
        self.assertEqual(confirmed, ["pool_l1", "pool_l5", "pool_p1",
                                     "pool_p5", "ring_b3", "ring_b4"])  # 6/6
        self.assertEqual(conservative, ["ring_b1", "ring_b2", "ring_b6"])
        self.assertEqual(missed, [])
        # controls: invariant fails but no proved postcondition to mask
        self.assertEqual(sorted(n for n, g, s in rows
                                if not g["masking_risk"]),
                         ["pool_l4", "pool_p4"])
        self.assertFalse(any(s for n, g, s in rows if not g["masking_risk"]))

    def test_cvc5_side_finding_is_prover_specific_risk_only(self):
        """CVC5 alone fails the Release invariant and proves its
        postcondition on CORRECT sources: SRD001 applies to that
        prover-specific result, while the portfolio run is clean."""
        for single, portfolio in (("pool_prover_cvc5", "pool_positive"),
                                  ("pool_lib_prover_cvc5",
                                   "pool_lib_positive")):
            self.assertEqual([d.entity for d in srd001(single)],
                             ["Fixed_Pool.Release"])
            self.assertEqual(support.analyzed(portfolio)[1], [])
            self.assertEqual(support.run_of(portfolio).unproved, [])

    def test_confirmed_masked_postconditions_are_listed(self):
        for name, gt in labelled():
            listed = {(r.rule, r.entity) for d in srd001(name)
                      for r in d.related if r.role == "potentially affected"}
            self.assertTrue({tuple(m) for m in gt["masked"]} <= listed,
                            name)


if __name__ == "__main__":
    unittest.main()
