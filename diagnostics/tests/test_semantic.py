"""Task 009: optional Libadalang semantic enrichment of SRD002.

Part 1 (always runs, no Libadalang): policy, degradation, rendering and
the no-heuristic guarantee, with a fake backend.
Part 2 (skipped unless `import libadalang` works and the snapshot projects
load, i.e. run under `alr -n exec` of examples/ring_buffer with the bundle
from scripts/setup_libadalang.sh on PYTHONPATH): real resolution on the
committed semantic snapshots (tests/semantic_fixtures).
"""

from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import support
from spark_refine_diagnostics import analyze_path_report
from spark_refine_diagnostics.cli import main
from spark_refine_diagnostics.gnat_checksum import gnat_checksum, token_bytes
from spark_refine_diagnostics.render import to_json, to_text
from spark_refine_diagnostics.semantic import (ATTRIBUTION, SemanticRequest,
                                               enrich_report)

SEM = support.TESTS / "semantic_fixtures"
PKG = support.DIAGNOSTICS / "spark_refine_diagnostics"


def base_report(name: str):
    return analyze_path_report(SEM / name / "results", name=name)


def strip(doc: dict) -> dict:
    """The JSON report without Task 009 additions."""
    doc = copy.deepcopy(doc)
    doc["analysis"].pop("semantic", None)
    for d in doc["diagnostics"]:
        d.pop("semantic", None)
    return doc


def as_json(rep) -> dict:
    return json.loads(to_json(rep.runs, rep.diagnostics, rep.notes,
                              rep.analysis))


class FakeBackend:
    version = "fake"

    def __init__(self, pre=None, fail_on=None):
        self.calls = []
        self.fail_on = fail_on
        self.pre = pre or {"explicit": True, "text": "A and then B",
                           "location": None,
                           "conjuncts": [{"index": 0, "text": "A",
                                          "location": None},
                                         {"index": 1, "text": "B",
                                          "location": None}]}

    def resolve_precondition(self, file, line, column):
        self.calls.append(("pre", file, line, column))
        if (line, column) == self.fail_on:
            raise RuntimeError("boom")
        return {"resolution": "exact",
                "call": {"text": "Op (X)", "location": None},
                "callee": {"name": "P.Op", "kind": "procedure",
                           "declaration": {"file": "p.ads",
                                           "start_line": 1,
                                           "start_column": 4,
                                           "end_line": 2,
                                           "end_column": 9}},
                "precondition": copy.deepcopy(self.pre)}

    def resolve_assertion(self, file, line, column):
        self.calls.append(("assert", file, line, column))
        return {"resolution": "ambiguous", "reason": "fake"}


def fake_factory(backend):
    return lambda project, scenario, records: backend


