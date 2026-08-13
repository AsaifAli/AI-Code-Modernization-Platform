# Scanning Architecture

## Symbol generation: Universal Ctags only

The migration scanner uses **Universal Ctags** as the symbol extraction engine. Ctags produces definitions, imports, references/calls and related tag metadata used to build the migration project graph.

Universal Ctags is installed **inside the agent Docker image**. `CTAGS_BIN` is optional; when unset the scanner resolves `ctags`/`universal-ctags` from the container PATH.

## What is not used for symbol generation

Tree-sitter is **not part of the symbol-generation pipeline** and is not a runtime dependency of the scanner.

The project previously contained a Tree-sitter AST engine. That was removed from the v12.4.3 scanner package to keep the architecture honest and avoid maintaining two competing symbol parsers.

Python's standard-library `ast` module may still be used by post-migration verification utilities for Python-specific semantic/behavioral checks. That is separate from source symbol extraction and does not replace Ctags.

## Stack Analyzer

`@specfy/stack-analyser` is used only for repository technology/stack discovery (languages, frameworks, libraries and infrastructure signals). It is not used to define migration symbols.

## Pipeline

```text
Source repository
      |
      +--> Stack Analyzer ----> technology / framework metadata
      |
      +--> Universal Ctags ---> symbols / imports / calls / graph
                                   |
                                   v
                            Migration planning
                                   |
                                   v
                              Conversion
                                   |
                                   v
                       Post-migration verification
```
