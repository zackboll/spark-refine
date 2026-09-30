"""Task 013: guard-sensitive conjunct re-proof EXPERIMENT (scripts only).

Part 1 (always runs; no Libadalang, no GNATprove): the pre-registered
matrix, the prefix planner and its refusal of selected-only guarded
suffixes, classification, structural matching, nested-check separation,
the frozen decision rule, deterministic evidence, source isolation,
scratch-root safety and the absence of message-text dependence.
Part 2 (skipped unless `import libadalang` works): extraction, exact
prefix text and the scratch transformation on a temporary copy of the
Task 013 corpus. No GNATprove: the seven proof runs are the CI step
"Task 013: guard-sensitive conjunct re-proof experiment".
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from spark_refine_diagnostics.model import Check, Location, Status

SCRIPT = support.DIAGNOSTICS / "scripts" / "guarded_reproof_experiment.py"
T12_SCRIPT = support.DIAGNOSTICS / "scripts" / "conjunct_reproof_experiment.py"
DOC = (support.REPO / "docs" / "tasks"
       / "013-guard-sensitive-conjunct-reproof.md")


def _load():
    spec = importlib.util.spec_from_file_location("guarded_reproof", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E = _load()
P, U, J = E.PROVED, E.UNPROVED, E.JUSTIFIED


def check(entity, file, line, column, status=Status.PROVED,
          rule="VC_PRECONDITION", disputed=False,
          message="precondition might fail"):
    return Check(rule=rule, status=status,
                 location=Location(file, line, column), entity=entity,
                 message=message, disputed=disputed)


def target_check(case, status):
    _, ent, f, ln, col, _ = E._target(case)
    return check(ent, f, ln, col, Status(status))


def nested_checks(status=Status.PROVED):
    return [check(E.NESTED_CALLEE, f, ln, col, status)
            for f, ln, col in E.NESTED_LOCATIONS]


def run_checks(name):
    """Synthetic GNATprove checks exactly as pre-registered for `name`."""
    callee_idx = {E.run_name(c, i): (c, i) for c in E.CALLEES
                  for i in range(2)}
    out = []
    for case, _e, _f, _l, _c, callee in E.TARGETS:
        if name in callee_idx and callee_idx[name][0] == callee:
            st = E.MATRIX[(case, callee_idx[name][1])][0]
        else:
            st = E.BASELINE_EXPECTED[case]
        out.append(target_check(case, st))
    if name != "use_nested_p0":
        out += nested_checks()
    if name != "use_access_p0":
        out.append(check("Guarded_Ops.Use_Access", "guarded_ops.ads", 12, 30,
                         rule="VC_NULL_POINTER_DEREFERENCE"))
    if name != "use_index_p0":
        out.append(check("Guarded_Ops.Use_Index", "guarded_ops.ads", 18, 31,
                         rule="VC_INDEX_CHECK"))
    out.append(check("Guarded_Ops.F", "guarded_ops.ads", 25, 32,
                     rule="VC_OVERFLOW_CHECK"))
    return out


def run_record(name):
    checks = run_checks(name)
    rec = {"run": name, "gate_problems": [], "reparse_problems": [],
           "trust_hits_introduced": [],
           "targets": [E.match_target(checks, c) for c in E.CASES],
           "inventory": E.check_inventory(checks),
           "mutation": {"changed_file_count": 0 if name == "baseline"
                        else 1}}
    rec["inventory_problems"] = E.inventory_problems(rec["inventory"], name)
    if name != "baseline":
        c, i = next((c, i) for c in E.CALLEES for i in range(2)
                    if E.run_name(c, i) == name)
        rec.update(callee=c, conjunct_index=i,
                   conjunct_text=E.EXPECTED_EXTRACTION[c]["conjuncts"][i],
                   prefix_text=E.EXPECTED_PREFIXES[(c, i)],
                   scratch_pre_is_planned_prefix=True)
    return rec


def good_evidence() -> dict:
    runs = [run_record(n) for n in E.RUN_NAMES]
    return {"runs": runs, "probes": E.derive_probes(runs),
            "refusals": [{"callee": c, "conjunct_index": 1,
                          "requested": "selected_only", "refused": True,
                          "reason": "guarded_and_then_suffix"}
                         for c in E.CALLEES],
            "trust_scan": {"original_hits": []},
            "corpus_unchanged": True}


def set_target(ev, run, case, **kw):
    r = next(r for r in ev["runs"] if r["run"] == run)
    t = next(t for t in r["targets"] if t["case"] == case)
    t.update(kw)
    ev["probes"] = E.derive_probes(ev["runs"])


def synthetic(expr: str, parts: list[str]):
    """A source line holding `expr`; conjunct ranges located left to
    right (test-only; the experiment takes them from Libadalang)."""
    head = "   with Pre => "
    src = (head + expr + ",\n").encode()
    es = len(head)
    conj, pos = [], es
    for p in parts:
        s = src.index(p.encode(), pos)
        conj.append({"text": p, "range": [s, s + len(p)]})
        pos = s + len(p)
    return src, [es, es + len(expr)], conj


class PreRegisteredMatrix(unittest.TestCase):
    def test_matrix_shape_and_totals(self):
        self.assertEqual(len(E.MATRIX), 18)
        sts = [v[0] for v in E.MATRIX.values()]
        self.assertEqual((sts.count(P), sts.count(U), sts.count(J)),
                         (9, 9, 0))
        cls = [v[1] for v in E.MATRIX.values()]
        self.assertEqual({c: cls.count(c) for c in E.CLASSIFICATIONS},
                         {E.PREFIX_PROVED: 9, E.NEWLY_UNPROVED: 6,
                          E.BLOCKED: 3, E.NESTED_UNPROVED: 0, E.INVALID: 0})

    def test_each_family_exercises_pp_pu_uu(self):
        for fam in "ABC":
            sigs = {tuple(E.MATRIX[(f"{fam}{k}", i)][0] for i in (0, 1))
                    for k in (1, 2, 3)}
            self.assertEqual(sigs, {(P, P), (P, U), (U, U)}, fam)

    def test_matrix_is_consistent_with_the_classifier(self):
        for (case, i), (st, cls) in E.MATRIX.items():
            prev = None if i == 0 else {
                "matches": 1, "status": E.MATRIX[(case, i - 1)][0]}
            self.assertEqual(E.classify(prev, {"matches": 1, "status": st}),
                             cls, (case, i))

    def test_baseline_is_the_full_prefix_status(self):
        for case, want in E.BASELINE_EXPECTED.items():
            self.assertEqual(E.MATRIX[(case, 1)][0], want)
        self.assertEqual([c for c, s in E.BASELINE_EXPECTED.items()
                          if s == P], ["A1", "B1", "C1"])

    def test_runs_and_switches(self):
        self.assertEqual(E.RUN_NAMES, (
            "baseline", "use_access_p0", "use_access_p1", "use_index_p0",
            "use_index_p1", "use_nested_p0", "use_nested_p1"))
        self.assertEqual(E.PROJECT_PROOF_SWITCHES,
                         ("-U", "--mode=all", "--level=2",
                          "--report=statistics"))
        self.assertEqual(E.PROVE_ARGS, ("-j0",))
        self.assertEqual(E.MUTABLE_FILE, "src/guarded_ops.ads")
        self.assertEqual(E.METHOD, "guard_preserving_prefix_reproof")

    def test_script_matches_the_frozen_document(self):
        pre = DOC.read_text("utf-8").split("## Observed results")[0]
        for (case, i), (st, cls) in E.MATRIX.items():
            _, ent, f, ln, col, _ = E._target(case)
            self.assertIn(f"| {case} | {ent} | {f}:{ln}:{col} | {i} | "
                          f"{st.upper()} | {cls} |", pre)
        for case, st in E.BASELINE_EXPECTED.items():
            _, _e, f, ln, col, _ = E._target(case)
            self.assertIn(f"| {case} | {f}:{ln}:{col} | {st.upper()} |", pre)
        for rel, digest in E.CORPUS_SHA256.items():
            self.assertIn(f"| `{rel}` | `{digest}` |", pre)
        for (c, i), text in E.EXPECTED_PREFIXES.items():
            self.assertIn(f"| {c} | {i} | `{json.dumps(text)}` |", pre)
        for c, x in E.EXPECTED_EXTRACTION.items():
            sl, sc, el, ec = x["span"]
            self.assertIn(f"| {c} | {sl}:{sc} | {el}:{ec} |", pre)
            self.assertIn(json.dumps(list(x["conjuncts"])), pre)
        for f, ln, col in E.NESTED_LOCATIONS:
            self.assertIn(f"`{f}:{ln}:{col}`", pre)
        self.assertIn(E.VALIDATED, pre)
        self.assertIn(E.NOT_VALIDATED, pre)

    def test_corpus_hashes(self):
        self.assertEqual(E.T12.tree_digest(E.CORPUS), E.CORPUS_SHA256)
        for rel, digest in E.CORPUS_SHA256.items():
            self.assertEqual(hashlib.sha256((E.CORPUS / rel).read_bytes())
                             .hexdigest(), digest)

    def test_vocabulary_has_no_attribution_words(self):
        for v in E.CLASSIFICATIONS:
            for bad in ("fail", "culprit", "root"):
                self.assertNotIn(bad, v)


class PrefixPlanner(unittest.TestCase):
    def test_exact_source_prefixes_and_predecessors(self):
        expr = "X > 0 and then (Y > 0)  and  Z > 0"
        src, rng, conj = synthetic(expr, ["X > 0", "(Y > 0)", "Z > 0"])
        plan = E.plan_prefixes(src, rng, conj, [E.AND_THEN, E.AND])
        self.assertEqual([p["prefix_text"] for p in plan],
                         ["X > 0", "X > 0 and then (Y > 0)", expr])
        self.assertEqual([p["conjunct_text"] for p in plan],
                         ["X > 0", "(Y > 0)", "Z > 0"])
        self.assertEqual([p["conjunct_index"] for p in plan], [0, 1, 2])
        self.assertEqual([p["predecessor_index"] for p in plan],
                         [None, 0, 1])
        self.assertEqual([p["requires_predecessor"] for p in plan],
                         [False, True, True])
        self.assertEqual([p["operators"] for p in plan],
                         [[], [E.AND_THEN], [E.AND_THEN, E.AND]])
        # original operators and spacing preserved: never and <-> and then
        self.assertIn(" and  Z", plan[2]["prefix_text"])
        self.assertNotIn("and then Z", plan[2]["prefix_text"])

    def test_deterministic(self):
        src, rng, conj = synthetic("A and then B and then C",
                                   ["A", "B", "C"])
        a = E.plan_prefixes(src, rng, conj, [E.AND_THEN, E.AND_THEN])
        b = E.plan_prefixes(src, rng, copy.deepcopy(conj),
                            (E.AND_THEN, E.AND_THEN))
        self.assertEqual(json.dumps(a), json.dumps(b))

    def test_multiline_prefix_keeps_layout(self):
        text = E.EXPECTED_PREFIXES[("Guarded_Ops.Use_Access", 1)]
        src, rng, conj = synthetic(text, ["P /= null", "P.all > 0"])
        plan = E.plan_prefixes(src, rng, conj, [E.AND_THEN])
        self.assertEqual(plan[1]["prefix_text"], text)
        self.assertEqual(plan[0]["prefix_text"], "P /= null")

    def test_refuses_malformed_input(self):
        src, rng, conj = synthetic("A and then B", ["A", "B"])
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, rng, conj, [])            # operator count
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, rng, conj, ["or else"])   # not a conjunction
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, rng, list(reversed(conj)),
                            [E.AND_THEN])                  # reordered
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, rng, [], [])
        bad = copy.deepcopy(conj)
        bad[1]["text"] = "C"                               # text vs range
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, rng, bad, [E.AND_THEN])
        with self.assertRaises(E.ExperimentStop):
            E.plan_prefixes(src, [rng[0] - 1, rng[1]], conj, [E.AND_THEN])


class SelectedOnlyRefused(unittest.TestCase):
    """Negative test (task item 20): Task 012's selected-only method is
    never scheduled for a guarded `and then` suffix."""

    SHAPES = {
        "Guarded_Ops.Use_Access": ("P /= null and then P.all > 0",
                                   ["P /= null", "P.all > 0"]),
        "Guarded_Ops.Use_Index": ("I in A'Range and then A (I) > 0",
                                  ["I in A'Range", "A (I) > 0"]),
        "Guarded_Ops.Use_Nested": ("X in 12 .. 999 and then F (F (X)) > 20",
                                   ["X in 12 .. 999", "F (F (X)) > 20"]),
    }

    def test_guarded_suffix_refused(self):
        for callee, (expr, parts) in self.SHAPES.items():
            src, rng, conj = synthetic(expr, parts)
            plan = E.plan_prefixes(src, rng, conj, [E.AND_THEN])
            for kind in ("selected_only", "suffix", "isolated"):
                with self.assertRaises(E.ProbeRefused, msg=callee):
                    E.request_probe(plan, [E.AND_THEN], kind, 1)
            rec = E.refusal_record(plan, [E.AND_THEN], callee, 1)
            self.assertEqual((rec["refused"], rec["reason"]),
                             (True, "guarded_and_then_suffix"))
            got = E.request_probe(plan, [E.AND_THEN], "prefix", 1)
            self.assertEqual(got["prefix_text"], expr)

    def test_no_plan_item_is_an_isolated_guarded_conjunct(self):
        for expr, parts in self.SHAPES.values():
            src, rng, conj = synthetic(expr, parts)
            plan = E.plan_prefixes(src, rng, conj, [E.AND_THEN])
            texts = [p["prefix_text"] for p in plan]
            self.assertNotIn(parts[1], texts)
            self.assertFalse(E.is_planned_prefix(parts[1], plan))
            for t in texts:
                self.assertTrue(t.startswith(parts[0]))

    def test_plain_and_suffix_is_also_not_a_prefix(self):
        src, rng, conj = synthetic("X > 0 and Y > 0", ["X > 0", "Y > 0"])
        plan = E.plan_prefixes(src, rng, conj, [E.AND])
        with self.assertRaises(E.ProbeRefused) as cm:
            E.request_probe(plan, [E.AND], "selected_only", 1)
        self.assertIn("not_a_prefix", str(cm.exception))

    def test_out_of_range_refused(self):
        src, rng, conj = synthetic("A and then B", ["A", "B"])
        plan = E.plan_prefixes(src, rng, conj, [E.AND_THEN])
        with self.assertRaises(E.ProbeRefused):
            E.request_probe(plan, [E.AND_THEN], "prefix", 2)

    def test_decision_requires_every_refusal(self):
        ev = good_evidence()
        ev["refusals"][2]["refused"] = False
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        ev = good_evidence()
        ev["refusals"].pop(0)
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_unplanned_scratch_pre_rejected(self):
        ev = good_evidence()
        ev["runs"][2]["scratch_pre_is_planned_prefix"] = False
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        ev = good_evidence()
        ev["runs"][2]["prefix_text"] = "P.all > 0"      # isolated suffix
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)


def o(status, matches=1, problem=None, disputed=False):
    return {"status": status, "matches": matches, "problem": problem,
            "disputed": disputed}


class Classification(unittest.TestCase):
    def test_transitions(self):
        self.assertEqual(E.classify(o(P), o(P)), E.PREFIX_PROVED)
        self.assertEqual(E.classify(o(P), o(U)), E.NEWLY_UNPROVED)
        self.assertEqual(E.classify(o(U), o(U)), E.BLOCKED)
        # conjunct 0: predecessor is conceptual TRUE
        self.assertEqual(E.classify(None, o(P)), E.PREFIX_PROVED)
        self.assertEqual(E.classify(None, o(U)), E.NEWLY_UNPROVED)

    def test_non_monotone_is_invalid(self):
        self.assertEqual(E.classify(o(U), o(P)), E.INVALID)

    def test_justified_is_invalid(self):
        self.assertEqual(E.classify(o(P), o(J)), E.INVALID)
        self.assertEqual(E.classify(o(J), o(U)), E.INVALID)
        self.assertEqual(E.classify(None, o(J)), E.INVALID)

    def test_missing_predecessor_is_invalid(self):
        self.assertEqual(E.classify({}, o(U)), E.INVALID)
        self.assertEqual(E.classify(o(None, 0, "none"), o(U)), E.INVALID)
        self.assertEqual(E.classify(o(P), {}), E.INVALID)

    def test_exactly_one_and_undisputed_required(self):
        for bad in (o(U, matches=0), o(U, matches=2),
                    o(U, disputed=True), o(U, problem="x")):
            self.assertEqual(E.classify(o(P), bad), E.INVALID)
            self.assertEqual(E.classify(bad, o(U)), E.INVALID)

    def test_nested_unproved_overrides_clean_classification(self):
        for pred, cur in ((o(P), o(U)), (o(P), o(P)), (o(U), o(U)),
                          (None, o(U))):
            self.assertEqual(E.classify(pred, cur, E.UNPROVED),
                             E.NESTED_UNPROVED)
        self.assertEqual(E.classify(o(P), o(U), E.PROVED), E.NEWLY_UNPROVED)
        # an invalid probe stays invalid
        self.assertEqual(E.classify(o(P), o(J), E.UNPROVED), E.INVALID)


class StructuralMatching(unittest.TestCase):
    def test_exactly_one_target(self):
        checks = run_checks("baseline")
        for case in E.CASES:
            r = E.match_target(checks, case)
            self.assertEqual((r["matches"], r["problem"]), (1, None))
            self.assertEqual(r["status"], E.BASELINE_EXPECTED[case])

    def test_zero_or_duplicate_target_invalid(self):
        checks = [c for c in run_checks("baseline")
                  if c.location.line != 12]
        r = E.match_target(checks, "A2")
        self.assertEqual((r["matches"], r["status"]), (0, None))
        dup = run_checks("baseline") + [target_check("A2", U)]
        self.assertEqual(E.match_target(dup, "A2")["matches"], 2)
        self.assertTrue(E.match_target(dup, "A2")["problem"])

    def test_other_rule_entity_or_column_not_matched(self):
        _, ent, f, ln, col, _ = E._target("A2")
        near = [check(ent, f, ln, col, rule="VC_RANGE_CHECK"),
                check("Guarded_Client.Other", f, ln, col),
                check(ent, f, ln, col + 1)]
        self.assertEqual(E.match_target(near, "A2")["matches"], 0)

    def test_disputed_and_justified_targets_flagged(self):
        _, ent, f, ln, col, _ = E._target("A2")
        r = E.match_target([check(ent, f, ln, col, Status.UNPROVED,
                                  disputed=True)], "A2")
        self.assertTrue(r["disputed"] and r["problem"])
        r = E.match_target([check(ent, f, ln, col, Status.JUSTIFIED)], "A2")
        self.assertEqual(r["status"], J)
        self.assertTrue(r["problem"])

    def test_message_text_is_irrelevant(self):
        a = run_checks("use_access_p1")
        b = [Check(rule=c.rule, status=c.status, location=c.location,
                   entity=c.entity, message="PROVED!!" + c.message[::-1])
             for c in a]
        self.assertEqual([E.match_target(a, x) for x in E.CASES],
                         [E.match_target(b, x) for x in E.CASES])
        self.assertEqual(E.check_inventory(a), E.check_inventory(b))


class NestedSeparation(unittest.TestCase):
    def test_nested_checks_never_counted_as_targets(self):
        inv = E.check_inventory(run_checks("use_nested_p1"))
        locs = [(r["location"]["line"], r["location"]["column"])
                for r in inv["nested"]]
        self.assertEqual(locs, [(29, 28), (29, 31)])
        for r in inv["nested"] + inv["guard"] + inv["other"]:
            self.assertFalse(E._is_target(Check(
                rule=r["rule"], status=Status(r["status"]),
                location=Location(**r["location"]), entity=r["entity"],
                message="")))

    def test_nested_inventory_expectations(self):
        for name in E.RUN_NAMES:
            self.assertEqual(E.inventory_problems(
                E.check_inventory(run_checks(name)), name), [], name)
        miss = [c for c in run_checks("use_nested_p1")
                if (c.location.line, c.location.column) != (29, 31)]
        self.assertTrue(E.inventory_problems(E.check_inventory(miss),
                                             "use_nested_p1"))
        extra = run_checks("use_nested_p0") + nested_checks()
        self.assertTrue(E.inventory_problems(E.check_inventory(extra),
                                             "use_nested_p0"))
        stray = run_checks("baseline") + [check(
            "Guarded_Ops.Use_Access", "guarded_ops.ads", 12, 20)]
        self.assertTrue(E.inventory_problems(E.check_inventory(stray),
                                             "baseline"))

    def test_unproved_nested_guard_or_other_check_is_a_problem(self):
        for extra in (
                check(E.NESTED_CALLEE, "guarded_ops.ads", 29, 28,
                      Status.UNPROVED),
                check("Guarded_Ops.Use_Index", "guarded_ops.ads", 18, 31,
                      Status.UNPROVED, rule="VC_INDEX_CHECK"),
                check("Guarded_Ops.F", "guarded_ops.ads", 25, 32,
                      Status.JUSTIFIED, rule="VC_POSTCONDITION")):
            cs = [c for c in run_checks("use_index_p1")
                  if (c.rule, c.location.line, c.location.column) !=
                  (extra.rule, extra.location.line, extra.location.column)]
            inv = E.check_inventory(cs + [extra])
            self.assertTrue(E.inventory_problems(inv, "use_index_p1"))

    def test_guard_check_absent_in_c0_only_run(self):
        cs = run_checks("use_access_p0") + [check(
            "Guarded_Ops.Use_Access", "guarded_ops.ads", 12, 30,
            rule="VC_NULL_POINTER_DEREFERENCE")]
        self.assertTrue(E.inventory_problems(E.check_inventory(cs),
                                             "use_access_p0"))

    def test_nested_unproved_run_classified_nested(self):
        ev = good_evidence()
        r = next(r for r in ev["runs"] if r["run"] == "use_nested_p1")
        r["inventory"]["nested"][0]["status"] = U
        probes = E.derive_probes(ev["runs"])
        got = {(p["case"], p["conjunct_index"]): p["classification"]
               for p in probes}
        for case in ("C1", "C2", "C3"):
            self.assertEqual(got[(case, 1)], E.NESTED_UNPROVED)
            self.assertNotEqual(got[(case, 1)], E.NEWLY_UNPROVED)
        self.assertEqual(got[("A2", 1)], E.NEWLY_UNPROVED)  # other callee
        ev["probes"] = probes
        s = E.decide(ev)
        self.assertEqual(s["verdict"], E.NOT_VALIDATED)
        self.assertEqual(s["classification_counts"][E.NESTED_UNPROVED], 3)


class DecisionRule(unittest.TestCase):
    def test_preregistered_evidence_validates(self):
        s = E.decide(good_evidence())
        self.assertEqual(s["reasons"], [])
        self.assertEqual(s["verdict"], E.VALIDATED)
        self.assertEqual((s["baseline_matches"], s["probe_observations"],
                          s["prefix_status_matches"],
                          s["classification_matches"], s["justified"],
                          s["disputed"], s["gnatprove_runs"]),
                         (9, 18, 18, 18, 0, 0, 7))

    def test_any_flipped_prefix_status_not_validated(self):
        n = 0
        for (case, i) in E.MATRIX:
            callee = E._target(case)[5]
            ev = good_evidence()
            cur = next(t for r in ev["runs"]
                       if r["run"] == E.run_name(callee, i)
                       for t in r["targets"] if t["case"] == case)
            set_target(ev, E.run_name(callee, i), case,
                       status=P if cur["status"] == U else U)
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED,
                             (case, i))
            n += 1
        self.assertEqual(n, 18)

    def test_any_flipped_baseline_not_validated(self):
        for case in E.CASES:
            ev = good_evidence()
            want = E.BASELINE_EXPECTED[case]
            set_target(ev, "baseline", case, status=P if want == U else U)
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_untouched_target_change_not_validated(self):
        ev = good_evidence()
        set_target(ev, "use_access_p0", "B1", status=U)
        s = E.decide(ev)
        self.assertEqual(s["verdict"], E.NOT_VALIDATED)
        self.assertTrue(any("untouched" in r for r in s["reasons"]))

    def test_justified_disputed_zero_duplicate_rejected(self):
        for kw in ({"status": J, "problem": "JUSTIFIED target"},
                   {"disputed": True, "problem": "x"},
                   {"matches": 0, "status": None, "problem": "x"},
                   {"matches": 2, "status": None, "problem": "x"}):
            ev = good_evidence()
            set_target(ev, "use_index_p1", "B2", **kw)
            s = E.decide(ev)
            self.assertEqual(s["verdict"], E.NOT_VALIDATED, kw)
        ev = good_evidence()
        set_target(ev, "use_index_p1", "B2", status=J, problem="J")
        self.assertEqual(E.decide(ev)["justified"], 1)

    def test_tampered_probe_records_rejected(self):
        ev = good_evidence()
        ev["probes"][3]["classification"] = E.PREFIX_PROVED
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_missing_or_extra_runs_rejected(self):
        for mutate in (lambda ev: ev["runs"].pop(3),
                       lambda ev: ev["runs"].append(
                           {**ev["runs"][1], "run": "extra"}),
                       lambda ev: ev["runs"].append(ev["runs"][1])):
            ev = good_evidence()
            mutate(ev)
            ev["probes"] = E.derive_probes(ev["runs"])
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        self.assertEqual(E.decide({})["verdict"], E.NOT_VALIDATED)

    def test_gate_failures_rejected(self):
        for key in ("gate_problems", "reparse_problems",
                    "trust_hits_introduced", "inventory_problems"):
            for idx in (0, 3):
                ev = good_evidence()
                ev["runs"][idx][key] = ["x"]
                ev["probes"] = E.derive_probes(ev["runs"])
                self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
                ev = good_evidence()
                del ev["runs"][idx][key]
                ev["probes"] = E.derive_probes(ev["runs"])
                self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        for mutate in (lambda ev: ev.update(corpus_unchanged=False),
                       lambda ev: ev["trust_scan"].update(
                           original_hits=[{"category": "pragma_assume"}]),
                       lambda ev: ev.pop("trust_scan")):
            ev = good_evidence()
            mutate(ev)
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_gate_failed_run_is_never_classified_as_evidence(self):
        ev = good_evidence()
        ev["runs"][2]["gate_problems"] = ["changed bytes outside range"]
        probes = E.derive_probes(ev["runs"])
        self.assertEqual({p["classification"] for p in probes
                          if p["run"] == "use_access_p1"}, {E.INVALID})


class DeterministicEvidence(unittest.TestCase):
    def test_order_independent_serialisation(self):
        a = good_evidence()
        b = copy.deepcopy(a)
        b["runs"].reverse()
        for r in b["runs"]:
            r["targets"].reverse()
        b["probes"].reverse()
        self.assertEqual(E.canonical(a), E.canonical(b))
        doc = json.loads(E.canonical(b))
        self.assertEqual([r["run"] for r in doc["runs"]], list(E.RUN_NAMES))
        self.assertEqual([(p["case"], p["conjunct_index"])
                          for p in doc["probes"]], list(E.MATRIX))

    def test_no_timestamps_absolute_paths_or_prose(self):
        ev = good_evidence()
        text = E.canonical({**ev, "summary": E.decide(ev)})
        self.assertNotIn(str(support.REPO), text)
        self.assertNotIn("might fail", text)
        self.assertNotIn('"message"', text)
        src = SCRIPT.read_text("utf-8")
        for bad in ("uuid", "datetime", ".message"):
            self.assertNotIn(bad, src)


class SourceIsolation(unittest.TestCase):
    ORIG = (b"x\n   with Pre    => P /= null\n"
            b"                  and then P.all > 0,\n end;\n")

    def item(self, upto: bytes):
        es = self.ORIG.index(b"P /=")
        return (es, self.ORIG.index(b",")), {
            "prefix_range": [es, self.ORIG.index(upto) + len(upto)]}

    def test_prefix_blanking_keeps_prefix_bytes_and_layout(self):
        (es, ee), it = self.item(b"null")
        out = E.prefix_source(self.ORIG, (es, ee), it)
        self.assertEqual(len(out), len(self.ORIG))
        self.assertEqual(E.T12.line_starts(out),
                         E.T12.line_starts(self.ORIG))
        self.assertEqual(out[es:it["prefix_range"][1]],
                         self.ORIG[es:it["prefix_range"][1]])
        self.assertNotIn(b"P.all", out)
        self.assertEqual(out.splitlines()[2].strip(), b",")

    def test_full_prefix_is_identity(self):
        (es, ee), it = self.item(b"P.all > 0")
        self.assertEqual(E.prefix_source(self.ORIG, (es, ee), it), self.ORIG)

    def test_non_prefix_range_refused(self):
        (es, ee), _ = self.item(b"null")
        with self.assertRaises(E.ExperimentStop):
            E.prefix_source(self.ORIG, (es, ee),
                            {"prefix_range": [es + 3, ee]})

    def test_isolation_gate(self):
        (es, ee), it = self.item(b"null")
        out = E.prefix_source(self.ORIG, (es, ee), it)
        o = {rel: (E.CORPUS / rel).read_bytes() for rel in E.COPIED_FILES}
        o[E.MUTABLE_FILE] = self.ORIG
        s = dict(o)
        s[E.MUTABLE_FILE] = out
        allowed = {E.MUTABLE_FILE: [(it["prefix_range"][1], ee)]}
        inv = E.T12.mutation_inventory(o, s, allowed)
        self.assertEqual(E.isolation_problems(inv, False), [])
        # a full-Pre run must be byte-identical
        self.assertTrue(E.isolation_problems(inv, True))
        # another changed file, or a byte outside the range, is rejected
        s2 = dict(s)
        s2["src/guarded_client.adb"] = s2["src/guarded_client.adb"] + b" "
        self.assertTrue(E.isolation_problems(
            E.T12.mutation_inventory(o, s2, allowed), False))
        s3 = dict(s)
        s3[E.MUTABLE_FILE] = b"y" + out[1:]
        self.assertTrue(E.isolation_problems(
            E.T12.mutation_inventory(o, s3, allowed), False))
        same = E.T12.mutation_inventory(o, dict(o), {})
        self.assertEqual(E.isolation_problems(same, True), [])


class ScratchRootSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t013-")
        self.base = Path(self.tmp.name)
        self.root = self.base / "task013-guarded-reproof"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_root(self):
        self.assertEqual(E.SCRATCH_ROOT.relative_to(support.REPO).as_posix(),
                         "diagnostics/obj/task013-guarded-reproof")
        self.assertNotEqual(E.SCRATCH_ROOT, E.T12.SCRATCH_ROOT)

    def test_refuses_outside_root_itself_and_symlinks(self):
        outside = self.base / "victim"
        outside.mkdir()
        (outside / "keep").write_text("x")
        for bad in (outside, self.root, self.base, Path("/"), support.REPO,
                    E.CORPUS / "src", self.root / ".." / "victim"):
            with self.assertRaises(E.ExperimentStop, msg=str(bad)):
                E.T12.reset_dir(bad, self.root)
        link = self.root / "link"
        link.symlink_to(outside, target_is_directory=True)
        for bad in (link, link / "sub"):
            with self.assertRaises(E.ExperimentStop):
                E.T12.reset_dir(bad, self.root)
        self.assertTrue((outside / "keep").is_file())

    def test_copies_real_files_and_refuses_symlinked_corpus(self):
        d = E.T12.reset_dir(self.root / "run", self.root)
        E.T12.copy_corpus(E.CORPUS, d, files=E.COPIED_FILES, root=self.root)
        for rel in E.COPIED_FILES:
            p = d / rel
            self.assertTrue(p.is_file() and not p.is_symlink())
            self.assertEqual(p.read_bytes(), (E.CORPUS / rel).read_bytes())
        src = self.base / "linked"
        (src / "src").mkdir(parents=True)
        (src / "src" / "a.ads").symlink_to(E.CORPUS / E.MUTABLE_FILE)
        with self.assertRaises(E.ExperimentStop):
            E.T12.copy_corpus(src, E.T12.reset_dir(self.root / "c2",
                                                   self.root),
                              files=("src/a.ads",), root=self.root)

    def test_experiment_always_passes_its_own_root(self):
        """Every destructive Task 012 helper call names SCRATCH_ROOT, so
        the Task 012 default root can never be used by Task 013."""
        tree = ast.parse(SCRIPT.read_text("utf-8"))
        n = 0
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("reset_dir", "copy_corpus")):
                args = [ast.unparse(a) for a in node.args] + [
                    ast.unparse(k.value) for k in node.keywords
                    if k.arg == "root"]
                self.assertIn("SCRATCH_ROOT", args, ast.unparse(node))
                n += 1
        # reset_dir (run dir), reset_dir (obj/), copy_corpus
        self.assertEqual(n, 3)


class TrustAndBoundaries(unittest.TestCase):
    def test_forbidden_trust_classification_includes_axiom(self):
        C = E.T12.classify_trust
        for rec, cat in (
                (("pragma", "Assume", ["X > 0"]), "pragma_assume"),
                (("pragma", "Annotate", ["GNATprove", "False_Positive"]),
                 "annotate_justification_or_skip"),
                (("pragma", "Annotate", ["GNATprove", "Intentional"]),
                 "annotate_justification_or_skip"),
                (("aspect", "Annotate", ["(GNATprove, Axiom)"]),
                 "annotate_justification_or_skip"),
                (("pragma", "Annotate", ["GNATprove", "Skip_Proof"]),
                 "annotate_justification_or_skip"),
                (("pragma", "Annotate", ["GNATprove",
                                         "Skip_Flow_And_Proof"]),
                 "annotate_justification_or_skip"),
                (("pragma", "Suppress", ["All_Checks"]), "suppress"),
                (("pragma", "Suppress_All", []), "suppress"),
                (("aspect", "SPARK_Mode", ["Off"]), "spark_mode_off"),
                (("aspect", "Import", ["True"]), "unchecked_axiom_mechanism"),
                (("ghost_decl_without_body", "X.Lemma", []),
                 "bodyless_ghost_subprogram")):
            self.assertEqual(C(rec), cat, rec)
        self.assertIsNone(C(("aspect", "SPARK_Mode", ["On"])))

    def test_task012_script_unchanged_and_not_a_product_module(self):
        pkg = support.DIAGNOSTICS / "spark_refine_diagnostics"
        for p in sorted(pkg.glob("*.py")):
            src = p.read_text("utf-8")
            self.assertNotIn("guarded_reproof", src, p.name)
            self.assertNotIn("task013", src, p.name)
        self.assertEqual(E.T12.SCRATCH_ROOT.name, "task012-conjunct-reproof")

    def test_failed_conjunct_policy_unchanged(self):
        from spark_refine_diagnostics.semantic import ATTRIBUTION
        self.assertEqual(ATTRIBUTION, "not_provided_by_gnatprove")


def _lal_available() -> str | None:
    try:
        import libadalang  # noqa: F401
    except Exception as exc:
        return f"libadalang not importable ({type(exc).__name__})"
    return None


_SKIP = _lal_available()


@unittest.skipIf(_SKIP, _SKIP or "")
class LibadalangGuardedExtraction(unittest.TestCase):
    """Extraction, exact prefixes and the scratch transformation on a
    TEMPORARY scratch root (no GNATprove)."""

    def setUp(self):
        self.before = E.T12.tree_digest(E.CORPUS)
        self.tmp = tempfile.TemporaryDirectory(prefix="t013-lal-")
        self.root = Path(self.tmp.name) / "task013-guarded-reproof"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()
        self.assertEqual(E.T12.tree_digest(E.CORPUS), self.before)

    def _extract(self, callee):
        return E.extract_pre(E.CORPUS / E.MUTABLE_FILE, callee)

    def _check_family(self, callee):
        want = E.EXPECTED_EXTRACTION[callee]
        p = self._extract(callee)
        self.assertEqual(tuple(c["text"] for c in p["conjuncts"]),
                         want["conjuncts"])
        self.assertEqual(tuple(p["operators"]), want["operators"])
        self.assertEqual(tuple(p["span"].values()), want["span"])
        data = (E.CORPUS / E.MUTABLE_FILE).read_bytes()
        plan = E.plan_prefixes(data, p["range"], p["conjuncts"],
                               p["operators"])
        for it in plan:
            self.assertEqual(it["prefix_text"],
                             E.EXPECTED_PREFIXES[(callee,
                                                  it["conjunct_index"])])
        self.assertEqual(plan[-1]["prefix_text"], p["text"])

    def test_access_null_case(self):
        self._check_family("Guarded_Ops.Use_Access")

    def test_array_index_case(self):
        self._check_family("Guarded_Ops.Use_Index")

    def test_nested_call_case(self):
        self._check_family("Guarded_Ops.Use_Nested")

    def test_same_decomposition_as_task009(self):
        lal, unit = E.T12.parse_unit(E.CORPUS / E.MUTABLE_FILE)
        from spark_refine_diagnostics.semantic_lal import LalBackend
        for callee in E.CALLEES:
            d = next(d for d in unit.root.findall(lal.BasicSubpDecl)
                     if d.p_fully_qualified_name == callee)
            be = E.T12._decomposer(lal)
            self.assertIs(type(be).conjuncts, LalBackend.conjuncts)
            self.assertEqual(
                [c.text for c in be.conjuncts(d.p_get_aspect("Pre").value)],
                list(E.EXPECTED_EXTRACTION[callee]["conjuncts"]))

    def test_every_scratch_pre_reextracts_to_the_planned_prefix(self):
        _, original, pres, plans = E._preconditions()
        n = 0
        with mock.patch.object(E, "SCRATCH_ROOT", self.root):
            for callee in E.CALLEES:
                for it in plans[callee]:
                    rec, d = E.make_run(original, pres, plans, callee,
                                        it["conjunct_index"], [])
                    n += 1
                    self.assertEqual(d.parent, self.root.resolve())
                    self.assertEqual(rec["gate_problems"], [], rec)
                    self.assertEqual(rec["reparse_problems"], [], rec)
                    self.assertTrue(rec["scratch_pre_is_planned_prefix"])
                    self.assertEqual(rec["trust_hits_introduced"], [])
                    got = E.extract_pre(d / E.MUTABLE_FILE, callee)
                    self.assertEqual(got["text"], it["prefix_text"])
                    self.assertEqual(got["operators"], it["operators"])
                    # no guarded conjunct is ever the whole scratch Pre
                    self.assertNotEqual(got["text"],
                                        plans[callee][-1]["conjunct_text"])
                    self.assertEqual(rec["mutation"]["changed_file_count"],
                                     0 if rec["full_pre"] else 1)
            rec, d = E.make_run(original, pres, plans, None, None, [])
            self.assertEqual(rec["gate_problems"], [])
        self.assertEqual(n, 6)

    def test_reparse_rejects_isolated_guarded_suffix(self):
        """If a scratch Pre were the isolated guarded conjunct (Task 012
        selected-only), the reparse gate flags it as unplanned."""
        _, original, pres, plans = E._preconditions()
        d = self.root / "bad"
        E.T12.copy_corpus(E.CORPUS, d, files=E.COPIED_FILES, root=self.root)
        target = d / E.MUTABLE_FILE
        s, e = pres["Guarded_Ops.Use_Access"]["range"]
        target.write_bytes(E.T12.overlay(target.read_bytes(), s, e,
                                         "P.all > 0"))
        item = plans["Guarded_Ops.Use_Access"][1]
        probs, planned = E.reparse_problems(
            target, "Guarded_Ops.Use_Access", item,
            plans["Guarded_Ops.Use_Access"],
            {c: pres[c] for c in E.CALLEES
             if c != "Guarded_Ops.Use_Access"})
        self.assertTrue(probs)
        self.assertFalse(planned)

    def test_trust_scan_clean_and_detects_additions(self):
        self.assertEqual(E.trust_scan(E.CORPUS), [])
        d = self.root / "t"
        E.T12.copy_corpus(E.CORPUS, d, files=E.COPIED_FILES, root=self.root)
        body = d / "src" / "guarded_client.adb"
        body.write_text(body.read_text().replace(
            "      Use_Access (P);\n   end A3_No_Guard;",
            "      pragma Assume (P /= null);\n      Use_Access (P);\n"
            "   end A3_No_Guard;"))
        spec = d / "src" / "guarded_ops.ads"
        spec.write_text(spec.read_text().replace(
            "package Guarded_Ops with SPARK_Mode is",
            "package Guarded_Ops with SPARK_Mode is\n"
            "   pragma Annotate (GNATprove, Axiom);"))
        cats = sorted(h["category"] for h in E.trust_scan(d))
        self.assertEqual(cats, ["annotate_justification_or_skip",
                                "pragma_assume"])
