# LegacyLens — Agentic Software Modernization

> **Agentic software modernization with program analysis, dependency intelligence, migration planning, context-grounded code conversion, syntax-aware validation, bounded repair, and release gates.**

LegacyLens analyzes a legacy repository, builds a structured representation of its codebase, creates a migration plan, performs context-grounded code transformation, validates generated source, and evaluates the resulting target project with deterministic engineering checks.

The conversion path is deliberately hybrid: deterministic repository analysis and validation remain outside the model, while the LLM is used for semantic translation and bounded repair where explicit transformation rules are insufficient.

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

The migration platform treats conversion as a verification loop rather than a one-shot generation step:

- LLM inference is routed through the shared Portfolio LLM Gateway using a request-scoped JWT.
- Deterministic repository analysis and validation remain outside the model.
- Generated source is sanitized and syntax-validated before it is accepted as migrated code.
- Syntax failures can trigger a bounded, targeted repair pass instead of a full regeneration.
- Failed conversion steps are propagated as migration failures rather than being counted as successful conversions.
- Post-migration quality gates determine release readiness.
- Blocked migrations are surfaced with explicit failure/review states rather than being presented as successful releases.

## Architecture

```text
Legacy Repository
       ↓
Program Analysis
  AST / CTags / dependencies / stack detection
       ↓
Knowledge Base
  analysis + dependency context
       ↓
Migration Planning
  target architecture + symbol/file mapping
       ↓
Agentic Conversion
  deterministic rules + context-grounded LLM translation
       ↓
Syntax Validation
  AST / tree-sitter checks + bounded repair
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
- Knowledge-base retrieval over repository analysis and dependency context
- Planning before conversion
- Agentic code transformation with deterministic conversion guidance
- Syntax-aware generated-code validation and bounded repair
- Deterministic post-migration QA
- Release gates and repair loops
- Evidence-backed migration reports
- Ask-the-codebase retrieval over migration artifacts

## BYOK / shared LLM Gateway

LegacyLens uses the portfolio's shared LLM Gateway as its inference boundary.

```text
Portfolio
      ↓
Create request-scoped BYOK session
      ↓
Short-lived JWT
      ↓
LegacyLens
  X-LLM-Gateway-Token
      ↓
Portfolio LLM Gateway
      ↓
Selected provider / model
```

LegacyLens does not use direct provider API keys for inference in the hosted portfolio path. The gateway handles provider/model selection and credential custody.

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

**Developer modernization workbench** — program analysis, migration planning, context-grounded conversion, syntax-aware validation, bounded repair, executable checks, and release-aware migration workflows.

## Website demo launch and Gateway session contract

The hosted portfolio launch uses the shared Portfolio LLM Gateway. The website remains the sole provider-credential owner and issues a short-lived, project-scoped Gateway JWT. The LegacyLens Streamlit application receives a one-time launch code, removes `portfolio_llm_handoff` from the browser URL, exchanges it server-side at the Gateway, and keeps the resulting bearer only in Streamlit server-side session state.

The agent-service API receives that bearer only in the `X-LLM-Gateway-Token` request header. The request-scoped `ContextVar` carries it into the migration workflow and the Gateway-aware Agno model client. The deprecated reusable `portfolio_llm_session` URL token is rejected.

For the hosted portfolio deployment, configure:

- `PORTFOLIO_SESSION_GATEWAY_URL`: shared Gateway root used for single-use code exchange.
- `LLM_GATEWAY_URL`: OpenAI-compatible Gateway inference base URL, ending in `/v1`.
- Website project slug: `legacylens`.

Do not pass reusable JWTs in query parameters, store them in browser local storage, or place end-user provider API keys in LegacyLens environment variables for the hosted portfolio path. Local-development provider adapters remain available only where already supported by existing code and explicit local configuration.
