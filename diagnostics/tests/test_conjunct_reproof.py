"""Task 012: per-conjunct GNATprove re-proof EXPERIMENT (scripts only).

Part 1 (always runs; no Libadalang, no GNATprove): the pre-registered
matrix, structural VC matching, the frozen decision rule, deterministic
evidence, scratch-root safety, the mutation inventory, the forbidden-trust
classification and the absence of any message-text dependence.
Part 2 (skipped unless `import libadalang` works): Pre extraction and the
scratch transformation on a temporary copy of the Task 009 corpus. No
GNATprove: the six proof runs are the CI step "Task 012: per-conjunct
re-proof experiment" (scripts/conjunct_reproof_experiment.py).
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

SCRIPT = support.DIAGNOSTICS / "scripts" / "conjunct_reproof_experiment.py"
PKG = support.DIAGNOSTICS / "spark_refine_diagnostics"
DOC = (support.REPO / "docs" / "tasks"
       / "012-per-conjunct-reproof-experiment.md")


def _load():
    spec = importlib.util.spec_from_file_location("conjunct_reproof", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E = _load()
P, U, J = E.PROVED, E.UNPROVED, E.JUSTIFIED


def check(entity, line, status=Status.UNPROVED, rule="VC_PRECONDITION",
          file="client.adb", column=10, message="precondition might fail",
          disputed=False):
    return Check(rule=rule, status=status,
                 location=Location(file, line, column),
                 entity=entity, message=message, disputed=disputed)


def outcome(entity, status):
    t = next(t for t in E.TARGETS if t[0] == entity)
    return {"entity": entity, "status": status, "matches": 1,
            "problem": None,
            "location": {"file": t[1], "line": t[2], "column": t[3]}}


def good_evidence() -> dict:
    """An evidence dict exactly matching the pre-registration."""
    probes = []
    for callee, conj in E.EXPECTED_CONJUNCTS.items():
        for idx, text in enumerate(conj):
            probes.append({
                "callee": callee, "conjunct_index": idx,
                "conjunct_text": text,
                "mutation": {"changed_files": ["src/ops.ads"],
                             "changed_file_count": 1,
                             "changed_range_count": 1,
                             "gate_problems": []},
                "reparse_problems": [], "trust_hits_introduced": [],
                "outcomes": [outcome(ent, E.GROUND_TRUTH[(c, i, ent)])
                             for (c, i, ent) in E.GROUND_TRUTH
                             if (c, i) == (callee, idx)]})
    return {"baseline": [outcome(e, U) for e in E.BASELINE_EXPECTED],
            "baseline_isolation": {"changed_file_count": 0, "problems": []},
            "probes": probes,
            "trust_scan": {"original_hits": [], "baseline_hits": []},
            "corpus_unchanged": True}


def flip(status):
    return P if status == U else U


class PreRegisteredMatrix(unittest.TestCase):
    def test_matrix_is_the_documented_matrix(self):
        self.assertEqual(E.GROUND_TRUTH, {
            ("Ops.Op", 0, "Client.Second_Fails"): P,
            ("Ops.Op", 0, "Client.First_Fails"): U,
            ("Ops.Op", 0, "Client.Both_Fail"): U,
            ("Ops.Op", 1, "Client.Second_Fails"): U,
            ("Ops.Op", 1, "Client.First_Fails"): P,
            ("Ops.Op", 1, "Client.Both_Fail"): U,
            ("Ops.Op3", 0, "Client.Middle_Fails"): P,
            ("Ops.Op3", 1, "Client.Middle_Fails"): U,
            ("Ops.Op3", 2, "Client.Middle_Fails"): P})

    def test_nine_observations_four_proved_five_unproved(self):
        vals = list(E.GROUND_TRUTH.values())
        self.assertEqual(len(vals), 9)
        self.assertEqual((vals.count(P), vals.count(U), vals.count(J)),
                         (4, 5, 0))

    def test_targets_extraction_baseline_and_runs(self):
        self.assertEqual(E.TARGETS, (
            ("Client.Second_Fails", "client.adb", 7, 10, "Ops.Op"),
            ("Client.First_Fails", "client.adb", 12, 10, "Ops.Op"),
            ("Client.Both_Fail", "client.adb", 17, 10, "Ops.Op"),
            ("Client.Middle_Fails", "client.adb", 22, 10, "Ops.Op3")))
        self.assertEqual(E.EXPECTED_CONJUNCTS,
                         {"Ops.Op": ("X > 0", "Y > 0"),
                          "Ops.Op3": ("X > 0", "Y > 0", "Z > 0")})
        self.assertEqual(E.BASELINE_EXPECTED,
                         {t[0]: U for t in E.TARGETS})
        runs = 1 + sum(len(c) for c in E.EXPECTED_CONJUNCTS.values())
        self.assertEqual(runs, 6)
        self.assertEqual(E.DISCRIMINATION, {"Client.First_Fails": [U, P],
                                            "Client.Both_Fail": [U, U]})
        self.assertEqual(E.PROJECT_PROOF_SWITCHES,
                         ("-U", "--mode=all", "--level=2",
                          "--report=statistics"))
        self.assertEqual(E.PROVE_ARGS, ("-j0",))
        self.assertEqual(E.COPIED_FILES,
                         ("experiment.gpr", "src/client.adb",
                          "src/client.ads", "src/ops.adb", "src/ops.ads"))
        self.assertEqual(E.MUTABLE_FILE, "src/ops.ads")

    def test_script_matches_the_preregistration_document(self):
        """The script's constants equal the frozen document's tables."""
        pre = DOC.read_text("utf-8").split("## Observed results")[0]
        for (callee, idx, ent), st in E.GROUND_TRUTH.items():
            if callee == "Ops.Op":
                t = next(t for t in E.TARGETS if t[0] == ent)
                row = f"| {ent} | {t[1]}:{t[2]}:{t[3]} | {st.upper()} |"
            else:
                row = (f"| {idx} | `{E.EXPECTED_CONJUNCTS[callee][idx]}` | "
                       f"{st.upper()} |")
            self.assertIn(row, pre)
        for ent, (_, f, ln, col, _c) in zip(E.BASELINE_EXPECTED, E.TARGETS):
            self.assertIn(f"| {ent} | {f}:{ln}:{col} | UNPROVED |", pre)
        for rel, digest in E.CORPUS_SHA256.items():
            self.assertIn(f"| `{rel}` | `{digest}` |", pre)
        self.assertIn('Ops.Op   ["X > 0", "Y > 0"]', pre)
        self.assertIn('Ops.Op3  ["X > 0", "Y > 0", "Z > 0"]', pre)

    def test_corpus_sha256_matches_task009_snapshot(self):
        snap = json.loads((E.CORPUS / "snapshot.json").read_text("utf-8"))
        self.assertEqual({k: v["sha256"] for k, v in
                          snap["sources"].items()}, E.CORPUS_SHA256)
        for rel, digest in E.CORPUS_SHA256.items():
            self.assertEqual(hashlib.sha256((E.CORPUS / rel).read_bytes())
                             .hexdigest(), digest)


class StructuralMatching(unittest.TestCase):
    def test_exactly_one_match(self):
        checks = [check("Client.First_Fails", 12, Status.PROVED),
                  check("Client.Both_Fail", 17),
                  # same line, other rule / entity / column: not matched
                  check("Client.First_Fails", 12, rule="VC_OVERFLOW_CHECK"),
                  check("Client.Other", 12),
                  check("Client.First_Fails", 12, column=11)]
        o = E.match_target(checks, "Client.First_Fails", "client.adb", 12, 10)
        self.assertEqual(o, {"entity": "Client.First_Fails",
                             "location": {"file": "client.adb", "line": 12,
                                          "column": 10},
                             "status": "proved", "matches": 1,
                             "problem": None})

    def test_zero_matches_rejected(self):
        o = E.match_target([check("Client.Both_Fail", 17)],
                           "Client.First_Fails", "client.adb", 12, 10)
        self.assertEqual((o["matches"], o["status"]), (0, None))
        self.assertTrue(o["problem"])

    def test_duplicate_matches_rejected_not_picked(self):
        checks = [check("Client.First_Fails", 12, Status.PROVED),
                  check("Client.First_Fails", 12, Status.UNPROVED)]
        o = E.match_target(checks, "Client.First_Fails", "client.adb", 12, 10)
        self.assertEqual((o["matches"], o["status"]), (2, None))
        self.assertTrue(o["problem"])

    def test_justified_and_disputed_reported_structurally(self):
        o = E.match_target([check("Client.Both_Fail", 17, Status.JUSTIFIED)],
                           "Client.Both_Fail", "client.adb", 17, 10)
        self.assertEqual(o["status"], "justified")
        o = E.match_target([check("Client.Both_Fail", 17, disputed=True)],
                           "Client.Both_Fail", "client.adb", 17, 10)
        self.assertTrue(o["problem"])

    def test_read_outcomes_keeps_every_occurrence(self):
        checks = [check(t[0], t[2]) for t in E.TARGETS]
        self.assertEqual([o["entity"] for o in
                          E.read_outcomes(checks, "Ops.Op")],
                         ["Client.Second_Fails", "Client.First_Fails",
                          "Client.Both_Fail"])
        self.assertEqual(len(E.read_outcomes(checks)), 4)

    def test_no_english_message_dependence(self):
        """Status never depends on message text (any message, same result)
        and the script never reads a message/level/severity field."""
        for msg in ("precondition might fail", "precondition proved", "",
                    "conjunct 1 failed: Y > 0"):
            o = E.match_target([check("Client.Both_Fail", 17, message=msg)],
                               "Client.Both_Fail", "client.adb", 17, 10)
            self.assertEqual(o["status"], "unproved")
        src = SCRIPT.read_text("utf-8")
        attrs = {n.attr for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Attribute)}
        self.assertFalse({"message", "sarif_level", "spark_severity"}
                         & attrs)
        self.assertNotIn("import re\n", src)


class DecisionRule(unittest.TestCase):
    def test_exact_expected_matrix_validated(self):
        s = E.decide(good_evidence())
        self.assertEqual(s["verdict"], E.VALIDATED, s["reasons"])
        self.assertEqual((s["baseline_matches"], s["probe_observations"],
                          s["proved"], s["unproved"], s["justified"],
                          s["ground_truth_matches"]), (4, 9, 4, 5, 0, 9))
        self.assertEqual(s["reasons"], [])
        self.assertTrue(s["discrimination"]["distinguished"])
        self.assertEqual(s["discrimination"]["signatures"],
                         {"Client.First_Fails": [U, P],
                          "Client.Both_Fail": [U, U]})

    def test_any_flipped_probe_result_not_validated(self):
        base = good_evidence()
        n = 0
        for pi, p in enumerate(base["probes"]):
            for oi in range(len(p["outcomes"])):
                ev = copy.deepcopy(base)
                o = ev["probes"][pi]["outcomes"][oi]
                o["status"] = flip(o["status"])
                s = E.decide(ev)
                self.assertEqual(s["verdict"], E.NOT_VALIDATED)
                self.assertEqual(s["ground_truth_matches"], 8)
                n += 1
        self.assertEqual(n, 9)

    def test_any_flipped_baseline_not_validated(self):
        for i in range(4):
            ev = good_evidence()
            ev["baseline"][i]["status"] = P
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_missing_observation_not_validated(self):
        for pi in range(5):
            ev = good_evidence()
            ev["probes"][pi]["outcomes"].pop()
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        ev = good_evidence()
        ev["probes"].pop()
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        ev = good_evidence()
        ev["baseline"].pop()
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        self.assertEqual(E.decide({})["verdict"], E.NOT_VALIDATED)

    def test_justified_rejected(self):
        ev = good_evidence()
        ev["probes"][0]["outcomes"][1]["status"] = J   # was unproved
        s = E.decide(ev)
        self.assertEqual((s["verdict"], s["justified"]),
                         (E.NOT_VALIDATED, 1))

    def test_zero_or_duplicate_match_rejected(self):
        for n in (0, 2):
            ev = good_evidence()
            ev["probes"][0]["outcomes"][0].update(matches=n, status=None,
                                                  problem="x")
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        ev = good_evidence()
        ev["probes"][0]["outcomes"].append(
            copy.deepcopy(ev["probes"][0]["outcomes"][0]))
        self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_source_isolation_failure_not_validated(self):
        for mutate in (
                lambda p: p["mutation"].update(gate_problems=["x"]),
                lambda p: p["mutation"].pop("gate_problems"),
                lambda p: p.update(reparse_problems=["x"]),
                lambda p: p.update(trust_hits_introduced=[{"c": 1}])):
            ev = good_evidence()
            mutate(ev["probes"][2])
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)
        for mutate in (
                lambda ev: ev["baseline_isolation"].update(
                    changed_file_count=1),
                lambda ev: ev.update(corpus_unchanged=False),
                lambda ev: ev["trust_scan"].update(
                    original_hits=[{"category": "suppress"}])):
            ev = good_evidence()
            mutate(ev)
            self.assertEqual(E.decide(ev)["verdict"], E.NOT_VALIDATED)

    def test_discrimination_pair_signature(self):
        ev = good_evidence()
        # First_Fails made to look like Both_Fail: no added discrimination
        for p in ev["probes"]:
            for o in p["outcomes"]:
                if o["entity"] == "Client.First_Fails":
                    o["status"] = U
        s = E.decide(ev)
        self.assertFalse(s["discrimination"]["distinguished"])
        self.assertEqual(s["verdict"], E.NOT_VALIDATED)


class DeterministicEvidence(unittest.TestCase):
    def test_order_independent_serialisation(self):
        a = good_evidence()
        b = copy.deepcopy(a)
        b["probes"].reverse()
        for p in b["probes"]:
            p["outcomes"].reverse()
        b["baseline"].reverse()
        self.assertEqual(E.canonical(a), E.canonical(b))
        doc = json.loads(E.canonical(b))
        self.assertEqual([(p["callee"], p["conjunct_index"])
                          for p in doc["probes"]],
                         [("Ops.Op", 0), ("Ops.Op", 1), ("Ops.Op3", 0),
                          ("Ops.Op3", 1), ("Ops.Op3", 2)])
        self.assertEqual([o["entity"] for o in doc["baseline"]],
                         [t[0] for t in E.TARGETS])

    def test_no_timestamps_absolute_paths_or_prose(self):
        text = E.canonical({**good_evidence(),
                            "summary": E.decide(good_evidence())})
        self.assertNotIn(str(support.REPO), text)
        self.assertNotIn("might fail", text)
        src = SCRIPT.read_text("utf-8")
        self.assertNotIn("uuid", src)
        self.assertNotIn("datetime", src)


class ScratchRootSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="t012-")
        self.base = Path(self.tmp.name)
        self.root = self.base / "task012-conjunct-reproof"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_refuses_outside_the_root(self):
        outside = self.base / "victim"
        outside.mkdir()
        (outside / "keep").write_text("x")
        for bad in (outside, self.root, self.base, self.root / ".." /
                    "victim", Path("/"), support.REPO,
                    E.CORPUS / "src"):
            with self.assertRaises(E.ExperimentStop, msg=str(bad)):
                E.reset_dir(bad, self.root)
        self.assertTrue((outside / "keep").is_file())

    def test_refuses_symlink_escape(self):
        outside = self.base / "victim"
        outside.mkdir()
        (outside / "keep").write_text("x")
        link = self.root / "link"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(E.ExperimentStop):
            E.reset_dir(link, self.root)
        with self.assertRaises(E.ExperimentStop):
            E.reset_dir(link / "sub", self.root)   # resolves outside
        self.assertTrue((outside / "keep").is_file())

    def test_resets_inside_the_root(self):
        d = self.root / "run"
        d.mkdir()
        (d / "old").write_text("x")
        E.reset_dir(d, self.root)
        self.assertEqual(list(d.iterdir()), [])

    def test_copies_real_files_not_symlinks(self):
        d = E.reset_dir(self.root / "copy", self.root)
        E.copy_corpus(E.CORPUS, d, root=self.root)
        for rel in E.COPIED_FILES:
            p = d / rel
            self.assertTrue(p.is_file() and not p.is_symlink())
            self.assertEqual(p.read_bytes(), (E.CORPUS / rel).read_bytes())
        self.assertFalse((d / "results").exists())
        self.assertFalse((d / "obj").exists())
        src = self.base / "src_with_link"
        (src / "src").mkdir(parents=True)
        (src / "src" / "a.ads").symlink_to(E.CORPUS / "src" / "ops.ads")
        with self.assertRaises(E.ExperimentStop):
            E.copy_corpus(src, E.reset_dir(self.root / "c2", self.root),
                          files=("src/a.ads",), root=self.root)

    def test_default_root_is_the_gitignored_obj_dir(self):
        self.assertEqual(E.SCRATCH_ROOT.relative_to(support.REPO).as_posix(),
                         "diagnostics/obj/task012-conjunct-reproof")


class MutationInventory(unittest.TestCase):
    ORIG = b"a\nwith Pre => X > 0\n   and Y > 0,\nend;\n"

    def trees(self, ops):
        o = {rel: (E.CORPUS / rel).read_bytes() for rel in E.COPIED_FILES}
        o[E.MUTABLE_FILE] = self.ORIG
        s = dict(o)
        s[E.MUTABLE_FILE] = ops
        return o, s

    def rng(self):
        start = self.ORIG.index(b"X")
        return start, self.ORIG.index(b",")

    def test_overlay_preserves_length_and_newlines(self):
        s, e = self.rng()
        out = E.overlay(self.ORIG, s, e, "Y > 0")
        self.assertEqual(len(out), len(self.ORIG))
        self.assertEqual(E.line_starts(out), E.line_starts(self.ORIG))
        self.assertEqual(out, b"a\nwith Pre => Y > 0\n" + b" " * 12
                         + b",\nend;\n")
        with self.assertRaises(E.ExperimentStop):
            E.overlay(self.ORIG, s, s + 3, "X > 0")   # does not fit
        with self.assertRaises(E.ExperimentStop):
            E.overlay(self.ORIG, s, e, "X >\n0")

    def test_allowed_single_range_passes(self):
        s, e = self.rng()
        o, sc = self.trees(E.overlay(self.ORIG, s, e, "Y > 0"))
        inv = E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})
        self.assertEqual((inv["changed_files"], inv["changed_file_count"],
                          inv["changed_range_count"]),
                         ([E.MUTABLE_FILE], 1, 1))
        self.assertEqual(E.probe_isolation_problems(inv), [])

    def test_byte_outside_range_rejected(self):
        s, e = self.rng()
        bad = bytearray(E.overlay(self.ORIG, s, e, "Y > 0"))
        bad[0] = ord("b")
        o, sc = self.trees(bytes(bad))
        inv = E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})
        self.assertTrue(E.probe_isolation_problems(inv))

    def test_other_file_or_length_or_no_change_rejected(self):
        s, e = self.rng()
        o, sc = self.trees(E.overlay(self.ORIG, s, e, "Y > 0"))
        sc["src/client.adb"] = sc["src/client.adb"] + b" "
        inv = E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})
        self.assertIn("src/client.adb", inv["changed_files"])
        self.assertTrue(E.probe_isolation_problems(inv))
        o, sc = self.trees(self.ORIG + b"\n")
        self.assertTrue(E.probe_isolation_problems(
            E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})))
        o, sc = self.trees(self.ORIG)      # nothing changed: not a probe
        self.assertTrue(E.probe_isolation_problems(
            E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})))
        o, sc = self.trees(self.ORIG.replace(b"\n   and", b"    and"))
        self.assertTrue(E.probe_isolation_problems(
            E.mutation_inventory(o, sc, {E.MUTABLE_FILE: [(s, e)]})))

    def test_identical_copy_has_no_changes(self):
        o, sc = self.trees(self.ORIG)
        inv = E.mutation_inventory(o, sc, {})
        self.assertEqual((inv["changed_file_count"], inv["problems"]),
                         (0, []))

    def test_plain_source_requirement(self):
        E.require_plain("x", self.ORIG)
        for bad in (b"a\tb", b"a\r\nb", "é".encode()):
            with self.assertRaises(E.ExperimentStop):
                E.require_plain("x", bad)


class ForbiddenTrust(unittest.TestCase):
    def test_forbidden_records(self):
        cases = {
            ("pragma", "Assume", ("X > 0",)): "pragma_assume",
            ("pragma", "assume", ("X > 0", '"why"')): "pragma_assume",
            ("pragma", "Annotate",
             ("GNATprove", "False_Positive", '"x"', '"y"')):
                "annotate_justification_or_skip",
            ("pragma", "Annotate", ("GNATprove", "Intentional", '"x"')):
                "annotate_justification_or_skip",
            ("pragma", "Annotate", ("GNATprove", "Axiom", '"reason"')):
                "annotate_justification_or_skip",
            ("aspect", "Annotate", ("(GNATprove, Axiom, ...)",)):
                "annotate_justification_or_skip",
            ("aspect", "Annotate", ("(GNATprove, Skip_Proof)",)):
                "annotate_justification_or_skip",
            ("pragma", "Suppress", ("All_Checks",)): "suppress",
            ("pragma", "SPARK_Mode", ("Off",)): "spark_mode_off",
            ("aspect", "SPARK_Mode", ("Off",)): "spark_mode_off",
            ("aspect", "Import", ("True",)): "unchecked_axiom_mechanism",
            ("aspect", "Import", ()): "unchecked_axiom_mechanism",
            ("ghost_decl_without_body", "Ops.Lemma", ()):
                "bodyless_ghost_subprogram",
        }
        for rec, cat in cases.items():
            self.assertEqual(E.classify_trust(rec), cat, rec)

    def test_axiom_annotation_is_not_allowed(self):
        for rec in (("pragma", "Annotate",
                     ("GNATprove", "Axiom", '"reason"')),
                    ("aspect", "Annotate",
                     ("(GNATprove, Axiom, ...)",))):
            self.assertIsNotNone(E.classify_trust(rec), rec)

    def test_allowed_records(self):
        for rec in (("aspect", "SPARK_Mode", []),
                    ("aspect", "SPARK_Mode", ["On"]),
                    ("aspect", "Pre", ["X > 0 and then Y > 0"]),
                    ("aspect", "Global", ["null"]),
                    ("aspect", "Post", ["F'Result = X - 1"]),
                    ("pragma", "Assert", ["V > 0"]),
                    ("pragma", "Annotate", ["GNATprove", "Terminating"]),
                    ("aspect", "Import", ["False"])):
            self.assertIsNone(E.classify_trust(rec), rec)

    def test_introduced_hits_is_a_multiset_difference(self):
        a = {"category": "suppress", "kind": "pragma", "name": "Suppress"}
        self.assertEqual(E.introduced_hits([a], [a]), [])
        self.assertEqual(E.introduced_hits([a], [a, a]), [a])
        self.assertEqual(E.introduced_hits([], [a]), [a])


class ProductBoundary(unittest.TestCase):
    """The experiment is not part of the installed product."""

    def test_package_does_not_reference_the_experiment(self):
        for p in sorted(PKG.glob("*.py")):
            text = p.read_text("utf-8")
            for word in ("conjunct_reproof", "task012", "probe"):
                self.assertNotIn(word, text.lower(), p.name)

    def test_script_imports_libadalang_lazily(self):
        tree = ast.parse(SCRIPT.read_text("utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([a.name for a in node.names]
                         if isinstance(node, ast.Import)
                         else [node.module or ""])
                for n in names:
                    self.assertNotIn("libadalang", n)
                    self.assertNotIn("semantic_lal", n)

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
class LibadalangTransformation(unittest.TestCase):
    """Extraction and scratch transformation on a TEMPORARY copy of the
    Task 009 corpus (no GNATprove)."""

    def setUp(self):
        self.before = E.tree_digest(E.CORPUS)
        self.tmp = tempfile.TemporaryDirectory(prefix="t012-lal-")
        self.root = Path(self.tmp.name) / "task012-conjunct-reproof"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()
        # the committed corpus is never modified
        self.assertEqual(E.tree_digest(E.CORPUS), self.before)

    def test_extraction_matches_preregistration(self):
        op = E.extract_pre(E.CORPUS / E.MUTABLE_FILE, "Ops.Op")
        self.assertEqual(op["text"], "X > 0 and then Y > 0")
        self.assertEqual(op["conjuncts"], ["X > 0", "Y > 0"])
        self.assertEqual(op["span"], {"start_line": 4, "start_column": 19,
                                      "end_line": 4, "end_column": 39})
        op3 = E.extract_pre(E.CORPUS / E.MUTABLE_FILE, "Ops.Op3")
        self.assertEqual(op3["conjuncts"], ["X > 0", "Y > 0", "Z > 0"])
        self.assertEqual((op3["span"]["start_line"],
                          op3["span"]["end_line"]), (8, 10))
        data = (E.CORPUS / E.MUTABLE_FILE).read_bytes()
        for p in (op, op3):
            s, e = p["range"]
            self.assertEqual(data[s:e].decode(), p["text"])

    def test_extraction_matches_task009_backend(self):
        """Same decomposition as the production Task 009 adapter."""
        from spark_refine_diagnostics.ali import load_ali_sources
        from spark_refine_diagnostics.semantic_lal import open_backend
        d = self.root / "c"
        E.copy_corpus(E.CORPUS, d, root=self.root)
        be = open_backend(str(d / "experiment.gpr"), {},
                          load_ali_sources(E.CORPUS / "results").records)
        for (ent, f, ln, col, callee) in E.TARGETS:
            unit = be.ctx.get_from_file(str(d / "src" / f))
            hits, _ = be.calls_at(unit, ln, col)
            self.assertEqual(len(hits), 1, ent)
            decl = hits[0][1].p_referenced_decl()
            self.assertEqual(decl.p_fully_qualified_name, callee)
            self.assertEqual([c["text"] for c in
                              be.precondition(decl)["conjuncts"]],
                             list(E.EXPECTED_CONJUNCTS[callee]))

    def test_every_probe_transformation(self):
        original = E.read_tree(E.CORPUS)
        pres = {c: E.extract_pre(E.CORPUS / E.MUTABLE_FILE, c)
                for c in E.EXPECTED_CONJUNCTS}
        n = 0
        with mock.patch.object(E, "SCRATCH_ROOT", self.root):
            for callee, conj in E.EXPECTED_CONJUNCTS.items():
                for idx, text in enumerate(conj):
                    probe, d = E.make_probe(original, pres, callee, idx,
                                            text, [])
                    n += 1
                    self.assertEqual(d.parent, self.root.resolve())
                    m = probe["mutation"]
                    self.assertEqual(m["gate_problems"], [], probe)
                    self.assertEqual(m["changed_files"], [E.MUTABLE_FILE])
                    self.assertEqual((m["changed_file_count"],
                                      m["changed_range_count"]), (1, 1))
                    self.assertEqual(probe["reparse_problems"], [])
                    self.assertEqual(probe["trust_hits_introduced"], [])
                    new = (d / E.MUTABLE_FILE).read_bytes()
                    old = original[E.MUTABLE_FILE]
                    self.assertEqual(len(new), len(old))
                    self.assertEqual(new.count(b"\n"), old.count(b"\n"))
                    for rel in E.COPIED_FILES:
                        if rel != E.MUTABLE_FILE:
                            self.assertEqual((d / rel).read_bytes(),
                                             original[rel], rel)
                    # target Pre is exactly the conjunct; the other
                    # callee's Pre is untouched
                    self.assertEqual(E.extract_pre(d / E.MUTABLE_FILE,
                                                   callee)["text"], text)
                    other = ({"Ops.Op", "Ops.Op3"} - {callee}).pop()
                    self.assertEqual(
                        E.extract_pre(d / E.MUTABLE_FILE, other)["text"],
                        pres[other]["text"])
        self.assertEqual(n, 5)

    def test_reparse_rejects_wrong_or_broken_source(self):
        d = self.root / "bad"
        E.copy_corpus(E.CORPUS, d, root=self.root)
        target = d / E.MUTABLE_FILE
        self.assertTrue(E.reparse_problems(target, "Ops.Op", "X > 0"))
        s, e = E.extract_pre(target, "Ops.Op")["range"]
        target.write_bytes(E.overlay(target.read_bytes(), s, e, "X >"))
        self.assertTrue(E.reparse_problems(target, "Ops.Op", "X >"))

    def test_trust_scan(self):
        self.assertEqual(E.trust_scan(E.CORPUS), [])
        d = self.root / "t"
        E.copy_corpus(E.CORPUS, d, root=self.root)
        body = d / "src" / "client.adb"
        body.write_text(body.read_text().replace(
            "      Ops.Op (X, Y);\n   end Both_Fail;",
            "      pragma Assume (X > 0);\n      Ops.Op (X, Y);\n"
            "   end Both_Fail;"))
        spec = d / "src" / "ops.ads"
        spec.write_text(spec.read_text().replace(
            "package Ops with SPARK_Mode is",
            "package Ops with SPARK_Mode is\n   pragma Suppress (All_Checks);"
            "\n   procedure Lemma with Ghost, Global => null;"))
        cats = sorted(h["category"] for h in E.trust_scan(d))
        self.assertEqual(cats, ["bodyless_ghost_subprogram",
                                "pragma_assume", "suppress"])

