# ADR 0004: Prefer standard Ada annotations for later source-local metadata

Status: Proposed

## Context

Once the semantic vocabulary stabilizes, representation-role metadata will often be easiest to maintain beside the declaration it describes.

## Decision

Investigate `pragma Annotate`/`aspect Annotate` plus Libadalang rather than inventing a new source syntax.

## Rationale

The mechanism is designed for external tools and is permitted by SPARK. It preserves ordinary Ada parsing and allows the project to remain external.

## Consequences

The exact annotation schema is deferred until after at least one successful pattern and benchmark.
