"""Narrow adapter: unit dependencies from GNAT .ali files.

ALI is a compiler-internal, version-sensitive format. This module is the
ONLY place that reads it, and it never raises: every problem becomes a
structured status. Only GNAT 16.1.0 ALI (header `V "GNAT Lib v16"`), as
written by FSF GNATprove 16.1.0, has been observed; no compatibility with
other compiler versions is claimed.

The header value is checked against SUPPORTED_ALI_VERSIONS. "GNAT Lib v16"
is accepted because it is the header the pinned GNAT 16.1.0 writes; this
does not claim that every GNAT 16 release writes a compatible format. Any
other value (e.g. "GNAT Lib v17", or an arbitrary string) yields status
`unsupported_version` with the observed version, no dependencies are read,
and SRD002 is skipped exactly as for any other unusable ALI file.

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
# The only ALI format validated (written by the pinned GNAT 16.1.0).
SUPPORTED_ALI_VERSIONS = frozenset({OBSERVED_ALI_VERSION})
UNSUPPORTED_VERSION_DETAIL = (
    "supported ALI version is "
    + ", ".join(sorted(SUPPORTED_ALI_VERSIONS)))

_VERSION = re.compile(r'^V "([^"]*)"')
_UNIT_REF = re.compile(r"^([a-z0-9_.]+)%[sb]$", re.IGNORECASE)

OK = "ok"
UNAVAILABLE = "unavailable"
UNSUPPORTED_VERSION = "unsupported_version"


@dataclass(frozen=True)
class AliFile:
    """status: ok | empty | no_version | unsupported_version | malformed |
    unreadable | missing. `version` is the observed header value whenever
    a header was found (also for unsupported_version)."""

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
    # header values of the ALI files that were read successfully
    versions: set[str] = field(default_factory=set)
    # header values that were recognised but are not supported
    unsupported_versions: set[str] = field(default_factory=set)

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
    if version not in SUPPORTED_ALI_VERSIONS:
        # Recognised header, unvalidated format: never read as dependency
        # data (a different record layout could silently drop a `with`).
        return AliFile(UNSUPPORTED_VERSION, version=version,
                       detail=UNSUPPORTED_VERSION_DETAIL)
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


_D_RECORD = re.compile(r"^D (\S+)\s+(\d{14}) ([0-9a-f]{8})(?:\s|$)")


@dataclass
class AliSources:
    """Task 009: the source files a result set was produced from, per the
    `D <file> <YYYYMMDDHHMMSS> <checksum> ...` records of its .ali files
    (GNAT's own source dependency list; timestamp = file mtime in UTC,
    checksum = GNAT source checksum, see gnat_checksum.py).

    records: basename -> {(timestamp, checksum), ...} over all .ali files.
    Used only by the semantic enrichment's provenance gate (source must
    match this GNAT source identity metadata; checksum + second-resolution
    timestamp, not byte identity). Never used by SRD001-SRD003."""

    records: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.records)


def load_ali_sources(directory: Path) -> AliSources:
    out = AliSources()
    try:
        paths = sorted(directory.glob("*.ali"))
    except OSError as exc:
        out.problems.append(f"cannot list {directory}: {exc}")
        return out
    for path in paths:
        try:
            lines = path.read_text("utf-8", errors="replace").splitlines()
        except OSError as exc:
            out.problems.append(f"{path.name}: {exc}")
            continue
        m = _VERSION.match(lines[0]) if lines else None
        if not m or m.group(1) not in SUPPORTED_ALI_VERSIONS:
            out.problems.append(f"{path.name}: unsupported or missing ALI "
                                "version header")
            continue
        for n, line in enumerate(lines, start=1):
            if not line.startswith("D "):
                continue
            d = _D_RECORD.match(line)
            if not d:
                out.problems.append(f"{path.name}: line {n}: malformed D "
                                    "record")
                continue
            out.records.setdefault(d.group(1), set()).add(
                (d.group(2), d.group(3)))
    if not out.records and not out.problems:
        out.problems.append("no .ali source (D) records")
    return out


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
            if ali.status == UNSUPPORTED_VERSION:
                out.unsupported_versions.add(ali.version)
                out.problems.append(f"{unit}.ali: {ali.status} "
                                    f"(version {ali.version!r}; "
                                    f"{ali.detail})")
            else:
                out.problems.append(
                    f"{unit}.ali: {ali.status}"
                    + (f" ({ali.detail})" if ali.detail else ""))
            continue
        out.versions.add(ali.version)
        out.deps[unit] = set(ali.deps)
    if not out.problems:
        out.status = OK
    return out
