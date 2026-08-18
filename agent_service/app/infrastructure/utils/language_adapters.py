"""Language/framework adapter registry for migration validation and execution semantics."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import re

CheckSpec = tuple[str, list[str], bool, str]


@dataclass(frozen=True)
class ExecutionContract:
    """Source-side executable behavior that a target should preserve."""

    executable: bool
    entry_symbol: Optional[str] = None
    reason: str = ""


ExecutionDetector = Callable[[Path, Optional[str]], Optional[ExecutionContract]]
EntryPointEnsurer = Callable[[str, ExecutionContract, Optional[str]], str]


@dataclass(frozen=True)
class LanguageAdapter:
    key: str
    display_name: str
    extensions: frozenset[str]
    manifest_files: tuple[str, ...]
    check_builder: Callable[[Path], list[CheckSpec]]
    ci_template: str
    probe_runtime: Optional[str] = None
    execution_detector: Optional[ExecutionDetector] = None
    entrypoint_ensurer: Optional[EntryPointEnsurer] = None

    def checks(self, root: Path) -> list[CheckSpec]:
        return self.check_builder(root)

    def supports_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def detect_execution_contract(
        self, source_file: Path, symbol_name: Optional[str]
    ) -> Optional[ExecutionContract]:
        if self.execution_detector is None:
            return None
        return self.execution_detector(source_file, symbol_name)

    def ensure_entrypoint(
        self,
        target_code: str,
        contract: Optional[ExecutionContract],
        symbol_name: Optional[str],
    ) -> str:
        if not contract or not contract.executable or self.entrypoint_ensurer is None:
            return target_code
        return self.entrypoint_ensurer(target_code, contract, symbol_name)


_REGISTRY: dict[str, LanguageAdapter] = {}


def register_adapter(adapter: LanguageAdapter) -> LanguageAdapter:
    if adapter.key in _REGISTRY:
        raise ValueError(f"Language adapter already registered: {adapter.key}")
    _REGISTRY[adapter.key] = adapter
    return adapter


def get_adapter(key: str) -> Optional[LanguageAdapter]:
    return _REGISTRY.get((key or "").lower())


def adapters() -> tuple[LanguageAdapter, ...]:
    return tuple(_REGISTRY.values())


def adapter_for_file(path: Path) -> Optional[LanguageAdapter]:
    for adapter in _REGISTRY.values():
        if adapter.supports_file(path):
            return adapter
    return None


def detect_by_extension(root: Path) -> Optional[str]:
    counts: dict[str, int] = {key: 0 for key in _REGISTRY}
    ignored = {
        ".git", ".venv", "venv", "node_modules", "vendor", "target",
        "build", "dist", "__pycache__", ".pytest_cache",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        for adapter in _REGISTRY.values():
            if adapter.supports_file(path):
                counts[adapter.key] += 1
    best = max(counts, key=counts.get) if counts else None
    return best if best and counts.get(best, 0) else None


# ---------------------------------------------------------------------------
# Execution-contract detection/realization is intentionally adapter-owned.
# The shared conversion engine does not branch on source/target language.
# ---------------------------------------------------------------------------


def _python_execution_contract(
    source_file: Path, symbol_name: Optional[str]
) -> Optional[ExecutionContract]:
    """Detect Python module-level execution of the symbol being migrated."""
    if not symbol_name:
        return None
    try:
        import ast
        tree = ast.parse(source_file.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None

    # Direct module-level invocation: calculator()
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name) and fn.id == symbol_name:
                return ExecutionContract(True, symbol_name, "module-level invocation")

    # Conventional __main__ guard: if __name__ == "__main__": calculator()
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        for child in node.body:
            if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                fn = child.value.func
                if isinstance(fn, ast.Name) and fn.id == symbol_name:
                    return ExecutionContract(True, symbol_name, "__main__ guarded invocation")

    return ExecutionContract(False, symbol_name, "no executable invocation detected")


def _java_entrypoint_ensurer(
    target_code: str, contract: ExecutionContract, symbol_name: Optional[str]
) -> str:
    """Java adapter: realize an executable contract as a Java main method."""
    if not target_code.strip() or re.search(r"\bstatic\s+void\s+main\s*\(", target_code):
        return target_code

    cls = re.search(r"\b(?:public\s+)?class\s+([A-Za-z_$][\w$]*)\b", target_code)
    if not cls:
        return target_code
    class_name = cls.group(1)

    candidates = re.findall(
        r"(?:public|protected|private)?\s*(?:final\s+)?(?:static\s+)?"
        r"[\w<>\[\],.? ]+\s+([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*\{",
        target_code,
    )
    desired = None
    normalized = re.sub(r"[^A-Za-z0-9_$]", "", symbol_name or "")
    for name in candidates:
        if name == normalized or name.lower() == normalized.lower():
            desired = name
            break
    if desired is None:
        for name in candidates:
            if name not in {"main", class_name}:
                desired = name
                break
    if desired is None:
        return target_code

    insertion = (
        "\n    public static void main(String[] args) {\n"
        f"        new {class_name}().{desired}();\n"
        "    }\n"
    )
    closing = target_code.rfind("}")
    if closing < 0:
        return target_code
    return target_code[:closing] + insertion + target_code[closing:]


def _go_entrypoint_ensurer(
    target_code: str, contract: ExecutionContract, symbol_name: Optional[str]
) -> str:
    """Go adapter: realize an executable contract as package main()."""
    if not target_code.strip() or re.search(r"\bfunc\s+main\s*\(", target_code):
        return target_code
    if not symbol_name or not re.search(
        rf"\bfunc\s+{re.escape(symbol_name)}\s*\(", target_code
    ):
        return target_code
    return target_code.rstrip() + f"\n\nfunc main() {{\n\t{symbol_name}()\n}}\n"


def _noop_entrypoint_ensurer(
    target_code: str, contract: ExecutionContract, symbol_name: Optional[str]
) -> str:
    return target_code


# ---------------------------------------------------------------------------
# Validation adapters
# ---------------------------------------------------------------------------


def _python(root: Path) -> list[CheckSpec]:
    import shutil

    checks: list[CheckSpec] = [
        ("python-compile", ["python", "-m", "compileall", "-q", "."], True, "syntax"),
    ]
    if shutil.which("ruff"):
        checks.append(("ruff", ["ruff", "check", "."], True, "lint"))
    else:
        checks.append(("ruff", ["python", "-m", "ruff", "check", "."], False, "lint"))
    checks.append(
        ("pytest", ["pytest", "-q"] if shutil.which("pytest") else ["python", "-m", "pytest", "-q"], True, "test")
    )
    if shutil.which("mypy"):
        checks.append(("mypy", ["mypy", "."], False, "typecheck"))
    return checks


def _node(root: Path) -> list[CheckSpec]:
    package = root / "package.json"
    scripts = {}
    if package.exists():
        import json
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {}) or {}
        except Exception:
            pass
    checks: list[CheckSpec] = []
    if (root / "package-lock.json").exists():
        checks.append(("npm-ci", ["npm", "ci"], True, "install"))
    elif (root / "pnpm-lock.yaml").exists():
        checks.append(("pnpm-install", ["pnpm", "install", "--frozen-lockfile"], True, "install"))
    if "lint" in scripts:
        checks.append(("npm-lint", ["npm", "run", "lint"], True, "lint"))
    if "test" in scripts:
        checks.append(("npm-test", ["npm", "test", "--", "--runInBand"], True, "test"))
    if "build" in scripts:
        checks.append(("npm-build", ["npm", "run", "build"], True, "build"))
    return checks


def _java(root: Path) -> list[CheckSpec]:
    if (root / "pom.xml").exists() or (root / "mvnw").exists():
        mvn = "./mvnw" if (root / "mvnw").exists() else "mvn"
        return [
            ("maven-test", [mvn, "-B", "test"], True, "test"),
            ("maven-package", [mvn, "-B", "-DskipTests", "package"], True, "build"),
        ]
    gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
    return [
        ("gradle-test", [gradle, "test"], True, "test"),
        ("gradle-build", [gradle, "build"], True, "build"),
    ]


def _go(root: Path) -> list[CheckSpec]:
    return [
        ("gofmt", ["sh", "-c", 'test -z "$(gofmt -l .)"'], True, "format"),
        ("go-vet", ["go", "vet", "./..."], True, "lint"),
        ("go-test", ["go", "test", "./..."], True, "test"),
        ("go-build", ["go", "build", "./..."], True, "build"),
    ]


def _php(root: Path) -> list[CheckSpec]:
    checks: list[CheckSpec] = [
        ("composer-validate", ["composer", "validate", "--no-check-publish"], True, "lint")
    ]
    if (root / "composer.lock").exists():
        checks.append(("composer-install", ["composer", "install", "--no-interaction", "--prefer-dist"], True, "install"))
    for p in root.rglob("*.php"):
        if any(part in {"vendor", ".git", ".migration"} for part in p.parts):
            continue
        checks.append((f"php-lint:{p.relative_to(root)}", ["php", "-l", str(p.relative_to(root))], True, "syntax"))
    if (root / "vendor" / "bin" / "phpunit").exists():
        checks.append(("phpunit", ["vendor/bin/phpunit", "--testdox"], True, "test"))
    return checks[:80]


def _dotnet(root: Path) -> list[CheckSpec]:
    return [
        ("dotnet-restore", ["dotnet", "restore"], True, "install"),
        ("dotnet-build", ["dotnet", "build", "--no-restore"], True, "build"),
        ("dotnet-test", ["dotnet", "test", "--no-build"], True, "test"),
    ]


# CI fragments intentionally contain only fixed commands.
register_adapter(LanguageAdapter(
    "python", "Python", frozenset({".py"}),
    ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"),
    _python,
    """      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install --upgrade pip
      - run: if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      - run: if [ -f pyproject.toml ]; then pip install -e .; fi
      - run: pip install ruff pytest
      - run: python -m compileall -q .
      - run: ruff check .
      - run: pytest -q
