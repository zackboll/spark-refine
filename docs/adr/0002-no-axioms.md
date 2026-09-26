# ADR 0002: No generated axioms or assumptions by default

Status: Accepted for bootstrap

## Context

A generator could make difficult proofs easy by emitting assumptions, trusted axioms, or bodyless proof declarations. That would undermine the project's central value.

## Decision

Stable/default generation must not emit proof-closing assumptions or unverified axioms.

## Rationale

The generator should stay outside the primary trust base. Wrong generated facts should fail under GNATprove.

## Consequences

Some patterns will require more generated proof code or user lemmas. This is desirable compared with hidden trust.
