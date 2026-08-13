# Migration Reporting Feature - Manager Brief + FAQ

## 1) What We Changed

We implemented a **new Migration Comparison Reporting capability** focused on source-vs-migrated code quality and review prioritization.

### New capabilities added

1. **Risk Heatmap generation**
   - Module-level risk scoring (`High`, `Medium`, `Low`) with reason and recommendation.

2. **Module Review Cards**
   - Summary: migrated LOC, auto-conversion percentage
   - Semantic change signals: function/LOC/dependency deltas
   - Auto-flagged risk areas
   - Suggested review checklist

3. **Gap Detection Engine**
   - Functional, Structural, Behavioral, Coverage gaps
   - Severity + suggested action

4. **Confidence Scoring**
   - Per-module confidence %, derived inversely from risk + test signals

5. **Report persistence**
   - JSON and Markdown artifacts are stored in migration output folder

6. **Service-level API strategy**
   - Report generation endpoint exists in `agent_service`
   - **Proxy endpoint added in `migration_service`** so clients do not need direct access to `agent_service`


## 2) Why This Approach

The goal is to move from raw migration logs to **actionable review intelligence**:

- Identify risky modules first (where manual review effort should go)
- Detect possible migration gaps early
- Provide leadership-level visibility via concise heatmaps + confidence
- Keep architecture secure and clean by exposing report API through `migration_service` only


## 3) High-Level Concept We Follow

We use a **hybrid evidence model**:

- Scanner artifacts (`source_scanner_output.json`, `target_scanner_output.json`)
- Response artifacts (`source_response.json`, `target_response.json`)
- Mapping artifacts (`file_mapping.json`)

From these, we compute deterministic metrics and aggregate them module-wise:

- Manual intervention proxy
- Complexity proxy
- Iteration proxy
- Unsupported pattern proxy
- Dependency density proxy

Then we derive:

- `Risk Score` (weighted formula)
- `Confidence Score` (inverse-risk style signal)
- Gap tables


## 4) Endpoints and Parameters

## A) Internal generator endpoint (agent service)

`POST /v1/report/migration`

### Request body

- `migration_name` (string, required)
  - Migration identifier used to locate artifacts in Temp folder
- `persist` (boolean, optional, default `true`)
  - If true, save report files (`json` + `md`) to disk
- `include_markdown` (boolean, optional, default `false`)
  - If true, include full markdown content in API response

### Response (key sections)

- `risk_heatmap`
- `module_review_cards`
- `gap_detection`
- `confidence_score`
- `conversion_pattern_shifts`
- `artifact_paths` (if persist=true)


## B) Public/proxy endpoint (migration service)

`POST /workflow/report/migration`

This endpoint forwards request to `agent_service` and returns the same report payload.

### Why proxy exists

- To avoid exposing `agent_service` directly to clients
- To keep client integration centralized in `migration_service`
- To preserve existing auth and gateway usage patterns


## 5) How Scoring Works

## Risk Score Formula

```text
Risk Score =
(0.3 * Manual Intervention) +
(0.2 * Complexity) +
(0.2 * Iterations) +
(0.2 * Unsupported Patterns) +
(0.1 * Dependency Density)
```

### Interpretation

- Higher score => higher risk => deeper review needed
- Banding:
  - `>= 67` -> High
  - `34 to 66.99` -> Medium
  - `< 34` -> Low

## Confidence Score

- Derived from inverse risk (plus small testing signal)
- Higher confidence means lower manual verification effort expected


## 6) How Report Is Generated (Flow)

1. Resolve migration directory from context (`migration_name`, user scope)
2. If full source-vs-target artifacts exist, run **comparison mode**
3. If only `migrated_code/` exists, run **migrated-code-only mode**
4. Build module-level grouped stats (files, LOC, function count, dependencies)
5. Compute weighted risk and confidence scores
6. Derive gap rows and review guidance
7. Build final payload sections
8. Persist JSON/Markdown artifacts (optional)

### Reporting Modes

- `source_vs_migrated`
  - Uses source + target artifacts for true comparison
- `migrated_code_only`
  - Uses only `migrated_code/` analysis when source/target response artifacts are missing
  - Useful when migration output is available but intermediate response files are not guaranteed


## 7) Artifacts Generated

When `persist=true`, files are written under:

`<migration_dir>/reporting/`

- `migration_risk_report_<timestamp>.json`
- `migration_risk_report_<timestamp>.md`
- `migration_risk_report_latest.json`
- `migration_risk_report_latest.md`


## 8) Manager-Level Value Summary

- Converts technical migration output into **audit-friendly decision support**
- Enables **risk-based review planning**
- Makes migration quality visible with objective metrics
- Supports governance with stored report artifacts
- Scales across migrations via standardized format


## 9) FAQ

### Q1) Is this AI-only or deterministic?
Mostly deterministic from scanner/mapping artifacts. AI is already used upstream in scanning/analysis, but report assembly itself is metric-driven.

### Q2) Why module-level reporting?
Managers and reviewers prioritize work per business module, not per raw file. Module heatmaps are easier to action.

### Q3) Can clients skip calling agent service?
Yes. Use `migration_service` endpoint `/workflow/report/migration`. It proxies internally.

### Q4) What if target artifacts are missing?
Report can still be generated with reduced comparison depth, but quality improves significantly when both source and target artifacts exist.

### Q5) Is this replacing code review?
No. It guides code review effort by ranking risk and likely gaps.

### Q6) What does `persist` do?
Saves generated report files (`json` + `md`) to migration folder for traceability, downloads, and audits.

### Q7) What does `include_markdown` do?
Returns markdown report text inline in API response for UI preview. If false, markdown is not included in payload (still persisted if `persist=true`).

### Q8) How should manager interpret confidence?
- `<70%`: detailed validation recommended
- `70%-89%`: moderate review
- `>=90%`: minimal review/spot checks

### Q9) Is risk formula fixed?
Current formula is configurable in code and can be tuned by organization policy.

### Q10) What are current limitations?
- Some proxies (iterations/manual effort) are inferred from available artifacts
- Module grouping is path-driven; future enhancement can use richer domain tagging
- Behavioral gap detection is heuristic in v1/v2

### Q11) Do we require `target_response.json`?
No. The latest implementation supports `migrated_code_only` mode if only migrated code exists.

### Q12) Are we using AST or KB?
Both:
- AST/scanner artifacts power deterministic metrics and structure analysis
- KB powers retrieval/assistive analysis (chat/docs/diagram context), with source/target separation via `is_target`


## 10) Suggested Next Enhancements

1. Persist report rows in DB for dashboard filtering and trend charts
2. Add release-by-release risk trend per migration
3. Add explicit test coverage import (if test reports available)
4. Add downloadable PDF endpoint generated from markdown
5. Add configurable risk weights via admin settings