class Policy(unittest.TestCase):
    def test_base_diagnostics_unchanged_by_enrichment(self):
        for name in ("ring_no_is_full_post", "pool_false_client_assert",
                     "conjunct_experiment"):
            with self.subTest(case=name):
                before = as_json(base_report(name))
                rep = enrich_report(base_report(name),
                                    SEM / name / "results",
                                    SemanticRequest("x.gpr"),
                                    factory=fake_factory(FakeBackend()))
                after = as_json(rep)
                self.assertEqual(strip(after), before)
                self.assertTrue(after["analysis"]["semantic"]["evaluated"])

    def test_enrichment_never_creates_srd002(self):
        """Implementation-failure controls stay silent: no SRD002, the
        backend is never even opened."""
        opened = []
        for name in ("ring_b3", "pool_p1", "ring_b_mask_baseline"):
            with self.subTest(fixture=name):
                rep = analyze_path_report(support.fixture(name), name=name)
                before = as_json(rep)
                enrich_report(rep, support.fixture(name),
                              SemanticRequest("x.gpr"),
                              factory=lambda *a: opened.append(a))
                after = as_json(rep)
                self.assertEqual(strip(after), before)
                self.assertNotIn("SRD002", [d["code"] for d in
                                            after["diagnostics"]])
                self.assertFalse(after["analysis"]["semantic"]["evaluated"])
        self.assertEqual(opened, [])

    def test_only_client_failures_are_resolved(self):
        be = FakeBackend()
        rep = enrich_report(base_report("pool_spec_no_count_posts"),
                            SEM / "pool_spec_no_count_posts" / "results",
                            SemanticRequest("x.gpr"),
                            factory=fake_factory(be))
        failures = sorted((r.location.line, r.location.column)
                          for d in rep.diagnostics for r in d.related
                          if r.role == "client failure")
        self.assertEqual(sorted((l, c) for _, _, l, c in be.calls), failures)
        # VC_ASSERT never goes through callee resolution
        kinds = {k for k, *_ in be.calls}
        self.assertEqual(kinds, {"pre", "assert"})

    def test_failed_conjunct_is_never_chosen(self):
        """Even with a multi-conjunct Pre and messages that name a
        conjunct ("cannot prove X > 10"), failed_conjunct stays null."""
        rep = enrich_report(base_report("conjunct_experiment"),
                            SEM / "conjunct_experiment" / "results",
                            SemanticRequest("x.gpr"),
                            factory=fake_factory(FakeBackend()))
        pres = [c["precondition"] for d in rep.diagnostics
                for c in d.semantic["checks"] if "precondition" in c]
        self.assertGreater(len(pres), 5)
        for p in pres:
            self.assertIsNone(p["failed_conjunct"])
            self.assertEqual(p["attribution"], ATTRIBUTION)

    def test_no_message_text_is_read_by_semantic_code(self):
        """Guard against heuristic attribution: the semantic modules never
        touch check messages or evaluate expressions."""
        for mod in ("semantic.py", "semantic_lal.py"):
            tree = ast.parse((PKG / mod).read_text("utf-8"))
            attrs = {n.attr for n in ast.walk(tree)
                     if isinstance(n, ast.Attribute)}
            names = {n.id for n in ast.walk(tree)
                     if isinstance(n, ast.Name)}
            with self.subTest(module=mod):
                self.assertNotIn("message", attrs)
                self.assertFalse({"eval", "exec", "re"} & names)
                self.assertNotIn("p_eval_as_int", attrs)

    def test_backend_exception_is_per_check_and_non_fatal(self):
        be = FakeBackend(fail_on=(9, 7))
        rep = enrich_report(base_report("ring_no_is_full_post"),
                            SEM / "ring_no_is_full_post" / "results",
                            SemanticRequest("x.gpr"),
                            factory=fake_factory(be))
        res = {(c["location"]["line"], c["location"]["column"]):
               c["resolution"]
               for d in rep.diagnostics for c in d.semantic["checks"]}
        self.assertEqual(res[(9, 7)], "unavailable")
        self.assertEqual(res[(10, 7)], "exact")

    def test_deterministic(self):
        outs = set()
        for _ in range(2):
            rep = enrich_report(base_report("ring_no_is_empty_post"),
                                SEM / "ring_no_is_empty_post" / "results",
                                SemanticRequest("x.gpr"),
                                factory=fake_factory(FakeBackend()))
            outs.add(to_json(rep.runs, rep.diagnostics, rep.notes,
                             rep.analysis))
            outs.add(to_text(rep.runs, rep.diagnostics, rep.notes,
                             rep.analysis))
        self.assertEqual(len(outs), 2)


def _block_libadalang():
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "libadalang" or name.startswith("libadalang."):
            raise ImportError("No module named 'libadalang' (test)")
        return real(name, *a, **k)
    return mock.patch("builtins.__import__", side_effect=fake)


