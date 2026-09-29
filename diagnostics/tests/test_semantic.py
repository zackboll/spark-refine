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


EXTERNAL_DECL_FILE = "spark-containers-functional-vectors.ads"
# the exact provenance_problem() messages of semantic_lal.py for a source
# whose identity does not match a D record
_PROVENANCE_MISMATCHES = (
    "GNAT checksum matches but the second-resolution timestamp does not "
    "match the result set's .ali D record (layout may differ)",
    "GNAT checksum does not match the result set's .ali D record")


def assert_external_call(tc: unittest.TestCase, check: dict,
                         expected_name: str,
                         decl_file: str = EXTERNAL_DECL_FILE) -> str:
    """Portable assertion for a VC_PRECONDITION whose callee is declared in
    an EXTERNAL dependency (SPARKlib) that the archived semantic snapshots
    deliberately do not copy. The archived fixture cannot control the
    active Alire checkout's mtime, so exactly two outcomes are allowed:

    A. `exact`: the external declaration passed the production provenance
       gate; the callee must be `expected_name`, declared in `decl_file`,
       with no failed-conjunct attribution.
    B. `unavailable`: the gate refused the external declaration; there must
       be no call/callee/precondition claim, and the reason must name the
       callee declaration's source-identity (D record) mismatch.

    Anything else (ambiguous, unresolved, other reasons) fails, with the
    complete check object in the message. Returns the outcome."""
    res = check.get("resolution")
    if res == "exact":
        callee = check.get("callee") or {}
        tc.assertEqual(callee.get("name"), expected_name, check)
        tc.assertEqual((callee.get("declaration") or {}).get("file"),
                       decl_file, check)
        pre = check.get("precondition")
        tc.assertIsInstance(pre, dict, check)
        tc.assertIsNone(pre["failed_conjunct"], check)
        tc.assertEqual(pre["attribution"], ATTRIBUTION, check)
        return res
    tc.assertEqual(res, "unavailable",
                   f"external call must be exact or unavailable: {check}")
    for k in ("call", "callee", "precondition"):
        tc.assertNotIn(k, check, check)
    reason = check.get("reason") or ""
    prefix = f"callee declaration: {decl_file}: "
    tc.assertTrue(reason.startswith(prefix),
                  f"reason must identify the callee-declaration provenance "
                  f"mismatch of {decl_file}: {check}")
    tc.assertIn(reason[len(prefix):], _PROVENANCE_MISMATCHES, check)
    return res


