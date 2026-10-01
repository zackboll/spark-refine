"""Task 018 pure qualification and portable evidence gates."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import external_candidate_survey as s  # noqa: E402


def case(**changes):
    c = dict(repository="example", failing_sha="a" * 40, committed_failure=True,
             gnatprove_major=16, gnatprove_version="16.1.0", reproducible_preproof=True,
             vc="VC_INVARIANT", documented_failed_vc=True, upstream_reference="issue 1",
             same_entity_post=True, same_entity_post_documented=True,
             correction_documented=True, caller_callee_documented=True,
             implementation_proved_documented=True, public_boundary_fix=True,
             public_boundary_fix_documented=True, evidence_kind="issue_pr",
             direct_pair=True, scope_units=1)
    c.update(changes)
    return c


class Survey(unittest.TestCase):
    def test_categories_and_invariant_documentation_gate(self):
        self.assertEqual(len(s.CATEGORIES), 10)
        self.assertEqual(s.qualify(case()), "QUALIFIED_SRD001")
        self.assertEqual(s.qualify(case(same_entity_post_documented=False)),
                         "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")
        self.assertEqual(s.qualify(case(documented_failed_vc=False)),
                         "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")
        self.assertEqual(s.qualify(case(correction_documented=False)),
                         "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")

    def test_srd002_documentation_and_implementation_gates(self):
        c = case(vc="VC_PRECONDITION")
        self.assertEqual(s.qualify(c), "QUALIFIED_SRD002")
        self.assertEqual(s.qualify(case(vc="VC_ASSERT")), "QUALIFIED_SRD002")
        self.assertEqual(s.qualify(case(vc="VC_ASSERT", implementation_proved_documented=False)),
                         "REJECT_IMPLEMENTATION_NOT_PROVED")
        self.assertEqual(s.qualify(case(vc="VC_PRECONDITION", public_boundary_fix_documented=False)),
                         "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")
        self.assertEqual(s.qualify(case(vc="VC_PRECONDITION", caller_callee_documented=False)),
                         "REJECT_NO_STRUCTURAL_UPSTREAM_EVIDENCE")

    def test_negative_gates(self):
        self.assertEqual(s.qualify(case(committed_failure=False)), "REJECT_UNCOMMITTED_FAILURE")
        self.assertEqual(s.qualify(case(gnatprove_major=15)), "REJECT_TOOLCHAIN_VERSION")
        self.assertEqual(s.qualify(case(vc="VC_OVERFLOW_CHECK")), "REJECT_WRONG_VC_SHAPE")
        self.assertEqual(s.qualify(case(reproducible_preproof=False)),
                         "REJECT_NOT_REPRODUCIBLE_PREPROOF")
        self.assertEqual(s.qualify(case(already_tested=True)), "REJECT_ALREADY_TESTED")

    def test_deterministic_selection_no_diagnostic_bias(self):
        a = case(repository="a", gnatprove_version="16.0.0")
        b = case(repository="b", evidence_kind="commit")
        c = case(repository="c", direct_pair=False)
        d = case(repository="d", scope_units=2)
        e = case(repository="e")
        self.assertEqual(s.select([a, b, c, d, e])["repository"], "e")
        self.assertEqual(s.select([e, d, c, b, a])["repository"], "e")
        self.assertIsNone(s.select([case(committed_failure=False)]))
        for field in s.FORBIDDEN:
            with self.assertRaises(ValueError):
                s.select([case(**{field: 0})])

    def test_canonical_paths_determinism(self):
        doc = {"candidates": [{"repository": "example", "category": "REJECT_OTHER"}],
               "verdict": "NO_NATURAL_POSITIVE_CANDIDATE_QUALIFIED"}
        self.assertEqual(s.canonical(doc), s.canonical(dict(reversed(list(doc.items())))))
        for value in ("/home/user/work", "C:\\Users\\private"):
            with self.assertRaises(ValueError):
                s.canonical({"file": value})
        with self.assertRaises(ValueError):
            s.canonical({"timestamp": "today"})


if __name__ == "__main__":
    unittest.main()