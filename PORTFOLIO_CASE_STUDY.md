# Portfolio case study — AI Code Modernization Platform

## One-line pitch

**An agentic code-modernization platform that combines program analysis, RAG, dependency intelligence and deterministic QA to make repository-scale migrations traceable and testable.**

## Problem

Naive LLM code conversion sends large repositories directly to a model. That loses dependency context, exceeds context windows, produces inconsistent transformations and offers weak evidence that the result works.

## Solution

The platform decomposes migration into explicit stages:

1. repository scanning;
2. AST / CTags / dependency extraction;
3. lossless, metadata-aware knowledge indexing;
4. migration planning;
5. symbol-level agentic conversion;
6. post-migration validation and risk reporting.

## Engineering differentiators

- **Hybrid deterministic + probabilistic architecture** — program analysis constrains LLM reasoning.
- **Bounded RAG context** — large analysis artifacts are retrieved selectively rather than injected wholesale.
- **Traceable migration workflow** — planning precedes conversion and produces reviewable artifacts.
- **Migration QA** — structural deltas, unsupported patterns, validation results and risk signals are surfaced after generation.
- **Provider abstraction** — cloud and self-hosted model endpoints are configuration-driven.
- **Evaluation contract** — deterministic multi-language benchmarks execute native build/syntax/test checks.

## Current validation evidence

| Benchmark | Target validation | Result |
|---|---|---|
| Python | unittest | PASS |
| JavaScript | node --check + node --test | PASS |
| Java | javac + executable assertions | PASS |
| Go | go test ./... | PASS |
| PHP | php -l + CLI assertions | PASS |
| CI smoke | unittest | PASS |

**6 / 6 cases passed in the checked-in benchmark suite.** These are hand-authored reference targets used to validate the evaluation framework, not claims of LLM semantic-equivalence accuracy.

## Production-minded safeguards

- `.env` excluded from source distribution;
- configuration-driven credentials;
- request correlation IDs;
- liveness and readiness endpoints;
- non-root Docker containers;
- dropped Linux capabilities;
- `no-new-privileges`;
- migration-name/path validation;
- repository quality and secret scans;
- automated CI tests and benchmark validation.

## Known limitation to discuss honestly

The current workflow uses FastAPI background execution for migration jobs. Task state is persisted, but an interrupted in-flight background job is not yet resumed automatically. A durable worker/queue architecture is the next production-hardening step.

## Suggested resume bullet

> Built an agentic code-modernization platform combining AST/CTags program analysis, metadata-aware RAG and workflow-based LLM agents to plan and execute repository migrations; added deterministic migration QA, multi-language build/test benchmarks, request tracing, Docker hardening and CI quality gates.

## Flagship-level engineering loop

The platform now exposes the live Agno execution plan in the UI, runs post-migration engineering gates (CI, linting, syntax/type checks, tests, builds and bounded AI repair), and generates a migrated-code architecture intelligence page with a module diagram, technology profile and README-style analysis. Final packaging remains gated by the engineering quality result.
