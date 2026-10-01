"""Synthetic Task 016 dependency authority and conservative matching tests."""
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401

from spark_refine_diagnostics import analyze_path_report
from spark_refine_diagnostics.loader import load_run
from spark_refine_diagnostics.ali import load_ali_deps


def result(rule, entity, line=1, col=1, kind='pass'):
    return {'ruleId': rule, 'kind': kind, 'level': 'none',
            'message': {'text': 'opaque'}, 'locations': [{
                'physicalLocation': {'artifactLocation': {'uri': 'p.ads'},
                                     'region': {'startLine': line, 'startColumn': col}},
                'logicalLocations': [{'name': entity}]}]}


def fixture(root, extra=True):
    checks = [result('VC_POSTCONDITION', 'Impl.X'),
              result('VC_PRECONDITION', 'Client.X', kind='fail')]
    if extra:
        checks.append(result('SUBPROGRAM_TERMINATION', 'Sml.Never'))
    (root/'gnatprove.sarif').write_text(json.dumps({'version': '2.1.0', 'runs': [{
        'tool': {'driver': {'name': 'GNATProve', 'version': 'FSF 16.1.0'}},
        'results': checks}]}))
    for unit, rule, entity, severity in [('impl', 'VC_POSTCONDITION', 'Impl.X', 'info'),
                                         ('client', 'VC_PRECONDITION', 'Client.X', 'high')]:
        (root/f'{unit}.spark').write_text(json.dumps({
            'stop_reason': 'STOP_REASON_NONE', 'entities': {'1': {'name': entity}},
            'proof': [{'rule': rule, 'severity': severity, 'file': 'p.ads',
                       'line': 1, 'col': 1, 'entity': 1}], 'flow': []}))
    (root/'impl.ali').write_text('V "GNAT Lib v16"\nU impl%s impl.ads\n')
    (root/'client.ali').write_text('V "GNAT Lib v16"\nU client%s client.ads\nW impl%s impl.ads impl.ali\n')


class AuthorityTests(unittest.TestCase):
    def test_fallback_does_not_disable_dependency_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fixture(d)
            run = load_run(d)
            self.assertEqual(run.unit_names(), ['client', 'impl', 'sml'])
            self.assertEqual(run.dependency_unit_names(), ['client', 'impl'])
            self.assertEqual(run.disputed_units, {'sml'})
            self.assertEqual(len(run.consistency_issues), 1)
            self.assertTrue(next(c for c in run.checks if c.entity == 'Sml.Never').disputed)
            rep = analyze_path_report(d)
            self.assertEqual(rep.analysis['rules']['SRD002']['ali_status'], 'ok')
            self.assertTrue(rep.analysis['rules']['SRD002']['evaluated'])
            self.assertEqual([x.code for x in rep.diagnostics], ['SRD002'])

    def test_real_ali_failures_remain_unavailable(self):
        for mode in ('missing', 'malformed', 'unsupported'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                fixture(d)
                f = d/'impl.ali'
                if mode == 'missing':
                    f.unlink()
                elif mode == 'malformed':
                    f.write_text('V "GNAT Lib v16"\nU impl%s impl.ads\nW broken\n')
                else:
                    f.write_text('V "GNAT Lib v17"\nU impl%s impl.ads\n')
                rep = analyze_path_report(d)
                self.assertFalse(rep.analysis['rules']['SRD002']['evaluated'])
                self.assertEqual(rep.analysis['rules']['SRD002']['ali_status'], 'unavailable')

    def test_no_spark_and_explicit_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fixture(d, False)
            for f in d.glob('*.spark'):
                f.unlink()
            run = load_run(d)
            self.assertEqual(run.dependency_unit_names(), run.unit_names())
            (d/'impl.ali').unlink()
            self.assertFalse(analyze_path_report(d).analysis['rules']['SRD002']['evaluated'])
            self.assertTrue(analyze_path_report(d, client_units=['client']).analysis['rules']['SRD002']['evaluated'])

    def test_unexplained_and_location_mismatches_remain_disputed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fixture(d)
            self.assertEqual(len(load_run(d).consistency_issues), 1)
            data = json.loads((d/'gnatprove.sarif').read_text())
            data['runs'][0]['results'][0]['locations'][0]['physicalLocation']['region']['startColumn'] = 2
            (d/'gnatprove.sarif').write_text(json.dumps(data))
            self.assertEqual(len(load_run(d).consistency_issues), 2)
            data['runs'][0]['results'][0]['locations'][0]['logicalLocations'][0]['name'] = 'Impl.Other'
            (d/'gnatprove.sarif').write_text(json.dumps(data))
            self.assertEqual(len(load_run(d).consistency_issues), 2)

    def test_exact_duplicate_cardinality_status_and_unreported_unproved(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fixture(d, False)
            self.assertEqual(load_run(d).consistency_issues, [])
            sarif = json.loads((d/'gnatprove.sarif').read_text())
            sarif['runs'][0]['results'].append(sarif['runs'][0]['results'][0].copy())
            (d/'gnatprove.sarif').write_text(json.dumps(sarif))
            self.assertEqual(len(load_run(d).consistency_issues), 1)
            sarif['runs'][0]['results'].pop()
            sarif['runs'][0]['results'][0]['kind'] = 'fail'
            (d/'gnatprove.sarif').write_text(json.dumps(sarif))
            self.assertTrue(any('status disagreement' in s for s in load_run(d).consistency_issues))
            sarif['runs'][0]['results'].pop(1)
            (d/'gnatprove.sarif').write_text(json.dumps(sarif))
            self.assertTrue(any('.spark unproved entry without SARIF' in s
                                for s in load_run(d).consistency_issues))


if __name__ == '__main__':
    unittest.main()