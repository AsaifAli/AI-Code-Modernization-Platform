# v12.4.1 — Docker Node Runtime Fix

- Fixed multi-stage Docker build copying npm/npx launchers incorrectly into the Python image.
- Recreated npm/npx symlinks to the Node runtime's bundled npm installation before installing the pinned Specfy Stack Analyser.
- Retained Agno workflow streaming as the canonical execution-event source.
- Retained WebSocket-free runtime transport.
- Verified pinned `@specfy/stack-analyser` 1.27.6 matches the upstream repository package metadata.

# v12.4.0 — Agno Streaming + Deterministic Stack Analysis

- Removed the legacy WebSocket transport/event bridge.
- Agno Workflow streaming is now the canonical live execution event source.
- Task progress is persisted through the existing REST task endpoint for the Streamlit UI.
- Integrated pinned @specfy/stack-analyser 1.27.6 as the primary deterministic stack detector.
- Runtime no longer invokes npx/network calls to discover the stack.
- Kept optional SourceAnalyzer API as a fallback only.
- Hardened Stack Analyser output handling and timeouts.
- Defaulted embeddings to FastEmbed for CPU/ARM64 deployment.
