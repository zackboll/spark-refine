"""Task 011: fail-safe text rendering of semantic enrichment.

Pure tests: no Libadalang. Malformed internal Task 009 semantic objects
are built directly and rendered through the FULL report renderer
(to_text), not only through the per-check helper. For every case:
rendering completes, no exception escapes, the entry is shown as
incomplete, and no call/callee/Pre/conjunct/assertion fact is invented.
Valid entries render exactly as before (golden lines), JSON keeps the raw
semantic object, and grouping and rendering share one structural
contract (semantic_shape.py)."""

from __future__ import annotations

import ast
import copy
import json
import unittest
from dataclasses import replace

import support
from spark_refine_diagnostics.model import Confidence
from spark_refine_diagnostics.render import (INCOMPLETE_ASSERTION,
                                             INCOMPLETE_PRECONDITION,
                                             diagnostic_to_dict,
                                             diagnostic_to_text,
                                             semantic_text, to_json, to_text)
from spark_refine_diagnostics.semantic_groups import build_srd002_groups
from spark_refine_diagnostics.semantic_shape import (
    exact_assertion_complete, exact_precondition_complete)
from test_semantic_groups import (MALFORMED_EXACT, MALFORMED_IMPLICIT,
                                  NO_PRE, PUSH_PRE, _drop, _set, diag,
                                  pre_check, span)

PKG = support.DIAGNOSTICS / "spark_refine_diagnostics"
FILE = "ring_buffer_client_proof.adb"
INCOMPLETE = "semantic entry: incomplete"

# Facts of a complete precondition entry (pre_check defaults). None of
# them may appear anywhere in the report once the entry is malformed.
PRE_FACTS = ("Push (Q, A)", "Ring_Buffer.Push", "not Is_Full (B)",
             "src/ring_buffer.ads")
PRE_LINES = ("      call:", "      callee:", "      public Pre:",
             "      failed conjunct:", "        [0]")

ASSERT_TEXT = "Free_Count (P) = 0"
ASSERT_SUBP = "Fixed_Pool_False_Client.Claim_Empty"
ASSERT_FACTS = (ASSERT_TEXT, ASSERT_SUBP, "src/" + FILE)
ASSERT_LINES = ("      assertion:", "      in:")


def assertion_check(line=16, col=43, enclosing=ASSERT_SUBP):
    return {"rule": "VC_ASSERT",
            "location": {"file": FILE, "line": line, "column": col},
            "resolution": "exact",
            "assertion": {"pragma": "Assert", "text": ASSERT_TEXT,
                          "location": span("src/" + FILE, line, col,
                                           line, col + 18)},
            "enclosing_subprogram": enclosing}


def report_text(diags, groups=True) -> str:
    """The full CLI text report (semantic metadata, Task 010 triage
    section built by the real grouping code, every diagnostic).

    groups=False omits the triage section: used only for a malformed
    semantic ENVELOPE (non-dict block, non-list checks, non-dict check),
    which semantic.py never produces (it builds the envelope itself) and
    which Task 010 grouping -- deliberately unchanged by Task 011 -- does
    not accept."""
    diags = list(diags)
    meta = {"requested": True, "evaluated": True, "backend": "libadalang",
            "version": "26.0.0", "project": "p.gpr",
            "resolutions": {"exact": 1}}
    if groups:
        meta["srd002_groups"] = build_srd002_groups(diags)
    return to_text([], diags, [], {"semantic": meta})


def diagnostic_section(txt: str) -> str:
    """The per-diagnostic part of a report (after the triage section)."""
    return txt[txt.index("\nSRD002: "):]


