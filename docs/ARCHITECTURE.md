# Architecture

> **Status.** Part I describes the current architecture: reusable proof
> patterns plus proof-aware diagnostics
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)). Part II keeps
> the original generator-first architecture as **deferred research**. It
> was not implemented. It was deprioritized after Tasks 001–004, and its
> text is preserved for the record.

**Documentation hierarchy.** Current direction: `README.md` →
`docs/VISION.md` → this file → `docs/ROADMAP.md`. Specialized current
docs:

* `docs/AGENT_INTEGRATION.md`;
* `diagnostics/README.md`;
* `docs/PROOF_PATTERNS.md`;
* `docs/TRUST_MODEL.md`;
* `docs/INTEGRATION.md`;
* `docs/METRICS.md`.

`docs/SPEC.md`, `docs/MANIFEST.md`, `docs/history/`, ADRs 0003/0004,
task records 001–006 and the benchmark `*METRICS*.md` files are
historical or deferred. See the README section "Where to start".

# Part I — Current architecture

## 1. Architectural goals

1. **GNATprove is the only proof authority.** Nothing in `spark-refine`
   decides whether a proof obligation is discharged.
2. **No hidden trust.** Proof-pattern libraries contain no assumptions,
   axioms, justifications or suppressions. Diagnostics never emit any.
3. **Read-only interpretation.** Diagnostics never edit sources, repair
   proofs or change contracts.
4. **Conservative inference.** When evidence is missing or ambiguous, a
   rule is skipped or its confidence is lowered, and the report says so.
5. **Determinism.** The same inputs give byte-identical reports, with no
   timestamps.
6. **Incremental adoption.** A project can use one library, or only the
   diagnostics, without adopting anything else.

## 2. Overview

```text
                Ada/SPARK application
      (implementation + authoritative contracts)
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
   proof-pattern library       GNATprove   ◄── proof authority
   (instantiated generics;        │            (proves the application
    re-proved per instance)       │             and every library instance)
            │                     │
            └──────────┬──────────┘
                       │
                       ▼
              SARIF / .spark / .ali
                       │
                       ▼
          spark-refine diagnostics      (read-only, deterministic)
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
           human               agent / CI
      (text report)     (format_version 1 JSON)
```

The key rule:

```text
GNATprove determines whether proof obligations are discharged.
spark-refine interprets patterns in those results.
```

Neither `spark-refine` nor an AI agent consuming its output is a proof
authority.

## 3. Three kinds of source

The architecture, the diagnostics and the agent guidance all rely on
separating three kinds of source:

| Kind | Examples | Change policy |
|---|---|---|
| **1. Production implementation** | executable Ada: operation bodies, concrete representation | normal engineering changes |
| **2. Authoritative specification** | public `Pre`/`Post`, abstract model semantics (what `Model` *means*), user-owned requirements | **high sensitivity**; should not be weakened just to get a green proof; changes deserve explicit human review |
| **3. Mechanical proof support** | representation invariants, model adapters, lemmas, loop invariants, reusable proof-pattern instantiation | may be changed to make the proof architecture work; still checked by GNATprove |

Proof-pattern libraries aim to shrink category 3. Diagnostics help decide
which category a failure should be fixed in.

A representation invariant is mechanical proof support in intent. Still,
changing it can change what the proved postconditions rest on (see
SRD001), so `docs/AGENT_INTEGRATION.md` asks for review of invariant
changes as well.

**This policy is not mechanically enforced.** `spark-refine` cannot yet
tell which source lines belong to which category. The policy is for
developers, reviewers and agent operators.

## 4. Components

### 4.1 Proof-pattern libraries: `proof_patterns/`

Hand-written, reviewed SPARK generics that encode recurring refinement
proof knowledge once.

* **Current pattern:** `SPARK_Refine_Prefix_Sets`. It reads a unique
  active prefix of a bounded array as a SPARKlib `Functional.Sets` set
  (`L = 98` SLOC, all ghost).
