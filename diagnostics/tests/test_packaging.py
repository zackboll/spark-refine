"""Task 006: packaging configuration (fast, no build). The real build /
install / run-outside-the-repository check is scripts/packaging_smoke.py
(CI job `diagnostics-packaging`); its wheel allow-list is unit-tested
here as well."""

from __future__ import annotations

import ast
import importlib.util
import tomllib
import unittest

import support
import spark_refine_diagnostics
from spark_refine_diagnostics import cli

PYPROJECT = support.DIAGNOSTICS / "pyproject.toml"


def _smoke():
    path = support.DIAGNOSTICS / "scripts" / "packaging_smoke.py"
    spec = importlib.util.spec_from_file_location("packaging_smoke", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PackagingConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = tomllib.loads(PYPROJECT.read_text("utf-8"))

    def test_console_script(self):
        self.assertEqual(self.cfg["project"]["scripts"],
                         {"spark-refine": "spark_refine_diagnostics.cli:main"})
        self.assertTrue(callable(cli.main))

    def test_no_runtime_dependencies(self):
        self.assertEqual(self.cfg["project"]["dependencies"], [])
        self.assertEqual(self.cfg["build-system"]["requires"],
                         ["setuptools>=77"])

    def test_only_the_package_is_packaged(self):
        st = self.cfg["tool"]["setuptools"]
        self.assertEqual(st["packages"], ["spark_refine_diagnostics"])
        self.assertFalse(st["include-package-data"])
        self.assertNotIn("package-data", st)
        manifest = (support.DIAGNOSTICS / "MANIFEST.in").read_text("utf-8")
        for d in ("tests", "scripts", "obj"):
            self.assertIn(f"prune {d}", manifest)

    def test_license_and_readme_present(self):
        for f in ("README.md", "LICENSE"):
            self.assertTrue((support.DIAGNOSTICS / f).is_file(), f)
        self.assertEqual((support.DIAGNOSTICS / "LICENSE").read_bytes(),
                         (support.REPO / "LICENSE").read_bytes())

    def test_version_is_single_sourced(self):
        self.assertEqual(self.cfg["tool"]["setuptools"]["dynamic"],
                         {"version": {"attr":
                                      "spark_refine_diagnostics.__version__"}})
        self.assertTrue(spark_refine_diagnostics.__version__)

    def test_runtime_imports_are_stdlib_only(self):
        import sys
        allowed = set(sys.stdlib_module_names) | {"__future__"}
        pkg = support.DIAGNOSTICS / "spark_refine_diagnostics"
        for src in sorted(pkg.glob("*.py")):
            tree = ast.parse(src.read_text("utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                for n in names:
                    with self.subTest(file=src.name, module=n):
                        self.assertIn(n.split(".")[0], allowed)

    def test_wheel_allow_list(self):
        bad = _smoke().wheel_disallowed
        good = ["spark_refine_diagnostics/__init__.py",
                "spark_refine_diagnostics/cli.py",
                "spark_refine-0.0.0.dev0.dist-info/METADATA",
                "spark_refine-0.0.0.dev0.dist-info/licenses/LICENSE"]
        self.assertEqual(bad(good), [])
        for member in ("tests/fixtures/pool_p5/gnatprove.sarif",
                       "spark_refine_diagnostics/fixtures/x.spark",
                       "spark_refine_diagnostics/tests/test_x.py",
                       "scripts/e2e_fresh.py",
                       "obj/e2e/summary.json",
                       "spark_refine_diagnostics/data.json"):
            with self.subTest(member=member):
                self.assertEqual(bad(good + [member]), [member])


if __name__ == "__main__":
    unittest.main()
