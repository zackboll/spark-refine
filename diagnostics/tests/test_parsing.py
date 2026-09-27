"""Parsing: SARIF classification, .spark reading and .ali dependencies.

The synthetic documents below only exercise classification edge cases that
no committed fixture contains (justified checks, notes, malformed input).
Every diagnostic rule is tested on real GNATprove output instead."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support
from spark_refine_diagnostics.ali import (OBSERVED_ALI_VERSION,
                                         SUPPORTED_ALI_VERSIONS,
                                         UNSUPPORTED_VERSION,
                                         load_ali_deps, parse_ali_text,
                                         read_ali)
from spark_refine_diagnostics.model import Status
from spark_refine_diagnostics.sarif import InputError, parse_sarif_data
from spark_refine_diagnostics.spark_results import parse_spark_data


def result(rule, kind, level="none", uri="p.ads", entity="P.X",
           text="msg", suppressions=None):
    loc = {"physicalLocation": {"artifactLocation": {"uri": uri},
                                "region": {"startLine": 1,
                                           "startColumn": 1}}}
    if entity is not None:
        loc["logicalLocations"] = [{"name": entity}]
    r = {"ruleId": rule, "kind": kind, "level": level,
         "message": {"text": text}, "locations": [loc]}
    if suppressions is not None:
        r["suppressions"] = suppressions
    return r


def sarif(*results):
    return {"version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "GNATProve", "version": "FSF 16.1.0"}},
        "invocations": [{"commandLine": "gnatprove -P p.gpr",
                         "exitCode": 0}],
        "results": list(results)}]}


FOUNDATION = "function Is_Valid is assumed to return True"


class SarifClassificationTests(unittest.TestCase):
    def test_structural_classification(self):
        run = parse_sarif_data(sarif(
            result("VC_POSTCONDITION", "pass", text="anything"),
            result("VC_ASSERT", "open"),
            result("VC_RANGE_CHECK", "open",
                   suppressions=[{"kind": "inSource"}]),
            result("error", "open", "warning", uri="a-nbnbin.ads",
                   entity=None, text=FOUNDATION),
            result("UNUSED", "open", "warning"),
            result("INFO", "open", "note")))
        self.assertEqual([c.status for c in run.checks],
                         [Status.PROVED, Status.UNPROVED, Status.JUSTIFIED])
        self.assertEqual([w.allowed for w in run.warnings],
                         [True, False, False])
        self.assertEqual(run.tool_version, "FSF 16.1.0")
        self.assertEqual(run.exit_code, 0)

    def test_message_text_never_decides_status(self):
        run = parse_sarif_data(sarif(
            result("VC_ASSERT", "open", text="assertion proved"),
            result("VC_ASSERT", "pass", text="assertion might fail")))
        self.assertEqual([c.status for c in run.checks],
                         [Status.UNPROVED, Status.PROVED])

    def test_allow_list_requires_rule_file_and_prefix(self):
        run = parse_sarif_data(sarif(
            result("error", "open", "warning", uri="other.ads",
                   text=FOUNDATION)))
        self.assertEqual([w.allowed for w in run.warnings], [False])

    def test_malformed_input(self):
        with self.assertRaises(InputError):
            parse_sarif_data({"runs": []})
        with self.assertRaises(InputError):
            parse_sarif_data({"version": "2.1.0", "runs": [
                {"results": [{"kind": "pass"}]}]})


class SparkFileTests(unittest.TestCase):
    def test_entity_index_severity_and_stats(self):
        unit = parse_spark_data({
            "stop_reason": "STOP_REASON_NONE", "pragma_assume": [{}],
            "entities": {" 3": {"name": "P.Op"}},
            "proof": [{"rule": "VC_ASSERT", "severity": "medium",
                       "file": "p.adb", "line": 4, "col": 7, "entity": 3,
                       "message": {"text": "m"},
                       "stats": {"Z3": {"count": 1, "max_steps": 9,
                                        "max_time": 0.5}}}],
            "flow": [{"rule": "UNINITIALIZED", "severity": "info",
                      "file": "p.adb", "line": 1, "col": 1,
                      "entity": 3}]}, "p")
        self.assertEqual(unit.entries[0].entity, "P.Op")
        self.assertTrue(unit.entries[0].unproved)
        self.assertFalse(unit.entries[1].unproved)
        self.assertEqual(unit.entries[0].stats[0].max_steps, 9)
        self.assertEqual(unit.result.pragma_assume, 1)
        self.assertEqual(unit.result.unproved_entries, 1)
        self.assertTrue(unit.result.complete)

    def test_stop_reason_other_than_none_is_incomplete(self):
        unit = parse_spark_data({"stop_reason": "STOP_REASON_ERROR"}, "p")
        self.assertFalse(unit.result.complete)

    def test_rejects_non_spark(self):
        with self.assertRaises(InputError):
            parse_spark_data({"proof": []}, "x")


VALID_ALI = ("V \"GNAT Lib v16\"\n"
             "U client%b  client.adb  1 OO PK\n"
             "W pkg%s\t\tpkg.adb\t\tpkg.ali\n"
             "Z spark.containers%s  x.ads  x.ali\n"
             "D pkg.ads 1 2\n")


class AliTests(unittest.TestCase):
    """The ALI adapter never raises; problems are structured statuses."""

    def test_with_lines(self):
        ali = parse_ali_text(VALID_ALI)
        self.assertEqual(ali.status, "ok")
        self.assertEqual(ali.deps, {"pkg", "spark.containers"})
        self.assertEqual(ali.version, "GNAT Lib v16")

    def test_valid_gnat_16_1_0_ali_from_fixture(self):
        ali = read_ali(support.fixture("pool_spec_no_count_posts")
                       / "fixed_pool_client_proof.ali")
        self.assertTrue(ali.ok)
        self.assertEqual(ali.version, OBSERVED_ALI_VERSION)
        self.assertIn("fixed_pool", ali.deps)

    def test_supported_version_v16(self):
        ali = parse_ali_text(VALID_ALI)
        self.assertEqual(ali.status, "ok")
        self.assertIn("GNAT Lib v16", SUPPORTED_ALI_VERSIONS)
        self.assertEqual(SUPPORTED_ALI_VERSIONS, {"GNAT Lib v16"})

    def test_unsupported_version_v17(self):
        text = VALID_ALI.replace("GNAT Lib v16", "GNAT Lib v17", 1)
        ali = parse_ali_text(text)
        self.assertEqual(ali.status, UNSUPPORTED_VERSION)
        self.assertFalse(ali.ok)
        self.assertEqual(ali.version, "GNAT Lib v17")
        self.assertEqual(ali.detail, "supported ALI version is GNAT Lib v16")
        # the otherwise well-formed W/Z records are NOT read
        self.assertEqual(ali.deps, frozenset())

    def test_unsupported_arbitrary_version(self):
        for version in ("something else", "", "GNAT Lib v16.1",
                        "gnat lib v16", "GNAT Lib v15"):
            with self.subTest(version=version):
                ali = parse_ali_text(
                    VALID_ALI.replace("GNAT Lib v16", version, 1))
                self.assertEqual(ali.status, UNSUPPORTED_VERSION)
                self.assertEqual(ali.version, version)
                self.assertEqual(ali.deps, frozenset())

    def test_unsupported_version_makes_directory_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "client.ali").write_text(VALID_ALI, "utf-8")
            (d / "pkg.ali").write_text(
                "V \"GNAT Lib v17\"\nU pkg%s  pkg.ads  1\n", "utf-8")
            deps = load_ali_deps(d, ["client", "pkg"])
        self.assertFalse(deps.ok)
        self.assertEqual(deps.versions, {"GNAT Lib v16"})
        self.assertEqual(deps.unsupported_versions, {"GNAT Lib v17"})
        self.assertEqual(deps.problems, [
            "pkg.ali: unsupported_version (version 'GNAT Lib v17'; "
            "supported ALI version is GNAT Lib v16)"])

    def test_missing_file(self):
        self.assertEqual(read_ali(Path("/nonexistent/x.ali")).status,
                         "missing")

    def test_empty_file(self):
        self.assertEqual(parse_ali_text("").status, "empty")
        self.assertEqual(parse_ali_text("\n  \n").status, "empty")

    def test_truncated_dependency_line(self):
        for text in (VALID_ALI + "W", VALID_ALI + "W \n",
                     VALID_ALI + "Wpkg%s x.adb x.ali\n"):
            with self.subTest(text=text[-20:]):
                ali = parse_ali_text(text)
                self.assertEqual(ali.status, "malformed")
                self.assertIn("truncated", ali.detail)

    def test_truncated_before_unit_record(self):
        # header only: no U record, so dependency information is absent
        self.assertEqual(parse_ali_text("V \"GNAT Lib v16\"\n").status,
                         "malformed")

    def test_missing_header(self):
        self.assertEqual(parse_ali_text(VALID_ALI[VALID_ALI.index("U"):])
                         .status, "no_version")

    def test_unknown_harmless_record_is_ignored(self):
        ali = parse_ali_text(VALID_ALI + "Q some future record 1 2 3\n"
                             "X 1 pkg.ads\n")
        self.assertEqual(ali.status, "ok")
        self.assertEqual(ali.deps, {"pkg", "spark.containers"})

    def test_malformed_dependency_entry(self):
        for bad in ("W pkg  pkg.adb  pkg.ali\n",      # no %s / %b
                    "W pkg%q  pkg.adb  pkg.ali\n",
                    "Z %s  x.ads  x.ali\n"):
            with self.subTest(line=bad):
                ali = parse_ali_text(VALID_ALI + bad)
                self.assertEqual(ali.status, "malformed")
                self.assertEqual(ali.deps, frozenset())

    def test_binary_garbage_does_not_raise(self):
        ali = parse_ali_text("\x00\x01\xff garbage\nW \x00%s\n")
        self.assertEqual(ali.status, "no_version")

    def test_directory_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertFalse(load_ali_deps(d).ok)          # no .ali at all
            (d / "client.ali").write_text(VALID_ALI, "utf-8")
            (d / "pkg.ali").write_text(
                "V \"GNAT Lib v16\"\nU pkg%s  pkg.ads  1\n", "utf-8")
            deps = load_ali_deps(d, ["client", "pkg"])
            self.assertTrue(deps.ok)
            self.assertEqual(deps.deps["client"], {"pkg",
                                                   "spark.containers"})
            # a requested unit without an .ali makes the set unavailable
            missing = load_ali_deps(d, ["client", "pkg", "other"])
            self.assertFalse(missing.ok)
            self.assertTrue(any("other.ali: missing" in p
                                for p in missing.problems))
            (d / "pkg.ali").write_text("", "utf-8")
            self.assertFalse(load_ali_deps(d, ["client", "pkg"]).ok)


if __name__ == "__main__":
    unittest.main()