* **Application side:** a small instantiation, a representation
  invariant and a one-call model adapter. On the fixed pool this is
  `R = 10` SLOC, down from 36 manual SLOC (−72.2 %).
* **Trust:**
  * only SPARKlib `Functional.Sets` / `Big_Integers` contracts are relied
    on;
  * no `pragma Assume`, axioms, justifications, imports or suppressions,
    as gated by a trust scan in CI;
  * GNATprove re-proves the generic body **per instance**, so the library
    is not a trusted theorem oracle. An instance whose VCs do not prove is
    not proved.
* **Validation:** three independent proof-only validation instances
  plus the fixed-pool instance are proved in CI, and negative fixtures
  L1–L6 show that seeded faults are detected.

See `proof_patterns/README.md`, `docs/PROOF_PATTERNS.md` and
`examples/fixed_pool/LIBRARY_METRICS.md`.

### 4.2 GNATprove result adapters: `diagnostics/spark_refine_diagnostics/`

| Source | Module | Used for |
|---|---|---|
| `gnatprove.sarif` | `sarif.py` | check results: rule id, status, location, message (messages never decide status) |
| `*.spark` | `spark_results.py` | unit ownership, proof/flow metadata, per-unit analysis completeness, consistency checks against SARIF |
| `*.ali` | `ali.py` | **only** SRD002's client dependency closure |

`loader.py` joins SARIF and `.spark`. A disagreement between them, such
as a check present in one but not the other, or a different status, is
recorded as a consistency issue and reported in the output. It is never
silently resolved, and it lowers or blocks the rules that depend on it.

The `.ali` adapter is intentionally narrow:

* it has been validated only on GNAT 16.1.0 `.ali` files (header
  `V "GNAT Lib v16"`), because `.ali` is a compiler-internal,
  version-sensitive format;
* it reads only the `V`, `U`, `W` and `Z` records and never raises;
* an unsupported version, or a missing, truncated or malformed file,
  gives a structured status. SRD002 is then **skipped** and reported as
  not evaluated. Dependencies are never guessed;
* the user can instead name client units explicitly
  (`explain --client-unit U`), which overrides `.ali` discovery;
* SRD001 and SRD003 do not use `.ali`.

### 4.3 Diagnostic rules

| Code | Category | Action | Structural rule |
|---|---|---|---|
| SRD001 | `proof_context` | `fix_invariant_then_reprove` | in one entity, an unproved invariant check and a proved postcondition, so there is a masking *risk* |
| SRD002 | `abstraction_boundary` | `validate_client_goal_then_review_public_contracts` | the client's whole `.ali` dependency closure is fully proved, but the client's `Pre`/`Assert` is not, so there is a client-only proof gap (medium/low confidence) |
| SRD003 | `prover_portfolio` | `preserve_portfolio_or_strengthen_proof` | a confidently matched check is proved by some single-prover runs and not others |

The rules interpret structure. They do not claim causality, falsity or
contract deficiency. See `diagnostics/DIAGNOSTICS_METRICS.md`.

### 4.4 Installed CLI: `spark-refine`

A Python ≥ 3.11 package with no runtime dependencies, installed from
`diagnostics/`.

```text
spark-refine explain [PATH] [--client-unit U ...] [--format text|json] [--fail-on CODE]
                                                  one run:  SRD001, SRD002
spark-refine compare-provers --run NAME=PATH --run ... [--reference NAME=PATH]
                                                  single-prover runs: SRD003
spark-refine rules [--format text|json]
spark-refine prove -P PROJECT [--gnatprove PATH] [--results PATH] [--dry-run]
                   [--format text|json] [--fail-on CODE] [-- GNATPROVE_ARGS...]
                                                  runs GNATprove, then one run: SRD001, SRD002
```

