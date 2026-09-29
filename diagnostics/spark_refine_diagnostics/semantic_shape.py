"""Task 011: the structural contract of a Task 009 `exact` semantic entry.

One definition of "complete", shared by
  * semantic_groups.py (Task 010): an exact VC_PRECONDITION entry that is
    not complete is `semantic_incomplete` and never grouped;
  * render.py (Task 011): an exact entry that is not complete is rendered
    as `semantic entry: incomplete` instead of being indexed.

Pure predicates over plain data: no Libadalang, no grouping policy, no
message text, no interpretation of any value (a string is a string; no
expression is parsed or evaluated). Anything absent, of the wrong type or
inconsistent -> False. Callers never repair or invent missing facts.

The shape is the one semantic_lal.py emits and semantic.py completes:

  VC_PRECONDITION
    call:         {text: str, location: SPAN}
    callee:       {name: non-empty str, kind: non-empty str,
                   declaration: SPAN}
    precondition: {explicit: True,  text: str,  location: SPAN,
                   conjuncts: [{index: int, text: str, location: SPAN}],
                   failed_conjunct: None,
                   attribution: "not_provided_by_gnatprove"}
               or {explicit: False, text: None, location: None,
                   conjuncts: [...], failed_conjunct: None,
                   attribution: "not_provided_by_gnatprove"}
  VC_ASSERT (and other assertion-context rules)
    assertion:    {pragma: str, text: str, location: SPAN}
    enclosing_subprogram: non-empty str or None (optional key)

  SPAN = {file: str, start_line: int, start_column: int,
          end_line: int, end_column: int}      (bool is not an int)
"""

from __future__ import annotations

ATTRIBUTION = "not_provided_by_gnatprove"   # Task 009 value, verbatim

_SPAN_FIELDS = (("file", str), ("start_line", int), ("start_column", int),
                ("end_line", int), ("end_column", int))


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def span_ok(s) -> bool:
    """A complete Task 009 source span: file + start AND end position."""
    return isinstance(s, dict) and all(
        (is_int(s.get(k)) if t is int else isinstance(s.get(k), t))
        for k, t in _SPAN_FIELDS)


def nonempty_str(v) -> bool:
    return isinstance(v, str) and v != ""


def exact_precondition_complete(c) -> bool:
    """An exact precondition entry carries the complete Task 009 semantic
    structure (call, callee, precondition) that grouping and rendering
    read. Structural only: no value is interpreted."""
    if not isinstance(c, dict):
        return False
    call, callee, pre = c.get("call"), c.get("callee"), c.get("precondition")
    if not (isinstance(call, dict) and isinstance(callee, dict)
            and isinstance(pre, dict)):
        return False
    if not (isinstance(call.get("text"), str)
            and span_ok(call.get("location"))):
        return False
    if not (nonempty_str(callee.get("name"))
            and nonempty_str(callee.get("kind"))
            and span_ok(callee.get("declaration"))):
        return False
    conjuncts = pre.get("conjuncts")
    if not ("failed_conjunct" in pre and pre["failed_conjunct"] is None
            and pre.get("attribution") == ATTRIBUTION
            and isinstance(conjuncts, list)):
        return False
    for cj in conjuncts:
        if not (isinstance(cj, dict) and is_int(cj.get("index"))
                and isinstance(cj.get("text"), str)
                and span_ok(cj.get("location"))):
            return False
    explicit = pre.get("explicit")
    if explicit is True:
        return (isinstance(pre.get("text"), str)
                and span_ok(pre.get("location")))
    if explicit is False:
        return ("text" in pre and pre["text"] is None
                and "location" in pre and pre["location"] is None)
    return False


def exact_assertion_complete(c) -> bool:
    """An exact assertion entry carries the complete Task 009 assertion
    context (asserted expression text + span, pragma name) and, if
    present, a usable enclosing subprogram name."""
    if not isinstance(c, dict):
        return False
    a = c.get("assertion")
    if not (isinstance(a, dict) and isinstance(a.get("pragma"), str)
            and isinstance(a.get("text"), str)
            and span_ok(a.get("location"))):
        return False
    enclosing = c.get("enclosing_subprogram")
    return enclosing is None or nonempty_str(enclosing)
