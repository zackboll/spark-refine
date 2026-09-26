# ADR 0003: Use a TOML manifest for the MVP

Status: Accepted for bootstrap

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
