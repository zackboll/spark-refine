"""Task 009: the Libadalang adapter (the ONLY module importing libadalang).

Owns: optional import, project context, unit loading, source-location
lookup, call discovery, name/declaration resolution, Pre aspect extraction
and conjunct decomposition. Everything is descriptive source semantics;
GNATprove stays the proof authority. Nothing here parses Ada text: all
structure comes from Libadalang's tree and name resolution.

Location -> call rule (observed for FSF GNATprove 16.1.0 on the fixtures
and the Task 009 experiment): a VC_PRECONDITION is reported at the start
of the called name or, for a selected name `P.Op (...)`, at the `.` before
the selector. A check resolves to a call only if EXACTLY ONE call in the
unit is anchored at the check's line:column; zero -> unresolved, more ->
ambiguous. Nothing is guessed from identifier text.

Public methods return plain dicts (no Libadalang objects) and never raise
for a semantic problem: problems become structured `resolution` states.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from .gnat_checksum import gnat_checksum

BACKEND = "libadalang"


class BackendUnavailable(Exception):
    """Libadalang cannot be used (import or project load failed)."""


def _import():
    try:
        import libadalang  # optional; see scripts/setup_libadalang.sh
    except Exception as exc:  # ImportError, or OSError from the native lib
        raise BackendUnavailable(
            f"libadalang not importable ({type(exc).__name__}: {exc})"
        ) from None
    return libadalang


def backend_version(lal) -> str:
    """Crate version recorded by setup_libadalang.sh (Libadalang's own
    `version` constant is "undefined" in Alire builds)."""
    marker = Path(lal.__file__).parent / "SPARK_REFINE_CRATE_VERSION"
    try:
        return marker.read_text("utf-8").strip()
    except OSError:
        return str(getattr(lal, "version", "unknown"))


def mtime_stamp(path: str) -> str:
    """File modification time as GNAT writes it in .ali D records."""
    t = datetime.datetime.fromtimestamp(os.stat(path).st_mtime,
                                        datetime.timezone.utc)
    return t.strftime("%Y%m%d%H%M%S")


class LalBackend:
    def __init__(self, project: str, scenario: dict[str, str],
                 ali_records: dict[str, set[tuple[str, str]]]):
        lal = _import()
        self.lal = lal
        self.version = backend_version(lal)
        self.project_dir = Path(project).resolve().parent
        try:
            self.gpr = lal.GPRProject(project, scenario_vars=dict(scenario),
                                      print_errors=False)
            self.ctx = self.gpr.create_context()
            files = self.gpr.source_files(
                mode=lal.SourceFilesMode.whole_project)
        except Exception as exc:
            first = (str(exc).splitlines() or [""])[0]
            raise BackendUnavailable(
                f"project {project} could not be loaded "
                f"({type(exc).__name__}: {first})") from None
        self.by_name: dict[str, list[str]] = {}
        for f in files:
            self.by_name.setdefault(os.path.basename(f), []).append(f)
        self.ali = ali_records
        self._prov: dict[str, str | None] = {}

    # ------------------------------------------------------------ helpers
    def rel(self, path: str) -> str:
        """Stable display path: relative to the project directory when the
        file lies below it, else the base name (e.g. SPARKlib sources)."""
        p = Path(path).resolve()
        try:
            return p.relative_to(self.project_dir).as_posix()
        except ValueError:
            return p.name

    def span(self, node) -> dict:
        r = node.sloc_range
        return {"file": self.rel(node.unit.filename),
                "start_line": r.start.line, "start_column": r.start.column,
                "end_line": r.end.line, "end_column": r.end.column}

    def provenance_problem(self, path: str) -> str | None:
        """None iff `path` is the source GNATprove analysed, per the result
        set's .ali D records: GNAT checksum AND timestamp both equal. (The
        checksum ignores layout, so the timestamp is required too before
        any line/column is trusted.)"""
        if path in self._prov:
            return self._prov[path]
        name = os.path.basename(path)
        records = self.ali.get(name)
        problem = None
        if not records:
            problem = f"{name}: not among the result set's .ali sources"
        else:
            unit = self.ctx.get_from_file(path)
            toks, t = [], unit.first_token
            while t is not None:
                if not t.is_trivia and t.kind != "Termination":
                    toks.append(t.text)
                t = t.next
            ck = gnat_checksum(toks)
            if ck is None:
                problem = f"{name}: GNAT checksum not computable"
            elif ck not in {c for _, c in records}:
                problem = (f"{name}: source differs from the source "
                           "GNATprove analysed (checksum)")
            elif (mtime_stamp(path), ck) not in records:
                problem = (f"{name}: same checksum but a different "
                           "timestamp than the analysed source (layout "
                           "may differ)")
        self._prov[path] = problem
        return problem

    def unit_for(self, basename: str):
        paths = self.by_name.get(basename, [])
        if len(paths) != 1:
            return None, (f"{basename}: {len(paths)} project sources with "
                          "this name" if paths else
                          f"{basename}: not a source of the project")
        problem = self.provenance_problem(paths[0])
        if problem:
            return None, problem
        unit = self.ctx.get_from_file(paths[0])
        if unit.diagnostics:
            return None, (f"{basename}: parse diagnostics prevent safe "
                          f"lookup ({unit.diagnostics[0]})")
        return unit, None

    # -------------------------------------------------------------- calls
    def _anchor(self, callee) -> tuple[int, int]:
        lal = self.lal
        if isinstance(callee, lal.DottedName):
            t = callee.f_suffix.token_start.previous
            while t is not None and t.is_trivia:
                t = t.previous
            s = t.sloc_range.start
        else:
            s = callee.sloc_range.start
        return s.line, s.column

    def calls_at(self, unit, line: int, column: int):
        """([(call node, called name)] anchored at line:column, whether a
        name-resolution error was seen)."""
        lal = self.lal
        hits, errors = [], False
        for n in unit.root.findall(lambda x: isinstance(x, lal.Name)):
            p = n.parent
            if ((isinstance(p, lal.CallExpr) and p.f_name == n)
                    or (isinstance(p, lal.DottedName) and p.f_suffix == n)):
                continue  # component of a larger call name
            try:
                if not n.p_is_call:
                    continue
            except lal.PropertyError:
                errors = True
                continue
            callee = n.f_name if isinstance(n, lal.CallExpr) else n
            if self._anchor(callee) == (line, column):
                hits.append((n, callee))
        return hits, errors

    def conjuncts(self, expr) -> list:
        """Top-level `and` / `and then` operands in source order. Tree
        structure only: no normalisation; parenthesised expressions and
        `or` / `or else` / `not` subtrees stay whole."""
        lal = self.lal
        if (isinstance(expr, lal.BinOp)
                and isinstance(expr.f_op, (lal.OpAnd, lal.OpAndThen))):
            return self.conjuncts(expr.f_left) + self.conjuncts(expr.f_right)
        return [expr]

    def precondition(self, decl) -> dict:
        """The EXPLICIT Pre aspect only (never synthesized language
        checks)."""
        aspect = decl.p_get_aspect("Pre")
        if not aspect.exists or aspect.value is None:
            return {"explicit": False, "text": None, "location": None,
                    "conjuncts": []}
        expr = aspect.value
        return {"explicit": True, "text": expr.text,
                "location": self.span(expr),
                "conjuncts": [{"index": i, "text": c.text,
                               "location": self.span(c)}
                              for i, c in enumerate(self.conjuncts(expr))]}

    def callee_kind(self, decl) -> str:
        lal = self.lal
        if isinstance(decl, lal.EntryDecl):
            return "entry"
        spec = decl.p_subp_spec_or_null()
        if spec is None:
            return "unknown"
        return ("function" if isinstance(spec.f_subp_kind,
                                         lal.SubpKindFunction)
                else "procedure")

    # ------------------------------------------------------------- checks
    def resolve_precondition(self, file: str, line: int, column: int
                             ) -> dict:
        unit, problem = self.unit_for(file)
        if unit is None:
            return {"resolution": "unavailable", "reason": problem}
        hits, errors = self.calls_at(unit, line, column)
        if len(hits) > 1:
            return {"resolution": "ambiguous",
                    "reason": f"{len(hits)} calls anchored at this "
                              "location"}
        if not hits:
            return {"resolution": "unresolved",
                    "reason": "no call anchored at this location"
                              + (" (name resolution errors in this unit)"
                                 if errors else "")}
        call, callee = hits[0]
        try:
            decl = callee.p_referenced_decl()
        except self.lal.PropertyError as exc:
            return {"resolution": "unresolved",
                    "reason": f"name resolution failed: {exc}"}
        if decl is None:
            return {"resolution": "unresolved",
                    "reason": "called name has no referenced declaration"}
        problem = self.provenance_problem(decl.unit.filename)
        if problem:
            return {"resolution": "unavailable",
                    "reason": f"callee declaration: {problem}"}
        return {"resolution": "exact",
                "call": {"text": call.text, "location": self.span(call)},
                "callee": {"name": decl.p_fully_qualified_name,
                           "kind": self.callee_kind(decl),
                           "declaration": self.span(decl)},
                "precondition": self.precondition(decl)}

    def resolve_assertion(self, file: str, line: int, column: int) -> dict:
        """Source context of a VC_ASSERT: the asserted expression that
        covers the location, and the enclosing subprogram. Never a callee
        or a contract."""
        lal = self.lal
        unit, problem = self.unit_for(file)
        if unit is None:
            return {"resolution": "unavailable", "reason": problem}
        node = unit.root.lookup(lal.Sloc(line, column))
        pragma = None
        for p in (node.parents() if node is not None else []):
            if isinstance(p, lal.PragmaNode):
                pragma = p
                break
        arg_index = {"assert": 0, "assert_and_cut": 0, "loop_invariant": 0,
                     "check": 1}
        name = pragma.f_id.text.lower() if pragma is not None else ""
        if name not in arg_index or len(pragma.f_args) <= arg_index[name]:
            return {"resolution": "unresolved",
                    "reason": "location is not inside an assertion pragma"}
        expr = pragma.f_args[arg_index[name]].f_expr
        r = expr.sloc_range
        if not ((r.start.line, r.start.column) <= (line, column)
                < (r.end.line, r.end.column)):
            return {"resolution": "unresolved",
                    "reason": "location is not inside the asserted "
                              "expression"}
        enclosing = None
        for p in pragma.parents():
            if isinstance(p, lal.BaseSubpBody):
                enclosing = p.p_fully_qualified_name
                break
        return {"resolution": "exact",
                "assertion": {"pragma": pragma.f_id.text, "text": expr.text,
                              "location": self.span(expr)},
                "enclosing_subprogram": enclosing}


def open_backend(project: str, scenario: dict[str, str],
                 ali_records: dict[str, set[tuple[str, str]]]) -> LalBackend:
    """Raises BackendUnavailable if Libadalang or the project cannot be
    used."""
    return LalBackend(project, scenario, ali_records)
