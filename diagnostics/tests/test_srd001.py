"""SRD001 (invariant masking risk) on real GNATprove fixtures."""

from __future__ import annotations

import unittest

import support
from spark_refine_diagnostics.model import Confidence

FORBIDDEN_CLAIMS = ("is wrong", "is false", "was proved using",
                    "definitely", "unsound", "wrong theorem", "depends on "
                    "the failed invariant", "bug")


def srd001(name):
    return support.by_code(support.analyzed(name)[1], "SRD001")


class Srd001Rule(unittest.TestCase):
    def test_required_positive_fixtures(self):
        # task section 6: B3, B4, P1, P5, L1, L5
        for name, entity in (("ring_b3", "Ring_Buffer.Pop"),
                             ("ring_b4", "Ring_Buffer.Push"),
                             ("pool_p1", "Fixed_Pool.Initialize"),
                             ("pool_p5", "Fixed_Pool.Release"),
                             ("pool_l1", "Fixed_Pool.Initialize"),
                             ("pool_l5", "Fixed_Pool.Release")):
            with self.subTest(fixture=name):
                diags = srd001(name)
                self.assertEqual([d.entity for d in diags], [entity])
                d = diags[0]
                self.assertEqual(d.confidence, Confidence.HIGH)
                failed = [r for r in d.related if r.role == "failed"]
                affected = [r for r in d.related
                            if r.role == "potentially affected"]
                self.assertTrue(failed and affected)
                self.assertTrue(all(r.rule == "VC_INVARIANT_CHECK"
                                    and r.status == "unproved"
                                    for r in failed))
                self.assertTrue(all(r.rule == "VC_POSTCONDITION"
                                    and r.status == "proved"
                                    and r.entity == entity
                                    for r in affected))
                self.assertEqual(d.primary_location, failed[0].location)

    def test_rule_definition_holds_on_every_fixture(self):
        """SRD001 fires for exactly the entities with an unproved
        VC_INVARIANT_CHECK and a proved VC_POSTCONDITION."""
        for name in support.manifest():
            with self.subTest(fixture=name):
                run = support.run_of(name)
                inv = {c.entity for c in run.unproved
                       if c.rule == "VC_INVARIANT_CHECK"}
                post = {c.entity for c in run.proved
                        if c.rule == "VC_POSTCONDITION"}
                self.assertEqual(sorted(d.entity for d in srd001(name)),
                                 sorted(inv & post))

    def test_no_srd001_without_proved_postcondition(self):
        # P4/L4: the invariant fails, but the Release postcondition is
        # already unproved. A failed invariant alone stays ordinary output.
        for name in ("pool_p4", "pool_l4"):
            with self.subTest(fixture=name):
                self.assertIn(("VC_INVARIANT_CHECK", "Fixed_Pool.Release"),
                              support.unproved_pairs(support.run_of(name)))
                self.assertEqual(srd001(name), [])

    def test_justified_invariant_does_not_trigger(self):
        from dataclasses import replace
        from spark_refine_diagnostics import srd001 as rule
        from spark_refine_diagnostics.model import ProofRun, Status
        src = support.run_of("pool_p5")
        run = ProofRun(name="j", source="", tool_version="",
                       command_line="", exit_code=None,
                       checks=[replace(c, status=Status.JUSTIFIED)
                               if c.unproved else c for c in src.checks])
        self.assertEqual(rule.check(run), [])

    def test_wording_does_not_overclaim(self):
        for name in ("ring_b3", "pool_p5", "ring_b1"):
            for d in srd001(name):
                text = " ".join((d.title, d.explanation, d.recommendation,
                                 *d.evidence)).lower()
                self.assertIn("may", text)
                self.assertIn("potentially", text)
                for bad in FORBIDDEN_CLAIMS:
                    self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
