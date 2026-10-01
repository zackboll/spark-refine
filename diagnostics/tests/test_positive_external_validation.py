"""Pure Task 017 comparison and evidence gates; no external checkout needed."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import positive_external_validation as p  # noqa: E402
from external_validation import canonical  # noqa: E402


def check(rule="VC_PRECONDITION", entity="A.B", line=1, column=1):
    return SimpleNamespace(rule=rule, entity=entity,
                           location=SimpleNamespace(file="a.adb", line=line, column=column))


class PositiveExternalValidation(unittest.TestCase):
    def test_pair_exact_unique_ambiguous_and_absent(self):
        a = check()
        self.assertEqual(p.pair(a, [check()])[0], "exact")
        self.assertEqual(p.pair(a, [check(line=2)])[0], "unique_entity_rule")
        self.assertEqual(p.pair(a, [check(), check()])[0], "not_comparable")
        self.assertEqual(p.pair(a, [check(line=2), check(line=3)])[0], "not_comparable")
        self.assertEqual(p.pair(a, [check(entity="X")])[0], "not_comparable")

    def test_rule_not_evaluated_is_not_zero(self):
        self.assertEqual(p.state({"evaluated": False, "reason": "no ALI"}, 0),
                         {"evaluated": False, "count": None, "reason": "no ALI"})
        self.assertEqual(p.state({"evaluated": True}, 0)["count"], 0)

    def test_srd001_structural_comparison(self):
        self.assertEqual(p.srd001_pattern(True, True, True), "same_structural_pattern_persists")
        self.assertEqual(p.srd001_pattern(False, True, True), "failing_invariant_disappears")
        self.assertEqual(p.srd001_pattern(True, False, True), "related_postcondition_disappears")
        self.assertEqual(p.srd001_pattern(True, True, False), "source_identity_changed")

    def test_srd002_structural_comparison(self):
        self.assertEqual(p.srd002_pattern(True, True, True), "same_structural_pattern_persists")
        self.assertEqual(p.srd002_pattern(False, True, True), "client_only_pattern_disappears")
        self.assertEqual(p.srd002_pattern(True, False, False), "not_comparable")

    def test_corroboration_requires_change_and_disappearance(self):
        self.assertEqual(p.category(True, True, "contract_changed"),
                         "externally_corroborated_structure")
        self.assertEqual(p.category(True, True, "unchanged"), "mechanically_supported_only")
        self.assertEqual(p.category(True, False, "both_changed"), "control_pattern_persists")
        self.assertEqual(p.category(True, True, "both_changed", comparable=False), "not_comparable")
        self.assertEqual(p.category(True, True, "both_changed", compatible=False),
                         "artifact_or_toolchain_limitation")
        with self.assertRaises(ValueError):
            p.category(True, True, "invented")

    def test_probe_estimate(self):
        self.assertEqual(p.estimate(3, 4, 4),
                         {"naive_observations": 12, "unique_prefix_programs": 4,
                          "additional_runs_after_baseline": 3})

    def test_upstream_total_and_rejection(self):
        self.assertEqual(p.summary("Total    1006    205 (20%)    790 (79%)    .    11 (1%)"),
                         {"checks": 1006, "proved": 995, "unproved": 11, "justified": 0})
        with self.assertRaises(ValueError):
            p.summary("Total    10    9    .    .    2")

    def test_deterministic_and_path_prose_rejection(self):
        self.assertEqual(canonical({"rules": ["VC_ASSERT"]}),
                         canonical({"rules": ["VC_ASSERT"]}))
        for item in ({"file": "/private/secret"}, {"prover_message": "failure"},
                     {"timestamp": "now"}):
            with self.assertRaises(ValueError):
                canonical(item)


if __name__ == "__main__":
    unittest.main()