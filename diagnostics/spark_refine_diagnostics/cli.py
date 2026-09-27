"""Command-line interface.

  spark-refine explain [PATH] [--client-unit U ...] [--format text|json]
                              [--fail-on SRD00x ...]
  spark-refine analyze PATH   (compatibility alias of explain; PATH
                               required)
  spark-refine compare-provers --run NAME=PATH --run ...
                               [--reference NAME=PATH]
  spark-refine rules [--format text|json]

`python3 -m spark_refine_diagnostics ...` accepts the same commands.

PATH is a GNATprove output directory (obj/<variant>/gnatprove, or its
parent) or a gnatprove.sarif file. An explicit PATH is authoritative; no
discovery is performed. Without PATH, `explain` searches the current
directory for exactly one GNATprove result set (a directory holding
gnatprove.sarif and *.spark files); if none or several are found it exits
2 and lists the candidates instead of guessing.

spark-refine analyzes the proof results you point it at. They correspond
to the current sources only if GNATprove was just run; spark-refine never
runs GNATprove and never modifies sources.

Exit status: 0 on success (diagnostics are informational), 1 if a
--fail-on code was emitted, 2 on input errors (missing/malformed SARIF or
.spark, no unique result set). Missing or malformed .ali files are NOT
input errors: SRD002 is then skipped and the report says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_path_report, compare_provers_report
from .discovery import DiscoveryError, discover
from .loader import load_run
from .render import rules_to_dict, wrap, to_json, to_text
from .rules import RULES
from .sarif import InputError

PROG = "spark-refine"
MODULE_PROG = "python3 -m spark_refine_diagnostics"


def _named(spec: str) -> tuple[str, Path]:
    name, sep, path = spec.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError(
            f"expected NAME=PATH, got {spec!r}")
    return name, Path(path)


def _single_run_args(s: argparse.ArgumentParser, optional_path: bool
                     ) -> None:
    if optional_path:
        s.add_argument("path", type=Path, nargs="?",
                       help="GNATprove output directory or gnatprove.sarif "
                            "(default: discover exactly one result set "
                            "under the current directory)")
    else:
        s.add_argument("path", type=Path,
                       help="GNATprove output directory or gnatprove.sarif")
    s.add_argument("--name", help="run name shown in the report")
    s.add_argument("--client-unit", action="append", default=[],
                   help="treat this unit as a client of all other analysed "
                        "units (overrides .ali dependency discovery)")


def _parser(prog: str = PROG) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=prog,
        description="spark-refine: proof-aware diagnostics over GNATprove "
                    "results (SARIF/.spark/.ali). GNATprove remains the "
                    "proof authority.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--version", action="version",
                   version=f"spark-refine {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("explain",
                       help="explain one GNATprove run (SRD001, SRD002)")
    _single_run_args(e, optional_path=True)
    # Compatibility alias (Task 005 name). Identical semantics for an
    # explicit PATH; PATH stays mandatory, as before.
    a = sub.add_parser("analyze",
                       help="compatibility alias of 'explain' (PATH "
                            "required)")
    _single_run_args(a, optional_path=False)

    c = sub.add_parser("compare-provers",
                       help="compare single-prover runs (SRD003)")
    c.add_argument("--run", action="append", type=_named, required=True,
                   metavar="NAME=PATH",
                   help="a single-prover run (at least two)")
    c.add_argument("--reference", type=_named, metavar="NAME=PATH",
                   help="optional portfolio run, shown for context")

    for s in (e, a, c):
        s.add_argument("--format", choices=("text", "json"),
                       default="text")
        s.add_argument("--fail-on", action="append", default=[],
                       choices=sorted(RULES), metavar="CODE",
                       help="exit 1 if this diagnostic code is emitted")

    r = sub.add_parser("rules", help="list the diagnostic rules")
    r.add_argument("--format", choices=("text", "json"), default="text")
    return p


def print_rules() -> None:
    for code, r in RULES.items():
        print(f"{code}  [confidence {r.confidence_label}, {r.scope}]  "
              f"{r.title}")
        print(f"        category: {r.category}   action: {r.action}")
        for line in wrap(r.summary, "        "):
            print(line)
        if r.confidence_policy:
            print(f"        confidence policy: {r.confidence_policy}")


def _explain_target(args) -> tuple[Path, dict | None]:
    """The explicit PATH (authoritative, no discovery) or the unique
    result set discovered under the current directory."""
    if args.path is not None:
        return args.path, None
    found = discover(Path.cwd())
    return found, {"path": found.as_posix(), "discovered": True}


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    args = _parser(prog).parse_args(argv)
    if args.command == "rules":
        if args.format == "json":
            sys.stdout.write(json.dumps({"rules": rules_to_dict()},
                                        indent=2) + "\n")
        else:
            print_rules()
        return 0
    try:
        if args.command in ("explain", "analyze"):
            path, source = _explain_target(args)
            report = analyze_path_report(path, args.name, args.client_unit)
            if source is not None:
                report.analysis["input"] = source
        else:
            if len(args.run) < 2:
                print("compare-provers needs at least two --run",
                      file=sys.stderr)
                return 2
            runs = [load_run(path, name) for name, path in args.run]
            ref = (load_run(args.reference[1], args.reference[0])
                   if args.reference else None)
            report = compare_provers_report(runs, ref)
    except DiscoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (InputError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    render = to_json if args.format == "json" else to_text
    sys.stdout.write(render(report.runs, report.diagnostics, report.notes,
                            report.analysis))
    return 1 if any(d.code in args.fail_on
                    for d in report.diagnostics) else 0
