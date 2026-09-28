"""Task 010: SRD002 semantic triage groups (semantic_groups.py).

Pure tests: no Libadalang. Enriched Diagnostic objects are built directly
(or enriched with a stub backend), so every grouping rule is exercised
deterministically. Real-backend grouping of the committed semantic
snapshots is in test_semantic.py (WithLibadalang)."""

from __future__ import annotations

import ast
import copy
import json
import unittest

import support
from spark_refine_diagnostics.model import (Confidence, Diagnostic, Location,
                                            RelatedCheck, Severity)
from spark_refine_diagnostics.render import (GROUPS_DISCLAIMER, to_json,
                                             to_text)
from spark_refine_diagnostics.semantic_groups import (
    REASONS, build_srd002_groups, coverage_problems, occurrence_ids)

PKG = support.DIAGNOSTICS / "spark_refine_diagnostics"
CLIENT = "ring_buffer_client_proof"
FILE = "ring_buffer_client_proof.adb"


def span(file, line, col, eline=None, ecol=None):
    return {"file": file, "start_line": line, "start_column": col,
            "end_line": eline or line, "end_column": ecol or col + 10}


PUSH = {"name": "Ring_Buffer.Push", "kind": "procedure",
        "declaration": span("src/ring_buffer.ads", 36, 4, 38, 62)}
PUSH_PRE = {"explicit": True, "text": "not Is_Full (B)",
            "location": span("src/ring_buffer.ads", 37, 17, 37, 32),
            "conjuncts": [{"index": 0, "text": "not Is_Full (B)",
                           "location": span("src/ring_buffer.ads", 37, 17,
                                            37, 32)}],
            "failed_conjunct": None,
            "attribution": "not_provided_by_gnatprove"}


def pre_check(line, col, callee=PUSH, pre=PUSH_PRE, text="Push (Q, A)",
              file=FILE):
    return {"rule": "VC_PRECONDITION",
            "location": {"file": file, "line": line, "column": col},
            "resolution": "exact",
            "call": {"text": text,
                     "location": span("src/" + file, line, col)},
            "callee": copy.deepcopy(callee),
            "precondition": copy.deepcopy(pre)}


def assert_check(line, col, file=FILE):
    return {"rule": "VC_ASSERT",
            "location": {"file": file, "line": line, "column": col},
            "resolution": "exact",
            "assertion": {"pragma": "Assert", "text": "X",
                          "location": span("src/" + file, line, col)},
            "enclosing_subprogram": "P.Q"}


def non_exact(line, col, resolution, rule="VC_PRECONDITION"):
    return {"rule": rule,
            "location": {"file": FILE, "line": line, "column": col},
            "resolution": resolution, "reason": f"test {resolution}"}


def diag(entity, checks, confidence=Confidence.MEDIUM, client=CLIENT,
         code="SRD002"):
    related = tuple(
        RelatedCheck("client failure", c["rule"], "unproved", entity,
                     Location(c["location"]["file"], c["location"]["line"],
                              c["location"]["column"]), "msg")
        for c in checks)
    return Diagnostic(
        code=code, severity=Severity.WARNING, confidence=confidence,
        title="t", entity=entity,
        primary_location=related[0].location if related else None,
        explanation="e", recommendation="r", related=related,
        data=(("client_unit", client),),
        semantic={"backend": "libadalang", "checks": checks})


def ring_full_post():
    """The ring_no_is_full_post shape: Push_Push_Pop (LOW: 2 Push + 1
    assert) and Rotate (MEDIUM: 1 Push)."""
    return [
        diag("Ring_Buffer_Client_Proof.Push_Push_Pop",
             [pre_check(9, 7, text="Push (Q, A)"),
              pre_check(10, 7, text="Push (Q, B)"),
              assert_check(16, 43)], Confidence.LOW),
        diag("Ring_Buffer_Client_Proof.Rotate",
             [pre_check(25, 7, text="Push (Q, X)")], Confidence.MEDIUM)]


def build(tc, diags):
    doc = build_srd002_groups(diags)
    tc.assertEqual(coverage_problems(doc, occurrence_ids(diags)), [])
    return doc


