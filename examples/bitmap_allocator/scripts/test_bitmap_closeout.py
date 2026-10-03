"""Pure closeout regressions: no Git history, network, logs or toolchain."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import closeout_bitmap_experiment as closeout


class CloseoutTests(unittest.TestCase):
    def test_recorded_candidate(self):
        data = closeout.build()
        self.assertEqual(data["counts"]["R"], 56)
        self.assertEqual(data["economics"]["decision"], "DO_NOT_ADOPT_BITMAP_PATTERN")
        self.assertTrue(data["economics"]["R_gt_20"])
        self.assertTrue(data["economics"]["reduction_lt_30_percent"])
        self.assertEqual(data["economics"]["reduction"]["displayed_percentage"], "-3.703704%")

    def test_size_independent(self):
        result = closeout.economics(100, 21)
        self.assertTrue(result["R_gt_20"])
        self.assertFalse(result["reduction_lt_30_percent"])
        self.assertEqual(result["decision"], "DO_NOT_ADOPT_BITMAP_PATTERN")

    def test_reduction_independent(self):
        result = closeout.economics(20, 15)
        self.assertFalse(result["R_gt_20"])
        self.assertTrue(result["reduction_lt_30_percent"])
        self.assertEqual(result["decision"], "DO_NOT_ADOPT_BITMAP_PATTERN")

    def test_acceptable_not_auto_adopted(self):
        result = closeout.economics(54, 10)
        self.assertFalse(result["R_gt_20"])
        self.assertFalse(result["reduction_lt_30_percent"])
        self.assertEqual(result["decision"], "ADOPTION_NOT_ESTABLISHED")
        self.assertIsNone(result["independent_validation"])

    def test_missing_unknown(self):
        result = closeout.economics(None, None)
        self.assertEqual(result["decision"], "UNKNOWN")
        self.assertIsNone(result["support_saved"])
        self.assertIsNone(result["R_gt_20"])
        self.assertIsNone(result["reduction_lt_30_percent"])

    def test_inconsistent_totals(self):
        snapshot = json.loads((closeout.ROOT / closeout.BASE / "evidence/library_minimization.json").read_text())
        for field in ("totals", "residual", "R", "L"):
            changed = copy.deepcopy(snapshot)
            if field == "totals":
                changed["current"]["totals"]["production"] += 1
            elif field == "residual":
                changed["residual_breakdown"]["raw_snapshots"] += 1
            else:
                changed[{"R": "R_final_for_this_continuation", "L": "L_current"}[field]] += 1
            with self.subTest(field=field), self.assertRaises(closeout.VerificationError):
                closeout.verify_totals(changed)

    def test_changed_input_and_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in closeout.INPUT_HASHES:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((closeout.ROOT / path).read_bytes())
            snapshot = json.loads((root / closeout.BASE / "evidence/library_minimization.json").read_text())
            manual = json.loads((root / closeout.BASE / "evidence/manual_inventory.json").read_text())
            paths = set(snapshot["current"]["files"]) | set(snapshot["candidate_configuration_sha256"])
            paths.update(closeout.BASE + p for p in manual["source_sha256"])
            for path in paths:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((closeout.ROOT / path).read_bytes())
            closeout.build(root)
            for path in sorted(set(closeout.INPUT_HASHES) | paths):
                original = (root / path).read_bytes()
                (root / path).write_bytes(original + b"\n")
                with self.subTest(path=path), self.assertRaises(closeout.VerificationError):
                    closeout.build(root)
                (root / path).write_bytes(original)

    def test_deterministic_serialization(self):
        self.assertEqual(closeout.serialize(closeout.build()), closeout.serialize(closeout.build()))

    def test_check_read_only(self):
        paths = set(closeout.INPUT_HASHES) | {closeout.OUTPUT}
        paths.update(closeout.build()["measured_source_sha256"])
        before = {p: ((closeout.ROOT / p).read_bytes(), (closeout.ROOT / p).stat().st_mtime_ns) for p in paths}
        subprocess.run([sys.executable, str(Path(closeout.__file__)), "--check"], check=True, capture_output=True)
        after = {p: ((closeout.ROOT / p).read_bytes(), (closeout.ROOT / p).stat().st_mtime_ns) for p in paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()