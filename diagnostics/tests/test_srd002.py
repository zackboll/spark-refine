"""SRD002 (client-only proof gap; public abstraction may be insufficient)
on real GNATprove fixtures."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import support
from spark_refine_diagnostics import (analyze_path_report, analyze_run,
                                      analyze_run_report, srd002)
from spark_refine_diagnostics.ali import AliDeps, load_ali_deps
from spark_refine_diagnostics.model import Confidence

L, M = Confidence.LOW, Confidence.MEDIUM

# known abstraction-gap ablations: entity -> expected confidence
# (medium: VC_PRECONDITION only; low: any VC_ASSERT, lowest applies)
POSITIVES = {
    "ring_no_public_model_bound": {"Ring_Buffer_Client_Proof.Rotate": M},
    "ring_no_is_empty_post": {"Ring_Buffer_Client_Proof.Push_Push_Pop": L,
                              "Ring_Buffer_Client_Proof.Rotate": M},
    "ring_no_is_full_post": {"Ring_Buffer_Client_Proof.Push_Push_Pop": L,
                             "Ring_Buffer_Client_Proof.Rotate": M},
    "pool_spec_no_count_posts": {
        "Fixed_Pool_Client_Proof.Release_Then_Allocate": M,
        "Fixed_Pool_Client_Proof.Two_Allocations_Then_Release": L},
}
# client-only gap whose cause is a FALSE client assertion, not a contract
FALSE_CLIENT = "pool_false_client_assert"
FALSE_CLIENT_ENTITY = "Fixed_Pool_False_Client.Initialize_Then_Claim_Empty"
NEGATIVE_CONTROLS = {
    "ring_n1": "implementation-local postcondition failure",
    "ring_n2": "range check inside production code",
    "ring_b1": "representation invariant failure",
    "ring_ctl_post_and_client": "implementation postcondition + client",
    "ring_ctl_range_and_client": "production range check + client",
    "ring_ctl_invariant_and_client": "representation invariant + client",
}
OVERCLAIMS = ("contract is insufficient", "is missing", "is insufficient",
              "abstraction gap", "contract gap", "the public contract does "
              "not expose")


def srd002_of(name):
    return support.by_code(support.analyzed(name)[1], "SRD002")


def text_of(d):
    return " ".join((d.title, d.explanation, d.recommendation,
                     *d.evidence)).lower()


class Srd002Positive(unittest.TestCase):
    def test_fires_on_task_001_and_003_ablations(self):
        for name, entities in POSITIVES.items():
            with self.subTest(fixture=name):
                diags = srd002_of(name)
                self.assertEqual({d.entity: d.confidence for d in diags},
                                 entities)
                for d in diags:
                    self.assertTrue(dict(d.data)["client_unit"]
                                    .endswith("_client_proof"))
                    fails = [r for r in d.related
                             if r.role == "client failure"]
                    self.assertTrue(fails)
                    self.assertTrue(all(
                        r.rule in ("VC_PRECONDITION", "VC_ASSERT")
                        and r.status == "unproved" and r.entity == d.entity
                        for r in fails))
                    self.assertEqual(d.primary_location, fails[0].location)
                    self.assertIn("unit dependencies from: ali", d.evidence)
                    self.assertEqual(dict(d.data)["implementation_failures"],
                                     0)

    def test_client_postcondition_failures_are_context_only(self):
        diags = {d.entity: d for d in srd002_of("pool_spec_no_count_posts")}
        d = diags["Fixed_Pool_Client_Proof.Release_Then_Allocate"]
        self.assertEqual([r.rule for r in d.related
                          if r.role == "client context"],
                         ["VC_POSTCONDITION"])
        # Round_Trip fails only its own postcondition: no SRD002 for it
        self.assertNotIn("Fixed_Pool_Client_Proof.Round_Trip", diags)

    def test_message_text_is_not_required(self):
        for name, entities in POSITIVES.items():
            run = support.run_of(name)
            blank = replace(run, checks=[replace(c, message="")
                                         for c in run.checks])
            ali = load_ali_deps(support.fixture(name), run.unit_names())
            diags, _ = analyze_run(blank, ali)
            self.assertEqual({d.entity: d.confidence for d in diags
                              if d.code == "SRD002"}, entities, name)

    def test_title_and_wording(self):
        for name in [*POSITIVES, FALSE_CLIENT]:
            for d in srd002_of(name):
                self.assertEqual(d.title, "Client-only proof gap; public "
                                 "abstraction may be insufficient")
                text = text_of(d)
                self.assertIn("client-only proof gap", text)
                for cause in srd002.POSSIBLE_CAUSES:
                    self.assertIn(cause, text)
                for bad in OVERCLAIMS:
                    self.assertNotIn(bad, text, (name, d.entity))


class Srd002Confidence(unittest.TestCase):
    def test_precondition_only_is_medium(self):
        d = srd002_of("ring_no_public_model_bound")[0]
        self.assertEqual(dict(d.data)["client_rules"], ("VC_PRECONDITION",))
        self.assertEqual(d.confidence, Confidence.MEDIUM)
        self.assertIn("called operation's precondition", d.explanation)

    def test_assertion_only_is_low(self):
        d = {d.entity: d for d in srd002_of("pool_spec_no_count_posts")}[
            "Fixed_Pool_Client_Proof.Two_Allocations_Then_Release"]
        self.assertEqual(dict(d.data)["client_rules"], ("VC_ASSERT",))
        self.assertEqual(d.confidence, Confidence.LOW)
        self.assertIn("may be too strong or false", d.explanation)

    def test_mixed_rules_take_the_lowest(self):
        d = {d.entity: d for d in srd002_of("ring_no_is_empty_post")}[
            "Ring_Buffer_Client_Proof.Push_Push_Pop"]
        self.assertEqual(dict(d.data)["client_rules"],
                         ("VC_ASSERT", "VC_PRECONDITION"))
        self.assertEqual(d.confidence, Confidence.LOW)


class Srd002FalseClientControl(unittest.TestCase):
    """A real GNATprove 16.1.0 run: the fully proved Task 003 pool plus a
    client asserting Free_Count (P) = 0 right after Initialize. The
    assertion is false; no contract is insufficient."""

    def test_implementation_is_fully_proved(self):
        run = support.run_of(FALSE_CLIENT)
        self.assertEqual([(c.rule, c.entity, c.unit) for c in run.unproved],
                         [("VC_ASSERT", FALSE_CLIENT_ENTITY,
                           "fixed_pool_false_client")])
        self.assertFalse(any(c.unit == "fixed_pool" and not c.proved
                             for c in run.checks))

    def test_srd002_fires_low_without_claiming_a_contract_defect(self):
        _, diags, notes = support.analyzed(FALSE_CLIENT)
        self.assertEqual(notes, [])
        self.assertEqual([(d.code, d.entity) for d in diags],
                         [("SRD002", FALSE_CLIENT_ENTITY)])
        d = diags[0]
        self.assertEqual(d.confidence, Confidence.LOW)
        self.assertEqual(dict(d.data)["implementation_units"],
                         ("fixed_pool",))
        self.assertIn("may simply be too strong or false", text_of(d))


class Srd002NegativeControls(unittest.TestCase):
    def test_no_srd002(self):
        for name, why in NEGATIVE_CONTROLS.items():
            with self.subTest(fixture=name, control=why):
                self.assertEqual(srd002_of(name), [])

    def test_mixed_controls_really_contain_a_client_failure(self):
        # otherwise those controls would pass trivially
        for name in NEGATIVE_CONTROLS:
            if not name.startswith("ring_ctl_"):
                continue
            run = support.run_of(name)
            client = [c for c in run.unproved
                      if c.unit == "ring_buffer_client_proof"
                      and c.rule in ("VC_PRECONDITION", "VC_ASSERT")]
            impl = [c for c in run.unproved if c.unit == "ring_buffer"]
            self.assertTrue(client and impl, name)


class Srd002UnitGraph(unittest.TestCase):
    def test_without_dependency_information_not_evaluated(self):
        run = support.run_of("ring_no_public_model_bound")
        diags, notes = analyze_run(run, ali=None)
        self.assertEqual(diags, [])
        self.assertTrue(any("SRD002 not evaluated: client dependency "
                            "information unavailable" in n for n in notes))

    # client -> ring_buffer_runtime_tests (analysed, 0 checks) -> ring_buffer:
    # the implementation is reachable only transitively
    CHAIN = {"ring_buffer_client_proof": {"ring_buffer_runtime_tests"},
             "ring_buffer_runtime_tests": {"ring_buffer"},
             "ring_buffer": set()}

    def test_dependency_closure_is_transitive(self):
        run = support.run_of("ring_no_public_model_bound")
        graph = srd002.build_unit_graph(run, AliDeps("ok", dict(self.CHAIN)))
        self.assertEqual(graph.deps["ring_buffer_client_proof"],
                         {"ring_buffer_runtime_tests", "ring_buffer"})
        self.assertEqual([d.entity for d in srd002.check(run, graph)],
                         ["Ring_Buffer_Client_Proof.Rotate"])

    def test_implementation_failure_in_transitive_closure_blocks(self):
        """An unproved check in `ring_buffer`, reached only transitively,
        still blocks SRD002 for the client."""
        run = support.run_of("ring_ctl_post_and_client")
        graph = srd002.build_unit_graph(run, AliDeps("ok", dict(self.CHAIN)))
        self.assertIn("ring_buffer", graph.deps["ring_buffer_client_proof"])
        self.assertEqual(srd002.check(run, graph), [])

    def test_explicit_client_unit(self):
        run = support.run_of("ring_no_public_model_bound")
        diags, _ = analyze_run(run, None, ["ring_buffer_client_proof"])
        self.assertEqual([d.entity for d in diags],
                         ["Ring_Buffer_Client_Proof.Rotate"])
        # the runtime-test unit (SPARK_Mode Off, 0 checks) is ignored ...
        self.assertEqual(len([c for c in run.checks
                              if c.unit == "ring_buffer_runtime_tests"]), 0)
        # ... and declaring the package as client finds no green dependency
        # (the client proof has failures): no diagnostic
        graph = srd002.build_unit_graph(run, None, ["ring_buffer"])
        self.assertEqual(srd002.check(run, graph), [])

    def test_no_dependency_with_checks_means_no_diagnostic(self):
        run = support.run_of("ring_no_public_model_bound")
        graph = srd002.UnitGraph(
            deps={"ring_buffer_client_proof": {"ring_buffer_runtime_tests"}},
            source="explicit")
        self.assertEqual(srd002.check(run, graph), [])

    def test_ali_graph_restricted_to_analysed_units(self):
        name = "pool_spec_no_count_posts"
        g = srd002.build_unit_graph(support.run_of(name),
                                    load_ali_deps(support.fixture(name)))
        self.assertEqual(g.source, "ali")
        self.assertEqual(g.deps["fixed_pool_client_proof"], {"fixed_pool"})
        self.assertEqual(g.deps["fixed_pool"], set())


def _copy_fixture(name: str, tmp: str) -> Path:
    dest = Path(tmp) / name
    shutil.copytree(support.fixture(name), dest)
    return dest


class Srd002AliDegradation(unittest.TestCase):
    """SRD002 is skipped -- never guessed, never an error -- when the ALI
    dependency data cannot be obtained; SRD001 still works."""

    CASES = {
        "missing": lambda p: p.unlink(),
        "empty": lambda p: p.write_text("", "utf-8"),
        "truncated": lambda p: p.write_text(
            p.read_text("utf-8").split("\nW ", 1)[0] + "\nW ", "utf-8"),
        "malformed": lambda p: p.write_text(
            p.read_text("utf-8") + "W not-a-unit-ref\n", "utf-8"),
        "no dependency info": lambda p: p.write_text(
            'V "GNAT Lib v16"\n', "utf-8"),
    }

    def test_srd002_skipped_analysis_succeeds(self):
        name = "pool_spec_no_count_posts"
        for case, damage in self.CASES.items():
            with self.subTest(case=case), \
                    tempfile.TemporaryDirectory() as tmp:
                d = _copy_fixture(name, tmp)
                damage(d / "fixed_pool_client_proof.ali")
                rep = analyze_path_report(d, name=name)
                self.assertEqual(rep.diagnostics, [])
                self.assertFalse(rep.analysis["rules"]["SRD002"]
                                 ["evaluated"])
                self.assertEqual(rep.analysis["rules"]["SRD002"]
                                 ["ali_status"], "unavailable")
                self.assertTrue(any(n.startswith(
                    "SRD002 not evaluated: client dependency information "
                    "unavailable") for n in rep.notes), rep.notes)
                # proof results are untouched by an ALI problem
                self.assertEqual(rep.runs[0].summary(),
                                 support.run_of(name).summary())

    def test_srd001_still_works_without_ali(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _copy_fixture("pool_p5", tmp)
            for p in d.glob("*.ali"):
                p.unlink()
            rep = analyze_path_report(d, name="pool_p5")
        self.assertEqual([(x.code, x.entity) for x in rep.diagnostics],
                         [("SRD001", "Fixed_Pool.Release")])
        self.assertFalse(rep.analysis["rules"]["SRD002"]["evaluated"])

    def test_cli_exits_successfully(self):
        import io
        from contextlib import redirect_stdout
        from spark_refine_diagnostics.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            d = _copy_fixture("ring_no_public_model_bound", tmp)
            (d / "ring_buffer.ali").write_text("garbage\x00", "utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["analyze", str(d), "--fail-on", "SRD002"])
        self.assertEqual(rc, 0)
        self.assertIn("SRD002 not evaluated", buf.getvalue())
        self.assertIn("ring_buffer.ali: no_version", buf.getvalue())

    def test_no_filename_based_fallback(self):
        # an explicit empty-but-"ok" ALI set lacking the analysed units must
        # not be completed by guessing dependencies from unit names
        run = support.run_of("ring_no_public_model_bound")
        graph = srd002.build_unit_graph(run, AliDeps(status="ok", deps={}))
        self.assertEqual(graph.source, "none")
        self.assertIn("no .ali file for analysed unit", graph.reason)


class Srd002DisputedStatus(unittest.TestCase):
    def test_disputed_implementation_blocks_and_is_reported(self):
        run = support.run_of("pool_spec_no_count_posts")
        disputed = replace(run, disputed_units={"fixed_pool"})
        ali = load_ali_deps(support.fixture("pool_spec_no_count_posts"),
                            run.unit_names())
        rep = analyze_run_report(disputed, ali)
        self.assertEqual(support.by_code(rep.diagnostics, "SRD002"), [])
        self.assertTrue(any("SRD002 not emitted for client "
                            "fixed_pool_client_proof: SARIF/.spark disagree"
                            in n for n in rep.notes))


if __name__ == "__main__":
    unittest.main()
