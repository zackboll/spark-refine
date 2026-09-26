# Manifest Design

The MVP uses `spark-refine.toml` as a bootstrap interface. This is intentionally not considered the final user experience.

## Goals

The manifest should describe **representation/refinement information**, not duplicate Ada specifications.

Bad direction:

```toml
# Duplicates the actual requirement and creates two sources of truth.
postcondition = "Model(B) = Model(B'Old) & E"
```

Preferred direction:

```toml
# Connects implementation roles to a standard proof pattern.
pattern = "circular_sequence"
storage = "Content"
first = "First"
length = "Length"
```

Behavior belongs in Ada contracts.

## Proposed version 1 shape

```toml
format_version = 1

[project]
gpr = "ring_buffer.gpr"
generated_dir = "generated"

[[refinement]]
name = "queue_contents"
target = "Ring_Buffer.Buffer"
pattern = "circular_sequence"
pattern_version = "1"
model_function = "Ring_Buffer.Model"

[refinement.representation]
storage = "Content"
first = "First"
length = "Length"
capacity = "Max_Size"
index_origin = 1

[refinement.generation]
backend = "derived"
emit_model_mapping = true
emit_representation_predicate = true
emit_lemmas = true
emit_refined_contracts = true

[[refinement.operation]]
entity = "Ring_Buffer.Push"
kind = "append"
value_parameter = "E"

[[refinement.operation]]
entity = "Ring_Buffer.Pop"
kind = "remove_first"
result_parameter = "E"
```

## Resolution rules

Names should be resolved semantically against the GPR project using Libadalang in the production implementation.

The manifest should not accept ambiguous unqualified names once semantic resolution exists.

Diagnostics should report both the requested name and candidate declarations.

## Configuration inheritance

Do not add inheritance in version 1. Repetition is preferable to a complex configuration language before real usage teaches us what should be shared.

A future project section may define defaults for generation policy.

## Environment variables

Avoid environment-variable substitution in semantic fields. Reproducibility matters. If environment-dependent paths are eventually required, restrict substitution to filesystem/tool-location settings and record resolved values in diagnostics.

## Why TOML

TOML is readable, diffable, simple to validate, and already has an Ada ecosystem parser (`ada_toml`). The repository should not depend on custom configuration parsing.

## Migration to source annotations

The likely long-term workflow is:

```ada
pragma Annotate (SPARK_Refine, ...);
```

because mapping information is closely related to the representation it describes.

However, we should discover the stable semantic vocabulary through the manifest first. Once users have built several patterns, the project can design annotations based on evidence instead of guessing.

The manifest should remain supported for generated code, third-party sources, or teams that prefer configuration outside source.
