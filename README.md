# LegacyLens — Agentic Software Modernization

> **Agentic legacy-code migration with program analysis, dependency intelligence, Qdrant-backed retrieval, migration planning, and post-migration QA.**

LegacyLens analyzes a legacy repository, builds a structured representation of its codebase, creates a migration plan, performs context-grounded code transformation, and evaluates the resulting target project with deterministic engineering checks.

The design deliberately combines **deterministic program analysis** with **probabilistic LLM reasoning** instead of sending an entire repository to a model in one prompt.

## Live deployment

**UI:** https://ai-code-modernization-ui.onrender.com

**API:** https://ai-code-modernization-api.onrender.com

**Deployment:** Render Blueprint (Streamlit UI + FastAPI API)

## Why this project is interesting

A naive modernization system looks like:

```text
Legacy repository → LLM → generated repository
```

That approach breaks down on real repositories because of context limits, missing dependencies, inconsistent transformations, hallucinated APIs, and weak validation.

LegacyLens uses a hybrid workflow:

```text
Repository
    ↓
Program Analysis ── AST / CTags / dependency graph / technology detection
    ↓
Knowledge Base ─── Qdrant + metadata-aware retrieval
    ↓
Migration Planning ── target architecture + file/symbol mapping
    ↓
Agentic Conversion ── context-grounded transformations
    ↓
Post-Migration QA ── structural + execution-aware validation
    ↓
Migration Report / Release Gate
```

## Key engineering decisions

- **Deterministic analysis before generation:** AST, symbols, dependencies, and technology signals ground the agents.
- **Bounded retrieval instead of giant prompts:** analysis artifacts are stored remotely and retrieved selectively.
- **Qdrant Cloud instead of an embedded vector database:** hosted retrieval avoids local database/model baggage in the Render deployment path.
- **Planning before conversion:** target structure and symbol mappings are established before generation.
- **Language-agnostic validation:** execution contracts and toolchain validation are resolved through language/target adapters rather than hard-coded Java/Python rules.
- **QA after generation:** conversion is treated as an engineering workflow with measurable structural and executable checks.

## Architecture

```text
                    ┌──────────────────────┐
                    │     Streamlit UI      │
                    │ upload / progress /   │
                    │ reports / chat        │
                    └──────────┬───────────┘
                               │ HTTP
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI         │
                    │ API + task lifecycle  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Workflow Orchestrator │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
     Repository            Qdrant Cloud          Planning
     Scanner               Knowledge Base        Agent
          │                    │                    │
      AST / CTags        dense + sparse       mappings / goals
      dependencies       metadata filters     target structure
          └────────────────────┼────────────────────┘
                               ▼
                        Conversion Agents
                               │
                               ▼
                         Target Repository
                               │
                               ▼
                       Post-Migration QA
                               │
                         Release Gate
```

## Core capabilities

### Repository intelligence

- Multi-language source scanning
- AST / tree-sitter analysis
- Universal CTags symbol extraction
- File and symbol dependency analysis
- Technology and framework detection
- Complexity and structural signals

### Knowledge engineering

- Lossless analysis-artifact chunking
- Metadata-aware retrieval
- Source/target context separation
- Qdrant Cloud vector storage
- Hosted dense and sparse embedding inference
- Token-bounded context construction

### Agentic migration workflow

- Scanner agent
- Knowledge-base agent
- Migration planning agent
- Conversion agent
- Post-migration analysis
- Conversational access to migration artifacts

### Migration QA + Release Engineering

The target repository enters a deterministic engineering gate after generation:

```text
Generated Target
      ↓
Stack / toolchain detection
      ├── lint / format / syntax
      ├── type checks where available
      ├── dependency install when supported
      ├── unit tests
      └── build / compile / execution checks
      ↓
Failure?
  ├── No  → Release Gate → package
  └── Yes → bounded repair loop → re-run gates
```

Execution-contract handling and target-toolchain validation are language-agnostic. A target adapter determines the appropriate entry-point and validation strategy for the detected ecosystem.

A green gate means the generated project passed the configured executable checks for its detected ecosystem; it is **not** a mathematical proof of semantic equivalence.

## BYOK / LLM integration

LegacyLens uses the shared Portfolio LLM Gateway for portfolio sessions.

```text
Portfolio BYOK
      ↓
Redis-backed session
      ↓
Short-lived JWT
      ↓
LegacyLens
      ↓
Portfolio LLM Gateway
      ↓
User-selected provider/model
```

The application receives a temporary gateway session token. Provider API keys remain server-side.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Typical local endpoints are exposed by the compose configuration for the UI, API, and Swagger interface.

## Testing

```bash
python -m pytest -q
python portfolio_quality/quality_gate.py .
```

## Security posture

- `.env` is ignored and credentials are environment-driven.
- Provider keys are not embedded in source code.
- Runtime/generated directories are ignored.
- Validation commands are allow-listed rather than arbitrary model-generated shell commands.
- External-impact actions are bounded by the workflow design.

## Limitations

LegacyLens is a portfolio and engineering demonstration, not a turnkey enterprise migration service. Semantic equivalence remains difficult to prove automatically, so the system exposes structural signals, execution checks, and review-oriented risk instead of pretending an LLM confidence score proves correctness.

Future production work includes durable worker queues, checkpointed execution, stronger multi-user authorization, deeper language-specific adapters, distributed tracing, and larger benchmark corpora.

## License

MIT License.