* `prove` (Task 008, `orchestration.py`) builds the argv
  `[gnatprove, -P, PROJECT, *ARGS]` and shows it on stderr. It runs the
  argv with `shell=False`, relaying GNATprove's output to stderr, then
  selects the **one** result set whose `gnatprove.sarif` was created or
  changed by that run. Changes are detected with a before/after stamp:
  device, inode, size, mtime_ns, ctime_ns and sha256. Zero or several
  fresh result sets are refused. An explicit `--results` must be fresh,
  with no fallback. It then calls the same `analyze_path_report` as
  `explain` and adds `analysis.orchestration`. GNATprove's nonzero exit
  code is `prove`'s exit code.
* `explain` without `PATH` looks for exactly one result set
  (`gnatprove.sarif` + `*.spark`) under the current directory. If it
  finds zero or several, it exits 2 and lists the candidates. It never
  guesses.
* `explain` does **not** run GNATprove. It analyzes existing results,
  which are fresh only if GNATprove was just run.
* The JSON output is `format_version` 1. Every diagnostic carries `code`,
  `category`, `action` and `confidence`. The report also has a derived
  `summary`, `notes`, and per-rule `analysis` including whether each rule
  was evaluated.
* `analyze` is a compatibility alias, and
  `python3 -m spark_refine_diagnostics` also works.

The Ada executable `spark_refine` (with an underscore) built from the
root `alire.toml` is a legacy bootstrap. It implements no commands.

### 4.5 Benchmark and evidence fixtures

| Location | Role |
|---|---|
| `examples/ring_buffer/` | Tasks 001–002: two representations, proof inventories, negative fixtures |
| `examples/fixed_pool/` | Tasks 003–004: manual and library-backed variants, P1–P6 / L1–L6 negatives, prover matrix |
| `diagnostics/tests/fixtures/` | 49 sanitized real GNATprove 16.1.0 result sets with provenance and ablation ground truth |
| `diagnostics/scripts/e2e_fresh.py` | fresh end-to-end gate: one real GNATprove run per rule, CI job `diagnostics-e2e` |

## 5. Workflows

Human, preferred:

```bash
spark-refine prove -P my_project.gpr         # GNATprove proves; SRD001 + SRD002 on ITS fresh result
```

Human, manual two-step (still supported):

```bash
gnatprove -P my_project.gpr                  # GNATprove proves
spark-refine explain                         # SRD001 + SRD002 on that one result set
spark-refine explain obj/<variant>/gnatprove # explicit path if discovery is ambiguous
```

`prove` guarantees that the analyzed result was freshly changed by the
command it just launched. `explain` never runs GNATprove. It analyzes an
existing result set, so the caller is responsible for freshness.

Prover robustness, SRD003:

```bash
# after one GNATprove run per prover (--prover=cvc5 / z3 / altergo)
spark-refine compare-provers --run cvc5=obj/cvc5/gnatprove \
  --run z3=obj/z3/gnatprove --run altergo=obj/altergo/gnatprove
```

Agent / CI (see `docs/AGENT_INTEGRATION.md`):

```text
agent edits source
    ↓
spark-refine prove -P project.gpr --format json
    (runs GNATprove; analyzes only that run's fresh result;
     GNATprove exit code preserved in analysis.orchestration)
    ↓
agent reads code / category / action / confidence
    ↓
agent chooses the appropriate class of change
(implementation or proof support; authoritative specs only via review)
```

## 6. What does not exist yet

* **Libadalang only as optional, descriptive SRD002 context** (Task 009,
  `--semantic`, `semantic.py` / `semantic_lal.py`). It can name the call,
  callee and explicit `Pre` behind an SRD002 precondition failure, but it
  cannot say which conjunct failed (GNATprove 16.1.0 output does not
  record it). It does not map failures to source abstractions, and no rule
  depends on it. Task 010 adds a backend-neutral report-level view
  (`semantic_groups.py`, `analysis.semantic.srd002_groups`). It groups
  exact precondition failures by identical callee declaration + `Pre`, for
  triage only. There is no causality, no group confidence, and no change to
  any diagnostic. Enrichment stays opt-in (see `docs/ROADMAP.md`).
