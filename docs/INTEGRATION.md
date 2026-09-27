# Ecosystem Integration

> **Status (Task 007).** Sections are marked **current**, **future** or
> **historical** according to the evidence-backed direction
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)).

## GNATprove (current)

GNATprove remains the proof authority. `spark-refine` never decides
whether a proof obligation is discharged. There are two ways to use it:

* `spark-refine prove -P project.gpr [-- ARGS...]` (Task 008) runs
  `gnatprove -P project.gpr ARGS...`, or `--gnatprove PATH`, as an argv
  list with no shell. It prints the exact command to stderr first and
  relays GNATprove's console output to stderr. It then analyzes only the
  result set that this invocation created or changed (a snapshot of
  `gnatprove.sarif` before and after the run). GNATprove's verdict and
  nonzero exit code are preserved, never hidden or altered. Stale
  results are never analyzed.
* `gnatprove` run by the user, then `spark-refine explain`, which does
  **not** invoke GNATprove.

Freshness relies on an observed property of FSF GNATprove 16.1.0: it
rewrites `gnatprove.sarif` on every run, even an incremental re-run of an
unchanged project, while the `.spark` files are left untouched in that
case (`docs/tasks/008-proof-run-orchestration.md`).

`spark-refine` integrates with GNATprove today by reading its
machine-readable output. It never scrapes terminal text.

| Artifact | What `spark-refine` reads | Used by |
|---|---|---|
| `gnatprove.sarif` | per-check result: rule id, status (proved / unproved / justified), location, message. Messages are never used to decide status | all rules |
| `*.spark` | unit ownership of checks; proof/flow metadata and per-unit analysis completeness; **consistency checks** against SARIF | all rules. Disagreements are reported, never silently resolved, and they lower confidence or block SRD002 |
| `*.ali` | `with` dependencies (`W`/`Z` records) to build a client's dependency closure | **SRD002 only** |

The `.ali` adapter is narrow and version-sensitive:

* only GNAT 16.1.0 `.ali` files (header `V "GNAT Lib v16"`) are
  supported;
* any other version, or a missing or malformed file, makes SRD002
  **skip** with an explicit "not evaluated" note. Dependencies are never
  guessed;
* `explain --client-unit U` lets a user name client units explicitly
  instead.

Proof-pattern libraries integrate in the most ordinary way. They are
SPARK generics that GNATprove proves at each instantiation, in the user's
own GNATprove run.

Result discovery: `spark-refine explain` without a path looks for exactly
one directory holding `gnatprove.sarif` and `*.spark` (e.g.
`obj/gnatprove/`). If it finds zero or several, it exits 2 and lists the
candidates.

## SPARK functional/formal containers (current)

**Current.** `SPARK_Refine_Prefix_Sets` uses SPARKlib
`SPARK.Containers.Functional.Sets` (and `Big_Integers`) as its abstract
model, and it takes the application's existing `Functional.Sets`
instance as a generic actual. The ring-buffer benchmark uses SPARKlib
functional sequences.

Use existing SPARK mathematical container abstractions rather than inventing incompatible sequence/set/map theories when practical.

Functional containers are particularly appropriate for ghost models because they provide high-level mathematical operations even if their executable performance would not be suitable for production code.

The project should investigate each pattern against current SPARKlib capabilities and prefer library models where they produce stable proofs.

## Libadalang (optional, Task 009)

**Libadalang is optional.** Every command works without it, and
SRD001–SRD003 never use it. It is used only by the experimental
`--semantic` flag (`explain`, `analyze`, `prove`), which adds source
context to SRD002:

```sh
diagnostics/scripts/setup_libadalang.sh ~/lal     # Alire source build of
source ~/lal/env.sh                               # libadalang=26.0.0, ~4 min,
                                                  # 166 MB relocatable bundle
cd examples/ring_buffer                           # SPARKlib projects: run in
alr -n exec -- spark-refine explain obj/ablation_no_is_full_post/gnatprove \
    --semantic -P ring_buffer.gpr \
    -XRING_BUFFER_SRC=obj/ablation_src/no_is_full_post \
    -XRING_BUFFER_VARIANT=ablation_no_is_full_post  # the crate's environment
```

Libadalang is not on PyPI, so no pip extra exists. `-P` is never guessed,
and `-X` values go only to Libadalang's project loader. For `prove`, repeat
them after `--` for GNATprove.

What it provides: the exact client call, the resolved callee and its
declaration, the callee's explicit `Pre` and its top-level `and` /
`and then` conjuncts. For assertions, the asserted expression. What it
does **not** provide: which conjunct failed. GNATprove 16.1.0 output
carries no such mapping (measured, `docs/tasks/009-libadalang-srd002-enrichment.md`).

