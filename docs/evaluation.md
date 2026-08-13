# Evaluation strategy

## What is measured today

The project includes a model-agnostic evaluation contract that can run without an LLM provider. The portfolio benchmark suite covers **Python, JavaScript, Java, Go and PHP** and executes language-native validation commands where the runtime is available.

| Evidence | Purpose |
|---|---|
| File/line counts | Detect unexpected artifact loss or explosion |
| Python AST/syntax metrics | Structural regression signal for Python cases |
| JavaScript syntax check | Target parse validation |
| Java compile | Target build validation |
| Go test | Build + behavioral validation |
| PHP lint | Target syntax validation |
| Language-native tests | Behavioral smoke validation |
| Execution duration | Baseline for evaluation cost/latency |

Run:

```bash
make benchmark
```

The suite writes `benchmarks/results.json`.

## Current benchmark evidence

The checked-in suite contains six deterministic cases: one CI smoke case plus five language-specific modernization cases. All six currently pass their configured validation commands in the development environment used to generate the report.

**Important:** the target repositories are hand-authored reference implementations. These results demonstrate the **evaluation and validation pipeline**, not LLM semantic-equivalence accuracy.

## Next evaluation layer

For a research-grade or production benchmark, add:

1. real legacy repositories with representative complexity;
2. fixed migration prompts and model/provider configuration;
3. compile/build/test adapters per target framework;
4. symbol and dependency mapping accuracy;
5. semantic regression tests derived from source behavior;
6. token, latency, retry and cost telemetry;
7. human review scores for maintainability and architecture quality;
8. repeated runs to measure variance.

A useful final scorecard is:

```text
Structural coverage
+ Build validity
+ Behavioral pass rate
+ Dependency preservation
+ Unsupported-pattern rate
+ Human review score
+ Cost / latency
```

No single metric should be presented as proof that two codebases are semantically equivalent.