""",
    "python", _python_execution_contract, None,
))
register_adapter(LanguageAdapter(
    "node", "Node.js", frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}),
    ("package.json",), _node,
    """      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: if [ -f package-lock.json ]; then npm ci; else npm install; fi
""",
    "node", None, _noop_entrypoint_ensurer,
))
register_adapter(LanguageAdapter(
    "java", "Java", frozenset({".java"}),
    ("pom.xml", "build.gradle", "build.gradle.kts"), _java,
    """      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: maven
      - run: mvn -B test
      - run: mvn -B -DskipTests package
""",
    "java", None, _java_entrypoint_ensurer,
))
register_adapter(LanguageAdapter(
    "go", "Go", frozenset({".go"}),
    ("go.mod",), _go,
    """      - uses: actions/setup-go@v5
        with:
          go-version: '1.23'
      - run: gofmt -l .
      - run: go vet ./...
      - run: go test ./...
      - run: go build ./...
""",
    "go", None, _go_entrypoint_ensurer,
))
register_adapter(LanguageAdapter(
    "php", "PHP", frozenset({".php"}),
    ("composer.json",), _php,
    """      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.3'
      - run: composer install --no-interaction --prefer-dist
      - run: composer validate --no-check-publish
""",
    "php", None, _noop_entrypoint_ensurer,
))
register_adapter(LanguageAdapter(
    "dotnet", ".NET", frozenset({".cs", ".fs", ".vb"}),
    (".sln", ".csproj"), _dotnet,
    """      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '8.0.x'
      - run: dotnet restore
      - run: dotnet build --no-restore
      - run: dotnet test --no-build
""",
    "dotnet", None, _noop_entrypoint_ensurer,
))
