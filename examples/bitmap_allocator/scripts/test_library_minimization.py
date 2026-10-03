"""Candidate inventory and canonical evidence regression tests."""
import json
from pathlib import Path
import subprocess
import unittest

EX = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def test_regeneration(self):
        files = [EX / "evidence/library_minimization.json", EX / "LIBRARY_METRICS.md"]
        before = [p.read_bytes() for p in files]
        for _ in range(2):
            subprocess.run(["python3", str(EX / "scripts/library_minimization.py")], check=True,
                           capture_output=True)
            self.assertEqual(before, [p.read_bytes() for p in files])

    def test_accounting(self):
        data = json.loads((EX / "evidence/library_minimization.json").read_text())
        self.assertEqual(sum(data["residual_breakdown"].values()), data["R_final_for_this_continuation"])
        self.assertEqual(data["support_saved"], 54-data["R_final_for_this_continuation"])
        for section in ("start", "current"):
            for file in data[section]["files"].values():
                lines = [row["line"] for row in file["lines"]]
                self.assertEqual(len(lines), len(set(lines)))


if __name__ == "__main__":
    unittest.main()