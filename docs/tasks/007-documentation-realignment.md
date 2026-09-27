# Task 007 — Realign project documentation with the evidence-backed direction

**Status:** executed.

**Base:** `origin/main` = `9df937f8a750907039b8cfbe4866c76d97e92b68`,
the PR #6 merge. The ancestor check against the reviewed Task 006 head
`fa340952d7e935748d72057cba66b79fe0d2bf9e` succeeded.

**Branch:** `feature/007-documentation-realignment`.

## Question

Tasks 001–006 moved the project away from its generator-first
hypothesis. Does the documentation now describe the project that the
evidence supports?

> **spark-refine is a proof-engineering toolkit for SPARK. It combines
> reusable, GNATprove-verified proof patterns with proof-aware
> diagnostics for humans and AI agents. GNATprove remains the proof
> authority.**

This is a documentation-focused task. No product behavior, proof source,
diagnostics code, CI job, packaging or GNATprove configuration was
changed. The single, explicitly authorized non-Markdown change is two
entries added to `REQUIRED` in `scripts/check_repo.py`.

## What changed

| File | Change |
|---|---|
| `docs/adr/0005-library-and-diagnostics-first.md` | **new.** Context, evidence (19 / 21 / 36 / `R = 10` / SRD001–SRD003 / installed CLI), decision, consequences. Accepted |
| `docs/adr/0003`, `0004` | status note: implementation priority superseded/deferred by ADR 0005; rationale kept |
| `docs/adr/0001`, `0002` | status note: still current, restated for libraries and diagnostics; decision text kept |
| `docs/VISION.md` | rewritten: mission, developer loop, three kinds of source, maturity Levels 1–4. The original vision is appended as history |
| `docs/ARCHITECTURE.md` | Part I is the current architecture (diagram, three kinds of source, components, `.ali` adapter limits, workflows, what does not exist). Part II is the original generator architecture, labelled deferred, with the reasons |
| `docs/MVP.md` | current MVP (implemented / validated / out of scope / future). The generator MVP M0–M5 is kept as history |
| `docs/ROADMAP.md` | Completed / Near term / Later / Research-deferred, plus the evidence history. The original phases 0–10 are kept as history |
| `docs/LANDSCAPE.md` | table and recommendation re-evaluated (libraries + diagnostics); diagnostics evidence recorded (49 fixtures, 137 tests, fresh E2E) |
| `docs/INTEGRATION.md` | current SARIF / `.spark` / `.ali` integration; Libadalang marked future and not required; Annotate deferred; CI current |
| `docs/MOTIVATION.md` | generator conclusions replaced by library + diagnostics evidence (fixed-pool table) |
| `docs/FAQ.md` | new current-product questions; stale generator answers reframed, with short historical notes |
| `docs/METRICS.md` | Part A: current library, diagnostics and usability metrics, with no aggregate accuracy score. Part B: original metrics, kept, with outcome notes |
| `docs/SPEC.md`, `docs/MANIFEST.md` | historical/deferred banner; body unchanged |
| `docs/TRUST_MODEL.md` | trust boundary restated for libraries and diagnostics; generator parts marked historical |
| `docs/EXECUTIVE_SUMMARY.md`, `DESIGN_PRINCIPLES.md`, `PROOF_PATTERNS.md`, `BENCHMARKS.md`, `RESEARCH.md` | status notes; generator phrasing adapted, originals kept in parentheses |
| `docs/AGENT_INTEGRATION.md` | cross-reference to the three kinds of source, and why invariant changes still get review |
| `README.md` | audited. Mission sentence aligned; three-kinds-of-source table; ADR 0005 and historical-doc pointers; repository map |
| `CONTRIBUTING.md` | current priorities; pattern and diagnostics contribution requirements |
| `SECURITY.md` | broadened to cover diagnostics (proof-authority misrepresentation, SARIF/.spark disagreement, SRD002 inference, read-only violations) and libraries (unchecked assumptions); ordinary bugs kept separate |
| `CHANGELOG.md` | Task 007 entry |
| `examples/ring_buffer/README.md`, `examples/ring_buffer/generated/README.md` | historical/deferred note on the unused manifest and `generated/` placeholder |
| `.github/pull_request_template.md` | "Generated/trusted assumptions" checkbox restated for libraries and diagnostics (template text only; no CI behavior) |
| `scripts/check_repo.py` | **only non-Markdown change**: ADR 0005 and this record added to `REQUIRED` |