class Degradation(unittest.TestCase):
    def meta(self, rep):
        return rep.analysis["semantic"]

    def check_degraded(self, rep, name, reason_part):
        m = self.meta(rep)
        self.assertEqual((m["requested"], m["evaluated"], m["backend"]),
                         (True, False, "libadalang"))
        self.assertIn(reason_part, m["reason"])
        self.assertEqual(strip(as_json(rep)), as_json(base_report(name)))
        self.assertTrue(all(d.semantic is None for d in rep.diagnostics))

    def test_libadalang_unavailable(self):
        with _block_libadalang():
            rep = enrich_report(base_report("ring_no_is_full_post"),
                                SEM / "ring_no_is_full_post" / "results",
                                SemanticRequest("ring_buffer.gpr"))
        self.check_degraded(rep, "ring_no_is_full_post", "not importable")

    def test_native_library_load_failure(self):
        from spark_refine_diagnostics import semantic_lal

        def broken():
            raise semantic_lal.BackendUnavailable(
                "libadalang not importable (OSError: libadalang.so: "
                "cannot open shared object file)")
        with mock.patch.object(semantic_lal, "_import", broken):
            rep = enrich_report(base_report("ring_no_is_full_post"),
                                SEM / "ring_no_is_full_post" / "results",
                                SemanticRequest("ring_buffer.gpr"))
        self.check_degraded(rep, "ring_no_is_full_post", "OSError")

    def test_project_not_supplied(self):
        rep = enrich_report(base_report("ring_no_is_full_post"),
                            SEM / "ring_no_is_full_post" / "results",
                            SemanticRequest(None))
        self.check_degraded(rep, "ring_no_is_full_post", "no project")

    def test_unexpected_backend_failure(self):
        def boom(*a):
            raise RuntimeError("crash")
        rep = enrich_report(base_report("ring_no_is_full_post"),
                            SEM / "ring_no_is_full_post" / "results",
                            SemanticRequest("p.gpr"), factory=boom)
        self.check_degraded(rep, "ring_no_is_full_post", "RuntimeError")

    def test_no_source_records(self):
        """The Task 005 fixtures keep no .ali D records: provenance cannot
        be established, so nothing is enriched."""
        rep = analyze_path_report(support.fixture("ring_no_is_full_post"))
        enrich_report(rep, support.fixture("ring_no_is_full_post"),
                      SemanticRequest("p.gpr"),
                      factory=fake_factory(FakeBackend()))
        self.assertFalse(self.meta(rep)["evaluated"])
        self.assertIn("provenance", self.meta(rep)["reason"])


class CliCompatibility(unittest.TestCase):
    def run_cli(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_without_flag_output_is_unchanged(self):
        """-P/-X alone (without --semantic) change nothing."""
        p = str(support.fixture("ring_no_is_full_post"))
        for fmt in ("text", "json"):
            base = self.run_cli(["explain", p, "--format", fmt])
            more = self.run_cli(["explain", p, "--format", fmt, "-P",
                                 "x.gpr", "-XA=B"])
            self.assertEqual(base, more)
            self.assertNotIn("semantic", base[1])

    def test_semantic_unavailable_keeps_exit_status(self):
        p = str(SEM / "ring_no_is_full_post" / "results")
        with _block_libadalang():
            code, out = self.run_cli(["explain", p, "--semantic", "-P",
                                      "nope.gpr", "--format", "json",
                                      "--fail-on", "SRD002"])
        base_code, base = self.run_cli(["explain", p, "--format", "json",
                                        "--fail-on", "SRD002"])
        self.assertEqual(code, base_code)
        doc = json.loads(out)
        self.assertEqual(doc["format_version"], 1)
        self.assertFalse(doc["analysis"]["semantic"]["evaluated"])
        self.assertEqual(strip(doc), json.loads(base))

    def test_scenario_syntax(self):
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), \
                    mock.patch("sys.stderr", io.StringIO()):
                main(["explain", "x", "-X", "novalue"])


