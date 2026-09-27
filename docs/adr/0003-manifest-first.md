# ADR 0003: Use a TOML manifest for the MVP

Status: Accepted for bootstrap. **Implementation priority superseded by
[ADR 0005](0005-library-and-diagnostics-first.md) (deferred).**

> **Note (Task 007).** The manifest existed to drive a source generator.
> Tasks 001–004 found generation not justified for the demonstrated
> patterns, so no manifest-driven tooling is planned. The only manifest
> in the repository, `examples/ring_buffer/spark-refine.toml`, is an
> illustrative fixture. Only the repository's structural checks read it;
> the product does not. The
> decision and rationale below are kept unchanged as history. They would
> apply again if future evidence revived generation.

## Context

Refinement metadata could be placed directly in Ada source, but we do not yet know the stable vocabulary or ergonomic annotation syntax.

## Decision

Prototype the first pattern using `spark-refine.toml`.

## Rationale

- no language/toolchain modification;
- easy schema evolution during pre-alpha;
- readable diffs;
- available Ada TOML libraries;
- separates semantic experimentation from source-rewriting problems.

## Consequences

There is temporary configuration duplication. Source annotations remain the likely long-term ergonomic path.
