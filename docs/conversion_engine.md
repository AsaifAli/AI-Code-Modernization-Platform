# Conversion Engine

LegacyLens uses the LLM for semantic translation while deterministic code handles hygiene, syntax gates, and bounded repair.

```text
source symbol -> dependency/context -> conversion rules -> LLM translation -> sanitation
  -> fragment syntax check -> bounded targeted repair -> persist -> repository validation
  -> semantic/behavioral verification
```

Python uses the native `ast` parser. Other supported languages use `tree-sitter-language-pack` when available; Java/Go/C# method fragments are wrapped for syntax checking. Parser availability never replaces the repository-level quality gate.

`CONVERSION_FRAGMENT_REPAIR_ATTEMPTS` defaults to `1` and controls the fragment repair budget.

The recipe approach follows the same composability principle used by OpenRewrite: keep transformations narrow, deterministic where possible, and validate after application.
