"""GNAT source checksum (the value GNAT records in .ali `D` lines).

Task 009 uses it for its SOURCE/RESULT PROVENANCE GATE: the source
Libadalang analyses must match GNAT's .ali source identity metadata (this
checksum plus the second-resolution D timestamp). That is not byte
identity; see semantic.py. GNAT writes, for every
source a unit depends on, a line

    D <file> <YYYYMMDDHHMMSS mtime, UTC> <8-hex checksum> ...

into the unit's .ali. The checksum algorithm is documented in GNAT's
sinput.ads ("Checksum Handling") and implemented in scng.adb:

  * CRC-32 (System.CRC32: reflected polynomial, initial value 16#FFFF_FFFF#)
    WITHOUT the final XOR;
  * accumulated over every non-blank character outside comments, excluding
    control characters;
  * identifier and keyword letters are folded to lower case, and each
    identifier/keyword adds the byte Token_Type'Pos (Tok_Identifier) = 5;
  * each numeric literal adds Tok_Integer_Literal = 0 / Tok_Real_Literal
    = 1; underscores of decimal digit sequences are not accumulated
    (those between extended digits of a based literal are), extended
    digits and the exponent mark are folded to lower case;
  * string and character literals are accumulated verbatim (no token
    byte);
  * the Ada 2022 bracket characters [ ] and the braces { } are not
    accumulated.

It is insensitive to layout and comments, so it alone says nothing about
line/column positions; the adapter also compares the D timestamp with the
file's modification time (semantic_lal.py). Both together still cannot
detect a layout/comment-only edit made within the same timestamp second.

This module is pure Python and only consumes a token stream; the tokens
come from Libadalang (semantic_lal.py). It never parses Ada itself.
Sources containing non-ASCII characters are not supported (the wide
character rules are not implemented): the result is then None and the
caller treats provenance as unavailable.
"""

from __future__ import annotations

import zlib
from collections.abc import Iterable

TOK_INTEGER_LITERAL = 0
TOK_REAL_LITERAL = 1
TOK_IDENTIFIER = 5
_NOT_ACCUMULATED = frozenset("[]{}")


def _numeric(text: str) -> bytes | None:
    t = text.lower()
    delim = "#" if "#" in t else (":" if ":" in t else None)
    if delim is not None:
        base, _, rest = t.partition(delim)
        body, sep, exponent = rest.partition(delim)
        if not sep:
            return None
        real = "." in body
        out = base.replace("_", "") + delim + body + delim
    else:
        body, _, exponent = t.partition("e")
        real = "." in body
        out = body.replace("_", "")
        exponent = ("e" + exponent) if exponent or t.endswith("e") else ""
    if exponent:
        if not exponent.startswith("e"):
            return None
        out += "e" + exponent[1:].replace("_", "")
    token = TOK_REAL_LITERAL if real else TOK_INTEGER_LITERAL
    return out.encode("ascii") + bytes([token])


def token_bytes(text: str) -> bytes | None:
    """Checksum contribution of one non-trivia token (None: unsupported)."""
    if not text:
        return b""
    if not text.isascii():
        return None
    first = text[0]
    if first in "\"%'":
        # string / character literal, or the tick of an attribute
        return text.encode("ascii")
    if first.isalpha():
        return text.lower().encode("ascii") + bytes([TOK_IDENTIFIER])
    if first.isdigit():
        return _numeric(text)
    return "".join(c for c in text
                   if c not in _NOT_ACCUMULATED).encode("ascii")


def gnat_checksum(tokens: Iterable[str]) -> str | None:
    """GNAT checksum (8 lower-case hex digits, as written in .ali D
    records) of the non-trivia token texts of one source file, in order.
    None if a token is not supported (non-ASCII, malformed literal)."""
    data = bytearray()
    for text in tokens:
        b = token_bytes(text)
        if b is None:
            return None
        data += b
    return f"{zlib.crc32(bytes(data)) ^ 0xFFFFFFFF:08x}"