Provenance: a source file is used only if it matches GNAT's `.ali` source
identity metadata, i.e. its GNAT checksum and second-resolution mtime equal
a `D` record of the result set. Otherwise the check is `unavailable`. This
is **not** byte identity. The checksum ignores layout and comments, so a
layout/comment-only change made within the same timestamp second cannot be
distinguished from the proof-time source by the available GNATprove 16.1.0
artifacts. Every report says so in `analysis.semantic.provenance`
(`basis: "gnat_ali_checksum_and_timestamp"`, `layout_exact: false`,
`byte_exact: false`). Every failure degrades, and the base report and exit
status are unchanged.

Still open: mapping failures to source abstractions (model, invariant,
adapter, library instance), and separating authoritative specification
from mechanical proof support.

*Historical note:* the original plan was for the first generator to
bootstrap with explicit manifest names and to add semantic integration
early. Generation is deferred.

## `pragma Annotate` / `aspect Annotate` (historical/deferred)

> Deferred with generation ([ADR 0004](adr/0004-annotations-later.md),
> [ADR 0005](adr/0005-library-and-diagnostics-first.md)). No annotation
> schema is being designed. The text below is kept as history.

Ada's implementation-defined `Annotate` mechanism is intended for information consumed by external tools and is allowed in SPARK. This is a promising long-term way to place refinement metadata near the code it describes without introducing a custom language extension.

Example concept only:

```ada
pragma Annotate
  (SPARK_Refine,
   Role,
   Queue_Contents,
   Storage,
   Content);
```

Do not freeze this syntax before the manifest MVP.

## Alire

**Current.** The benchmarks and the proof-pattern library
(`proof_patterns/alire.toml`) are Alire crates. CI pins Alire 2.1.1 and
GNAT / GNATprove / SPARKlib 16.1.0 through them. The diagnostics CLI is
a Python package installed with `pip` (`python3 -m pip install
./diagnostics`), not an Alire crate.

**Future.** Publishing proof-pattern libraries to the Alire index is the
natural distribution path once more than one pattern is validated.

*Historical:* the original plan was to publish the Ada CLI as an Alire
crate once it performed real generation, with `ada_toml` and
`libadalang` dependencies. Generation is deferred.

## GPR projects

**Current.** Users build and prove with their own GPR project. The
diagnostics read only GNATprove's output directory and never parse GPR
files. `spark-refine prove -P project.gpr` passes the project to
GNATprove unchanged and runs it in the current directory. It does not
parse the GPR or duplicate project-source discovery; it looks for fresh
results under the current directory. If the project's `Object_Dir` lies
outside that tree, pass `--results PATH`.

**Alire.** Run the whole CLI inside the crate environment:
`alr exec -- spark-refine prove -P project.gpr`. There is no
Alire-specific execution layer.

## Ada Language Server / editors (future)

Editor integration should consume the structured JSON of
`spark-refine explain --format json` (`format_version` 1: `code`,
`category`, `action`, `confidence`, locations). It should fit existing
Ada tooling rather than fork it.

Desired features later:

- show SRD001–SRD003 diagnostics inline, beside GNATprove's own
  messages;
- mark "potentially affected" proved postconditions (SRD001);
- navigate to related locations;
- surface "rule not evaluated" states rather than implying a clean
  result.

*Historical:* earlier ideas were to navigate from generated lemmas to
manifest roles and to preview generated proof changes. They depended on
the deferred generator.

## GNATtest/GNATfuzz (future)

GNATprove counterexamples can already participate in test workflows. A
future diagnostic could relate a counterexample to the proof-engineering
pattern around it, for example a masked postcondition.

## CI

**Current.** The repository's CI has separate gates:

```text
structural checks + unit tests (fixture-based diagnostics suite)
diagnostics packaging (wheel build/inspect/install, outside the repo; Python 3.11)
fresh end-to-end diagnostics (real GNATprove, one case per rule, plus
  `spark-refine prove` E2E-D/E-E)
GNATprove proof gates per benchmark and variant
negative proof fixtures
forbidden-trust scan (incl. proof_patterns/)
library validation instances
public-API / client-proof unchanged controls
```

**For users.** A project can add, after its own GNATprove step:

```bash
spark-refine explain --format json > spark-refine.json
spark-refine explain --fail-on SRD001     # optional gate
```

GNATprove's own result remains the pass/fail proof gate. A
`spark-refine` gate is additional policy, not proof.

Separating the gates makes a failure understandable.
