# Architecture and Data Flow

## Design goal

The platform is designed around one principle: **LLMs should reason over structured, bounded evidence instead of receiving an entire repository as an opaque prompt.**

## Pipeline

### 1. Scan

The scanner builds repository intelligence from source files using Universal CTags for symbol extraction; Python stdlib AST is used only for targeted semantic verification and dependency analysis.

Outputs include files, symbols, relationships, technology hints, complexity signals and scan artifacts.

### 2. Knowledge base

Large analysis artifacts are chunked and stored in a vector-backed knowledge base. Metadata lets retrieval narrow results by source/target repository, artifact type and related context.

This avoids a failure mode where a complete AST consumes the model context window before the agent can reason about the actual migration.

### 3. Plan

The planning stage converts repository intelligence into target-language migration goals, file mappings and conversion steps.

Planning is deliberately separate from code generation so the migration has an inspectable intermediate representation.

### 4. Convert

Conversion agents retrieve only the relevant source symbols, dependencies, target conventions and plan information for each transformation.

### 5. QA

Post-migration analysis compares source and target structures. The current reporting layer calculates heuristic risk from manual intervention, complexity, iterations, unsupported patterns and dependency density, then adds review guidance.

### 6. API/UI

FastAPI owns the task lifecycle and workflow entry points. Streamlit provides a human-friendly interface for uploads, progress, migration artifacts, reports and conversational access.

## Why hybrid AI?

Deterministic components are better at facts such as:

- what files exist
- which functions/classes exist
- which modules depend on each other
- whether generated Python parses
- how many files/functions changed

LLMs are better at semantic work such as:

- inferring intent
- mapping legacy idioms to target idioms
- producing transformation plans
- generating target code

The architecture therefore gives each technique the job it is best suited to perform.
