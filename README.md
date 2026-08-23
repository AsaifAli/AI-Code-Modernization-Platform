# LegacyLens — Agentic Software Modernization

> **Agentic legacy-code migration with program analysis, dependency intelligence, Qdrant-backed retrieval, migration planning, context-grounded conversion, and post-migration release gates.**

LegacyLens analyzes a legacy repository, builds a structured representation of its codebase, creates a migration plan, performs context-grounded code transformation, and evaluates the resulting target project with deterministic engineering checks.

## What changed in the portfolio-ready release

### Developer workbench UI

LegacyLens is intentionally presented as a **developer migration workbench**, not a generic dashboard:

- Migration-oriented workspace and live workflow stages
- Before/after change exploration
- Release-readiness presentation
- Ask-the-codebase workspace
- Persistent migration/task context
- Hosted-safe Streamlit sidebar collapse/reopen behavior
- System-adaptive light/dark theme with live switching
- Failure states expose a downloadable failure report instead of leaving the user at a dead end

### Live migration telemetry

The task lifecycle is explicitly bound to its backend task ID so workflow progress events can update the task being polled by the UI.

```text
Migration request
      ↓
Task created + bound
      ↓
Scanner / planning / conversion progress
      ↓
Task status endpoint
      ↓
Live migration workspace
```

### Reliability / release behavior

The migration platform now has stronger failure handling around the hosted LLM gateway and artifact generation:

- Gateway rate-limit failures are surfaced as real migration failures rather than fabricated code.
- Invalid/empty model output is rejected instead of being treated as generated source.
- Directory-like output paths are normalized defensively.
- Release readiness is derived from the post-migration quality gate.
- A blocked/failed migration can still produce a clearly labeled failure report when no valid migration artifact exists.
- Hosted execution can use lightweight workflow settings to reduce unnecessary agent-event retention.

## Architecture

```text
Legacy Repository
       ↓
Program Analysis
  AST / CTags / dependencies / stack detection
       ↓
Knowledge Base
  Qdrant + metadata-aware retrieval
       ↓
Migration Planning
  target architecture + symbol/file mapping
       ↓
Agentic Conversion
  context-grounded transformations
       ↓
Post-Migration QA
  structural + executable validation
       ↓
Release Gate
  ready / blocked / review
       ↓
Migration artifact or failure report
```

## Core capabilities

- Multi-language source scanning
- AST / tree-sitter analysis
- Universal CTags symbol extraction
- File and symbol dependency analysis
- Technology/framework detection
- Qdrant-backed analysis retrieval
- Planning before conversion
- Agentic code transformation
- Deterministic post-migration QA
- Release gates and repair loops
- Evidence-backed migration reports
- Ask-the-codebase retrieval over migration artifacts

## BYOK / shared LLM Gateway

LegacyLens uses the portfolio's shared LLM Gateway for request-scoped inference sessions.

```text
Portfolio BYOK
      ↓
Short-lived gateway session
      ↓
LegacyLens
      ↓
Portfolio LLM Gateway
      ↓
Selected provider / model
```

Provider credentials remain outside the project frontend/source repository.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

## Testing

```bash
python -m pytest -q
python portfolio_quality/quality_gate.py .
```

## Limitations

LegacyLens is a portfolio and engineering demonstration, not a turnkey enterprise migration service. Semantic equivalence remains difficult to prove automatically, so the system exposes structural signals, executable checks, release gates, and review-oriented evidence rather than pretending an LLM confidence score proves correctness.

## Portfolio positioning

**Developer modernization workbench** — program analysis, retrieval-grounded planning, agentic conversion, executable validation, and release-aware migration workflows.
