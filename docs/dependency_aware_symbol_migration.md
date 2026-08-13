# Dependency-aware symbol migration policy

## Why the old `>150 LOC => Split` rule is not enough

Symbol-wise migration creates a special failure mode: a source file can contain
multiple symbols and each symbol can carry its own imports or dependency
assumptions. A later symbol may have an import that appears after the first
symbol's body. If generated fragments are appended directly, those imports can
end up in the middle of the target file.

The platform now handles this in two layers:

1. **Planning:** dependency-aware symbol sizing and graph analysis.
2. **Post-migration:** deterministic import normalization before quality gates.

## LOC policy

There is no credible industry standard that says a one-to-many, many-to-one,
or many-to-many relationship must have a particular LOC limit. Relationship
cardinality is a graph property; LOC is a size property.

The platform therefore uses:

| Signal | Policy |
|---|---:|
| Hard migration split | >150 LOC |
| Review/refactor signal | >40 LOC |
| Target size for a split part | ~80 LOC |
| Soft minimum part size | 20 LOC |
| Complexity review | cyclomatic complexity >10 |
| High complexity | >15 |
| Fan-out review | >5 dependencies |
| High fan-out | >10 dependencies |
| Shared dependency | fan-in >=10 |

The 150 LOC guardrail is retained for compatibility with the existing
symbol-wise workflow. It is not presented as an industry-mandated number.

Google's Python style guide explicitly avoids a hard function-length limit but
suggests reconsidering functions above about 40 lines. Microsoft's code
metrics combine lines of code with cyclomatic complexity and Halstead volume,
and Microsoft documents a complexity threshold of 25 for its CA1502 rule.
The platform uses the more conservative >10 complexity value as an early
review signal rather than a release failure.

## Relationship cardinality

For a directed dependency edge:

- **one-to-one:** one source and one target relationship
- **one-to-many:** one source fans out to multiple targets
- **many-to-one:** multiple sources depend on one target
- **many-to-many:** multiple sources and targets are connected

The system never uses cardinality as a reason to blindly split a symbol.

### Many-to-one

This commonly indicates a shared utility/service/repository.

The split planner should:

- keep one authoritative implementation;
- avoid copying shared logic into each caller;
- preserve the public contract;
- consider a stable facade if the target architecture requires one.

### One-to-many

This commonly indicates orchestration or a coordinator with too many
responsibilities.

The split planner should consider extracting cohesive collaborators while
keeping orchestration order explicit.

### Many-to-many

This is the highest architectural risk because splitting can increase
coupling or create circular dependencies.

The planner should prefer:

- cohesive bounded modules;
- stable interfaces;
- dependency inversion where appropriate;
- no duplicate state;
- explicit dependency edges for every generated part.

## Import normalization

After symbol conversion, `import_normalizer.py` runs before lint/build/test.

It:

- parses Python imports with the Python AST;
- moves imports above generated code while preserving module docstrings;
- recognizes common JavaScript/TypeScript imports;
- handles Java package/import ordering;
- handles Go package/import placement;
- handles PHP namespace/use placement;
- handles C# using directives;
- deduplicates exact repeated import declarations.

This is intentionally deterministic. The LLM is not trusted to perform this
structural cleanup.

## Design principle

The flagship workflow should be:

**AST evidence → dependency graph → policy → LLM transformation → deterministic
normalization → lint/typecheck/test/build → repair → release.**

That makes the migration explainable and auditable instead of relying on a
single LLM judgment.
