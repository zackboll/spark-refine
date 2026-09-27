# ADR 0001: Start as an external tool

Status: Accepted for bootstrap. **Still current.**

> **Note (Task 007).** The core decision still holds: stay external and
> rely on stock GNATprove. What changed is the form of the external tool.
> Per [ADR 0005](0005-library-and-diagnostics-first.md), it is now:
>
> * reusable SPARK proof-pattern libraries, proved by stock GNATprove;
> * a read-only diagnostics CLI (`spark-refine`) over GNATprove output.
>
> It is no longer a source generator. The wording below is unchanged.

## Context

The project could be implemented as a GNATprove modification, a SPARK language extension, a preprocessor, or an external source generator/analyzer.

## Decision

Start as an external command-line tool that generates ordinary SPARK artifacts and relies on stock GNATprove.

## Rationale

- Smaller trust impact.
- Faster iteration.
- Does not require maintaining a GNATprove fork.
- Lets benchmarks establish which concepts deserve upstream support.
- Makes failure obvious: generated SPARK must still prove.

## Consequences

Some source-placement/visibility problems may be less elegant than a native language feature. We accept that during experimentation.