class Checksum(unittest.TestCase):
    """gnat_checksum rules (scng.adb), and agreement with the checksums
    GNAT itself recorded for the committed snapshots."""

    def test_token_rules(self):
        self.assertEqual(token_bytes("Push"), b"push\x05")
        self.assertEqual(token_bytes("1_000"), b"1000\x00")
        self.assertEqual(token_bytes("1.5E+3"), b"1.5e+3\x01")
        self.assertEqual(token_bytes("16#FF_FF#"), b"16#ff_ff#\x00")
        self.assertEqual(token_bytes('"Ab"'), b'"Ab"')
        self.assertEqual(token_bytes("'A'"), b"'A'")
        self.assertEqual(token_bytes("["), b"")
        self.assertEqual(token_bytes("=>"), b"=>")
        self.assertIsNone(token_bytes("caf\u00e9"))

    def test_layout_insensitive_case_sensitive_strings(self):
        a = gnat_checksum(["X", ":=", '"a"', ";"])
        self.assertEqual(a, gnat_checksum(["x", ":=", '"a"', ";"]))
        self.assertNotEqual(a, gnat_checksum(["x", ":=", '"A"', ";"]))
        self.assertRegex(a, r"^[0-9a-f]{8}$")

    def test_snapshot_records_match_gnat(self):
        """snapshot.json checksums were computed by gnat_checksum on
        Libadalang tokens and equal GNAT's own D records."""
        from spark_refine_diagnostics.ali import load_ali_sources
        n = 0
        for snap in sorted(SEM.glob("*/snapshot.json")):
            meta = json.loads(snap.read_text("utf-8"))
            recs = load_ali_sources(snap.parent / "results").records
            for rel, m in meta["sources"].items():
                with self.subTest(case=snap.parent.name, file=rel):
                    self.assertIn((m["d_timestamp"], m["gnat_checksum"]),
                                  recs[Path(rel).name])
                    self.assertEqual(hashlib.sha256(
                        (snap.parent / rel).read_bytes()).hexdigest(),
                        m["sha256"])
                    n += 1
        self.assertEqual(n, 19)


class ConjunctExperiment(unittest.TestCase):
    """Pre-registered experiment: does GNATprove 16.1.0's machine-readable
    output identify the failed Pre conjunct? Result: NOT ATTRIBUTABLE.

    client.adb calls Ops.Op (Pre => X > 0 and then Y > 0) in contexts
    where only the 2nd conjunct fails (line 7), only the 1st (12), both
    (17), and Ops.Op3 (X > 0 and Y > 0 and Z > 0) where only the middle
    fails (22). The failures are structurally indistinguishable."""

    RESULTS = SEM / "conjunct_experiment" / "results"
    LINES = {7: "second", 12: "first", 17: "both", 22: "middle"}

    def sarif(self):
        doc = json.loads((self.RESULTS / "gnatprove.sarif").read_text())
        return {r["locations"][0]["physicalLocation"]["region"]
                ["startLine"]: r for r in doc["runs"][0]["results"]
                if r["ruleId"] == "VC_PRECONDITION"
                and r["locations"][0]["physicalLocation"]["artifactLocation"]
                ["uri"] == "client.adb"}

    def test_sarif_has_one_result_per_call_and_no_conjunct_field(self):
        res = self.sarif()
        for line in self.LINES:
            r = res[line]
            self.assertEqual(r["kind"], "fail")
            self.assertEqual(set(r), {"kind", "level", "locations",
                                      "message", "ruleId"})
            self.assertEqual(len(r["locations"]), 1)
            loc = r["locations"][0]
            self.assertEqual(set(loc), {"logicalLocations",
                                        "physicalLocation"})
            # the same call location whichever conjunct fails
            self.assertEqual(loc["physicalLocation"]["region"],
                             {"startLine": line, "startColumn": 10})
        # structurally identical: only the line differs
        shapes = {json.dumps({**res[l], "locations": None},
                             sort_keys=True) for l in self.LINES}
        self.assertEqual(len(shapes), 1)

    def test_spark_entries_carry_no_conjunct_mapping(self):
        doc = json.loads((self.RESULTS / "client.spark").read_text())
        entries = [e for e in doc["proof"]
                   if e["rule"] == "VC_PRECONDITION"
                   and e["line"] in self.LINES]
        self.assertEqual(sorted(e["line"] for e in entries),
                         sorted(self.LINES))
        keys = {k for e in entries for k in e}
        self.assertEqual(keys, {"rule", "severity", "file", "line", "col",
                                "entity", "stats"} & keys)

    def test_srd002_fires_and_is_unchanged(self):
        rep = base_report("conjunct_experiment")
        got = {d.entity: d.confidence.value for d in rep.diagnostics}
        self.assertEqual(got, {"Client.Both_Fail": "medium",
                               "Client.First_Fails": "medium",
                               "Client.Middle_Fails": "medium",
                               "Client.Second_Fails": "medium",
                               "Client.Shapes": "low",
                               "Client.Shapes2": "medium"})

    def test_check_tree_goals_do_not_map_to_conjuncts(self):
        """The raw .spark check_tree (Why3 goals, undocumented format,
        captured in evidence.json) is not a conjunct mapping: 'first
        conjunct fails' (12) and 'both fail' (17) produce IDENTICAL goal
        outcomes, so no rule over it could tell them apart."""
        ev = json.loads((SEM / "conjunct_experiment" / "evidence.json")
                        .read_text())
        self.assertEqual(ev["12"]["check_tree_goals"],
                         ev["17"]["check_tree_goals"])
        self.assertNotEqual(ev["12"]["ground_truth"],
                            ev["17"]["ground_truth"])
        for e in ev.values():
            self.assertEqual(e["sarif_message"], "precondition might fail")
            self.assertFalse({k for k in e["entry_keys"]
                              if "conj" in k or "sub" in k})