class Identity(unittest.TestCase):
    def test_one_occurrence_one_group(self):
        doc = build(self, [diag("C.P", [pre_check(9, 7)])])
        self.assertEqual((doc["group_count"], doc["grouped_check_count"],
                          doc["ungrouped_check_count"]), (1, 1, 0))
        self.assertEqual(doc["groups"][0]["check_count"], 1)

    def test_three_same_callee_pre_one_group(self):
        doc = build(self, ring_full_post())
        self.assertEqual((doc["client_failure_count"], doc["group_count"],
                          doc["grouped_check_count"],
                          doc["ungrouped_check_count"]), (4, 1, 3, 1))
        g = doc["groups"][0]
        self.assertEqual(g["callee"], PUSH)
        self.assertEqual(g["precondition"], PUSH_PRE)  # verbatim Task 009
        self.assertEqual(g["check_count"], 3)
        self.assertEqual([(o["location"]["line"], o["location"]["column"],
                           o["call"]["text"]) for o in g["occurrences"]],
                         [(9, 7, "Push (Q, A)"), (10, 7, "Push (Q, B)"),
                          (25, 7, "Push (Q, X)")])
        self.assertEqual(doc["ungrouped"], [{
            "client_unit": CLIENT,
            "entity": "Ring_Buffer_Client_Proof.Push_Push_Pop",
            "diagnostic_confidence": "low", "rule": "VC_ASSERT",
            "location": {"file": FILE, "line": 16, "column": 43},
            "resolution": "exact", "reason": "assertion_has_no_callee"}])

    def test_same_name_different_declaration_span_two_groups(self):
        other = copy.deepcopy(PUSH)
        other["declaration"]["start_line"] = 50
        doc = build(self, [diag("C.P", [pre_check(9, 7),
                                        pre_check(10, 7, callee=other)])])
        self.assertEqual([g["callee"]["declaration"]["start_line"]
                          for g in doc["groups"]], [36, 50])

    def test_same_declaration_different_pre_text_two_groups(self):
        other = dict(PUSH_PRE, text="not  Is_Full (B)")  # layout only
        doc = build(self, [diag("C.P", [pre_check(9, 7),
                                        pre_check(10, 7, pre=other)])])
        self.assertEqual(doc["group_count"], 2)

    def test_same_declaration_different_pre_span_two_groups(self):
        other = copy.deepcopy(PUSH_PRE)
        other["location"]["start_column"] = 18
        doc = build(self, [diag("C.P", [pre_check(9, 7),
                                        pre_check(10, 7, pre=other)])])
        self.assertEqual(doc["group_count"], 2)

    def test_inconsistent_pre_metadata_is_split_not_chosen(self):
        """Same declaration, differing extracted Pre metadata: both kept
        verbatim in separate groups; neither is silently chosen."""
        other = dict(PUSH_PRE, conjuncts=[])
        doc = build(self, [diag("C.P", [pre_check(9, 7)]),
                           diag("C.Q", [pre_check(25, 7, pre=other)])])
        self.assertEqual(doc["group_count"], 2)
        self.assertEqual(sorted(len(g["precondition"]["conjuncts"])
                                for g in doc["groups"]), [0, 1])

    def test_logically_equivalent_pre_not_merged(self):
        a = dict(PUSH_PRE, text="A and then B")
        b = dict(PUSH_PRE, text="B and then A")
        doc = build(self, [diag("C.P", [pre_check(9, 7, pre=a),
                                        pre_check(10, 7, pre=b)])])
        self.assertEqual(doc["group_count"], 2)

    def test_overloads_same_qualified_name_separate_groups(self):
        over1 = {"name": "Ops.Over", "kind": "procedure",
                 "declaration": span("src/ops.ads", 32, 4, 34, 24)}
        over2 = {"name": "Ops.Over", "kind": "procedure",
                 "declaration": span("src/ops.ads", 36, 4, 38, 24)}
        p1 = dict(PUSH_PRE, text="X > 0",
                  location=span("src/ops.ads", 33, 19))
        p2 = dict(PUSH_PRE, text="X", location=span("src/ops.ads", 37, 19))
        doc = build(self, [diag("Client.Shapes2", [
            pre_check(40, 10, callee=over1, pre=p1, file="client.adb"),
            pre_check(41, 10, callee=over2, pre=p2, file="client.adb")])])
        self.assertEqual([(g["callee"]["name"], g["precondition"]["text"])
                          for g in doc["groups"]],
                         [("Ops.Over", "X > 0"), ("Ops.Over", "X")])

    def test_different_kind_separate_groups(self):
        fn = dict(PUSH, kind="function")
        doc = build(self, [diag("C.P", [pre_check(9, 7),
                                        pre_check(10, 7, callee=fn)])])
        self.assertEqual(doc["group_count"], 2)

    def test_no_explicit_pre_is_its_own_identity(self):
        none = {"explicit": False, "text": None, "location": None,
                "conjuncts": [], "failed_conjunct": None,
                "attribution": "not_provided_by_gnatprove"}
        doc = build(self, [diag("C.P", [pre_check(9, 7, pre=none),
                                        pre_check(10, 7, pre=none),
                                        pre_check(11, 7)])])
        self.assertEqual(sorted(g["check_count"] for g in doc["groups"]),
                         [1, 2])


