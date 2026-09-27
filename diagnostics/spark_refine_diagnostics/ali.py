"""Narrow adapter: unit dependencies from GNAT .ali files.

ALI is a compiler-internal, version-sensitive format. This module is the
ONLY place that reads it, and it never raises: every problem becomes a
structured status. Only GNAT 16.1.0 ALI (header `V "GNAT Lib v16"`), as
written by FSF GNATprove 16.1.0, has been observed; no compatibility with
other compiler versions is claimed.

Records read (one per line, record kind = first character):

    V "GNAT Lib v<N>"              version header (must be the first line)
    U <unit>%s|b  <file>  ...      a compilation unit of this ALI
    W <unit>%s|b  [<file> <ali>]   explicit `with`
    Z <unit>%s|b  [<file> <ali>]   implicit `with` (e.g. generic bodies)

Any other record kind is ignored (it carries nothing SRD002 needs). A W/Z
record whose first field is not `<name>%s` / `<name>%b` is malformed and
makes the whole file unusable: a partially read dependency list could hide
an implementation dependency and let SRD002 fire wrongly.

Per file:   parse_ali_text(text)          -> AliFile(status, deps, detail)
Per run:    load_ali_deps(dir, units)     -> AliDeps(status, deps, problems)

AliDeps.status is "ok" only when every requested unit has a valid .ali
file; otherwise it is "unavailable" and SRD002 is skipped. There is no
fallback (in particular, dependencies are never guessed from file names).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

OBSERVED_ALI_VERSION = "GNAT Lib v16"

_VERSION = re.compile(r'^V "([^"]*)"')
_UNIT_REF = re.compile(r"^([a-z0-9_.]+)%[sb]$", re.IGNORECASE)

OK = "ok"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AliFile:
    """status: ok | empty | no_version | malformed | unreadable | missing"""

    status: str
    deps: frozenset[str] = frozenset()
    version: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK


@dataclass
class AliDeps:
    status: str = UNAVAILABLE
    deps: dict[str, set[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    versions: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return self.status == OK


def parse_ali_text(text: str) -> AliFile:
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        return AliFile("empty", detail="empty ALI file")
    m = _VERSION.match(lines[0])
    if not m:
        return AliFile("no_version",
                       detail="first line is not a V \"GNAT Lib ...\" header "
                              "(truncated or not an ALI file)")
    version = m.group(1)
    deps: set[str] = set()
    units = 0
    for n, line in enumerate(lines[1:], start=2):
        kind = line[:1]
        if kind == "U":
            units += 1
        if kind not in ("W", "Z"):
            continue  # unknown or irrelevant record kinds are harmless
        fields = line[1:].split()
        if line[1:2] not in (" ", "\t") or not fields:
            return AliFile("malformed", version=version,
                           detail=f"line {n}: truncated {kind} record")
        ref = _UNIT_REF.match(fields[0])
        if not ref:
            return AliFile("malformed", version=version,
                           detail=f"line {n}: malformed {kind} record "
                                  f"{fields[0]!r}")
        deps.add(ref.group(1).lower())
    if units == 0:
        return AliFile("malformed", version=version,
                       detail="no U (unit) record: dependency information "
                              "absent or truncated")
    return AliFile(OK, deps=frozenset(deps), version=version)


def read_ali(path: Path) -> AliFile:
    if not path.is_file():
        return AliFile("missing", detail=f"{path.name}: no such file")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return AliFile("unreadable", detail=f"{path.name}: {exc}")
    return parse_ali_text(text)


def load_ali_deps(directory: Path,
                  units: list[str] | None = None) -> AliDeps:
    """Dependencies of `units` (default: every <unit>.ali in `directory`).

    status "ok" requires a valid ALI file for every requested unit. Units
    without checks (for example SPARK_Mode => Off drivers) must still have
    an ALI file: GNATprove writes one for every analysed unit.
    """
    out = AliDeps()
    try:
        present = {p.stem.lower(): p for p in directory.glob("*.ali")}
    except OSError as exc:
        out.problems.append(f"cannot list {directory}: {exc}")
        return out
    wanted = sorted(set(units) if units is not None else set(present))
    if not wanted:
        out.problems.append("no .ali files")
        return out
    for unit in wanted:
        path = present.get(unit, directory / f"{unit}.ali")
        ali = read_ali(path)
        if not ali.ok:
            out.problems.append(f"{unit}.ali: {ali.status}"
                                + (f" ({ali.detail})" if ali.detail else ""))
            continue
        out.versions.add(ali.version)
        out.deps[unit] = set(ali.deps)
    if not out.problems:
        out.status = OK
    return out
