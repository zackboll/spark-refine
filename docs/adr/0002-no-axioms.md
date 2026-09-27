# ADR 0002: No generated axioms or assumptions by default

Status: Accepted for bootstrap. **Still current.**

> **Note (Task 007).** With generation deferred
> ([ADR 0005](0005-library-and-diagnostics-first.md)), this rule now
> applies to the current product:
>
> * proof-pattern libraries contain no `pragma Assume`, axioms,
>   justifications, imports or suppressions, as gated by the trust scan;
> * diagnostics never emit assumptions or edit sources.
>
> The wording below is unchanged.

## Context

A generator could make difficult proofs easy by emitting assumptions, trusted axioms, or bodyless proof declarations. That would undermine the project's central value.

## Decision

Stable/default generation must not emit proof-closing assumptions or unverified axioms.

## Rationale

The generator should stay outside the primary trust base. Wrong generated facts should fail under GNATprove.

## Consequences

Some patterns will require more generated proof code or user lemmas. This is desirable compared with hidden trust.