def _lal_available() -> str | None:
    try:
        import libadalang  # noqa: F401
    except Exception as exc:
        return f"libadalang not importable ({type(exc).__name__})"
    return None


_SKIP = _lal_available()


def materialize(name: str, root: Path) -> Path:
    """Copy a snapshot to `root`, re-verify sha256, then restore the D
    timestamps (git does not keep mtimes). Returns the case directory."""
    src = SEM / name
    dest = root / name
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("obj"))
    meta = json.loads((src / "snapshot.json").read_text("utf-8"))
    for rel, m in meta["sources"].items():
        p = dest / rel
        if hashlib.sha256(p.read_bytes()).hexdigest() != m["sha256"]:
            raise AssertionError(f"{name}/{rel}: snapshot modified")
        t = datetime.strptime(m["d_timestamp"], "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc).timestamp()
        os.utime(p, (t, t))
    return dest


@unittest.skipIf(_SKIP, _SKIP or "")
class WithLibadalang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="srd-sem-")
        cls.root = Path(cls.tmp.name)
        cls.reports = {}
        for snap in sorted(SEM.glob("*/snapshot.json")):
            name = snap.parent.name
            meta = json.loads(snap.read_text("utf-8"))
            d = materialize(name, cls.root)
            rep = analyze_path_report(d / "results", name=name)
            enrich_report(rep, d / "results",
                          SemanticRequest(str(d / meta["project"])))
            cls.reports[name] = rep
        if not cls.reports["ring_no_is_full_post"].analysis["semantic"][
                "evaluated"]:
            reason = cls.reports["ring_no_is_full_post"].analysis[
                "semantic"]["reason"]
            cls.tmp.cleanup()
            raise unittest.SkipTest(f"snapshot projects not loadable "
                                    f"(run under `alr -n exec` of "
                                    f"examples/ring_buffer): {reason}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def checks(self, name, entity=None):
        return {(c["location"]["line"], c["location"]["column"]): c
                for d in self.reports[name].diagnostics
                if entity is None or d.entity == entity
                for c in d.semantic["checks"]}

    def call(self, c):
        return (c["resolution"], c["call"]["text"], c["callee"]["name"],
                c["precondition"]["text"])

    def test_metadata(self):
        m = self.reports["ring_no_is_full_post"].analysis["semantic"]
        self.assertEqual((m["requested"], m["evaluated"], m["backend"],
                          m["version"]), (True, True, "libadalang",
                                          "26.0.0"))
        self.assertEqual(m["resolutions"], {"exact": 4, "ambiguous": 0,
                                            "unresolved": 0,
                                            "unavailable": 0})

    def test_ring_no_is_full_post(self):
        c = self.checks("ring_no_is_full_post")
        push = ("Ring_Buffer.Push", "not Is_Full (B)")
        self.assertEqual(self.call(c[(9, 7)]), ("exact", "Push (Q, A)", *push))
        self.assertEqual(self.call(c[(10, 7)]),
                         ("exact", "Push (Q, B)", *push))
        self.assertEqual(self.call(c[(25, 7)]),
                         ("exact", "Push (Q, X)", *push))
        decl = c[(9, 7)]["callee"]["declaration"]
        self.assertEqual((decl["file"], decl["start_line"]),
                         ("src/ring_buffer.ads", 36))
        pre = c[(9, 7)]["precondition"]
        self.assertEqual(pre["location"]["start_line"], 37)
        self.assertEqual([x["text"] for x in pre["conjuncts"]],
                         ["not Is_Full (B)"])
        self.assertIsNone(pre["failed_conjunct"])
        self.assertEqual(pre["attribution"], ATTRIBUTION)
        a = c[(16, 43)]
        self.assertEqual(a["assertion"]["text"],
                         "not Is_Empty (Q) and not Is_Full (Q)")
        self.assertNotIn("callee", a)

    def test_other_ring_cases(self):
        c = self.checks("ring_no_public_model_bound")
        self.assertEqual(self.call(c[(25, 7)]), ("exact", "Push (Q, X)",
                         "Ring_Buffer.Push", "not Is_Full (B)"))
        c = self.checks("ring_no_is_empty_post")
        self.assertEqual(self.call(c[(11, 7)]), ("exact", "Pop (Q, X)",
                         "Ring_Buffer.Pop", "not Is_Empty (B)"))
        self.assertEqual(c[(24, 45)]["callee"]["name"],
                         "Ring_Buffer.Sequences.Remove")
        self.assertEqual(c[(25, 45)]["callee"]["name"],
                         "Ring_Buffer.Sequences.Get")
        self.assertTrue(all(x["resolution"] == "exact" for x in c.values()))

    def test_pool_spec_no_count_posts(self):
        c = self.checks("pool_spec_no_count_posts")
        self.assertEqual(self.call(c[(35, 7)]),
                         ("exact", "Allocate (P, X)", "Fixed_Pool.Allocate",
                          "Free_Count (P) > 0"))
        self.assertEqual(c[(35, 7)]["callee"]["declaration"]["file"],
                         "src/fixed_pool.ads")
        for pos in ((15, 22), (20, 22)):
            self.assertIn("assertion", c[pos])
            self.assertNotIn("precondition", c[pos])

    def test_false_client_control(self):
        c = self.checks("pool_false_client_assert")
        self.assertEqual(list(c), [(9, 22)])
        a = c[(9, 22)]
        self.assertEqual(a["resolution"], "exact")
        self.assertEqual(a["assertion"]["text"], "Free_Count (P) = 0")
        self.assertEqual(a["enclosing_subprogram"],
                         "Fixed_Pool_False_Client.Initialize_Then_Claim_Empty")
        for k in ("callee", "precondition", "call"):
            self.assertNotIn(k, a)
        d = self.reports["pool_false_client_assert"].diagnostics[0]
        self.assertEqual(d.confidence.value, "low")

    # ---- source-position lookup (experiment corpus, real GNATprove) ----
    def test_lookup_shapes(self):
        c = self.checks("conjunct_experiment")
        # selected name P.Op: GNATprove anchors at the '.'
        self.assertEqual(self.call(c[(7, 10)])[:3],
                         ("exact", "Ops.Op (X, Y)", "Ops.Op"))
        # use-clause call spanning two lines, at statement start
        self.assertEqual(c[(29, 7)]["call"]["text"], "Op (X,\n          1)")
        loc = c[(29, 7)]["call"]["location"]
        self.assertEqual((loc["start_line"], loc["end_line"]), (29, 30))
        # nested function calls and several calls on one line
        self.assertEqual(c[(31, 12)]["call"]["text"], "F (F (X))")
        self.assertEqual(c[(31, 15)]["call"]["text"], "F (X)")
        self.assertEqual(c[(31, 23)]["call"]["text"], "Op (V, X)")
        self.assertEqual(c[(31, 12)]["callee"]["kind"], "function")
        # overloads resolved by Libadalang, not by name
        self.assertEqual(c[(40, 10)]["callee"]["declaration"]["start_line"],
                         32)
        self.assertEqual(c[(41, 10)]["callee"]["declaration"]["start_line"],
                         36)
        self.assertEqual(c[(41, 10)]["precondition"]["text"], "X")

    def test_pre_decomposition(self):
        c = self.checks("conjunct_experiment")

        def conj(pos):
            return [x["text"] for x in c[pos]["precondition"]["conjuncts"]]
        self.assertEqual(conj((7, 10)), ["X > 0", "Y > 0"])      # and then
        self.assertEqual(conj((22, 10)), ["X > 0", "Y > 0", "Z > 0"])  # and
        self.assertEqual(c[(22, 10)]["precondition"]["text"],
                         "X > 0\n                  and Y > 0\n"
                         "                  and Z > 0")   # multiline
        # parentheses and OR stay whole, no normalisation
        self.assertEqual(conj((38, 10)), ["(X > 0 or else Y > 0)",
                                          "(X < 100)"])
        # nested calls inside Pre; parenthesised AND is not flattened
        self.assertEqual(conj((39, 10)), ["X in 12 .. 999",
                                          "(F (F (X)) > 20 and X /= 500)"])
        self.assertEqual(conj((31, 12)), ["X > 10", "X < 1000"])
        self.assertEqual(
            [x["index"] for x in c[(22, 10)]["precondition"]["conjuncts"]],
            [0, 1, 2])
        for x in c.values():
            if "precondition" in x:
                self.assertIsNone(x["precondition"]["failed_conjunct"])

    def test_no_explicit_pre(self):
        from spark_refine_diagnostics.semantic_lal import open_backend
        d = self.root / "conjunct_experiment"
        from spark_refine_diagnostics.ali import load_ali_sources
        be = open_backend(str(d / "experiment.gpr"), {},
                          load_ali_sources(d / "results").records)
        # Ops.No_Pre (X) at client.adb:37 is proved (no check), so query
        # the adapter directly at its anchor
        r = be.resolve_precondition("client.adb", 37, 10)
        self.assertEqual(r["callee"]["name"], "Ops.No_Pre")
        self.assertEqual(r["precondition"], {"explicit": False, "text": None,
                                             "location": None,
                                             "conjuncts": []})
        self.assertEqual(be.resolve_precondition("client.adb", 37, 7)
                         ["resolution"], "unresolved")
        self.assertEqual(be.resolve_precondition("missing.adb", 1, 1)
                         ["resolution"], "unavailable")
        self.assertEqual(be.resolve_assertion("client.adb", 7, 10)
                         ["resolution"], "unresolved")

    # ---- provenance and failure modes ----
    def enrich_copy(self, name, mutate):
        with tempfile.TemporaryDirectory() as t:
            d = materialize(name, Path(t))
            mutate(d)
            meta = json.loads((d / "snapshot.json").read_text())
            rep = analyze_path_report(d / "results", name=name)
            enrich_report(rep, d / "results",
                          SemanticRequest(str(d / meta["project"])))
            return rep

    def test_modified_source_is_refused(self):
        def edit(d):
            p = d / "src" / "ring_buffer.ads"
            st = p.stat()
            p.write_text(p.read_text().replace("not Is_Full (B)",
                                               "Is_Full (B) = False"))
            os.utime(p, (st.st_atime, st.st_mtime))  # same mtime
        rep = self.enrich_copy("ring_no_is_full_post", edit)
        c = {(x["location"]["line"]): x for d in rep.diagnostics
             for x in d.semantic["checks"]}
        self.assertEqual(c[9]["resolution"], "unavailable")
        self.assertIn("checksum", c[9]["reason"])
        self.assertEqual(c[16]["resolution"], "exact")  # client unchanged

    def test_layout_change_is_refused(self):
        def touch(d):
            p = d / "src" / "ring_buffer_client_proof.adb"
            p.write_text("\n" + p.read_text())   # same checksum
        rep = self.enrich_copy("ring_no_is_full_post", touch)
        for d in rep.diagnostics:
            for x in d.semantic["checks"]:
                self.assertEqual(x["resolution"], "unavailable")
                self.assertIn("timestamp", x["reason"])

    def test_parse_error_is_unavailable(self):
        def breakit(d):
            p = d / "src" / "client.adb"
            st = p.stat()
            p.write_text(p.read_text().replace("end Shapes2;", "end;;"))
            os.utime(p, (st.st_atime, st.st_mtime))
        rep = self.enrich_copy("conjunct_experiment", breakit)
        m = rep.analysis["semantic"]
        self.assertEqual(m["resolutions"]["exact"], 0)

    def test_project_load_failure(self):
        rep = base_report("ring_no_is_full_post")
        enrich_report(rep, SEM / "ring_no_is_full_post" / "results",
                      SemanticRequest(str(self.root / "none.gpr")))
        m = rep.analysis["semantic"]
        self.assertFalse(m["evaluated"])
        self.assertIn("could not be loaded", m["reason"])
        self.assertTrue(all(d.semantic is None for d in rep.diagnostics))


class E2ECheckSemantic(unittest.TestCase):
    """scripts/e2e_fresh.py check_semantic (E2E-F pass criteria) on the
    enriched committed ring_no_is_full_post snapshot, via a backend stub
    that replays the structural answers E2E-F expects."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "e2e_fresh", support.DIAGNOSTICS / "scripts" / "e2e_fresh.py")
        cls.e2e = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.e2e)

    def good(self) -> dict:
        class Stub(FakeBackend):
            def resolve_precondition(self, file, line, column):
                r = super().resolve_precondition(file, line, column)
                r["call"]["text"] = {9: "Push (Q, A)", 10: "Push (Q, B)",
                                     25: "Push (Q, X)"}[line]
                r["callee"] = {"name": "Ring_Buffer.Push",
                               "kind": "procedure", "declaration": {
                                   "file": "obj/ablation_src/"
                                           "no_is_full_post/ring_buffer.ads",
                                   "start_line": 36, "start_column": 4,
                                   "end_line": 38, "end_column": 63}}
                r["precondition"] = {
                    "explicit": True, "text": "not Is_Full (B)",
                    "location": {"file": "x", "start_line": 37,
                                 "start_column": 17, "end_line": 37,
                                 "end_column": 32}, "conjuncts": []}
                return r

            def resolve_assertion(self, file, line, column):
                return {"resolution": "exact", "assertion": {
                    "pragma": "Assert", "text": "t", "location": None},
                    "enclosing_subprogram": None}
        rep = enrich_report(base_report("ring_no_is_full_post"),
                            SEM / "ring_no_is_full_post" / "results",
                            SemanticRequest("ring_buffer.gpr"),
                            factory=fake_factory(Stub()))
        return as_json(rep)

    def test_accepts_known_good(self):
        self.assertEqual(self.e2e.check_semantic(self.good()), [])

    def test_rejects_claimed_conjunct(self):
        doc = self.good()
        for d in doc["diagnostics"]:
            for c in d["semantic"]["checks"]:
                if "precondition" in c:
                    c["precondition"]["failed_conjunct"] = 0
        self.assertTrue(self.e2e.check_semantic(doc))

    def test_rejects_unevaluated_or_wrong_callee(self):
        doc = self.good()
        doc["analysis"]["semantic"]["evaluated"] = False
        self.assertTrue(self.e2e.check_semantic(doc))
        doc = self.good()
        doc["diagnostics"][0]["semantic"]["checks"][0]["callee"][
            "name"] = "Ring_Buffer.Pop"
        self.assertTrue(self.e2e.check_semantic(doc))

    def test_default_gate_excludes_semantic(self):
        self.assertIn("semantic", self.e2e.CASES)