class Ungrouped(unittest.TestCase):
    def reasons(self, checks):
        doc = build(self, [diag("C.P", checks)])
        return doc, [(u["location"]["line"], u["reason"])
                     for u in doc["ungrouped"]]

    def test_assertion_is_never_grouped(self):
        doc, r = self.reasons([assert_check(16, 43)])
        self.assertEqual((doc["group_count"], r),
                         (0, [(16, "assertion_has_no_callee")]))

    def test_non_exact_preconditions_are_ungrouped(self):
        doc, r = self.reasons([non_exact(1, 1, "ambiguous"),
                               non_exact(2, 1, "unresolved"),
                               non_exact(3, 1, "unavailable")])
        self.assertEqual(doc["group_count"], 0)
        self.assertEqual(r, [(1, "semantic_ambiguous"),
                             (2, "semantic_unresolved"),
                             (3, "semantic_unavailable")])
        # Task 009's reason is kept as a human detail, never as the key
        self.assertEqual([u["detail"] for u in doc["ungrouped"]],
                         ["test ambiguous", "test unresolved",
                          "test unavailable"])
        self.assertEqual([u["resolution"] for u in doc["ungrouped"]],
                         ["ambiguous", "unresolved", "unavailable"])

    def test_unavailable_external_callee_does_not_disappear(self):
        """Archived-fixture outcome for SPARKlib Remove/Get."""
        doc, r = self.reasons([pre_check(11, 7),
                               non_exact(24, 45, "unavailable"),
                               non_exact(25, 45, "unavailable")])
        self.assertEqual((doc["group_count"], doc["ungrouped_check_count"]),
                         (1, 2))
        self.assertEqual({x for _, x in r}, {"semantic_unavailable"})

    def test_malformed_exact_entry_is_semantic_incomplete(self):
        broken = []
        for drop in ("call", "callee", "precondition"):
            c = pre_check(len(broken) + 1, 1)
            del c[drop]
            broken.append(c)
        c = pre_check(10, 1)
        del c["callee"]["declaration"]
        broken.append(c)
        c = pre_check(11, 1)
        c["precondition"]["text"] = None      # explicit, but no text
        broken.append(c)
        c = pre_check(12, 1)
        c["resolution"] = "weird"
        broken.append(c)
        doc, r = self.reasons(broken)
        self.assertEqual(doc["group_count"], 0)
        self.assertEqual({x for _, x in r}, {"semantic_incomplete"})
        self.assertEqual(len(r), 6)

    def test_missing_semantic_entry_is_semantic_incomplete(self):
        d = diag("C.P", [pre_check(9, 7)])
        d.semantic["checks"].clear()
        doc = build(self, [d])
        self.assertEqual([u["reason"] for u in doc["ungrouped"]],
                         ["semantic_incomplete"])

    def test_reason_vocabulary_is_stable(self):
        self.assertEqual(REASONS, (
            "assertion_has_no_callee", "rule_not_groupable",
            "semantic_ambiguous", "semantic_unresolved",
            "semantic_unavailable", "semantic_incomplete"))

    def test_false_client_shape_has_no_group(self):
        doc = build(self, [diag(
            "Fixed_Pool_False_Client.Initialize_Then_Claim_Empty",
            [assert_check(9, 22, file="fixed_pool_false_client.adb")],
            Confidence.LOW, client="fixed_pool_false_client")])
        self.assertEqual((doc["group_count"], doc["grouped_check_count"],
                          doc["ungrouped_check_count"]), (0, 0, 1))
        self.assertEqual(doc["groups"], [])