# Task 011 brief, section 7: named precondition corruptions (the broader
# Task 010 MALFORMED_EXACT / MALFORMED_IMPLICIT lists are also run below).
MALFORMED_PRECONDITION = [
    ("missing call", _drop("call")),
    ("call = {}", _set("call", {})),
    ("call not a dict", _set("call", "Push (Q, A)")),
    ("call.text missing", _drop("call.text")),
    ("call.location missing", _drop("call.location")),
    ("callee missing", _drop("callee")),
    ("callee = {}", _set("callee", {})),
    ("callee not a dict", _set("callee", ["Ring_Buffer.Push"])),
    ("callee.name missing", _drop("callee.name")),
    ("callee.name not a string", _set("callee.name", 3)),
    ("declaration missing", _drop("callee.declaration")),
    ("declaration = {}", _set("callee.declaration", {})),
    ("precondition missing", _drop("precondition")),
    ("precondition None", _set("precondition", None)),
    ("precondition = {}", _set("precondition", {})),
    ("explicit missing", _drop("precondition.explicit")),
    ("text missing", _drop("precondition.text")),
    ("conjuncts missing", _drop("precondition.conjuncts")),
    ("conjuncts not a list", _set("precondition.conjuncts", "A")),
    ("conjunct None", _set("precondition.conjuncts.0", None)),
    ("attribution missing", _drop("precondition.attribution")),
]

MALFORMED_ASSERTION = [
    ("assertion missing", _drop("assertion")),
    ("assertion = {}", _set("assertion", {})),
    ("assertion not a dict", _set("assertion", ASSERT_TEXT)),
    ("assertion None", _set("assertion", None)),
    ("assertion.text missing", _drop("assertion.text")),
    ("assertion.text not a string", _set("assertion.text", 0)),
    ("assertion.location missing", _drop("assertion.location")),
    ("assertion.location None", _set("assertion.location", None)),
    ("assertion.location = {}", _set("assertion.location", {})),
    ("assertion.location.end_line missing",
     _drop("assertion.location.end_line")),
    ("assertion.pragma missing", _drop("assertion.pragma")),
    ("enclosing_subprogram not a string",
     _set("enclosing_subprogram", ["P", "Q"])),
    ("enclosing_subprogram empty", _set("enclosing_subprogram", "")),
]


class MotivatingCase(unittest.TestCase):
    """Task 010 discovery: an exact entry with `call = {}` raised
    KeyError in the per-diagnostic renderer."""

    def test_call_empty_full_report(self):
        bad = pre_check(10, 7)
        bad["call"] = {}
        diags = [diag("C.P", [pre_check(9, 7), bad])]
        txt = report_text(diags)          # must not raise
        sec = diagnostic_section(txt)
        self.assertIn("    ring_buffer_client_proof.adb:10:7 "
                      "VC_PRECONDITION: exact\n"
                      f"      {INCOMPLETE}\n"
                      f"      reason: {INCOMPLETE_PRECONDITION}\n", sec)
        # the valid sibling still renders its facts, the broken one none
        self.assertEqual(sec.count("      call: "), 1)
        self.assertEqual(sec.count("      callee: "), 1)
        self.assertEqual(sec.count("      failed conjunct: "), 1)
        # Task 010 grouping is independent and unchanged
        g = build_srd002_groups(diags)
        self.assertEqual((g["group_count"], g["grouped_check_count"],
                          [u["reason"] for u in g["ungrouped"]]),
                         (1, 1, ["semantic_incomplete"]))

    def test_minimal_raw_object(self):
        """The literal object from the Task 011 brief, on its own."""
        raw = {"resolution": "exact", "call": {}}
        lines = "\n".join(semantic_text({"backend": "libadalang",
                                         "checks": [raw]}))
        self.assertIn(INCOMPLETE, lines)
        for bad in ("call:", "callee:", "public Pre", "failed conjunct"):
            self.assertNotIn(bad, lines)
        d = diag("C.P", [pre_check(9, 7)])
        d.semantic["checks"][0] = raw
        self.assertIn(INCOMPLETE, diagnostic_to_text(d))
        self.assertIn(INCOMPLETE, report_text([d]))


