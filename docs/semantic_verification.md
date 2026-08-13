# Semantic & Behavioral Verification

## Why it exists

Compilation and linting prove that a migrated project is structurally executable. They do not prove that the migrated system still exposes the same important contracts or that its existing tests pass. The semantic verifier adds an evidence layer between source/target analysis and release.

## Evidence model

1. Extract public symbols from the source and target.
2. Normalize names so common cross-language migrations can be matched.
3. Compare callable arity when statically observable.
4. Inventory target-side tests.
5. Execute the existing target test runner when a supported runner is available.
6. Persist the evidence and limitations with the migration artifacts.

## Release interpretation

- `verified`: source contracts are matched, signatures are compatible, and target tests pass or are not applicable.
- `partial`: useful evidence exists, but missing symbols or incompatible signatures remain.
- `not_available`: the source path or analyzable contracts were unavailable.

The verifier is deliberately not a formal-equivalence engine. Business semantics, renamed APIs, runtime reflection, external services, nondeterministic behavior, and hidden integration contracts require additional evidence.
