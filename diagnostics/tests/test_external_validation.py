"""Pure Task 015 harness tests; no network, GNATprove or external checkout."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/external_validation.py"
spec = importlib.util.spec_from_file_location("external_validation", SCRIPT)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class TestExternalValidation(unittest.TestCase):
    def test_parse_real_shape_summary(self):
        log = ("info: unrelated\nSuccess: all checks proved (356 checks).\n"
               "Summary logged in /ignored/gnatprove.out\nproof_exit=0\n")
        self.assertEqual(E.parse_gnatprove_summary(log), {
            "checks": 356, "proved": 356, "unproved": 0, "justified": 0})

    def test_parse_synthetic_nonclean_and_justified_summary(self):
        self.assertEqual(E.parse_gnatprove_summary(
            "Summary: 10 checks: 8 proved, 2 unproved, 0 justified.\n"),
            {"checks": 10, "proved": 8, "unproved": 2, "justified": 0})
        self.assertEqual(E.parse_gnatprove_summary(
            "Summary: 10 checks: 7 proved, 2 unproved, 1 justified.\n"),
            {"checks": 10, "proved": 7, "unproved": 2, "justified": 1})

    def test_reject_missing_duplicate_and_malformed_summary(self):
        for log in ("", "Success: all checks proved (10 checks).\n" * 2,
                    "Success: all checks proved (ten checks).\n",
                    "Summary: 10 checks: 8 proved, x unproved, 0 justified.\n",
                    "Summary: 10 checks: 8 proved, 1 unproved, 0 justified.\n",
                    "Success: all checks proved (10 checks).\n"
                    "Summary: 10 checks: 8 proved, 2 unproved, 0 justified.\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                E.parse_gnatprove_summary(log)

    def test_proof_exit(self):
        self.assertEqual(E.parse_proof_exit("proof_exit=0\n"), 0)
        self.assertEqual(E.parse_proof_exit("proof_exit=1\n"), 1)
        for log in ("", "proof_exit=0\nproof_exit=1\n", "proof_exit=not_a_number\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                E.parse_proof_exit(log)

    def test_report_states_follow_inputs(self):
        core = {"analysis": {"rules": {}}}
        diagnostics = {"SRD001": {"evaluated": False},
                       "SRD002": {"evaluated": True}}
        semantic = {"evaluated": True}
        self.assertEqual(E.report_states(core, diagnostics, semantic,
                                         {"group_count": 1}, ["a", "b"]), {
            "core_analysis": True, "srd001_evaluated": False,
            "srd002_evaluated": True, "semantic_evaluated": True,
            "grouping_available": True, "probe_opportunities": 2})

    def test_selection_and_states(self):
        self.assertEqual(E.select_target(True, True), "muen")
        self.assertEqual(E.select_target(False, True), "sml-ada")
        self.assertIsNone(E.select_target(False, False))
        self.assertEqual(E.verdict(True, True, True), "EXTERNAL_VALIDATION_COMPLETED")
        self.assertEqual(E.verdict(True, False, True), "EXTERNAL_VALIDATION_BLOCKED_BY_COMPATIBILITY")
        self.assertEqual(E.verdict(False, False, True), "EXTERNAL_TARGET_NOT_REPRODUCIBLE")

    def test_structural(self):
        from collections import namedtuple
        Check = namedtuple("Check", "rule status location")
        V = namedtuple("V", "value")
        Loc = namedtuple("Loc", "file")
        checks = [Check("VC_PRECONDITION", V("proved"), Loc("a.adb")),
                  Check("VC_ASSERT", V("unproved"), Loc("b.adb")),
                  Check("VC_LOOP_INVARIANT_INIT", V("justified"), Loc("a.adb"))]
        m = E.structural(checks)
        self.assertEqual((m["sarif_checks"], m["source_units"], m["invariant"]), (3, 2, 1))
        self.assertEqual(m["statuses"], {"justified": 1, "proved": 1, "unproved": 1})

    def test_disabled_is_not_zero(self):
        report = {"analysis": {"rules": {"SRD001": {"evaluated": True},
                    "SRD002": {"evaluated": False, "reason": "missing ali"}}},
                  "summary": {"by_code": {"SRD001": 0, "SRD002": 0}}}
        self.assertIsNone(E.diagnostics_metrics(report)["SRD002"]["count"])
        self.assertEqual(E.diagnostics_metrics(report)["SRD001"]["count"], 0)
        report["analysis"]["semantic"] = {"evaluated": False, "reason": "no diagnostic"}
        self.assertFalse(E.semantic_metrics(report)["evaluated"])
        self.assertIsNone(E.group_metrics(report))
        report["analysis"]["semantic"]["srd002_groups"] = {
            "client_failure_count": 3, "group_count": 1,
            "grouped_check_count": 2, "ungrouped_check_count": 1}
        self.assertEqual(E.group_metrics(report)["group_count"], 1)

    def test_probe_and_estimate(self):
        check = {"rule": "VC_PRECONDITION", "resolution": "exact",
                 "callee": {"declaration": {"file": "x"}},
                 "precondition": {"explicit": True,
                                  "conjuncts": [{"text": "A"}, {"text": "B"}]}}
        self.assertTrue(E.probe_eligible(check))
        self.assertEqual(E.estimate(4, 2), {
            "naive_occurrence_prefix_observations": 8,
            "unique_callee_prefix_programs": 2, "additional_prefix_runs": 1})
        check["resolution"] = "ambiguous"
        self.assertFalse(E.probe_eligible(check))

    def test_canonical_and_hash(self):
        self.assertEqual(E.canonical({"z": 1, "a": 2}), '{\n  "a": 2,\n  "z": 1\n}\n')
        with self.assertRaises(ValueError):
            E.canonical({"path": "/home/user/file"})
        with self.assertRaises(ValueError):
            E.canonical({"message": "proof prose"})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.spark"
            p.write_bytes(b"abc")
            self.assertEqual(E.sha256(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            self.assertEqual(E.inventory(Path(d), ".spark")["count"], 1)

    def test_dirty_tree_rejected_and_no_mutation_helpers(self):
        with patch.object(E.subprocess, "check_output", side_effect=[b"sha\n", b" M source.ads\n"]):
            with self.assertRaises(ValueError):
                E.clean_identity(Path("/tmp/external"), "sha")
        import ast
        tree = ast.parse(SCRIPT.read_text())
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertFalse(names & {"edit_source", "patch_source", "run_proof", "ablate"})

    def test_committed_evidence_is_deterministic_and_path_free(self):
        repo = SCRIPT.parents[2]
        evidence = repo / "docs/evidence/task015-external-validation.json"
        import json
        saved = evidence.read_text()
        self.assertEqual(E.canonical(json.loads(saved)), saved)
        self.assertNotIn(str(repo), saved)


if __name__ == "__main__":
    unittest.main()