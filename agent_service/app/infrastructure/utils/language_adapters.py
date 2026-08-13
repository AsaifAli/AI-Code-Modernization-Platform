"""Language/framework adapter registry for migration validation.

The migration engine is intentionally language-agnostic.  This module isolates
runtime/tooling conventions behind small adapters so the release-gate engine does
not grow a collection of ``if language == ...`` branches.

Adapters are deterministic: they define commands and evidence rules, but never
let an LLM choose arbitrary shell commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

CheckSpec = tuple[str, list[str], bool, str]


@dataclass(frozen=True)
class LanguageAdapter:
    key: str
    display_name: str
    extensions: frozenset[str]
    manifest_files: tuple[str, ...]
    check_builder: Callable[[Path], list[CheckSpec]]
    ci_template: str
    probe_runtime: Optional[str] = None

    def checks(self, root: Path) -> list[CheckSpec]:
        return self.check_builder(root)

    def supports_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions


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


def detect_by_extension(root: Path) -> Optional[str]:
    counts: dict[str, int] = {key: 0 for key in _REGISTRY}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in {".git", ".venv", "venv", "node_modules", "vendor", "target", "build", "dist", "__pycache__"} for part in rel_parts):
            continue
        for adapter in _REGISTRY.values():
            if adapter.supports_file(path):
                counts[adapter.key] += 1
    best = max(counts, key=counts.get) if counts else None
    return best if best and counts.get(best, 0) else None


def _python(root: Path) -> list[CheckSpec]:
    # Keep optional tooling optional: the adapter must not turn a missing
    # developer tool into a false migration failure.
    import shutil
    checks: list[CheckSpec] = [("python-compile", ["python", "-m", "compileall", "-q", "."], True, "syntax")]
    if shutil.which("ruff"):
        checks.append(("ruff", ["ruff", "check", "."], True, "lint"))
    else:
        checks.append(("ruff", ["python", "-m", "ruff", "check", "."], False, "lint"))
    checks.append(("pytest", ["pytest", "-q"] if shutil.which("pytest") else ["python", "-m", "pytest", "-q"], True, "test" if shutil.which("pytest") else "test"))
    if shutil.which("mypy"):
        checks.append(("mypy", ["mypy", "."], False, "typecheck"))
    return checks


def _node(root: Path) -> list[CheckSpec]:
    # The detailed Node repository integrity check lives in post_migration_engine;
    # the adapter only owns ecosystem commands.
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
        return [("maven-test", [mvn, "-B", "test"], True, "test"),
                ("maven-package", [mvn, "-B", "-DskipTests", "package"], True, "build")]
    gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
    return [("gradle-test", [gradle, "test"], True, "test"),
            ("gradle-build", [gradle, "build"], True, "build")]


def _go(root: Path) -> list[CheckSpec]:
    return [("gofmt", ["sh", "-c", "test -z \"$(gofmt -l .)\""], True, "format"),
            ("go-vet", ["go", "vet", "./..."], True, "lint"),
            ("go-test", ["go", "test", "./..."], True, "test"),
            ("go-build", ["go", "build", "./..."], True, "build")]


def _php(root: Path) -> list[CheckSpec]:
    checks: list[CheckSpec] = [("composer-validate", ["composer", "validate", "--no-check-publish"], True, "lint")]
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
    return [("dotnet-restore", ["dotnet", "restore"], True, "install"),
            ("dotnet-build", ["dotnet", "build", "--no-restore"], True, "build"),
            ("dotnet-test", ["dotnet", "test", "--no-build"], True, "test")]


# CI fragments intentionally contain only fixed commands.  The engine controls
# whether a given adapter exists; no model-generated shell is accepted.
register_adapter(LanguageAdapter(
    "python", "Python", frozenset({".py"}), ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"), _python,
    """      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n      - run: python -m pip install --upgrade pip\n      - run: if [ -f requirements.txt ]; then pip install -r requirements.txt; fi\n      - run: if [ -f pyproject.toml ]; then pip install -e .; fi\n      - run: pip install ruff pytest\n      - run: python -m compileall -q .\n      - run: ruff check .\n      - run: pytest -q\n""", "python"))
register_adapter(LanguageAdapter(
    "node", "Node.js", frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}), ("package.json",), _node,
    """      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n          cache: npm\n      - run: if [ -f package-lock.json ]; then npm ci; else npm install; fi\n      - run: node -e \"const p=require('./package.json'); if (p.scripts && p.scripts.lint) process.exit(require('child_process').spawnSync('npm',['run','lint'],{stdio:'inherit'}).status||1)\"\n      - run: node -e \"const p=require('./package.json'); if (p.scripts && p.scripts.test) process.exit(require('child_process').spawnSync('npm',['test'],{stdio:'inherit'}).status||1); else { console.error('Missing scripts.test'); process.exit(1) }\"\n      - run: node -e \"const p=require('./package.json'); if (p.scripts && p.scripts.build) process.exit(require('child_process').spawnSync('npm',['run','build'],{stdio:'inherit'}).status||1)\"\n""", "node"))
register_adapter(LanguageAdapter(
    "java", "Java", frozenset({".java"}), ("pom.xml", "build.gradle", "build.gradle.kts"), _java,
    """      - uses: actions/setup-java@v4\n        with:\n          distribution: temurin\n          java-version: '21'\n          cache: maven\n      - run: mvn -B test\n      - run: mvn -B -DskipTests package\n""", "java"))
register_adapter(LanguageAdapter(
    "go", "Go", frozenset({".go"}), ("go.mod",), _go,
    """      - uses: actions/setup-go@v5\n        with:\n          go-version: '1.23'\n      - run: gofmt -l .\n      - run: go vet ./...\n      - run: go test ./...\n      - run: go build ./...\n""", "go"))
register_adapter(LanguageAdapter(
    "php", "PHP", frozenset({".php"}), ("composer.json",), _php,
    """      - uses: shivammathur/setup-php@v2\n        with:\n          php-version: '8.3'\n      - run: composer install --no-interaction --prefer-dist\n      - run: composer validate --no-check-publish\n      - run: find . -name '*.php' -not -path './vendor/*' -print0 | xargs -0 -n1 php -l\n      - run: if [ -x vendor/bin/phpunit ]; then vendor/bin/phpunit; fi\n""", "php"))
register_adapter(LanguageAdapter(
    "dotnet", ".NET", frozenset({".cs", ".fs", ".vb"}), (".sln", ".csproj"), _dotnet,
    """      - uses: actions/setup-dotnet@v4\n        with:\n          dotnet-version: '8.0.x'\n      - run: dotnet restore\n      - run: dotnet build --no-restore\n      - run: dotnet test --no-build\n""", "dotnet"))
