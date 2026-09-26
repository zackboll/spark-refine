# Security and Soundness Policy

This project treats **proof soundness regressions** as security-sensitive issues.

Please report privately before public disclosure if a bug can cause the tool to:

- silently weaken a user-authored requirement;
- emit an unchecked assumption while claiming assumption-free generation;
- omit a required generated proof obligation in a way that misrepresents verification coverage;
- misreport an unproved generated property as proved;
- execute untrusted project input unexpectedly during analysis/generation.

Until a dedicated private reporting channel exists, do not use this bootstrap repository for sensitive vulnerability details. Establish a security contact before public release.

Ordinary generator bugs, unsupported language constructs, and proof-performance regressions can use the normal issue tracker once one exists.