class ConfidenceAndOrder(unittest.TestCase):
    def test_mixed_confidences_preserved_per_occurrence(self):
        g = build(self, ring_full_post())["groups"][0]
        self.assertEqual([(o["entity"].rsplit(".", 1)[1],
                           o["diagnostic_confidence"])
                          for o in g["occurrences"]],
                         [("Push_Push_Pop", "low"), ("Push_Push_Pop", "low"),
                          ("Rotate", "medium")])
        self.assertEqual(g["diagnostic_confidences"], ["low", "medium"])
        self.assertNotIn("confidence", g)

    def test_order_independent_of_input_order(self):
        diags = ring_full_post() + [diag("A.X", [
            pre_check(3, 3, callee=dict(PUSH, name="A.Op")),
            non_exact(4, 4, "ambiguous")])]
        ref = json.dumps(build_srd002_groups(diags))
        rev = [copy.deepcopy(d) for d in reversed(diags)]
        for d in rev:
            d.semantic["checks"].reverse()
        self.assertEqual(json.dumps(build_srd002_groups(rev)), ref)
        doc = json.loads(ref)
        self.assertEqual([g["callee"]["name"] for g in doc["groups"]],
                         ["A.Op", "Ring_Buffer.Push"])

    def test_occurrence_order(self):
        """client unit, entity, file, line, column."""
        diags = [diag("C.Z", [pre_check(1, 1)], client="b"),
                 diag("C.B", [pre_check(20, 1), pre_check(3, 9),
                              pre_check(3, 2)], client="a"),
                 diag("C.A", [pre_check(50, 1)], client="a")]
        occs = build(self, diags)["groups"][0]["occurrences"]
        self.assertEqual([(o["client_unit"], o["entity"],
                           o["location"]["line"], o["location"]["column"])
                          for o in occs],
                         [("a", "C.A", 50, 1), ("a", "C.B", 3, 2),
                          ("a", "C.B", 3, 9), ("a", "C.B", 20, 1),
                          ("b", "C.Z", 1, 1)])

    def test_non_srd002_diagnostics_ignored(self):
        doc = build(self, [diag("C.P", [pre_check(9, 7)], code="SRD001")])
        self.assertEqual(doc["client_failure_count"], 0)
        self.assertEqual((doc["groups"], doc["ungrouped"]), ([], []))