class MalformedPrecondition(unittest.TestCase):
    CASES = (MALFORMED_PRECONDITION
             + [("task010: " + n, m) for n, m in MALFORMED_EXACT]
             + [("task010 implicit: " + n, m)
                for n, m in MALFORMED_IMPLICIT])

    def test_every_case_renders_incomplete_without_facts(self):
        for name, mutate in self.CASES:
            with self.subTest(case=name):
                bad = pre_check(10, 7, pre=NO_PRE if "implicit" in name
                                else PUSH_PRE)
                mutate(bad)
                self.assertFalse(exact_precondition_complete(bad))
                d = diag("C.P", [bad])
                full = report_text([d])
                for txt in (full, diagnostic_to_text(d),
                            "\n".join(semantic_text(d.semantic))):
                    self.assertIn(
                        f"      {INCOMPLETE}\n"
                        f"      reason: {INCOMPLETE_PRECONDITION}", txt)
                    for line in PRE_LINES:
                        self.assertNotIn(line, txt)
                for fact in PRE_FACTS:
                    self.assertNotIn(fact, full)
                self.assertTrue(full.endswith("summary: SRD002=1\n"))

    def test_complete_variants_are_not_incomplete(self):
        many = dict(PUSH_PRE, text="A and then B", conjuncts=[
            {"index": 0, "text": "A", "location": span("s.ads", 1, 1)},
            {"index": 1, "text": "B", "location": span("s.ads", 1, 9)}])
        for pre in (PUSH_PRE, dict(PUSH_PRE, conjuncts=[]), NO_PRE, many):
            with self.subTest(pre=pre.get("text")):
                txt = report_text([diag("C.P", [pre_check(9, 7, pre=pre)])])
                self.assertNotIn(INCOMPLETE, txt)
                self.assertIn("      callee: Ring_Buffer.Push", txt)



class MalformedAssertion(unittest.TestCase):
    def test_every_case_renders_incomplete_without_facts(self):
        for name, mutate in MALFORMED_ASSERTION:
            with self.subTest(case=name):
                bad = assertion_check()
                mutate(bad)
                self.assertFalse(exact_assertion_complete(bad))
                d = diag("C.P", [bad])
                full = report_text([d])
                for txt in (full, diagnostic_to_text(d)):
                    self.assertIn(
                        "    ring_buffer_client_proof.adb:16:43 "
                        "VC_ASSERT: exact\n"
                        f"      {INCOMPLETE}\n"
                        f"      reason: {INCOMPLETE_ASSERTION}", txt)
                    for line in ASSERT_LINES:
                        self.assertNotIn(line, txt)
                for fact in ASSERT_FACTS:
                    self.assertNotIn(fact, full)
                # grouping is unaffected: an assertion is never grouped
                self.assertEqual(
                    [u["reason"] for u in
                     build_srd002_groups([d])["ungrouped"]],
                    ["assertion_has_no_callee"])

    def test_no_enclosing_subprogram_is_complete(self):
        for enclosing in (None, "absent"):
            with self.subTest(enclosing=enclosing):
                c = assertion_check(enclosing=enclosing)
                if enclosing == "absent":
                    del c["enclosing_subprogram"]
                self.assertTrue(exact_assertion_complete(c))
                txt = "\n".join(semantic_text({"backend": "libadalang",
                                               "checks": [c]}))
                self.assertNotIn(INCOMPLETE, txt)
                self.assertNotIn("      in:", txt)

    def test_precondition_shape_is_not_rendered_as_assertion(self):
        """A VC_ASSERT entry carrying call/callee/Pre keys (the pre-Task
        011 renderer picked the branch by `"call" in c`) is judged by the
        assertion contract only: nothing from those keys is rendered."""
        c = pre_check(16, 43)
        c["rule"] = "VC_ASSERT"
        txt = report_text([diag("C.P", [c])])
        self.assertIn(INCOMPLETE_ASSERTION, txt)
        for fact in PRE_FACTS:
            self.assertNotIn(fact, txt)


