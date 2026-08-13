# v12.4.3

- Symbol generation is explicitly Ctags-only; removed Tree-sitter runtime imports from the scanner.
- Removed `tree-sitter` and `tree-sitter-language-pack` Python dependencies.
- Retained Python stdlib `ast` only where used for post-migration semantic/behavioral validation; it is not the symbol generator.
- Fixed and verified `AgentConstants` import in `planning_helper.py`.
- Docker build now performs a planning-helper import smoke test so missing imports fail at image build time instead of container startup.
- Universal Ctags remains installed inside the agent container and is the symbol extraction engine.
