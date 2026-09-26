# Architecture

## 1. Architectural goals

The architecture must satisfy five constraints simultaneously:

1. **Low trust:** the generator must not need to be trusted for correctness if generated claims are proved by GNATprove.
2. **Incremental adoption:** a project should use one pattern without reorganizing its entire proof architecture.
3. **Reviewability:** generated Ada/SPARK must be readable and traceable to source declarations.
4. **Determinism:** generation must be stable enough for CI drift checks and meaningful code review.
5. **Extensibility:** new patterns should not require invasive changes to the core.

## 2. Major components

```text
                         +----------------------+
 Ada/SPARK source ------>| semantic source view |
                         |   (Libadalang later) |
                         +----------+-----------+
                                    |
 Manifest --------------+----------+
                                    v
                         +----------------------+
                         | refinement IR        |
                         | - targets            |
                         | - model              |
                         | - representation     |
                         | - operations         |
                         | - policies           |
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
          +-------------------+            +-------------------+
          | pattern registry  |            | validator         |
          | circular_sequence |            | semantic checks   |
          | fixed_pool        |            | policy checks     |
          | ...               |            | name checks       |
          +---------+---------+            +---------+---------+
                    |                                |
                    +---------------+----------------+
                                    v
                         +----------------------+
                         | generation plan      |
                         +----------+-----------+
                                    |
                  +-----------------+------------------+
                  |                                    |
                  v                                    v
       +----------------------+             +---------------------+
       | SPARK source emitter |             | metadata emitter    |
       | proof packages       |             | source maps         |
       | helper contracts     |             | hashes / provenance |
       +----------+-----------+             +----------+----------+
                  |                                    |
                  +-----------------+------------------+
                                    v
                             stock GNATprove
                                    |
                                    v
                       .spark / SARIF / diagnostics
                                    |
                                    v
                      future refinement-aware explain
```

## 3. Refinement IR

The core should not generate directly from TOML syntax. Parse configuration and source into an internal model with explicit semantics.

Illustrative IR:

```text
Refinement
  id
  target_entity
  abstract_model
  pattern_id
  representation_roles
  operations
  generation_backend
  proof_policy
  source_locations
```

The same IR can later be populated from `pragma Annotate`, TOML, or another frontend.

This is important because the first manifest format should not become accidental architecture.

## 4. Three model backends

A single strategy will not be ideal for every SPARK proof. The architecture should permit three related backends.

### 4.1 Derived model

The abstract model is computed from concrete state by a ghost function:

```text
Concrete state -> ghost Model(B)
```

Advantages:

- one source of state truth;
- no shadow-state synchronization;
- direct semantics.

Costs:

- the function can be expensive for proof;
- repeated model expansion may stress provers;
- slicing/wraparound can create difficult VCs.

This should be the first backend because it has the smallest conceptual trust surface.

### 4.2 Shadow model

A ghost model is stored/updated alongside concrete state:

```text
Concrete state <--- Valid_Model ---> Ghost model
```

Advantages:

- operations may have simpler model contracts;
- avoids repeatedly reconstructing a large model.

Costs:

- mutating operations must update both worlds;
- a `Valid_Model` relation must be preserved;
- maintenance can feel like the duplication we want to reduce unless generation is strong.

This backend is especially important because existing SPARK examples use this style.

### 4.3 Layered refinement

Complex structures may require:

```text
Concrete
   |
 Intermediate model A
   |
 Intermediate model B
   |
 Public abstract model
```

Each step is intentionally small enough for automated proof.

Recent AdaCore container work demonstrates why this can be necessary. The project should eventually let a pattern own these intermediate layers so application developers do not have to reinvent them.

## 5. Pattern interface

A pattern should declare:

```text
PatternMetadata
PatternRoles
PatternValidation
PatternGeneratedTypes
PatternGeneratedFunctions
PatternGeneratedPredicates
PatternGeneratedLemmas
PatternOperationSchemas
PatternDiagnostics
```

A circular sequence might require roles:

```text
storage
first
length
capacity
index_origin
```

and expose facts such as:

```text
logical_length_bounded
logical_index_maps_in_bounds
empty_equivalence
full_equivalence
append_preserves_prefix
remove_first_preserves_suffix
```

Patterns must not simply be string templates. Their inputs should be typed in the IR and validated before generation.

## 6. Generated-package boundary

Generated artifacts should normally live in a sibling/child proof package, not be interleaved unpredictably with production source.

Example:

```text
ring_buffer.ads
ring_buffer.adb
ring_buffer-proof.ads          generated
ring_buffer-proof.adb          generated
```

Whether a child package can see the required private representation depends on Ada visibility. The implementation may therefore need a dedicated proof child, generated nested declarations, or a controlled generated include point. This must be validated with real code during MVP rather than assumed.

One early architecture task is to compare:

- child proof package;
- private child;
- generated package nested in implementation;
- generated source fragments consumed at explicit markers;
- user-authored ghost accessor functions exposing just enough representation.

The selection should minimize production API pollution while remaining legal SPARK.

## 7. Source metadata strategy

### MVP

Use `spark-refine.toml`. It is explicit, easy to prototype, and avoids source rewriting.

### Later

Support Ada's standard annotation mechanism:

```ada
pragma Annotate
  (SPARK_Refine,
   Circular_Sequence,
   ...);
```

or an equivalent aspect where legal and ergonomic.

`Annotate` is designed for external tooling and is permitted in SPARK. Libadalang can provide semantic access to Ada source so the tool does not need a home-grown parser.

The exact annotation schema must be designed after the MVP reveals which metadata is stable.

## 8. GNATprove integration

Generation and proving should remain separable:

```text
spark_refine generate

gnatprove ...
```

`spark_refine check` can orchestrate both later but must not obscure the command that GNATprove actually ran.

Future `explain` support can ingest GNATprove machine-readable artifacts and use a generated source map:

```json
{
  "generated_entity": "Ring_Buffer_Proof.Lemma_Append_Wrap",
  "refinement": "queue_contents",
  "pattern_rule": "circular_sequence.append.wrap",
  "user_source": "ring_buffer.ads:42",
  "manifest_source": "spark-refine.toml:8"
}
```

This makes diagnostics semantic rather than merely textual.

## 9. Determinism

Generation should avoid nondeterminism from:

- hash-map iteration order;
- temporary identifiers based on process IDs;
- timestamps in generated source;
- environment-dependent formatting;
- unstable solver output.

Generated metadata may contain a tool version and input digest, but timestamp inclusion should be optional or kept outside files used for drift comparison.

## 10. Compatibility

The project should record:

- compiler version;
- GNATprove version;
- SPARKlib assumptions/dependencies;
- pattern version;
- generator version.

A pattern's semantic version matters because changing a generated lemma or invariant can affect proof behavior even when the public CLI is unchanged.

## 11. Future plugin architecture

Do not build dynamic plugins first. Start with in-tree patterns and a stable internal interface. Once two or three patterns demonstrate common structure, define a versioned external pattern package format.

Premature plugin APIs would freeze assumptions before we know what a proof pattern actually needs.
