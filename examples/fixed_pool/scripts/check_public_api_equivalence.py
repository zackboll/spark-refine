#!/usr/bin/env python3
"""Public-API equivalence gate for the fixed-pool variants (Task 004).

The library-backed variant must expose exactly the Task 003 visible
specification: the same declarations, the same public ghost Free_Model and
the same abstract Pre/Post contracts. Only context clauses that are
`private with` (invisible to clients) and the private part may differ.

For each fixed_pool.ads this script takes the text from the start of the
file up to the "private" keyword that opens the private part, removes Ada
comments and `private with` context clauses, splits it into lexical tokens
(whitespace and layout ignored) and requires the token sequences to be
identical to the reference (src/fixed_pool.ads, the Task 003 baseline).
Identifier and keyword case is preserved.

The number of removed `private with` clauses is reported so that the
exclusion is visible, not silent.

  python3 scripts/check_public_api_equivalence.py          # gate
  python3 scripts/check_public_api_equivalence.py --show   # print tokens

Same tokenizer and rules as examples/ring_buffer/scripts/
check_public_api_equivalence.py (kept independent per benchmark).
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
REFERENCE = "src/fixed_pool.ads"
VARIANTS = ("variants/library_backed/fixed_pool.ads",)

TOKEN = re.compile(
    r'"(?:[^"]|"")*"'            # string literal
    r"|'.'(?!\w)"                 # character literal
    r"|[A-Za-z_][A-Za-z0-9_]*"    # identifier / reserved word
    r"|\d[\d_]*(?:#[\dA-Fa-f_.]+#)?(?:\.[\d_]+)?(?:[Ee][+-]?\d+)?"
    r"|=>|\.\.|\*\*|:=|/=|>=|<=|<<|>>|<>"
    r"|[&'()*+,\-./:;<=>|\[\]@]")


def strip_comments(text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def visible_part(path: Path) -> tuple[list[str], int]:
    code = strip_comments(path.read_text(encoding="utf-8"))
    tokens = TOKEN.findall(code)
    leftovers = TOKEN.sub(" ", code).split()
    if leftovers:
        raise SystemExit(f"{path}: untokenizable text {leftovers[:5]}")
    # Drop "private with X[, Y];" context clauses: they are not visible to
    # clients (RM 10.1.2) and cannot change the public API.
    out, removed, i = [], 0, 0
    while i < len(tokens):
        if (tokens[i].lower() == "private" and i + 1 < len(tokens)
                and tokens[i + 1].lower() == "with"
                and (i == 0 or tokens[i - 1] == ";")):
            j = tokens.index(";", i)
            removed += 1
            i = j + 1
            continue
        out.append(tokens[i])
        i += 1
    lowered = [t.lower() for t in out]
    starts = [i for i, t in enumerate(lowered)
              if t == "private" and i > 0 and lowered[i - 1] == ";"]
    if len(starts) != 1:
        raise SystemExit(f"{path}: expected exactly one private part, "
                         f"found {len(starts)}")
    return out[:starts[0]], removed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    ref, ref_removed = visible_part(EXAMPLE / REFERENCE)
    if args.show:
        print(" ".join(ref))
    if len(ref) < 50 or ref_removed:
        print("public API equivalence FAILED: unexpected reference "
              f"({len(ref)} tokens, {ref_removed} private with)",
              file=sys.stderr)
        return 1
    failures = 0
    for rel in VARIANTS:
        path = EXAMPLE / rel
        if not path.is_file():
            print(f"public API equivalence FAILED: missing {rel}",
                  file=sys.stderr)
            failures += 1
            continue
        got, removed = visible_part(path)
        if got != ref:
            failures += 1
            print(f"public API equivalence FAILED: {rel} differs from "
                  f"{REFERENCE} (token diff):", file=sys.stderr)
            for line in difflib.unified_diff(ref, got, REFERENCE, rel,
                                             lineterm="", n=4):
                print("  " + line, file=sys.stderr)
        else:
            print(f"  {rel}: identical visible part ({len(got)} tokens, "
                  f"0 public token changes; {removed} 'private with' "
                  "context clause(s) excluded)")
    if failures:
        return 1
    print(f"public API equivalence: PASS ({len(VARIANTS)} variant(s) match "
          f"{REFERENCE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
