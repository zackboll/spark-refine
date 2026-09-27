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

## Libadalang (future)

**Libadalang is not used, and not required, for current operation.**
Diagnostics work purely from GNATprove output.

When source semantics become necessary, they should come from
Libadalang, not a home-grown parser:

- Ada parsing is complex;
- name resolution matters;
- source locations matter;
- semantic type compatibility matters;
- a home-grown parser would become a maintenance liability.

The concrete motivation is now diagnostic, not generative. Libadalang
could provide:

- **call → callee mapping**, to name the call whose precondition a client
  cannot prove;
- **contract conjunct resolution**, to name which conjunct of a
  `Pre`/`Post` is involved;
- **a source semantic graph**, to map a failed check to a source
  abstraction (model, invariant, adapter, library instance);
- **a stronger SRD002 explanation**, since SRD002 today cannot identify
  a callee or a contract.

It could also later help separate authoritative specification from
mechanical proof support.

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
