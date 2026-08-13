# Behavioral Probe Verification

The migration platform now adds an evidence-driven source-vs-target probe layer after symbol contract matching.

## What it does

1. Selects conservative, side-effect-light public functions with small arity.
2. Generates deterministic JSON-serializable input vectors from parameter names.
3. Executes the source function as the behavioral oracle.
4. Executes the migrated target function with the exact same inputs when a supported runtime/export is available.
5. Compares normalized JSON-compatible outputs.
6. Persists the evidence under `.migration/semantic_verification.json` and `.migration/semantic_verification.md`.

## Current safe execution matrix

| Source | Target | Probe support |
|---|---|---|
| Python | Python | Yes |
| Python | JavaScript/Node | Yes |
| Other | Other | Contract evidence only unless a dedicated adapter exists |

Unsupported combinations are reported as unavailable rather than guessed.

## Why the probe set is conservative

The engine intentionally avoids functions that import modules, perform explicit I/O, raise/handle exceptions, mutate external state, or call unknown functions. This reduces false confidence and keeps the probe executor deterministic.

## Release behavior

A behavioral mismatch is a validation failure. When the normal quality gates are green, the platform can give the bounded Agno FileTools repair agent one evidence-driven repair pass. It then reruns the deterministic quality gate and behavioral probes. A remaining mismatch blocks release.

## Important limitation

Passing probes are evidence, not proof of semantic equivalence. The selected input vectors are representative probes, not exhaustive property-based verification. High-risk or stateful business logic should receive explicit human-authored tests or a future domain-specific adapter.