class Coverage(unittest.TestCase):
    def setUp(self):
        self.diags = ring_full_post()
        self.expected = occurrence_ids(self.diags)
        self.doc = build_srd002_groups(self.diags)

    def problems(self, doc):
        return coverage_problems(doc, self.expected)

    def test_ok(self):
        self.assertEqual(self.problems(self.doc), [])
        self.assertEqual(len(self.expected), 4)

    def test_duplicated_occurrence_is_caught(self):
        doc = copy.deepcopy(self.doc)
        doc["ungrouped"].append(copy.deepcopy(
            doc["groups"][0]["occurrences"][0]))
        doc["ungrouped_check_count"] += 1
        self.assertTrue(any("listed 2 times" in p
                            for p in self.problems(doc)))

    def test_dropped_occurrence_is_caught(self):
        doc = copy.deepcopy(self.doc)
        doc["groups"][0]["occurrences"].pop()
        p = self.problems(doc)
        self.assertTrue(any("missing" in x for x in p), p)
        self.assertTrue(any("check_count" in x for x in p), p)
        doc = copy.deepcopy(self.doc)
        doc["ungrouped"].clear()
        doc["ungrouped_check_count"] = 0
        self.assertTrue(any("missing" in x for x in self.problems(doc)))

    def test_bad_counts_are_caught(self):
        for key, delta in (("group_count", 1), ("grouped_check_count", -1),
                           ("ungrouped_check_count", 1),
                           ("client_failure_count", 1)):
            doc = copy.deepcopy(self.doc)
            doc[key] += delta
            with self.subTest(key=key):
                self.assertTrue(self.problems(doc))

    def test_forbidden_group_content_is_caught(self):
        doc = copy.deepcopy(self.doc)
        doc["groups"][0]["confidence"] = "high"
        self.assertTrue(self.problems(doc))
        doc = copy.deepcopy(self.doc)
        doc["groups"][0]["precondition"]["failed_conjunct"] = 0
        self.assertTrue(self.problems(doc))
        doc = copy.deepcopy(self.doc)
        doc["groups"][0]["occurrences"][0]["rule"] = "VC_ASSERT"
        self.assertTrue(self.problems(doc))
        doc = copy.deepcopy(self.doc)
        doc["ungrouped"][0]["reason"] = "the assertion is false"
        self.assertTrue(self.problems(doc))

    def test_duplicate_input_kept_once_and_marked(self):
        """The same related check twice in one diagnostic is one
        occurrence with duplicate_count 2, not a double count."""
        d = self.diags[1]
        dup = Diagnostic(**{**d.__dict__,
                            "related": d.related + d.related,
                            "semantic": {"backend": "libadalang",
                                         "checks": d.semantic["checks"] * 2}})
        diags = [self.diags[0], dup]
        doc = build_srd002_groups(diags)
        self.assertEqual(coverage_problems(doc, occurrence_ids(diags)), [])
        self.assertEqual(doc["grouped_check_count"], 3)
        rotate = doc["groups"][0]["occurrences"][2]
        self.assertEqual(rotate["duplicate_count"], 2)
        self.assertTrue(all("duplicate_count" not in o
                            for o in doc["groups"][0]["occurrences"][:2]))
        self.assertIn("reported 2 times", "\n".join(
            _render({"srd002_groups": doc})))