class ExternalCallAssertion(unittest.TestCase):
    """The helper itself (no Libadalang): accepts only the two portable
    outcomes and rejects everything else."""

    NAME = "Ring_Buffer.Sequences.Remove"
    LOC = {"file": "ring_buffer_client_proof.ads", "line": 24, "column": 45}

    def exact(self, name=NAME, file=EXTERNAL_DECL_FILE):
        return {"rule": "VC_PRECONDITION", "location": self.LOC,
                "resolution": "exact",
                "call": {"text": "Sequences.Remove (M, 1)", "location": None},
                "callee": {"name": name, "kind": "function",
                           "declaration": {"file": file, "start_line": 1,
                                           "start_column": 1, "end_line": 1,
                                           "end_column": 1}},
                "precondition": {"explicit": True, "text": "P",
                                 "location": None, "conjuncts": [],
                                 "failed_conjunct": None,
                                 "attribution": ATTRIBUTION}}

    def unavailable(self, detail=_PROVENANCE_MISMATCHES[0],
                    file=EXTERNAL_DECL_FILE):
        return {"rule": "VC_PRECONDITION", "location": self.LOC,
                "resolution": "unavailable",
                "reason": f"callee declaration: {file}: {detail}"}

    def test_accepts_exact(self):
        self.assertEqual(assert_external_call(self, self.exact(), self.NAME),
                         "exact")

    def test_accepts_provenance_unavailable(self):
        for detail in _PROVENANCE_MISMATCHES:
            self.assertEqual(assert_external_call(
                self, self.unavailable(detail), self.NAME), "unavailable")

    def test_rejects_everything_else(self):
        bad = [self.exact(name="Ring_Buffer.Sequences.Get"),
               self.exact(file="ring_buffer.ads"),
               {**self.unavailable(), "callee": {"name": self.NAME}},
               self.unavailable(file="ring_buffer.ads"),
               {**self.unavailable(), "reason": "boom"},
               {"resolution": "ambiguous", "reason": "2 calls anchored"},
               {"resolution": "unresolved", "reason": "no call anchored"}]
        c = self.exact()
        c["precondition"]["failed_conjunct"] = 0
        bad.append(c)
        for check in bad:
            with self.assertRaises(AssertionError, msg=check):
                assert_external_call(self, check, self.NAME)

    def test_failure_message_shows_the_check(self):
        with self.assertRaises(AssertionError) as cm:
            assert_external_call(self, {"resolution": "unresolved",
                                        "reason": "xyzzy"}, self.NAME)
        self.assertIn("xyzzy", str(cm.exception))


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
        """(resolution, call text, callee, Pre text) of an expected `exact`
        precondition check; on anything else the failure shows the whole
        check (resolution + reason) instead of a KeyError."""
        self.assertEqual(c.get("resolution"), "exact", c)
        for k in ("call", "callee", "precondition"):
            self.assertIn(k, c, c)
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
        self.assertEqual(m["provenance"], {
            "basis": "gnat_ali_checksum_and_timestamp",
            "checksum": "gnat_source_checksum",
            "timestamp_resolution": "seconds",
            "layout_exact": False, "byte_exact": False})

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
        name = "ring_no_is_empty_post"
        # base SRD002 exists and is unchanged by enrichment
        rep = self.reports[name]
        self.assertEqual(
            {d.entity: (d.code, d.confidence.value) for d in rep.diagnostics},
            {"Ring_Buffer_Client_Proof.Push_Push_Pop": ("SRD002", "low"),
             "Ring_Buffer_Client_Proof.Rotate": ("SRD002", "medium")})
        c = self.checks(name)
        self.assertEqual(self.call(c[(11, 7)]), ("exact", "Pop (Q, X)",
                         "Ring_Buffer.Pop", "not Is_Empty (B)"))
        # Project-local source is snapshotted: everything except the two
        # SPARKlib callees must resolve exact.
        external = {(24, 45): "Ring_Buffer.Sequences.Remove",
                    (25, 45): "Ring_Buffer.Sequences.Get"}
        for pos, x in c.items():
            if pos not in external:
                self.assertEqual(x.get("resolution"), "exact", x)
        # SPARKlib is NOT snapshotted: it is resolved from the active Alire
        # checkout, whose mtime the archived D records cannot control. Only
        # the portable outcomes are allowed (exact to the right callee, or
        # an explicit callee-declaration provenance refusal). Fresh E2E-G
        # requires exact.
        outcomes = {assert_external_call(self, c[pos], expected)
                    for pos, expected in external.items()}
        # both calls resolve to the same SPARKlib file: same verdict
        self.assertEqual(len(outcomes), 1, {p: c[p] for p in external})
        m = rep.analysis["semantic"]
        n_unavail = 2 if outcomes == {"unavailable"} else 0
        self.assertEqual(m["resolutions"], {
            "exact": len(c) - n_unavail, "ambiguous": 0, "unresolved": 0,
            "unavailable": n_unavail}, m)

    def test_external_dependency_mismatch_degrades(self):
        """The hosted-runner situation, made deterministic: the archived
        result set records a SPARKlib D timestamp that the active Alire
        checkout does not have. Simulated by changing that D record in a
        TEMPORARY COPY of the archived results (the dependency checkout and
        its mtimes are never touched). The production gate must refuse the
        external callee declaration -> `unavailable`, no callee/Pre claim,
        while every project-local check stays exact."""
        def other_checkout(d):
            for ali in (d / "results").glob("*.ali"):
                lines = ali.read_text("utf-8").splitlines(keepends=True)
                out = []
                for ln in lines:
                    f = ln.split()
                    if f[:2] == ["D", EXTERNAL_DECL_FILE]:
                        ln = ln.replace(f[2], "19990101000000", 1)
                    out.append(ln)
                ali.write_text("".join(out), "utf-8")
        rep = self.enrich_copy("ring_no_is_empty_post", other_checkout)
        c = {(x["location"]["line"], x["location"]["column"]): x
             for d in rep.diagnostics for x in d.semantic["checks"]}
        for pos, name in {(24, 45): "Ring_Buffer.Sequences.Remove",
                          (25, 45): "Ring_Buffer.Sequences.Get"}.items():
            self.assertEqual(assert_external_call(self, c[pos], name),
                             "unavailable")
            self.assertIn("timestamp", c[pos]["reason"])
        for pos in ((7, 22), (11, 7), (16, 22), (25, 7)):
            self.assertEqual(c[pos]["resolution"], "exact", c[pos])
        self.assertEqual(rep.analysis["semantic"]["resolutions"],
                         {"exact": 4, "ambiguous": 0, "unresolved": 0,
                          "unavailable": 2})
        self.assertEqual({d.entity: d.confidence.value
                          for d in rep.diagnostics},
                         {"Ring_Buffer_Client_Proof.Push_Push_Pop": "low",
                          "Ring_Buffer_Client_Proof.Rotate": "medium"})

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

    # ---- Task 010: pre-registered semantic triage groups ----
    def groups(self, name):
        from spark_refine_diagnostics.semantic_groups import (
            coverage_problems, occurrence_ids)
        rep = self.reports[name]
        g = rep.analysis["semantic"]["srd002_groups"]
        self.assertEqual(coverage_problems(g, occurrence_ids(
            rep.diagnostics)), [])
        for grp in g["groups"]:
            self.assertNotIn("confidence", grp)
            self.assertIsNone(grp["precondition"]["failed_conjunct"])
        return g, [(x["callee"]["name"], x["precondition"]["text"],
                    x["check_count"]) for x in g["groups"]], \
            [(u["rule"], u["reason"]) for u in g["ungrouped"]]

    def test_groups_ring_no_is_full_post(self):
        g, groups, ung = self.groups("ring_no_is_full_post")
        self.assertEqual((g["client_failure_count"], g["group_count"],
                          g["grouped_check_count"],
                          g["ungrouped_check_count"]), (4, 1, 3, 1))
        self.assertEqual(groups, [("Ring_Buffer.Push", "not Is_Full (B)", 3)])
        self.assertEqual([(o["location"]["line"], o["location"]["column"])
                          for o in g["groups"][0]["occurrences"]],
                         [(9, 7), (10, 7), (25, 7)])
        self.assertEqual(g["groups"][0]["diagnostic_confidences"],
                         ["low", "medium"])
        self.assertEqual(ung, [("VC_ASSERT", "assertion_has_no_callee")])
        self.assertEqual((g["ungrouped"][0]["location"]["line"],
                          g["ungrouped"][0]["location"]["column"]), (16, 43))

    def test_groups_ring_no_public_model_bound(self):
        g, groups, ung = self.groups("ring_no_public_model_bound")
        self.assertEqual(groups, [("Ring_Buffer.Push", "not Is_Full (B)", 1)])
        self.assertEqual(ung, [])

    def test_groups_ring_no_is_empty_post_archived(self):
        """Archived fixture: SPARKlib Remove/Get are exact (own groups) or,
        when the active checkout's D timestamp differs, ungrouped
        semantic_unavailable. Never lost, never forced into a group."""
        g, groups, ung = self.groups("ring_no_is_empty_post")
        names = [n for n, _, _ in groups]
        self.assertEqual(names[:2], ["Ring_Buffer.Pop", "Ring_Buffer.Push"])
        self.assertIn(names[2:], ([], ["Ring_Buffer.Sequences.Get",
                                       "Ring_Buffer.Sequences.Remove"]))
        want = [("VC_ASSERT", "assertion_has_no_callee")] * 2
        if not names[2:]:
            want += [("VC_PRECONDITION", "semantic_unavailable")] * 2
        self.assertEqual(sorted(ung), sorted(want))
        self.assertEqual(g["client_failure_count"], 6)

    def test_groups_external_mismatch_is_ungrouped_unavailable(self):
        def other_checkout(d):
            for ali in (d / "results").glob("*.ali"):
                text = ali.read_text("utf-8")
                out = []
                for ln in text.splitlines(keepends=True):
                    f = ln.split()
                    if f[:2] == ["D", EXTERNAL_DECL_FILE]:
                        ln = ln.replace(f[2], "19990101000000", 1)
                    out.append(ln)
                ali.write_text("".join(out), "utf-8")
        rep = self.enrich_copy("ring_no_is_empty_post", other_checkout)
        g = rep.analysis["semantic"]["srd002_groups"]
        self.assertEqual([x["callee"]["name"] for x in g["groups"]],
                         ["Ring_Buffer.Pop", "Ring_Buffer.Push"])
        self.assertEqual(sorted(u["reason"] for u in g["ungrouped"]),
                         ["assertion_has_no_callee"] * 2
                         + ["semantic_unavailable"] * 2)

    def test_groups_pool_spec_no_count_posts(self):
        g, groups, ung = self.groups("pool_spec_no_count_posts")
        self.assertEqual(groups,
                         [("Fixed_Pool.Allocate", "Free_Count (P) > 0", 1)])
        self.assertEqual(ung, [("VC_ASSERT", "assertion_has_no_callee")] * 2)

    def test_groups_false_client_control(self):
        g, groups, ung = self.groups("pool_false_client_assert")
        self.assertEqual((g["group_count"], g["grouped_check_count"],
                          g["ungrouped_check_count"]), (0, 0, 1))
        self.assertEqual(ung, [("VC_ASSERT", "assertion_has_no_callee")])
        rep = self.reports["pool_false_client_assert"]
        self.assertEqual([d.confidence.value for d in rep.diagnostics],
                         ["low"])
        txt = to_text(rep.runs, rep.diagnostics, rep.notes, rep.analysis)
        sec = txt[txt.index("SRD002 semantic triage:"):
                  txt.index("SRD002: ")]
        self.assertNotIn("public Pre", sec)
        self.assertIn("0 callee/contract groups", sec)

    def test_groups_overloads_do_not_collapse(self):
        """conjunct_experiment: Ops.Over has two overloads (decl lines 32
        and 36) -> two groups sharing the name."""
        g, groups, _ = self.groups("conjunct_experiment")
        over = [x for x in g["groups"] if x["callee"]["name"] == "Ops.Over"]
        self.assertEqual(sorted(x["callee"]["declaration"]["start_line"]
                                for x in over), [32, 36])
        self.assertEqual(sorted(x["precondition"]["text"] for x in over),
                         ["X", "X > 0"])

    # ---- source-position lookup (experiment corpus, real GNATprove) ----
    def test_lookup_shapes(self):
        c = self.checks("conjunct_experiment")
        for pos in ((29, 7), (31, 12), (31, 15), (31, 23), (40, 10),
                    (41, 10)):
            self.call(c[pos])   # exact, else fail with the whole check
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
            self.call(c[pos])   # exact, else fail with the whole check
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
        self.assertEqual(r.get("resolution"), "exact", r)
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

    CLIENT = "src/ring_buffer_client_proof.adb"

    def _layout_edit(self, d: Path, offset: float) -> Path:
        """Insert one comment line at the top of the client body (GNAT
        checksum unchanged: comments and layout are not accumulated) and
        set its mtime to the recorded D timestamp + `offset` seconds."""
        meta = json.loads((d / "snapshot.json").read_text())
        stamp = meta["sources"][self.CLIENT]["d_timestamp"]
        t = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc).timestamp() + offset
        p = d / self.CLIENT
        p.write_text("--  layout-only edit\n" + p.read_text())
        os.utime(p, (t, t))
        return p

    def test_layout_change_in_later_second_is_refused(self):
        """The normal case: a layout edit made in a later second changes
        the D-comparable timestamp, so the gate refuses the file."""
        rep = self.enrich_copy("ring_no_is_full_post",
                               lambda d: self._layout_edit(d, 5.0))
        for d in rep.diagnostics:
            for x in d.semantic["checks"]:
                self.assertEqual(x["resolution"], "unavailable")
                self.assertIn("timestamp", x["reason"])

    def test_same_second_layout_change_is_undetectable(self):
        """The documented LIMITATION, not a solved case. A layout/comment
        edit whose mtime falls in the SAME second as the .ali D record is
        indistinguishable from the proof-time source by GNAT's metadata
        (checksum ignores layout; timestamp has 1 s resolution), so the
        gate accepts it. The report must say the match is not
        layout-exact, and `exact` resolution then describes the CURRENT
        source, not the proof-time one."""
        from spark_refine_diagnostics.ali import load_ali_sources
        from spark_refine_diagnostics.semantic_lal import (mtime_stamp,
                                                           open_backend)
        with tempfile.TemporaryDirectory() as t:
            d = materialize("ring_no_is_full_post", Path(t))
            meta = json.loads((d / "snapshot.json").read_text())
            rec = meta["sources"][self.CLIENT]
            p = self._layout_edit(d, 0.7)
            # the bytes did change ...
            self.assertNotEqual(hashlib.sha256(p.read_bytes()).hexdigest(),
                                rec["sha256"])
            records = load_ali_sources(d / "results").records
            be = open_backend(str(d / meta["project"]), {}, records)
            # ... but both recorded identity values still match
            self.assertEqual(mtime_stamp(str(p)), rec["d_timestamp"])
            self.assertIn((rec["d_timestamp"], rec["gnat_checksum"]),
                          records[p.name])
            self.assertIsNone(be.provenance_problem(str(p.resolve())))
            rep = analyze_path_report(d / "results")
            enrich_report(rep, d / "results",
                          SemanticRequest(str(d / meta["project"])))
        m = rep.analysis["semantic"]
        self.assertTrue(m["evaluated"])
        self.assertEqual(m["provenance"]["basis"],
                         "gnat_ali_checksum_and_timestamp")
        self.assertEqual(m["provenance"]["timestamp_resolution"], "seconds")
        self.assertIs(m["provenance"]["layout_exact"], False)
        self.assertIs(m["provenance"]["byte_exact"], False)
        # Additional evidence (not the core assertion): locations shifted
        # by one line. 9:7 now hits a blank line; 10:7 now hits the call
        # that was on line 9 at proof time and resolves `exact` to it.
        # `exact` = one call found + resolved, NOT source identity.
        c = {(x["location"]["line"], x["location"]["column"]): x
             for dg in rep.diagnostics for x in dg.semantic["checks"]}
        self.assertEqual(c[(9, 7)]["resolution"], "unresolved")
        self.assertEqual(c[(10, 7)]["resolution"], "exact", c[(10, 7)])
        self.assertEqual(c[(10, 7)]["call"]["text"], "Push (Q, A)")

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
        return as_json(self._good_report())

    def _good_report(self):
        class Stub(FakeBackend):
            def resolve_precondition(self, file, line, column):
                r = super().resolve_precondition(file, line, column)
                r["call"]["text"] = {9: "Push (Q, A)", 10: "Push (Q, B)",
                                     25: "Push (Q, X)"}[line]
                # Task 010: grouping requires a complete call span (as
                # real Libadalang always reports)
                r["call"]["location"] = {
                    "file": file, "start_line": line,
                    "start_column": column, "end_line": line,
                    "end_column": column + 10}
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
        return enrich_report(base_report("ring_no_is_full_post"),
                             SEM / "ring_no_is_full_post" / "results",
                             SemanticRequest("ring_buffer.gpr"),
                             factory=fake_factory(Stub()))

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

    def test_rejects_provenance_overclaim(self):
        doc = self.good()
        doc["analysis"]["semantic"]["provenance"]["layout_exact"] = True
        self.assertTrue(self.e2e.check_semantic(doc))
        doc = self.good()
        del doc["analysis"]["semantic"]["provenance"]
        self.assertTrue(self.e2e.check_semantic(doc))

    # ---- Task 010: E2E-F grouping criteria ----
    def test_known_good_groups(self):
        g = self.good()["analysis"]["semantic"]["srd002_groups"]
        self.assertEqual((g["group_count"], g["grouped_check_count"],
                          g["ungrouped_check_count"]), (1, 3, 1))
        self.assertEqual(g["groups"][0]["callee"]["name"],
                         "Ring_Buffer.Push")
        self.assertNotIn("confidence", g["groups"][0])

    def test_rejects_wrong_groups(self):
        doc = self.good()
        del doc["analysis"]["semantic"]["srd002_groups"]
        self.assertIn("analysis.semantic.srd002_groups missing",
                      self.e2e.check_semantic(doc))
        doc = self.good()
        g = doc["analysis"]["semantic"]["srd002_groups"]
        g["groups"][0]["occurrences"].pop()
        g["groups"][0]["check_count"] = 2
        g["grouped_check_count"] = 2
        self.assertTrue(self.e2e.check_semantic(doc))
        doc = self.good()
        g = doc["analysis"]["semantic"]["srd002_groups"]
        g["groups"][0]["confidence"] = "medium"
        self.assertTrue(self.e2e.check_semantic(doc))
        doc = self.good()
        g = doc["analysis"]["semantic"]["srd002_groups"]
        g["groups"][0]["precondition"]["failed_conjunct"] = 0
        self.assertTrue(self.e2e.check_semantic(doc))
        doc = self.good()
        g = doc["analysis"]["semantic"]["srd002_groups"]
        g["ungrouped"][0]["reason"] = "semantic_unavailable"
        self.assertTrue(self.e2e.check_semantic(doc))

    def test_split_push_group_fails(self):
        """A second Push declaration (different span) must not be merged,
        and E2E-F then fails: 2 groups instead of 1."""
        from spark_refine_diagnostics.semantic_groups import (
            build_srd002_groups)
        rep = self._good_report()
        for d in rep.diagnostics:
            for c in d.semantic["checks"]:
                if c["location"]["line"] == 25:
                    c["callee"]["declaration"]["start_line"] = 99
        rep.analysis["semantic"]["srd002_groups"] = build_srd002_groups(
            rep.diagnostics)
        doc = as_json(rep)
        self.assertEqual(
            doc["analysis"]["semantic"]["srd002_groups"]["group_count"], 2)
        self.assertTrue(any("(2, 3, 1)" in p
                            for p in self.e2e.check_semantic(doc)))

    def test_default_gate_excludes_semantic(self):
        self.assertIn("semantic", self.e2e.CASES)
        self.assertIn("semantic_external", self.e2e.CASES)
        self.assertEqual(self.e2e.OPT_IN, {"semantic", "semantic_external"})


