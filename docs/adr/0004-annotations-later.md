# ADR 0004: Prefer standard Ada annotations for later source-local metadata

Status: Proposed. **Deferred by
[ADR 0005](0005-library-and-diagnostics-first.md).**

> **Note (Task 007).** This ADR concerns source-local metadata *for
> generation*. With generation deferred, no annotation schema is being
> designed. `pragma Annotate` plus Libadalang may still be useful later
> for other purposes, such as marking which source is authoritative
> specification versus mechanical proof support for diagnostics or agent
> policy. That would need its own evidence and ADR. The text below is
> kept unchanged as history.

## Context

Once the semantic vocabulary stabilizes, representation-role metadata will often be easiest to maintain beside the declaration it describes.

## Decision

Investigate `pragma Annotate`/`aspect Annotate` plus Libadalang rather than inventing a new source syntax.

## Rationale

The mechanism is designed for external tools and is permitted by SPARK. It preserves ordinary Ada parsing and allows the project to remain external.

## Consequences

The exact annotation schema is deferred until after at least one successful pattern and benchmark.