class MalformedEnvelope(unittest.TestCase):
    """The semantic block and the per-check envelope themselves."""

    CASES = [
        ("semantic is a list", []),
        ("semantic is a string", "libadalang"),
        ("checks missing", {"backend": "libadalang"}),
        ("checks None", {"backend": "libadalang", "checks": None}),
        ("checks a dict", {"backend": "libadalang", "checks": {}}),
        ("backend missing", {"checks": []}),
        ("check not a dict", {"backend": "libadalang", "checks": [None, 7]}),
        ("check empty", {"backend": "libadalang", "checks": [{}]}),
        ("location missing", {"backend": "libadalang", "checks": [
            {"rule": "VC_PRECONDITION", "resolution": "unresolved"}]}),
        ("location None", {"backend": "libadalang", "checks": [
            {"rule": "VC_ASSERT", "location": None,
             "resolution": "exact"}]}),
        ("location partial", {"backend": "libadalang", "checks": [
            {"rule": "VC_PRECONDITION", "location": {"line": 3},
             "resolution": "exact"}]}),
        ("resolution missing", {"backend": "libadalang", "checks": [
            {"rule": "VC_PRECONDITION",
             "location": {"file": FILE, "line": 9, "column": 7}}]}),
        ("rule missing, exact", {"backend": "libadalang", "checks": [
            {"resolution": "exact", "call": {}}]}),
    ]

    def test_never_raises(self):
        for name, sem in self.CASES:
            with self.subTest(case=name):
                d = replace(diag("C.P", [pre_check(9, 7)]),
                            semantic=copy.deepcopy(sem))
                for txt in (report_text([d], groups=False),
                            diagnostic_to_text(d),
                            "\n".join(semantic_text(d.semantic))):
                    self.assertIn("  semantic", txt)
                    for line in PRE_LINES:
                        self.assertNotIn(line, txt)

    def test_structural_problems_are_reported(self):
        for sem in ([], {"checks": None}, {"checks": [None]},
                    {"checks": [{"resolution": "exact"}]}):
            with self.subTest(sem=sem):
                self.assertIn(INCOMPLETE, "\n".join(semantic_text(sem)))

    def test_malformed_metadata_line(self):
        txt = to_text([], [], [], {"semantic": {
            "evaluated": True, "resolutions": None, "provenance": None}})
        self.assertIn("semantic enrichment: - -, project -; checks: -", txt)



class ValidRenderingIsUnchanged(unittest.TestCase):
    """Golden lines: the exact pre-Task 011 rendering of complete
    entries. (Byte-compatibility with origin/main was additionally checked
    over every fixture, every semantic snapshot and the CI E2E-F/G
    reports; see docs/tasks/011-defensive-semantic-rendering.md.)"""

    def lines(self, *checks):
        return semantic_text({"backend": "libadalang",
                              "checks": list(checks)})

    def test_single_conjunct(self):
        self.assertEqual(self.lines(pre_check(9, 7)), [
            "  semantic (libadalang):",
            "    ring_buffer_client_proof.adb:9:7 VC_PRECONDITION: exact",
            "      call: Push (Q, A)",
            "      callee: Ring_Buffer.Push (src/ring_buffer.ads:36:4)",
            "      public Pre: not Is_Full (B)",
            "      failed conjunct: unknown (GNATprove result does not "
            "identify a specific conjunct)"])

    def test_multi_conjunct_and_line_folding(self):
        pre = dict(PUSH_PRE, text="A and then\n     B", conjuncts=[
            {"index": 0, "text": "A", "location": span("s.ads", 1, 1)},
            {"index": 1, "text": "B", "location": span("s.ads", 2, 6)}])
        self.assertEqual(self.lines(pre_check(9, 7, pre=pre,
                                              text="Op\n  (X)"))[2:], [
            "      call: Op (X)",
            "      callee: Ring_Buffer.Push (src/ring_buffer.ads:36:4)",
            "      public Pre: A and then B",
            "        [0] A",
            "        [1] B",
            "      failed conjunct: unknown (GNATprove result does not "
            "identify a specific conjunct)"])

    def test_no_explicit_pre(self):
        self.assertEqual(self.lines(pre_check(9, 7, pre=NO_PRE))[2:], [
            "      call: Push (Q, A)",
            "      callee: Ring_Buffer.Push (src/ring_buffer.ads:36:4)",
            "      public Pre: none (no explicit Pre aspect)"])

    def test_assertion(self):
        self.assertEqual(self.lines(assertion_check()), [
            "  semantic (libadalang):",
            "    ring_buffer_client_proof.adb:16:43 VC_ASSERT: exact",
            "      assertion: Free_Count (P) = 0 "
            "(src/ring_buffer_client_proof.adb:16:43)",
            f"      in: {ASSERT_SUBP}"])

    def test_non_exact(self):
        self.assertEqual(self.lines(
            {"rule": "VC_PRECONDITION",
             "location": {"file": FILE, "line": 9, "column": 7},
             "resolution": "unavailable",
             "reason": "callee declaration: checksum mismatch"}), [
            "  semantic (libadalang):",
            "    ring_buffer_client_proof.adb:9:7 VC_PRECONDITION: "
            "unavailable",
            "      reason: callee declaration: checksum mismatch"])

    def test_check_without_line_column(self):
        """Task 009 `unavailable` for a check with no line/column."""
        self.assertEqual(self.lines(
            {"rule": "VC_ASSERT",
             "location": {"file": FILE, "line": None, "column": None},
             "resolution": "unavailable",
             "reason": "check has no line/column"})[1],
            "    ring_buffer_client_proof.adb:None:None VC_ASSERT: "
            "unavailable")