class E2ECheckSemanticExternal(unittest.TestCase):
    """scripts/e2e_fresh.py check_semantic_external (E2E-G pass criteria)
    on the committed ring_no_is_empty_post snapshot, via a backend stub
    that replays the structural answers E2E-G expects. E2E-G is strict:
    unlike the archived-fixture test, `unavailable` is NOT accepted."""

    ANSWERS = {
        ("ring_buffer_client_proof.adb", 11): (
            "Pop (Q, X)", "Ring_Buffer.Pop",
            "obj/ablation_src/no_is_empty_post/ring_buffer.ads",
            "not Is_Empty (B)"),
        ("ring_buffer_client_proof.adb", 25): (
            "Push (Q, X)", "Ring_Buffer.Push",
            "obj/ablation_src/no_is_empty_post/ring_buffer.ads",
            "not Is_Full (B)"),
        ("ring_buffer_client_proof.ads", 24): (
            "Sequences.Remove (Model (Q)'Old, 1)",
            "Ring_Buffer.Sequences.Remove", EXTERNAL_DECL_FILE,
            "(SPARKlib_Defensive => ...)"),
        ("ring_buffer_client_proof.ads", 25): (
            "Sequences.Get (Model (Q)'Old, 1)", "Ring_Buffer.Sequences.Get",
            EXTERNAL_DECL_FILE, "(SPARKlib_Defensive => ...)"),
    }

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "e2e_fresh", support.DIAGNOSTICS / "scripts" / "e2e_fresh.py")
        cls.e2e = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.e2e)

    def good(self, degrade_external=False) -> dict:
        answers = self.ANSWERS

        class Stub(FakeBackend):
            def resolve_precondition(self, file, line, column):
                text, name, decl, pre = answers[(file, line)]
                if degrade_external and decl == EXTERNAL_DECL_FILE:
                    return {"resolution": "unavailable", "reason":
                            f"callee declaration: {decl}: "
                            f"{_PROVENANCE_MISMATCHES[0]}"}
                return {"resolution": "exact",
                        # Task 010: complete call span (as real
                        # Libadalang always reports)
                        "call": {"text": text, "location": {
                            "file": file, "start_line": line,
                            "start_column": column, "end_line": line,
                            "end_column": column + 10}},
                        "callee": {"name": name, "kind": "procedure",
                                   "declaration": {
                                       "file": decl, "start_line": 1,
                                       "start_column": 1, "end_line": 1,
                                       "end_column": 1}},
                        # Task 010: an explicit Pre always has a source
                        # span (as real Libadalang reports); grouping
                        # needs it for the contract identity
                        "precondition": {"explicit": True, "text": pre,
                                         "location": {
                                             "file": decl, "start_line": 2,
                                             "start_column": 19,
                                             "end_line": 2,
                                             "end_column": 40},
                                         "conjuncts": []}}

            def resolve_assertion(self, file, line, column):
                return {"resolution": "exact", "assertion": {
                    "pragma": "Assert", "text": "t", "location": None},
                    "enclosing_subprogram": None}
        rep = enrich_report(base_report("ring_no_is_empty_post"),
                            SEM / "ring_no_is_empty_post" / "results",
                            SemanticRequest("ring_buffer.gpr"),
                            factory=fake_factory(Stub()))
        return as_json(rep)

    def entry(self, doc, file, line):
        for d in doc["diagnostics"]:
            for c in d["semantic"]["checks"]:
                if (c["location"]["file"], c["location"]["line"]) == (
                        file, line):
                    return c
        raise KeyError((file, line))

    def test_accepts_known_good(self):
        self.assertEqual(self.e2e.check_semantic_external(self.good()), [])

    def test_rejects_degraded_external(self):
        """The archived-fixture outcome B is a FAILURE in fresh E2E-G."""
        problems = self.e2e.check_semantic_external(
            self.good(degrade_external=True))
        self.assertTrue(any("24, 45" in p and "unavailable" in p
                            for p in problems), problems)
        self.assertTrue(any("25, 45" in p for p in problems), problems)

    def test_rejects_wrong_callee_or_decl(self):
        doc = self.good()
        self.entry(doc, "ring_buffer_client_proof.ads", 24)["callee"][
            "name"] = "Ring_Buffer.Sequences.Get"
        self.assertTrue(self.e2e.check_semantic_external(doc))
        doc = self.good()
        self.entry(doc, "ring_buffer_client_proof.ads", 25)["callee"][
            "declaration"]["file"] = "ring_buffer.ads"
        self.assertTrue(self.e2e.check_semantic_external(doc))
        doc = self.good()
        self.entry(doc, "ring_buffer_client_proof.adb", 11)[
            "precondition"]["text"] = "True"
        self.assertTrue(self.e2e.check_semantic_external(doc))

    def test_rejects_conjunct_claim_and_overclaim(self):
        doc = self.good()
        self.entry(doc, "ring_buffer_client_proof.ads", 24)[
            "precondition"]["failed_conjunct"] = 0
        self.assertTrue(self.e2e.check_semantic_external(doc))
        doc = self.good()
        doc["analysis"]["semantic"]["provenance"]["byte_exact"] = True
        self.assertTrue(self.e2e.check_semantic_external(doc))
        doc = self.good()
        doc["analysis"]["semantic"]["evaluated"] = False
        self.assertTrue(self.e2e.check_semantic_external(doc))

    def test_rejects_missing_srd002(self):
        doc = self.good()
        doc["analysis"]["rules"]["SRD002"]["evaluated"] = False
        self.assertTrue(self.e2e.check_semantic_external(doc))

    # ---- Task 010: E2E-G grouping criteria ----
    def test_known_good_groups(self):
        g = self.good()["analysis"]["semantic"]["srd002_groups"]
        self.assertEqual(sorted(x["callee"]["name"] for x in g["groups"]),
                         sorted(self.e2e.EXTERNAL_GROUPS))
        self.assertEqual((g["group_count"], g["grouped_check_count"],
                          g["ungrouped_check_count"]), (4, 4, 2))

    def test_rejects_degraded_external_groups(self):
        """Archived outcome B (Remove/Get unavailable) is ungrouped, not
        lost; but in fresh E2E-G it must fail the grouping criteria."""
        doc = self.good(degrade_external=True)
        g = doc["analysis"]["semantic"]["srd002_groups"]
        self.assertEqual((g["group_count"], g["ungrouped_check_count"]),
                         (2, 4))
        self.assertEqual(sorted(u["reason"] for u in g["ungrouped"]),
                         ["assertion_has_no_callee"] * 2
                         + ["semantic_unavailable"] * 2)
        problems = self.e2e.check_semantic_external(doc)
        self.assertTrue(any("(2, 2, 4)" in p for p in problems), problems)

    def test_rejects_missing_or_broken_groups(self):
        doc = self.good()
        del doc["analysis"]["semantic"]["srd002_groups"]
        self.assertIn("analysis.semantic.srd002_groups missing",
                      self.e2e.check_semantic_external(doc))
        doc = self.good()
        g = doc["analysis"]["semantic"]["srd002_groups"]
        g["ungrouped"].pop()
        self.assertTrue(any("missing" in p for p in
                            self.e2e.check_semantic_external(doc)))
        doc = self.good()
        doc["analysis"]["semantic"]["srd002_groups"]["groups"][0][
            "confidence"] = "medium"
        self.assertTrue(self.e2e.check_semantic_external(doc))


