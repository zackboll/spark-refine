#!/usr/bin/env python3
"""Public-API equivalence gate for the ring-buffer representations.

Every private representation of Ring_Buffer must expose exactly the same
visible specification: the same declarations, the same public ghost Model
and the same abstract Pre/Post contracts. Only the private part may differ.

For each ring_buffer.ads this script takes the text from the start of the
file up to the "private" keyword that opens the private part, removes Ada
comments, splits it into lexical tokens (whitespace and layout ignored) and
requires the token sequences to be identical to the reference
(src/ring_buffer.ads, the Task 001 baseline). Identifier and keyword case
is preserved: any textual change to a declaration or contract, including
one that would be semantically equivalent, is reported so that a reviewer
has to look at it.

  python3 scripts/check_public_api_equivalence.py          # gate
  python3 scripts/check_public_api_equivalence.py --show   # print tokens
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
REFERENCE = "src/ring_buffer.ads"
VARIANTS = ("variants/head_tail_count/ring_buffer.ads",)

# Ada lexical tokens: string literals, character literals, identifiers /
# keywords / numeric literals (incl. based literals and attributes), and
# compound or single delimiters.
TOKEN = re.compile(
    r'"(?:[^"]|"")*"'            # string literal
    r"|'.'(?!\w)"                 # character literal
    r"|[A-Za-z_][A-Za-z0-9_]*"    # identifier / reserved word
    r"|\d[\d_]*(?:#[\dA-Fa-f_.]+#)?(?:\.[\d_]+)?(?:[Ee][+-]?\d+)?"
    r"|=>|\.\.|\*\*|:=|/=|>=|<=|<<|>>|<>"
    r"|[&'()*+,\-./:;<=>|\[\]@]")


def strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        # A "--" inside a string literal would be mis-stripped; the package
        # spec contains no string literals, and the tokenizer below would
        # expose any such damage as a token difference.
        out.append(line.split("--", 1)[0])
    return "\n".join(out)


def visible_part(path: Path) -> list[str]:
    code = strip_comments(path.read_text(encoding="utf-8"))
    tokens = TOKEN.findall(code)
    leftovers = TOKEN.sub(" ", code).split()
    if leftovers:
        raise SystemExit(f"{path}: untokenizable text {leftovers[:5]}")
    lowered = [t.lower() for t in tokens]
    # The private part starts at a "private" that follows the ";" of the
    # last visible declaration, not at "is private" in a private type
    # declaration such as "type Buffer is private;".
    starts = [i for i, t in enumerate(lowered)
              if t == "private" and i > 0 and lowered[i - 1] == ";"]
    if len(starts) != 1:
        raise SystemExit(f"{path}: expected exactly one private part, "
                         f"found {len(starts)}")
    return tokens[:starts[0]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true",
                    help="print the normalised visible part of the reference")
    args = ap.parse_args()

    ref = visible_part(EXAMPLE / REFERENCE)
    if args.show:
        print(" ".join(ref))
    if len(ref) < 50:
        print(f"public API equivalence FAILED: reference visible part has "
              f"only {len(ref)} tokens", file=sys.stderr)
        return 1
    failures = 0
    for rel in VARIANTS:
        path = EXAMPLE / rel
        if not path.is_file():
            print(f"public API equivalence FAILED: missing {rel}",
                  file=sys.stderr)
            failures += 1
            continue
        got = visible_part(path)
        if got != ref:
            failures += 1
            diff = difflib.unified_diff(ref, got, REFERENCE, rel,
                                        lineterm="", n=4)
            print(f"public API equivalence FAILED: {rel} differs from "
                  f"{REFERENCE} (token diff):", file=sys.stderr)
            for line in diff:
                print("  " + line, file=sys.stderr)
        else:
            print(f"  {rel}: identical visible part ({len(got)} tokens)")
    if failures:
        return 1
    print(f"public API equivalence: PASS ({len(VARIANTS)} variant(s) match "
          f"{REFERENCE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
