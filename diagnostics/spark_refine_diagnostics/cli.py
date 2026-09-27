"""Command-line interface.

  spark-refine explain [PATH] [--client-unit U ...] [--format text|json]
                              [--fail-on SRD00x ...]
  spark-refine analyze PATH   (compatibility alias of explain; PATH
                               required)
  spark-refine compare-provers --run NAME=PATH --run ...
                               [--reference NAME=PATH]
  spark-refine rules [--format text|json]
  spark-refine prove -P PROJECT [--gnatprove PATH] [--results PATH]
                     [--dry-run] [--client-unit U ...]
                     [--format text|json] [--fail-on SRD00x ...]
                     [-- GNATPROVE_ARGS...]

`python3 -m spark_refine_diagnostics ...` accepts the same commands.

`prove` (Task 008) runs `GNATPROVE -P PROJECT GNATPROVE_ARGS...` (argv,
never a shell; command shown on stderr first; GNATprove's own output goes
to stderr) in the current directory, then explains the ONE result set
that this invocation created or changed. Unchanged (stale) result sets
are ignored; zero or several fresh ones -> no report. With --results,
that location must have been freshly written by this run. `prove` does not
prove anything itself and never produces SRD003 (use compare-provers).
Exit status of `prove`: GNATprove's nonzero exit code if it returned one
(diagnostics are still emitted when a fresh result exists); else 1 if a
--fail-on code was emitted; else 0; 2 on errors before a usable result
(launch failure, no unique fresh result) when GNATprove itself exited 0.
A process killed by signal N is reported as 128+N.

PATH is a GNATprove output directory (obj/<variant>/gnatprove, or its
parent) or a gnatprove.sarif file. An explicit PATH is authoritative; no
discovery is performed. Without PATH, `explain` searches the current
directory for exactly one GNATprove result set (a directory holding
gnatprove.sarif and *.spark files); if none or several are found it exits
2 and lists the candidates instead of guessing.

explain/analyze analyse the proof results you point them at. They
correspond to the current sources only if GNATprove was just run; explain
never runs GNATprove (use `prove` for a fresh run). spark-refine never
modifies sources.

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
from .orchestration import (DEFAULT_GNATPROVE, Freshness, FreshnessError,
                            LaunchError, build_command, display_command,
                            exit_status, metadata, normalize_returncode,
                            plan, run_gnatprove)
from .render import (JSON_FORMAT_VERSION, orchestration_plan_text,
                     rules_to_dict, wrap, to_json, to_text)
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

    pr = sub.add_parser(
        "prove",
        usage=f"{prog} prove -P PROJECT [options] [-- GNATPROVE_ARGS...]",
        help="run GNATprove, then explain the result set THAT run wrote "
             "(SRD001, SRD002)",
        description="Run GNATprove (argv, no shell) in the current "
                    "directory, then analyse the one result set that this "
                    "invocation created or changed. Stale (unchanged) "
                    "result sets are never analysed. Everything after the "
                    "first `--` is passed to GNATprove verbatim, after "
                    "-P PROJECT. GNATprove's console output goes to "
                    "stderr; stdout carries only the spark-refine report.")
    pr.add_argument("-P", "--project", required=True,
                    help="GPR project file, passed to GNATprove as -P")
    pr.add_argument("--gnatprove", default=DEFAULT_GNATPROVE,
                    metavar="PATH",
                    help="GNATprove executable (default: gnatprove, "
                         "looked up on PATH)")
    pr.add_argument("--results", type=Path, metavar="PATH",
                    help="the result-set directory (or its "
                         "gnatprove.sarif) GNATprove writes; authoritative, "
                         "and it must be freshly written by this run "
                         "(default: the one result set under the current "
                         "directory created or changed by this run)")
    pr.add_argument("--dry-run", action="store_true",
                    help="show the GNATprove command and exit 0 without "
                         "running it or inspecting any results")
    pr.add_argument("--name", help="run name shown in the report")
    pr.add_argument("--client-unit", action="append", default=[],
                    help="as for explain")

    for s in (e, a, c, pr):
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


def split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """For `prove`, everything after the FIRST `--` is GNATprove's,
    verbatim (including any later `--`). Split before argparse sees it, so
    the behaviour does not depend on argparse's version-specific `--`
    handling. Other commands are untouched."""
    if argv[:1] == ["prove"] and "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def _unproved_note(report) -> str | None:
    unproved = sum(len(r.unproved) for r in report.runs)
    if not unproved:
        return None
    return (f"GNATprove exited 0 although {unproved} check(s) are "
            "unproved (permitted by its configuration); spark-refine "
            "reports them but does not override GNATprove's exit status")


def prove(args, passthrough: list[str]) -> int:
    """`spark-refine prove`: run GNATprove, then explain the fresh result.
    Exit policy: see orchestration.exit_status and the module docstring."""
    argv = build_command(args.project, passthrough, args.gnatprove)
    print(f"GNATprove command:\n  {display_command(argv)}", file=sys.stderr,
          flush=True)
    if args.dry_run:
        doc = plan(argv, args.results)
        if args.format == "json":
            sys.stdout.write(json.dumps(
                {"format_version": JSON_FORMAT_VERSION,
                 "tool": "spark_refine_diagnostics",
                 "orchestration": doc}, indent=2) + "\n")
        else:
            sys.stdout.write(orchestration_plan_text(doc))
        return 0
    # snapshot BEFORE launching: the freshness baseline
    freshness = Freshness(Path.cwd(), args.results)
    try:
        raw = run_gnatprove(argv)
    except LaunchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    code = normalize_returncode(raw)
    signal = f" (terminated by signal {-raw})" if raw < 0 else ""
    print(f"GNATprove exit: {code}{signal}", file=sys.stderr, flush=True)
    try:
        selection = freshness.select()
        report = analyze_path_report(selection.path, args.name,
                                     args.client_unit)
    except (FreshnessError, InputError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if code != 0:
            print(f"GNATprove failed (exit {code}) before usable fresh "
                  "result output was found; no diagnostics report was "
                  "produced. Its console output is shown above, on "
                  "stderr.", file=sys.stderr)
            return code
        return 2
    report.analysis["orchestration"] = metadata(argv, raw, selection)
    if code == 0:
        note = _unproved_note(report)
        if note:
            report.notes.append(note)
    render = to_json if args.format == "json" else to_text
    sys.stdout.write(render(report.runs, report.diagnostics, report.notes,
                            report.analysis))
    return exit_status(code, any(d.code in args.fail_on
                                 for d in report.diagnostics))


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    argv, passthrough = split_passthrough(argv)
    args = _parser(prog).parse_args(argv)
    if args.command == "prove":
        return prove(args, passthrough)
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