class ProvenanceContract(unittest.TestCase):
    """Task 009 corrective: analysis.semantic.provenance states what the
    source/result gate can establish, machine-readably and deterministically,
    independent of backend availability and of resolution quality."""

    EXPECTED = {"basis": "gnat_ali_checksum_and_timestamp",
                "checksum": "gnat_source_checksum",
                "timestamp_resolution": "seconds",
                "layout_exact": False, "byte_exact": False}

    def meta(self, request, factory=None, name="ring_no_is_full_post"):
        rep = enrich_report(base_report(name), SEM / name / "results",
                            request, factory=factory)
        return rep, as_json(rep)["analysis"]["semantic"]

    def test_present_when_evaluated_and_when_not(self):
        _, ok = self.meta(SemanticRequest("x.gpr"),
                          fake_factory(FakeBackend()))
        _, no_project = self.meta(SemanticRequest(None))
        with _block_libadalang():
            _, no_lal = self.meta(SemanticRequest("x.gpr"))
        for m in (ok, no_project, no_lal):
            self.assertEqual(m["provenance"], self.EXPECTED)
        self.assertTrue(ok["evaluated"])
        self.assertFalse(no_project["evaluated"])

    def test_no_run_specific_values(self):
        """No timestamps/hashes of the current run: byte-identical JSON
        across runs, and the block holds only the constant keys."""
        a = self.meta(SemanticRequest("x.gpr"), fake_factory(FakeBackend()))
        b = self.meta(SemanticRequest("x.gpr"), fake_factory(FakeBackend()))
        self.assertEqual(to_json(a[0].runs, a[0].diagnostics, a[0].notes,
                                 a[0].analysis),
                         to_json(b[0].runs, b[0].diagnostics, b[0].notes,
                                 b[0].analysis))
        self.assertEqual(set(a[1]["provenance"]), set(self.EXPECTED))

    def test_exact_resolution_does_not_upgrade_provenance(self):
        """All checks `exact`, yet the gate still reports layout_exact /
        byte_exact false: resolution quality and source-identity strength
        are separate fields."""
        rep, m = self.meta(SemanticRequest("x.gpr"),
                           fake_factory(FakeBackend()),
                           name="pool_spec_no_count_posts")
        res = {c["resolution"] for d in rep.diagnostics
               for c in d.semantic["checks"]
               if c["rule"] == "VC_PRECONDITION"}
        self.assertEqual(res, {"exact"})
        self.assertIs(m["provenance"]["layout_exact"], False)
        self.assertIs(m["provenance"]["byte_exact"], False)
        for d in rep.diagnostics:
            for c in d.semantic["checks"]:
                self.assertNotIn("provenance", c)

    def test_text_states_limitation(self):
        rep, _ = self.meta(SemanticRequest("x.gpr"),
                           fake_factory(FakeBackend()))
        txt = to_text(rep.runs, rep.diagnostics, rep.notes, rep.analysis)
        self.assertIn("GNAT checksum + second-resolution .ali timestamp "
                      "(not byte-exact)", txt)

    def test_no_stronger_provenance_is_invented(self):
        """The gate compares only what GNAT recorded: no content hashing,
        no sub-second mtime, no persisted state in the semantic modules."""
        for mod in ("semantic.py", "semantic_lal.py"):
            src = (PKG / mod).read_text("utf-8")
            tree = ast.parse(src)
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            attrs = {n.attr for n in ast.walk(tree)
                     if isinstance(n, ast.Attribute)}
            with self.subTest(module=mod):
                self.assertNotIn("hashlib", names)
                self.assertFalse({"st_mtime_ns", "write_text",
                                  "write_bytes"} & attrs)