`docs/history/ORIGINAL_README.md`, the task records 001–006 and the
benchmark `*METRICS*.md` records are unchanged (verified with
`git diff`).

## Human workflow (section 23)

```bash
gnatprove -P my_project.gpr                   # GNATprove proves
spark-refine explain                          # SRD001 + SRD002 on one existing result set
spark-refine explain obj/<variant>/gnatprove   # explicit path when discovery is ambiguous
spark-refine explain --format json            # agents / CI
spark-refine compare-provers --run ... --run ...   # SRD003, over single-prover runs
```

`explain` does not run GNATprove, and auto-discovered results may be
stale. SRD003 comes only from `compare-provers`. This was verified on all
49 fixtures: `explain` JSON always has `by_code.SRD003 = 0`. There is no
`spark-refine prove`; proof-run orchestration is only a possible future
direction. README, VISION, ARCHITECTURE, ROADMAP, MVP, FAQ and
AGENT_INTEGRATION all state this consistently.

## Documentation hierarchy (section 26)

This hierarchy is discoverable from README ("Where to start") and from
the head of `docs/ARCHITECTURE.md`.

* **Current direction:** README → VISION → ARCHITECTURE → ROADMAP.
* **Current, specialized:** AGENT_INTEGRATION, `diagnostics/README.md`,
  PROOF_PATTERNS, TRUST_MODEL, INTEGRATION, METRICS, ADR 0005.
* **Historical/deferred:** SPEC, MANIFEST, `docs/history/`, ADRs
  0003/0004, task records 001–006, benchmark `*METRICS*.md`.

## Terminology audit (section 24)

The repository-wide search covered these terms: `the generator`,
`generated proof package`, `manifest MVP`, `first generator`,
`refinement IR`, `spark_refine generate`, `generation backend`,
`generated code is disposable`, `generated refinement`,
`generated lemma(s)`. A broader pass also covered `generat*`,
`manifest`, `drift` and the `spark_refine validate|check|diff|migrate|trust-report`
commands. Task records 001–006, `docs/history/` and benchmark
`*METRICS*.md` are historical by definition and were excluded.

Result: **zero unqualified generator-first claims in current-facing
prose.** Every remaining occurrence is one of:

| Class | Where | Why it stays |
|---|---|---|
| HISTORICAL (whole document bannered) | `docs/SPEC.md`, `docs/MANIFEST.md` | original generator design; banner at the top |
| HISTORICAL (labelled section) | ARCHITECTURE Part II (G1–G11); VISION "Historical: the original generator-first vision"; MVP "Historical: generator MVP (M0–M5)"; ROADMAP "Historical: original phase plan"; BENCHMARKS A2; PROOF_PATTERNS Pattern 001 and the pre-Task 003 framing | preserved experimental architecture; each section has a status note |
| HISTORICAL (quoted original wording) | FAQ, DESIGN_PRINCIPLES, TRUST_MODEL §1, MOTIVATION, LANDSCAPE, PROOF_PATTERNS, METRICS ("Originally: …" / "*Historical:* …") | shows what changed without erasing it |
| HISTORICAL (under a "current reading" note) | TRUST_MODEL §§3–6, 8; METRICS Part B | current meaning stated first; original generator text kept below |
| HISTORICAL (ADR) | ADR 0002 body text; ADR 0005 Context | decision record; ADR 0002 has a Task 007 note |
| DEFERRED | ROADMAP "Research / deferred" (source generation, annotations for generation); ADR 0005 Decision; INTEGRATION `Annotate` section; `examples/ring_buffer/generated/README.md`, `spark-refine.toml` | explicitly deferred pending new evidence |
| CURRENT (meta) | README / ROADMAP / MVP / VISION / this record | describe the *pivot* ("generator hypothesis", "PIVOT away from source generation"), not a current generator |

The `spark_refine` command sketches (`validate`, `generate`, `check`,
`diff`, `migrate`, `trust-report`) appear only inside historical sections
or behind an explicit note (TRUST_MODEL §6). The legacy Ada executable
really does reject them (README "Two executables, two names").

## Consistency rules applied

