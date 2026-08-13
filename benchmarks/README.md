# Portfolio benchmark suite

This repository contains **five deterministic validation benchmarks** covering Python, JavaScript, Java, Go and PHP. The benchmark targets are hand-authored reference implementations; they are **not presented as LLM conversion accuracy**.

Each benchmark records:

- source/target artifact counts
- target-language syntax or build validation
- behavioral tests
- execution duration
- pass/fail status

The purpose is to demonstrate that the platform has an evaluation contract that can be extended to real migration corpora.

Run the complete suite:

```bash
python evaluation/run_benchmarks.py
```

The generated report is written to `benchmarks/results.json`.

## Benchmark cases

| Case | Transformation | Validation |
|---|---|---|
| Python refactor | legacy utility → typed service-style implementation | `unittest` + AST parse |
| JavaScript ESM | CommonJS module → ESM module | `node --check` + Node test runner |
| Java modernization | mutable utility → records/static utility API | `javac` + executable assertion harness |
| Go modernization | package utility cleanup | `go test` |
| PHP modernization | procedural helper → class-based API | `php -l` + CLI assertions |

These are deliberately small smoke benchmarks. A production evaluation corpus should use representative repositories, expected behavior, target-language builds, and per-case semantic assertions.