class JsonIsUnchanged(unittest.TestCase):
    def test_malformed_semantic_is_serialised_verbatim(self):
        cases = ([("pre " + n, m, pre_check(10, 7))
                  for n, m in MALFORMED_PRECONDITION]
                 + [("assert " + n, m, assertion_check())
                    for n, m in MALFORMED_ASSERTION])
        for name, mutate, bad in cases:
            with self.subTest(case=name):
                mutate(bad)
                d = diag("C.P", [bad])
                raw = copy.deepcopy(d.semantic)
                self.assertEqual(diagnostic_to_dict(d)["semantic"], raw)
                doc = json.loads(to_json([], [d], [], {}))
                self.assertEqual(doc["diagnostics"][0]["semantic"], raw)
                report_text([d])
                self.assertEqual(d.semantic, raw)   # rendering: no mutation

    def test_non_dict_semantic_is_serialised_verbatim(self):
        d = replace(diag("C.P", [pre_check(9, 7)], Confidence.LOW),
                    semantic=["not", "an", "object"])
        self.assertEqual(json.loads(to_json([], [d], [], {}))[
            "diagnostics"][0]["semantic"], ["not", "an", "object"])


class SharedContract(unittest.TestCase):
    """Grouping completeness (Task 010) and rendering completeness (Task
    011) are one predicate (semantic_shape.exact_precondition_complete)."""

    def test_grouping_and_rendering_agree(self):
        cases = ([("valid", lambda c: None)] + MALFORMED_PRECONDITION
                 + MALFORMED_EXACT)
        for name, mutate in cases:
            with self.subTest(case=name):
                c = pre_check(10, 7)
                mutate(c)
                d = diag("C.P", [c])
                grouped = build_srd002_groups([d])["group_count"] == 1
                rendered = INCOMPLETE not in diagnostic_to_text(d)
                self.assertEqual(grouped, rendered)
                self.assertEqual(grouped, exact_precondition_complete(c))

    def _imports(self, mod):
        tree = ast.parse((PKG / mod).read_text("utf-8"))
        mods = {n.module or "" for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}
        return tree, mods

    def test_module_dependencies(self):
        """render.py depends on the shape contract only, never on
        grouping policy, enrichment or Libadalang; semantic_shape.py
        depends on nothing."""
        _, render = self._imports("render.py")
        self.assertIn("semantic_shape", render)
        self.assertFalse({m for m in render if "semantic" in m
                          and m != "semantic_shape"}, render)
        self.assertFalse({m for m in render if "libadalang" in m})
        _, groups = self._imports("semantic_groups.py")
        self.assertIn("semantic_shape", groups)
        tree, shape = self._imports("semantic_shape.py")
        self.assertEqual(shape, {"__future__"})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse({"eval", "exec", "re"} & names)

    def test_renderer_has_no_exception_swallowing(self):
        """Robustness comes from explicit structural checks, not from a
        try/except around rendering."""
        tree, _ = self._imports("render.py")
        self.assertFalse([n for n in ast.walk(tree)
                          if isinstance(n, ast.Try)])


if __name__ == "__main__":
    unittest.main()