* GNATprove is the only proof authority in every current document.
  `spark-refine` and AI agents interpret results; they do not decide
  them.
* There are three kinds of source: implementation, authoritative
  specification, and mechanical proof support. The distinction is
  documented as policy, **not** as mechanical enforcement.
* The agent loop matches `docs/AGENT_INTEGRATION.md`: edit → GNATprove →
  `spark-refine explain --format json` → act on
  `category`/`action`/`confidence`. The per-rule guardrails are the same
  as there:
  * SRD001: repair the invariant or state transition first;
  * SRD002: validate the client goal before changing public contracts;
  * SRD003: do not rewrite a valid proof merely because one solver fails.
* `explain` runs SRD001/SRD002 on one run, and `compare-provers` runs
  SRD003. Neither runs GNATprove.
* Generation is described as "not justified on current evidence",
  "deprioritized" and "deferred pending new evidence", never as
  impossible.
* Diagnostic results are quoted per case and per category, with no
  aggregate accuracy percentage.

## Validation

* `python3 scripts/check_repo.py`: passes (34 required files).
* `python3 -m unittest discover -s tests -v`: 4 tests pass.
* `cd diagnostics && python3 -m unittest discover -s tests -t tests -v`:
  137 tests pass. Nothing in `diagnostics/` code changed.
* `git diff --check`: clean.
* A relative-link check over every changed Markdown file: every link
  target exists.
* The only non-Markdown file changed relative to `origin/main` is
  `scripts/check_repo.py`.

## Final consistency questions (section 29)

These answers come from README / VISION / ARCHITECTURE / ROADMAP, which
agree.

1. **What is it today?** A proof-engineering toolkit for SPARK that
   combines reusable, GNATprove-verified proof patterns with proof-aware
   diagnostics for humans and AI agents.
2. **Problem solved.** It addresses two costs:
   * recurring hand-written proof plumbing between representation and
     model;
   * low-level proof output that hides *which layer* failed.
3. **Capabilities.**
   * `SPARK_Refine_Prefix_Sets`;
   * `spark-refine explain` (SRD001/SRD002);
   * `compare-provers` (SRD003);
   * `rules`;
   * `format_version` 1 JSON.
4. **GNATprove vs spark-refine.** GNATprove decides proof status;
   spark-refine interprets results and never runs GNATprove or edits
   source.
5. **The two pillars.** Reusable proof-pattern libraries and proof-aware
   diagnostics.
6. **What Tasks 001–004 taught.**
   * Ring-buffer support was small (19 and 21 SLOC).
   * Fixed-pool support (36 SLOC) was all generic.
   * A library cut it to R = 10, giving PIVOT.
7. **Why generation was deprioritized.** A library absorbed the generic
   support. The residual is as small as a manifest would be, so a
   generator would add trust surface for little gain. It is deferred,
   not ruled out.
8. **Human use.** `gnatprove -P …`, then `spark-refine explain`.
9. **Agent use.** Edit, then GNATprove, then `explain --format json`,
   then act on category/action/confidence. Do not weaken authoritative
   specifications. SRD001: fix the invariant first. SRD002: validate the
   client goal first. SRD003: keep the portfolio.
10. **Authoritative vs mechanical.**
    * Authoritative: public Pre/Post, model semantics and requirements.
      High sensitivity.
    * Mechanical: invariants, adapters, lemmas, loop invariants and
      library instantiation. Changeable, and still proved.
    * The distinction is policy, not enforced.
11. **Current / future / historical / deferred.**
    * Current: the two pillars.
    * Future: orchestration, Libadalang enrichment, more patterns, editor
      and agent integration.
    * Historical: Tasks 001–006, SPEC, MANIFEST, the original README.
    * Deferred: generation, annotations for generation, invariant
      synthesis, concurrency, WCET.
12. **Where to start.** README "Where to start", then VISION, then
    ARCHITECTURE, then ROADMAP.
13. **SRD001/SRD002.** `spark-refine explain`.
14. **SRD003.** `spark-refine compare-provers`.
15. **Does `explain` run GNATprove?** No.

## Not done / follow-ups

* `docs/PROOF_PATTERNS.md` and `docs/BENCHMARKS.md` got status notes and
  labels only. Their per-pattern and per-benchmark bodies are evidence
  records and were left as written.
