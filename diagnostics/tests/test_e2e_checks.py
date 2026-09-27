"""The fresh end-to-end gate's checkers (scripts/e2e_fresh.py), exercised
on the committed fixtures of the same three cases.

The fresh gate itself needs the pinned toolchain and runs in CI job
`diagnostics-e2e`. These tests need no toolchain: they check that the
gate's pass criteria accept the known-good reports (fixtures captured from
the same cases) and reject reports where the expected finding is absent.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from dataclasses import replace

import support
from spark_refine_diagnostics import analyze_path_report, compare_provers_report
from spark_refine_diagnostics.render import to_json

_spec = importlib.util.spec_from_file_location(
    "e2e_fresh", support.DIAGNOSTICS / "scripts" / "e2e_fresh.py")
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)


def report_json(rep) -> dict:
    return json.loads(to_json(rep.runs, rep.diagnostics, rep.notes,
                              rep.analysis))


def analyze(name: str) -> dict:
    return report_json(analyze_path_report(support.fixture(name), name=name))


def compare(prefix: str, provers=("cvc5", "z3", "altergo")) -> dict:
    runs = [replace(support.run_of(f"{prefix}_{p}"), name=p)
            for p in provers]
    return report_json(compare_provers_report(runs))


class E2ECheckersAcceptKnownGood(unittest.TestCase):
    def test_srd001_ring_b3(self):
        self.assertEqual(e2e.check_srd001(analyze("ring_b3")), [])

    def test_srd002_ring_no_is_full_post(self):
        self.assertEqual(e2e.check_srd002(analyze("ring_no_is_full_post")),
                         [])

    def test_srd003_library_backed_pool(self):
        self.assertEqual(e2e.check_srd003(compare("pool_lib_prover")), [])

    def test_srd003_two_runs_are_sufficient(self):
        self.assertEqual(e2e.check_srd003(
            compare("pool_lib_prover", ("z3", "altergo"))), [])


class E2ECheckersRejectBadReports(unittest.TestCase):
    def test_srd001_absent(self):
        # B5: functional fault, invariant intact -> no SRD001
        self.assertTrue(e2e.check_srd001(analyze("ring_b5")))

    def test_srd001_wrong_entity(self):
        # B4 fires SRD001 on Ring_Buffer.Push, not Ring_Buffer.Pop
        self.assertTrue(e2e.check_srd001(analyze("ring_b4")))

    def test_srd002_absent(self):
        # implementation failure + client failure: SRD002 silent
        self.assertTrue(e2e.check_srd002(
            analyze("ring_ctl_post_and_client")))

    def test_srd002_requires_ali_dependency_source(self):
        rep = analyze("ring_no_is_full_post")
        rep["analysis"]["rules"]["SRD002"]["dependency_source"] = "explicit"
        for d in rep["diagnostics"]:
            d["data"]["dependency_source"] = "explicit"
        self.assertTrue(e2e.check_srd002(rep))

    def test_srd003_absent(self):
        # ring buffer A proves with every prover alone: no SRD003
        self.assertTrue(e2e.check_srd003(compare("ring_prover")))

    def test_wrong_toolchain_is_rejected(self):
        rep = analyze("ring_b3")
        rep["runs"][0]["gnatprove"] = "FSF 17.0.0"
        self.assertTrue(e2e.check_srd001(rep))


def with_orchestration(name: str, command: list[str], exit_code: int,
                       path: str, stale: list[str]) -> dict:
    """A fixture report as `prove` would emit it (Task 008 E2E-D/E)."""
    rep = analyze(name)
    rep["analysis"]["orchestration"] = {
        "command": command, "gnatprove_exit_code": exit_code,
        "result_path": path, "result_selection": "fresh_discovery",
        "fresh": True, "stale_result_sets_ignored": stale}
    return rep


def prove_positive_report(**changes) -> dict:
    rep = with_orchestration(
        "ring_positive", ["gnatprove", "-P", "ring_buffer.gpr", "-j0"], 0,
        e2e.PROVE_BASELINE_PATH, [e2e.PROVE_DECOY, "obj/other/gnatprove"])
    rep["analysis"]["orchestration"].update(changes)
    return rep


def prove_negative_report() -> dict:
    return with_orchestration(
        "ring_b3", ["gnatprove", "-P", "ring_buffer.gpr", "-j0",
                    f"-XRING_BUFFER_SRC={e2e.PROVE_B3_SRC}",
                    f"-XRING_BUFFER_VARIANT={e2e.PROVE_B3_VARIANT}"],
        1, e2e.PROVE_B3_PATH, [e2e.PROVE_DECOY])


class E2EProveCheckers(unittest.TestCase):
    """E2E-D / E2E-E pass criteria on fixture-derived reports."""

    def test_positive_accepts_known_good(self):
        self.assertEqual(e2e.check_prove_positive(prove_positive_report()),
                         [])

    def test_negative_accepts_known_good(self):
        self.assertEqual(e2e.check_prove_negative(prove_negative_report()),
                         [])

    def test_positive_rejects_wrong_selection(self):
        for change in ({"result_path": e2e.PROVE_DECOY},
                       {"result_selection": "explicit"},
                       {"fresh": False},
                       {"gnatprove_exit_code": 1},
                       {"command": ["gnatprove", "-P", "other.gpr"]},
                       {"stale_result_sets_ignored": []}):
            with self.subTest(change=change):
                self.assertTrue(e2e.check_prove_positive(
                    prove_positive_report(**change)))

    def test_positive_rejects_missing_orchestration(self):
        self.assertTrue(e2e.check_prove_positive(analyze("ring_positive")))

    def test_positive_rejects_unproved_run(self):
        rep = with_orchestration(
            "ring_n1", ["gnatprove", "-P", "ring_buffer.gpr", "-j0"], 0,
            e2e.PROVE_BASELINE_PATH, [e2e.PROVE_DECOY])
        self.assertTrue(e2e.check_prove_positive(rep))

    def test_negative_rejects_zero_exit(self):
        rep = prove_negative_report()
        rep["analysis"]["orchestration"]["gnatprove_exit_code"] = 0
        self.assertTrue(e2e.check_prove_negative(rep))


if __name__ == "__main__":
    unittest.main()
