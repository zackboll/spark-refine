"""Pure checks of Task 016's research-only normalization decisions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from artifact_compatibility_investigation import investigate
from test_artifact_compatibility import fixture
import tempfile


class InvestigationTests(unittest.TestCase):
    def test_fallback_and_near_match_are_structural(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            x = investigate(root)
            self.assertEqual(x['sets']['fallback_only_units'], ['sml'])
            self.assertEqual(x['sets']['missing_requested_ali_units'], ['sml'])
            self.assertEqual(x['authority_probe']['status'], 'ok')
            self.assertEqual(x['mismatches'][0]['taxonomy'], 'unexplained')


if __name__ == '__main__':
    unittest.main()