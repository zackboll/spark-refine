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
