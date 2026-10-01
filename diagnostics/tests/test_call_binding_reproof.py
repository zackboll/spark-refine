"""Task 014: frozen matrix, structural gates, and scratch isolation."""
import ast
import copy
import importlib.util
import json
import unittest
from pathlib import Path

import support
from spark_refine_diagnostics.model import Check, Location, Status

SCRIPT = support.DIAGNOSTICS / "scripts" / "call_binding_reproof_experiment.py"
spec = importlib.util.spec_from_file_location("task014_reproof", SCRIPT)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class BindingReproof(unittest.TestCase):
    def test_frozen_matrix_and_corpus(self):
        self.assertEqual(E.T12.tree_digest(E.CORPUS), E.CORPUS_SHA256)
        manifest = json.loads((E.CORPUS / E.MANIFEST).read_text())
        self.assertEqual(len(manifest["occurrences"]), 26)
        self.assertEqual(len(manifest["callees"]), 7)
        self.assertEqual(sum(map(len, E.SIGNATURES)), 60)
        self.assertEqual(sum(s.count("P") for s in E.SIGNATURES), 34)
        self.assertEqual({k: "".join(E.CLASS_SIGNATURES).count(k)
                          for k in "PNBA"}, {"P": 31, "N": 17, "B": 9, "A": 3})
        self.assertEqual(len(E.BASELINE), 26)
        self.assertEqual({"P": 9, "U": 17},
                         {k: E.BASELINE.count(k) for k in "PU"})

    def test_classifier_fail_closed(self):
        p = {"matches": 1, "status": E.PROVED, "problem": None, "disputed": False}
        u = {**p, "status": E.UNPROVED}
        self.assertEqual(E.classify(None, p), E.PREFIX_PROVED)
        self.assertEqual(E.classify(p, u), E.NEWLY_UNPROVED)
        self.assertEqual(E.classify(u, u), E.BLOCKED)
        self.assertEqual(E.classify(u, p), E.INVALID)
        self.assertEqual(E.classify(p, u, True), E.AUX)
        for bad in ({**p, "matches": 0}, {**p, "disputed": True},
                    {**p, "status": E.JUSTIFIED}):
            self.assertEqual(E.classify(p, bad), E.INVALID)

    def test_structural_target_and_auxiliary_separation(self):
        manifest = json.loads((E.CORPUS / E.MANIFEST).read_text())
        occ = manifest["occurrences"][6]
        loc = occ["call"]
        def check(entity, line, col, rule="VC_PRECONDITION", status=Status.PROVED):
            return Check(rule=rule, status=status,
                         location=Location("binding_client.adb", line, col),
                         entity=entity, message="irrelevant prover text")
        t = check(occ["client_entity"], loc["line"], loc["column"])
        conversion = check(occ["client_entity"], 37, 20, "VC_RANGE_CHECK")
        other = check("Binding_Client.A8_Conversion_Unbounded", 43, 20,
                      "VC_RANGE_CHECK", Status.UNPROVED)
        self.assertEqual(E.target([t, conversion], occ)["status"], E.PROVED)
        self.assertEqual(E.target([t, t], occ)["matches"], 2)
        inv = E.inventory([t, conversion, other], manifest)
        self.assertEqual([len(inv[k]) for k in ("conversion_A7", "conversion_A8", "other")],
                         [1, 1, 0])
        self.assertEqual(E.inventory_problems(inv), [])

    def test_frozen_decision_rejects_bad_evidence(self):
        path = E.SCRATCH_ROOT / "evidence.json"
        if not path.is_file():
            manifest = json.loads((E.CORPUS / E.MANIFEST).read_text())
            self.assertEqual(E.decide({"manifest": manifest, "runs": [],
                                       "plans": {}, "refusals": []})["verdict"],
                             E.NOT_VALIDATED)
            return
        evidence = json.loads(path.read_text())
        self.assertEqual(E.decide(evidence)["verdict"], E.VALIDATED)
        for change in ("target", "untouched", "auxiliary", "resolution", "refusal"):
            bad = copy.deepcopy(evidence)
            if change == "target":
                bad["runs"][0]["targets"][0]["status"] = E.UNPROVED
            elif change == "untouched":
                bad["runs"][1]["targets"][0]["status"] = E.UNPROVED
            elif change == "auxiliary":
                bad["runs"][0]["inventory_problems"].append("missing conversion")
            elif change == "resolution":
                bad["runs"][0]["resolution"] = []
            else:
                bad["refusals"] = []
            self.assertEqual(E.decide(bad)["verdict"], E.NOT_VALIDATED, change)

    def test_no_substitution_or_eval(self):
        tree = ast.parse(SCRIPT.read_text())
        calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)]
        self.assertFalse(set(calls) & {"eval", "exec"})
        source = SCRIPT.read_text()
        self.assertNotIn("f_assocs", source)
        self.assertNotIn("f_actual", source)


try:
    import libadalang  # noqa: F401
except ImportError:
    HAVE_LAL = False
else:
    HAVE_LAL = True


@unittest.skipUnless(HAVE_LAL, "Libadalang bundle not available")
class SemanticGates(unittest.TestCase):
    def test_all_scratch_prefixes_and_manifest(self):
        before, manifest, original, pres, plans = E.preconditions()
        hits = E.trust_scan(E.CORPUS)
        self.assertEqual(hits, [])
        self.assertEqual(sum(len(v) for v in plans.values()), 15)
        for c in manifest["callees"]:
            for i in range(len(plans[c])):
                r, d = E.make_run(original, manifest, pres, plans, c, i, hits)
                self.assertEqual(r["gate_problems"], [], (c, i))
                self.assertEqual(r["reparse_problems"], [], (c, i))
                self.assertEqual(r["trust_hits_introduced"], [], (c, i))
                self.assertEqual(len(r["resolution"]), 26)
        self.assertEqual(E.T12.tree_digest(E.CORPUS), before)