* **No prover-matrix orchestration.** `prove` runs exactly one GNATprove
  invocation. SRD003 still requires separate single-prover runs plus
  `compare-provers`. `prove` also parses no GPR and has no
  Alire-specific layer.
* **No source generation, manifest processing or source annotations.**
  See Part II.
* **No mechanical enforcement** of the source categories in section 3.

## 7. Compatibility

Validated on the pinned FSF GNAT / GNATprove / SPARKlib 16.1.0 toolchain
(Alire 2.1.1):

* the SARIF and `.spark` readers are parity-tested against the benchmark
  gates;
* `.ali` support is limited to `GNAT Lib v16`, and other versions degrade
  as described above;
* generic proof libraries depend on prover behavior, as the prover matrix
  in `LIBRARY_METRICS.md` shows. Their proofs are pinned by CI, not
  assumed portable.

---

# Part II — Deferred generator research (historical)

> **Status: historical/deferred.** Everything below is the original
> generator-first architecture (manifest → refinement IR → pattern
> registry → generator), preserved unchanged. None of it is implemented.
>
> **Why it was deprioritized.** Tasks 001–004 found:
>
> * the ring-buffer mechanical support was small (19 and 21 SLOC);
> * the larger fixed-pool support (36 SLOC) was entirely generic;
> * a reusable SPARK library reduced the pool's local support to 10 SLOC.
>
> Source generation is therefore **not justified on current evidence**
> for the demonstrated patterns, and is **deferred pending new
> evidence** ([ADR 0005](adr/0005-library-and-diagnostics-first.md)).
> This does not rule it out for patterns a library cannot absorb.
>
> Some ideas below carried over to Part I in a different form. The
> determinism, compatibility recording and no-premature-plugin rules
> apply to libraries and diagnostics. The "future refinement-aware
> explain" became `spark-refine explain` over GNATprove output, with no
> generated source map.

## G1. Architectural goals

The architecture must satisfy five constraints simultaneously:

1. **Low trust:** the generator must not need to be trusted for correctness if generated claims are proved by GNATprove.
2. **Incremental adoption:** a project should use one pattern without reorganizing its entire proof architecture.
3. **Reviewability:** generated Ada/SPARK must be readable and traceable to source declarations.
4. **Determinism:** generation must be stable enough for CI drift checks and meaningful code review.
5. **Extensibility:** new patterns should not require invasive changes to the core.

## G2. Major components

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

## G3. Refinement IR

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

## G4. Three model backends

A single strategy will not be ideal for every SPARK proof. The architecture should permit three related backends.

### G4.1 Derived model

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

### G4.2 Shadow model

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

### G4.3 Layered refinement

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

## G5. Pattern interface

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

## G6. Generated-package boundary

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

## G7. Source metadata strategy

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

## G8. GNATprove integration

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

## G9. Determinism

Generation should avoid nondeterminism from:

- hash-map iteration order;
- temporary identifiers based on process IDs;
- timestamps in generated source;
- environment-dependent formatting;
- unstable solver output.

Generated metadata may contain a tool version and input digest, but timestamp inclusion should be optional or kept outside files used for drift comparison.

## G10. Compatibility

The project should record:

- compiler version;
- GNATprove version;
- SPARKlib assumptions/dependencies;
- pattern version;
- generator version.

A pattern's semantic version matters because changing a generated lemma or invariant can affect proof behavior even when the public CLI is unchanged.

## G11. Future plugin architecture

Do not build dynamic plugins first. Start with in-tree patterns and a stable internal interface. Once two or three patterns demonstrate common structure, define a versioned external pattern package format.

Premature plugin APIs would freeze assumptions before we know what a proof pattern actually needs.
