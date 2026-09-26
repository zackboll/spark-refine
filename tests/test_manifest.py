import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/ring_buffer/spark-refine.toml"


class ManifestFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_format_version(self):
        self.assertEqual(self.data["format_version"], 1)

    def test_first_pattern_is_circular_sequence(self):
        self.assertEqual(self.data["refinement"][0]["pattern"], "circular_sequence")

    def test_required_roles_exist(self):
        rep = self.data["refinement"][0]["representation"]
        for key in ("storage", "first", "length", "capacity", "index_origin"):
            self.assertIn(key, rep)

    def test_default_backend_is_derived_in_fixture(self):
        gen = self.data["refinement"][0]["generation"]
        self.assertEqual(gen["backend"], "derived")


if __name__ == "__main__":
    unittest.main()