class NoMutation(unittest.TestCase):
    def test_diagnostics_are_not_mutated(self):
        diags = ring_full_post()
        before = copy.deepcopy(diags)
        before_json = [json.dumps(d.semantic, sort_keys=True) for d in diags]
        doc = build_srd002_groups(diags)
        self.assertEqual(diags, before)
        self.assertEqual([json.dumps(d.semantic, sort_keys=True)
                          for d in diags], before_json)
        # the output owns its data: editing it cannot reach a diagnostic
        doc["groups"][0]["precondition"]["text"] = "changed"
        doc["groups"][0]["callee"]["name"] = "changed"
        self.assertEqual([json.dumps(d.semantic, sort_keys=True)
                          for d in diags], before_json)

    def test_module_is_backend_neutral_and_reads_no_messages(self):
        tree = ast.parse((PKG / "semantic_groups.py").read_text("utf-8"))
        mods = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module or "" for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom)}
        self.assertFalse({m for m in mods if "libadalang" in m
                          or "semantic_lal" in m})
        attrs = {n.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute)}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("message", attrs)
        self.assertFalse({"eval", "exec", "re"} & names)

    def test_srd002_does_not_import_semantic_modules(self):
        """SRD002 stays independent of optional enrichment/grouping."""
        tree = ast.parse((PKG / "srd002.py").read_text("utf-8"))
        mods = {n.module or "" for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse({m for m in mods if "semantic" in m}, mods)


def _render(analysis_semantic: dict, diags=()) -> list[str]:
    txt = to_text([], list(diags), [], {"semantic": {
        "requested": True, "evaluated": True, "backend": "libadalang",
        "version": "x", "project": "p.gpr", "resolutions": {},
        **analysis_semantic}})
    return txt.splitlines()


# Wording the triage renderer must never produce (it would claim a cause,
# a defect or a fix). Gated on the new section only.
FORBIDDEN = ("root cause", "contract is insufficient", "contract defect",
             "fix the contract", "missing contract", "same cause",
             "is the problem", "is insufficient", "recommended fix")


def _section(lines: list[str]) -> str:
    start = lines.index("SRD002 semantic triage:")
    end = next(i for i in range(start, len(lines))
               if lines[i].startswith("SRD002: "))
    return "\n".join(lines[start:end])


class Text(unittest.TestCase):
    def lines(self, diags):
        return _render({"srd002_groups": build_srd002_groups(diags)}, diags)

    def test_ring_full_post_section(self):
        lines = self.lines(ring_full_post())
        sec = _section(lines)
        self.assertEqual(sec.splitlines()[:11], [
            "SRD002 semantic triage:",
            "  3 grouped precondition checks -> 1 callee/contract group",
            "  1 ungrouped check",
            "",
            "  Ring_Buffer.Push (procedure, src/ring_buffer.ads:36:4)",
            "    public Pre: not Is_Full (B)",
            "    calls: 3",
            "      ring_buffer_client_proof.adb:9:7  Push (Q, A)",
            "      ring_buffer_client_proof.adb:10:7 Push (Q, B)",
            "      ring_buffer_client_proof.adb:25:7 Push (Q, X)",
            ""])
        self.assertIn("  ungrouped:\n"
                      "    ring_buffer_client_proof.adb:16:43 VC_ASSERT\n"
                      "      assertion_has_no_callee", sec)
        self.assertIn(" ".join(GROUPS_DISCLAIMER.split()),
                      " ".join(sec.split()))

    def test_section_precedes_individual_diagnostics(self):
        lines = self.lines(ring_full_post())
        first_diag = next(i for i, x in enumerate(lines)
                          if x.startswith("SRD002: "))
        self.assertLess(lines.index("SRD002 semantic triage:"), first_diag)
        # summary + detail: per-diagnostic semantic blocks still rendered
        self.assertEqual(sum(x == "  semantic (libadalang):"
                             for x in lines), 2)

    def test_no_causal_or_fix_wording(self):
        other = dict(PUSH_PRE, explicit=False, text=None, location=None,
                     conjuncts=[])
        cases = [ring_full_post(),
                 [diag("C.P", [assert_check(9, 22)], Confidence.LOW)],
                 [diag("C.P", [non_exact(1, 1, "unavailable"),
                               pre_check(2, 2, pre=other)])]]
        for diags in cases:
            sec = _section(self.lines(diags)).lower()
            flat = " ".join(sec.split())
            for bad in FORBIDDEN:
                with self.subTest(bad=bad):
                    self.assertNotIn(bad, flat)
            self.assertIn("groups are descriptive", flat)
            self.assertIn("does not establish a shared cause", flat)

    def test_false_client_text(self):
        diags = [diag("Fixed_Pool_False_Client.Initialize_Then_Claim_Empty",
                      [assert_check(9, 22, file="fixed_pool_false_client.adb")],
                      Confidence.LOW, client="fixed_pool_false_client")]
        sec = _section(self.lines(diags))
        self.assertIn("0 grouped precondition checks -> 0 callee/contract "
                      "groups", sec)
        self.assertIn("1 ungrouped check", sec)
        self.assertNotIn("public Pre", sec)

    def test_not_rendered_without_groups(self):
        txt = to_text([], [], [], {"semantic": {
            "requested": True, "evaluated": False, "backend": "libadalang",
            "reason": "no project supplied (-P PROJECT)"}})
        self.assertNotIn("semantic triage", txt)

    def test_json_location_and_format_version(self):
        diags = ring_full_post()
        doc = json.loads(to_json([], diags, [], {"semantic": {
            "evaluated": True, "srd002_groups": build_srd002_groups(diags)}}))
        self.assertEqual(doc["format_version"], 1)
        g = doc["analysis"]["semantic"]["srd002_groups"]
        self.assertEqual(list(g), ["client_failure_count", "group_count",
                                   "grouped_check_count",
                                   "ungrouped_check_count", "groups",
                                   "ungrouped"])
        self.assertEqual(list(g["groups"][0]), [
            "callee", "precondition", "check_count",
            "diagnostic_confidences", "occurrences"])
        self.assertEqual(list(g["groups"][0]["occurrences"][0]), [
            "client_unit", "entity", "diagnostic_confidence", "rule",
            "location", "call"])


class ReportIntegration(unittest.TestCase):
    """Through enrich_report on the committed semantic snapshots, with the
    Task 009 FakeBackend (no Libadalang)."""

    @classmethod
    def setUpClass(cls):
        import test_semantic as ts
        cls.ts = ts

    def enrich(self, name, backend=None, request=None):
        from spark_refine_diagnostics.semantic import (SemanticRequest,
                                                       enrich_report)
        ts = self.ts
        return enrich_report(ts.base_report(name),
                             ts.SEM / name / "results",
                             request or SemanticRequest("x.gpr"),
                             factory=ts.fake_factory(
                                 backend or ts.FakeBackend()))

    def test_diagnostics_identical_with_and_without_groups(self):
        """Only analysis.semantic.srd002_groups is added; every Diagnostic
        (count, order, fields, semantic block) is what Task 009 made."""
        from spark_refine_diagnostics import semantic
        for name in ("ring_no_is_full_post", "ring_no_is_empty_post",
                     "pool_spec_no_count_posts", "pool_false_client_assert",
                     "conjunct_experiment"):
            with self.subTest(case=name):
                rep = self.enrich(name)
                with unittest.mock.patch.object(
                        semantic, "build_srd002_groups",
                        lambda diags: None):
                    old = self.enrich(name)
                new = self.ts.as_json(rep)
                ref = self.ts.as_json(old)
                groups = new["analysis"]["semantic"].pop("srd002_groups")
                ref["analysis"]["semantic"].pop("srd002_groups")
                self.assertEqual(new, ref)
                self.assertEqual(
                    coverage_problems(groups, occurrence_ids(
                        rep.diagnostics)), [])
                self.assertEqual(list(rep.analysis["semantic"])[-1],
                                 "srd002_groups")

    def test_srd002_count_unchanged(self):
        for name in ("ring_no_is_full_post", "conjunct_experiment"):
            base = self.ts.base_report(name)
            rep = self.enrich(name)
            self.assertEqual([(d.code, d.entity, d.confidence)
                              for d in rep.diagnostics],
                             [(d.code, d.entity, d.confidence)
                              for d in base.diagnostics])

    def test_not_evaluated_means_no_groups(self):
        from spark_refine_diagnostics.semantic import SemanticRequest
        rep = self.enrich("ring_no_is_full_post",
                          request=SemanticRequest(None))
        self.assertNotIn("srd002_groups", rep.analysis["semantic"])
        with self.ts._block_libadalang():
            from spark_refine_diagnostics.semantic import enrich_report
            rep = enrich_report(
                self.ts.base_report("ring_no_is_full_post"),
                self.ts.SEM / "ring_no_is_full_post" / "results",
                SemanticRequest("ring_buffer.gpr"))
        self.assertNotIn("srd002_groups", rep.analysis["semantic"])
        txt = to_text(rep.runs, rep.diagnostics, rep.notes, rep.analysis)
        self.assertNotIn("semantic triage", txt)

    def test_explicit_pre_without_span_is_incomplete(self):
        """The Task 009 FakeBackend answers an explicit Pre whose location
        is None: its identity is incomplete, so nothing is grouped, and
        nothing disappears either."""
        rep = self.enrich("ring_no_is_empty_post")
        g = rep.analysis["semantic"]["srd002_groups"]
        self.assertEqual((g["group_count"], g["ungrouped_check_count"]),
                         (0, 6))
        self.assertEqual(sorted(u["reason"] for u in g["ungrouped"]),
                         ["assertion_has_no_callee"] * 2
                         + ["semantic_incomplete"] * 4)

    def test_complete_stub_groups_by_full_identity(self):
        """A stub answering the same complete callee/Pre for every call:
        all preconditions of the report form one group; assertions
        (answered `ambiguous` by the stub) never do."""
        class Stub(self.ts.FakeBackend):
            def resolve_precondition(self, file, line, column):
                r = super().resolve_precondition(file, line, column)
                r["precondition"] = copy.deepcopy(PUSH_PRE)
                return r
        rep = self.enrich("ring_no_is_empty_post", backend=Stub())
        g = rep.analysis["semantic"]["srd002_groups"]
        self.assertEqual((g["group_count"], g["grouped_check_count"],
                          g["ungrouped_check_count"]), (1, 4, 2))
        self.assertEqual({u["reason"] for u in g["ungrouped"]},
                         {"assertion_has_no_callee"})
        self.assertEqual(g["groups"][0]["diagnostic_confidences"],
                         ["low", "medium"])
