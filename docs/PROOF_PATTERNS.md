# Proof Pattern Library

## Purpose

Patterns are the reusable intellectual property of the project. The generator is infrastructure; patterns encode proof-engineering knowledge.

A pattern is not simply a code template. It defines a relation among:

- a family of concrete representations;
- an abstract mathematical model;
- validity conditions;
- operation semantics;
- standard proof obligations;
- reusable lemmas.

## Pattern 001: circular sequence

### Abstract meaning

A finite ordered sequence of elements with maximum capacity `N`.

### Candidate concrete representation A

```text
Content : array [Index] of Element
First   : Index
Length  : 0 .. N
```

Logical element `J`, where `0 <= J < Length`, maps to a physical index equivalent to:

```text
First + J modulo N
```

with an index-origin adjustment for Ada array bounds.

### Representation properties

The pattern should generate/prove facts equivalent to:

```text
Length <= Capacity
Every logical position maps into Content'Range
Model'Length = Length
For each logical position J:
    Model(J) = Content(Logical_To_Physical(J))
Empty(concrete) <=> Model'Length = 0
Full(concrete)  <=> Model'Length = Capacity
```

### Operation schemas

`append(E)`:

```text
Pre:  not full
Post: Model' = Model_old & E
```

`remove_first`:

```text
Pre:  not empty
Post: returned = First(Model_old)
      Model' = Tail(Model_old)
```

`replace(J,E)`:

```text
Pre:  J in model range
Post: same length
      Model'(J)=E
      all K /= J unchanged
```

### Standard lemmas

Candidate library:

```text
Logical_To_Physical_In_Range
Advance_First_In_Range
Append_No_Wrap
Append_With_Wrap
Append_Preserves_Prefix
Remove_First_Preserves_Suffix
Model_Length_Equals_Concrete_Length
Empty_Equivalent
Full_Equivalent
```

The actual implementation should seek the smallest useful lemma set. Too many lemmas can slow proof and make generated output harder to understand.

#### Evidence from the Task 001 manual baseline (representation A)

With SPARKlib `Functional.Vectors` as the model and GNATprove FSF 16.1.0 at
level 2, **none of the candidate lemmas above was needed**. Neither were a
representation predicate, a proof-only index mapping, or operation
`Refined_Post`s. The complete manual proof support was:

```ada
function Model (B : Buffer) return Sequences.Sequence
with Refined_Post =>                                      -- abstraction relation
  Sequences.Last (Model'Result) = B.Length
  and then (for all K in 1 .. B.Length =>
              Sequences.Get (Model'Result, K)
              = B.Content (Physical_Index (B.First, K - 1)))
is
   R : Sequences.Sequence;
begin
   for J in 1 .. B.Length loop                            -- derived model
      R := Sequences.Add (R, B.Content (Physical_Index (B.First, J - 1)));
      pragma Loop_Invariant (Sequences.Last (R) = J);     -- prefix length
      pragma Loop_Invariant                               -- prefix elements
        (for all K in 1 .. J =>
           Sequences.Get (R, K) = B.Content (Physical_Index (B.First, K - 1)));
   end loop;
   return R;
end Model;
```

`Physical_Index` is production code (`Push`/`Pop` use it), so the mapping
comes for free. The facts that actually had to be stated were therefore:

```text
Model'Length = Length                          (Refined_Post + invariant)
Model(K) = Content(Logical_To_Physical(K-1))    (Refined_Post + invariant)
```

The following were discharged automatically by the provers from the Ada
subtypes and SPARKlib's `Add`/`Remove`/`Range_Shifted` contracts:

```text
Length <= Capacity                              (subtype)
Every logical position maps into Content'Range  (Physical_Index returns Storage_Index)
Append with/without wrap                        (no lemma)
Remove-first shift                              (SPARKlib Remove, no lemma)
```

`Empty(concrete) <=> Model'Length = 0` and the matching `Full` relation still
matter, but as **public postconditions** on `Is_Empty`/`Is_Full`, written by
the developer. Clients cannot call `Push`/`Pop` without them. Similarly the
public `Last (Model) <= Capacity` bound is needed for clients, not for the
implementation proof.

Tail is expressed as `Remove (Model, 1)`; no custom `Tail` is needed.

Loop unrolling caveat: with a small static capacity, GNATprove may unroll
the model loop and prove it without invariants. Proof fixtures should use
`--no-loop-unrolling` so that measurements reflect realistic capacities.

### Representation B

```text
Content
Head
Tail
Count
```

The same abstract pattern can have a separate adapter. This is the first representation-refactor benchmark.

## Pattern 002 candidate: fixed object pool

### Abstract meaning

A finite universe of object identities partitioned into `Free` and `Allocated`, with optional object values.

### Concrete implementations

- free-list array;
- bitmap;
- stack of free indices.

### Useful properties

```text
Free ∩ Allocated = {}
Free ∪ Allocated = Universe
Allocate removes exactly one identity from Free
Release returns exactly one identity to Free
No allocated identity is returned twice without release
```

This is a strong second pattern because its abstract model is set-oriented, unlike the sequence-oriented first pattern.

## Pattern 003 candidate: bitmap set/allocator

### Abstract meaning

A finite set of indices.

### Concrete representation

Packed words/bits.

### Proof value

This exercises bit arithmetic and mapping from mathematical membership to representation bits. It is relevant to kernels, embedded allocators, permissions, and hardware state.

## Pattern 004 candidate: state machine

### Abstract meaning

A finite state plus permitted transition relation and optional abstract event trace.

### Concrete representation

Enums, flags, counters, or packed protocol state.

### Long-term leverage

This pattern could become a bridge to temporal/specification tools without requiring that bridge in the core generator.

## Pattern 005 candidate: descriptor ring

This should **not** be an MVP pattern. It combines circular structure with ownership, volatility, memory ordering, hardware interaction, and sometimes concurrency.

It is a high-value long-term target precisely because it demonstrates the real-time systems use case, but the project should establish proof-generation soundness on simpler structures first.

## Pattern acceptance criteria

A new pattern should not enter the stable library until it has:

1. a written mathematical meaning;
2. at least one realistic implementation fixture;
3. complete GNATprove proof under the project's supported profile;
4. negative tests showing important invalid implementations fail;
5. measured reduction in developer-authored proof support;
6. deterministic generated output;
7. documentation of unsupported representation variants;
8. no default generated assumptions.

## Pattern evolution

Patterns require semantic versioning because proof behavior matters.

A change is potentially breaking if it:

- strengthens generated preconditions;
- weakens generated obligations;
- changes abstract indexing semantics;
- changes the meaning of a role;
- changes required trust foundations;
- causes previously accepted mappings to resolve differently.

Pure formatting changes need not bump the pattern major version.
