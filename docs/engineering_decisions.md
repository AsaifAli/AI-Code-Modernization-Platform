# Engineering decisions

## 1. Hybrid deterministic + agentic architecture

Program analysis is performed before LLM generation. ASTs, CTags, dependency information and technology detection provide evidence that agents can retrieve and reason over.

**Why:** LLM-only repository conversion is difficult to reproduce, debug and validate.

## 2. Retrieval instead of giant prompts

Large analysis artifacts are chunked and stored in a vector-backed knowledge layer. Retrieval is bounded by metadata and context needs.

**Why:** keeps prompts within practical limits while preserving access to repository-level information.

## 3. Plan before conversion

The planning stage creates file/symbol mappings and target architecture decisions before conversion workers generate code.

**Why:** introduces traceability and reduces blind, file-by-file generation.

## 4. QA is a first-class workflow

Post-migration analysis compares source and target structure and produces risk/review signals.

**Why:** generated code should be treated as an artifact requiring validation, not automatically accepted output.

## 5. Deterministic evaluation is separate from LLM judgement

The benchmark evaluator does not ask an LLM whether a migration is good. It measures structural properties and, when supplied, runs an explicit test suite.

**Why:** this creates reproducible regression signals that can run in CI.

## 6. Provider abstraction

Model selection is environment-driven so the same orchestration layer can target cloud or self-hosted inference.

**Why:** keeps model infrastructure replaceable and makes local/private deployment possible.

## 7. Correlated observability

API requests receive an `X-Request-ID`, and application logs include that identifier.

**Why:** migration workflows are asynchronous and multi-step; correlation is essential when diagnosing failures across API, agents and background execution.

## 8. Explicit production boundary

The repository documents what is and is not production-ready rather than hiding prototype constraints.

**Why:** credible engineering includes clearly stated limitations and a concrete path to production hardening.
