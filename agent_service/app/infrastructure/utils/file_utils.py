import logging
import json
import shutil
from pathlib import Path
from app.infrastructure.repositories.prompt_repository import fetch_prompt_from_db
from app.infrastructure.utils.Constants.app_constants import Constants
from typing import Dict, Any, List
import re
from app.infrastructure.utils.Constants.prompt_constants import PromptConstants as PC
from app.infrastructure.utils.migration_context import (
    migration_name_ctx,
    migration_path_ctx,
)
from app.infrastructure.utils.Constants.prompt_messages import PromptMessages as PM
from app.infrastructure.utils.Constants.validation_messages import ValidationMessages as VM
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from app.infrastructure.utils.migration_context import (
    target_language_ctx,
    target_framework_ctx,
    target_architecture_ctx,
)

def _get_runtime_tech_context():
    return {
        "language": target_language_ctx.get(""),
        "framework": target_framework_ctx.get() or "None",
        "architecture": target_architecture_ctx.get() or "Unknown",
    }

def read_file_content(file_path: str) -> str:
    """Safely read file content with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return ""
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return ""


def read_json_file(file_path: str) -> dict:
    """
    Read and parse a JSON file with enhanced error handling.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Validate data is not None
        if data is None:
            logger.error(f"JSON file {file_path} parsed to None")
            return {}
            
        # Log structure for debugging
        if isinstance(data, dict):
            logger.debug(f"Read JSON from {file_path}: {len(data)} top-level keys")
        else:
            logger.warning(f"JSON from {file_path} is not a dict, it's {type(data)}")
            
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        raise
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}")
        raise

def add_placeholder_content(structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add placeholder content to files when generation fails.
    This is a recursive helper function.
    """
    def add_placeholders(node):
        if isinstance(node, dict):
            if node.get("kind") == "file":
                if "content" not in node or node["content"] is None:
                    file_name = node.get("name", "file")
                    ext = Path(file_name).suffix
                    
                    # Generate appropriate placeholder based on file type
                    if ext == ".json":
                        node["content"] = "{\n  \"placeholder\": true\n}\n"
                    elif ext == ".md":
                        node["content"] = "# Placeholder\n\nContent generation pending.\n"
                    elif ext in [".js", ".ts"]:
                        node["content"] = "// TODO: Implement this file\n// Placeholder content\n\nmodule.exports = {};\n"
                    else:
                        node["content"] = "// Placeholder - content generation failed\n"
                        
            if "children" in node and isinstance(node["children"], list):
                for child in node["children"]:
                    add_placeholders(child)
        return node
    
    return add_placeholders(structure.copy())

def get_migration_directory(migration_name: str = "", source_path: str = "./") -> Path:
    """
    Returns the migration directory for the CURRENT USER REQUEST.

    NOTE:
    - migration_name & source_path arguments are ignored
    - Values come from ContextVars set by the orchestrator
    """

    ctx_migration_name = migration_name_ctx.get(None)
    ctx_migration_path = migration_path_ctx.get(None)
    if ctx_migration_name and ctx_migration_path:
        migration_name = ctx_migration_name
        migration_path = ctx_migration_path
    else:
        # Fallback to parameters (for initialization)
        if not migration_name:
            # During initialization, allow empty migration_name and create a temp directory
            migration_name = "temp_init"
        migration_path = migration_path_ctx.get(None)
        if not migration_path:
            # For initialization, create a temporary path
            migration_path = Path(source_path).parent / "migrations" / migration_name
    if not migration_path:
        raise ValueError("migration_path not set")

    # Some orchestrator flows already provide a migration_path that ends with the migration_name
    # (e.g. .../Temp/<user>/<migration>/Dest/<migration>). Avoid duplicating the name.
    base = Path(migration_path)
    migration_dir = base if base.name == migration_name else (base / migration_name)
    migration_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Migration directory: {migration_dir}")
    return migration_dir



def parse_json_response(response_text: str) -> dict:
    """
    Universal JSON parser for LLM responses with comprehensive fallback strategies.
    Handles all known LLM output patterns across different models and prompts.
    Language-agnostic - works with any JSON structure.
    
    Args:
        response_text: Raw LLM response text
        
    Returns:
        Parsed JSON as dict or list
        
    Raises:
        ValueError: If all parsing strategies fail
    """
    if not response_text or not isinstance(response_text, str):
        raise ValueError(VM.INVALID_LLM_RESPONSE_TEXT)
    
    text = response_text.strip()
    
    # Strategy 1: Direct parse (cleanest response)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Remove ALL markdown code blocks (```json, ```, ```python, etc.)
    try:
        # Remove code block markers with any language tag
        cleaned = re.sub(r'```[\w]*\s*', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Remove common LLM preambles and postambles
    try:
        # Remove common conversational prefixes
        preambles = [
            r'^(?:here\'s?|here is|sure,?|okay,?|alright,?|certainly,?)\s*(?:the|a)?\s*(?:json|result|response|output)?[:\s]*',
            r'^(?:let me|i\'ll|i will)\s*(?:provide|give|show)\s*(?:you\s*)?(?:the|a)?\s*(?:json|result)?[:\s]*',
            r'^(?:based on|according to|analyzing)\s*.*?[:\s]*',
        ]
        
        cleaned = text
        for pattern in preambles:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove trailing explanations
        postambles = [
            r'(?:let me know|please note|note that|this (?:json|result|output)).*$',
            r'(?:i hope|hope this).*$',
        ]
        
        for pattern in postambles:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        cleaned = cleaned.strip()
        if cleaned:
            return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 4: Extract first complete JSON object {...}
    try:
        start = text.find('{')
        if start != -1:
            # Find matching closing brace
            brace_count = 0
            for i in range(start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_text = text[start:i+1]
                        return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 5: Extract first complete JSON array [...]
    try:
        start = text.find('[')
        if start != -1:
            # Find matching closing bracket
            bracket_count = 0
            for i in range(start, len(text)):
                if text[i] == '[':
                    bracket_count += 1
                elif text[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_text = text[start:i+1]
                        parsed = json.loads(json_text)
                        # Wrap array in object for consistency
                        if isinstance(parsed, list):
                            return {"data": parsed}
                        return parsed
    except json.JSONDecodeError:
        pass
    
    # Strategy 6: Handle JSONL (JSON Lines) - multiple JSON objects
    try:
        lines = text.strip().split('\n')
        json_objects = []
        for line in lines:
            line = line.strip()
            if line.startswith('{') or line.startswith('['):
                try:
                    obj = json.loads(line)
                    json_objects.append(obj)
                except json.JSONDecodeError:
                    continue
        
        if json_objects:
            # If multiple objects, return as array
            if len(json_objects) > 1:
                return {"data": json_objects}
            return json_objects[0]
    except Exception:
        pass
    
    # Strategy 7: Fix common JSON syntax errors
    try:
        # Fix single quotes to double quotes
        cleaned = text.replace("'", '"')
        
        # Fix trailing commas
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        # Fix Python-style booleans/None
        cleaned = re.sub(r'\bTrue\b', 'true', cleaned)
        cleaned = re.sub(r'\bFalse\b', 'false', cleaned)
        cleaned = re.sub(r'\bNone\b', 'null', cleaned)
        
        # Try to find and extract JSON
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_text = cleaned[start:end+1]
            return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 8: Handle escaped JSON (double-encoded)
    try:
        # Check if response is escaped JSON
        if '\\{' in text or '\\"' in text:
            # Try to decode escaped JSON
            decoded = text.encode().decode('unicode_escape')
            return json.loads(decoded)
    except Exception:
        pass
    
    # Strategy 9: Extract from code examples (some LLMs wrap in examples)
    try:
        # Pattern: Example: {...}
        example_pattern = r'(?:example|output|result)[:\s]*({.*?}|\[.*?\])'
        match = re.search(example_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError:
        pass
    
    # Strategy 10: Parse YAML-like responses (some LLMs output YAML)
    try:
        import yaml
        # Try parsing as YAML and convert to JSON-compatible dict
        parsed = yaml.safe_load(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass
    
    # Strategy 11: Extract key-value pairs manually (last resort)
    try:
        # Try to construct JSON from visible key-value patterns
        result = {}
        
        # Pattern: "key": "value" or key: value
        kv_pattern = r'["\']?(\w+)["\']?\s*:\s*["\']?([^,}\n]+)["\']?'
        matches = re.findall(kv_pattern, text)
        
        if matches:
            for key, value in matches:
                # Clean value
                value = value.strip().strip('"').strip("'").strip()
                # Try to parse as number/boolean
                try:
                    if value.lower() == 'true':
                        result[key] = True
                    elif value.lower() == 'false':
                        result[key] = False
                    elif value.lower() == 'null':
                        result[key] = None
                    else:
                        # Try as number
                        try:
                            result[key] = int(value)
                        except ValueError:
                            try:
                                result[key] = float(value)
                            except ValueError:
                                result[key] = value
                except Exception:
                    result[key] = value
            
            if result:
                return result
    except Exception:
        pass
    
    # Strategy 12: Handle HTML/XML tags (some responses have tags)
    try:
        # Remove HTML/XML tags
        cleaned = re.sub(r'<[^>]+>', '', text)
        cleaned = cleaned.strip()
        if cleaned:
            # Try parsing the cleaned text
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_text = cleaned[start:end+1]
                return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    # Final fallback: Return structured error info
    logger.error("=" * 60)
    logger.error("ALL JSON PARSING STRATEGIES FAILED")
    logger.error("=" * 60)
    logger.error(f"Response length: {len(text)} characters")
    logger.error(f"Starts with: {text[:100]}")
    logger.error(f"Ends with: {text[-100:]}")
    logger.error(f"Contains '{{': {'{' in text}")
    logger.error(f"Contains '[': {'[' in text}")
    logger.error(f"Contains markdown: {'```' in text}")
    
    # Try to identify what the response looks like
    if not any(c in text for c in ['{', '[', ':']):
        logger.error("Response appears to be plain text (no JSON structure)")
    elif '```' in text:
        logger.error("Response contains markdown code blocks")
    elif '<' in text and '>' in text:
        logger.error("Response appears to contain HTML/XML")
    
    logger.error("=" * 60)
    
    raise ValueError(VM.LLM_JSON_PARSE_FAILED)

def cleanup_migration_directory(migration_name: str, source_path: str, force: bool = False) -> bool:
    """
    Cleanup migration directory after successful code push.
    Language-agnostic - removes all migration artifacts.
    
    Args:
        migration_name: Migration identifier
        source_path: Source project path
        force: If True, delete without confirmation
        
    Returns:
        True if cleanup successful, False otherwise
    """
    try:
        migration_dir = get_migration_directory(migration_name, source_path)
        
        if not migration_dir.exists():
            logger.warning(f"Migration directory does not exist: {migration_dir}")
            return False
        
        # Log what will be deleted
        total_size = sum(
            f.stat().st_size for f in migration_dir.rglob('*') if f.is_file()
        )
        file_count = sum(1 for _ in migration_dir.rglob('*') if _.is_file())
        
        logger.info(f"Cleaning up migration directory:")
        logger.info(f"  Path: {migration_dir}")
        logger.info(f"  Files: {file_count}")
        logger.info(f"  Size: {total_size / (1024*1024):.2f} MB")
        
        # Perform cleanup
        shutil.rmtree(migration_dir)
        
        logger.info(f"✅ Migration directory cleaned up successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup migration directory: {e}")
        return False

def _collect_convertible_files(source_path_obj: Path, non_convertible: set) -> list[Path]:
    """Scan folder and return list of convertible files."""
    # Directories and exact filenames that are never convertible source code.
    # Mirrors the directory + exact-filename sets in _apply_rule_based_exclusions
    # so both functions stay consistent without duplicating extension logic.
    QUICK_EXCLUDE_DIRS = {
        # Dependency caches
        "node_modules", "vendor", "bower_components",
        # VCS
        ".git", ".svn", ".hg",
        # Build outputs
        "dist", "build", "out", "output", "target", "bin", "obj",
        "release", "debug", ".next", ".nuxt", ".svelte-kit", "_site",
        "__pycache__",
        # Test / coverage
        "coverage", "htmlcov", ".nyc_output",
        # Virtual envs
        ".venv", "venv", "env", "site-packages", ".tox", ".nox",
        # Tool caches
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
        ".parcel-cache", ".turbo", ".gradle", ".m2",
        # IDE
        ".idea", ".vscode", ".vs",
        # Misc / archive metadata
        ".blib", "tmp", "temp", "logs", ".docker", "__MACOSX",
    }

    QUICK_EXCLUDE_NAMES = {
        # Lock files
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "composer.lock", "Gemfile.lock", "Cargo.lock",
        "go.sum", "poetry.lock", "Pipfile.lock",
        # Manifests (read by package scanner, not converted)
        "package.json", "composer.json", "pyproject.toml",
        "setup.py", "setup.cfg", "Pipfile",
        "pom.xml", "build.gradle", "build.gradle.kts",
        "Cargo.toml", "go.mod", "Gemfile", "pubspec.yaml",
        # VCS / env / docs
        ".gitignore", ".gitattributes",
        ".env", ".env.local", ".env.example",
        ".editorconfig", ".dockerignore",
        "README.md", "CHANGELOG.md", "LICENSE", "LICENSE.md",
    }

    # Extensions that are never convertible source code
    QUICK_EXCLUDE_EXTENSIONS = {
        ".json", ".yaml", ".yml", ".toml", ".lock",
        ".sum", ".log", ".csv", ".tsv",
        ".env", ".ini", ".cfg", ".conf", ".config", ".properties",
        ".xml", ".map", ".md",
        # Binary / media (fast path)
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp",
        ".mp3", ".mp4", ".wav", ".zip", ".tar", ".gz", ".7z", ".rar",
        ".jar", ".war", ".exe", ".dll", ".so", ".dylib", ".class",
        ".pyc", ".pyo", ".wasm", ".pdf", ".doc", ".docx",
        ".ttf", ".otf", ".woff", ".woff2",
        ".db", ".sqlite", ".pkl", ".npy", ".pt", ".pem", ".crt",
    }

    def should_exclude(path: Path) -> bool:
        # Directory component match
        if any(part in QUICK_EXCLUDE_DIRS for part in path.parts):
            return True
        # macOS Finder metadata from uploaded archives
        if "__MACOSX" in path.parts or path.name.startswith("._"):
            return True
        # Exact filename match (case-insensitive)
        if path.name.lower() in {n.lower() for n in QUICK_EXCLUDE_NAMES}:
            return True
        # Extension match
        if path.suffix.lower() in QUICK_EXCLUDE_EXTENSIONS:
            return True
        return False

    convertible_files = []
    for file_path in source_path_obj.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(source_path_obj).as_posix()
        if rel_path in non_convertible or should_exclude(file_path):
            continue
        convertible_files.append(file_path)
    logger.info(f"Total convertible files after exclusion: {len(convertible_files)}")
    return convertible_files

def _apply_rule_based_exclusions(all_files: List[Path],
                                 source_path: Path) -> tuple[set, List[str]]:
    """
    Apply fast, rule-based exclusions before the LLM pass.
    Language-agnostic: covers binaries, media, generated artefacts, lock files,
    package manifests, data files, infra configs, and tooling metadata.

    Reuses _find_package_manager_files logic implicitly: every file that
    _find_package_manager_files would return is also listed here so it is
    excluded from the convertible-code set.
    """

    # ── Directories: any file whose path contains one of these parts ────────
    EXCLUDED_DIRS = {
        # Dependency caches
        "node_modules", "vendor", "bower_components", ".pnp",
        # VCS
        ".git", ".svn", ".hg",
        # Build outputs
        "dist", "build", "out", "output", "target", "bin", "obj",
        "release", "debug", ".next", ".nuxt", ".output", ".svelte-kit",
        "public/build", "_site", "site", "__pycache__",
        # Test / coverage artefacts
        "coverage", "htmlcov", ".nyc_output", "lcov-report",
        # Virtual envs / sandboxes
        ".venv", "venv", "env", ".env", "Env",
        "site-packages", ".tox", ".nox",
        # Tool caches
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
        ".parcel-cache", ".turbo", ".gradle", ".m2", ".ivy2",
        # IDE / editor
        ".idea", ".vscode", ".vs", ".eclipse",
        # Misc generated
        ".blib", "vendor_bundle", "tmp", "temp", "logs",
        # Containerisation layers
        ".docker",
    }

    # ── Binary / media / archive extensions ────────────────────────────────
    BINARY_EXTENSIONS = {
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".ico", ".svg", ".webp", ".avif", ".heic", ".heif", ".raw",
        ".psd", ".ai", ".eps", ".xcf",
        # Audio / video
        ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".aac", ".m4a",
        ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm",
        # Archives / packages
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
        ".jar", ".war", ".ear", ".aar", ".apk", ".ipa", ".deb", ".rpm",
        ".whl", ".egg", ".gem", ".nupkg", ".vsix",
        # Compiled / binary
        ".exe", ".dll", ".so", ".dylib", ".lib", ".a", ".o", ".obj",
        ".class", ".pyc", ".pyo", ".pyd",
        ".wasm", ".bin", ".elf", ".out",
        # Documents / data blobs
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        # Database / model files
        ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb",
        ".pkl", ".pickle", ".joblib", ".npy", ".npz", ".h5", ".hdf5",
        ".pt", ".pth", ".ckpt", ".onnx", ".pb", ".tflite",
        # Certificates / keys
        ".pem", ".crt", ".cer", ".p12", ".pfx", ".key", ".pub",
    }

    # ── Exact filenames always excluded ────────────────────────────────────
    EXCLUDED_EXACT = {
        # ── Lock files (every ecosystem) ───────────────────────────────────
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "composer.lock", "Gemfile.lock", "gems.locked",
        "Podfile.lock", "Cartfile.resolved", "Package.resolved",
        "Cargo.lock", "go.sum", "go.work.sum", "Gopkg.lock",
        "poetry.lock", "Pipfile.lock",
        "paket.lock", "packages.lock.json",
        "mix.lock", "rebar.lock",
        "stack.yaml.lock", "cabal.project.freeze",
        "cpanfile.snapshot", "renv.lock", "packrat.lock",
        "shard.lock", "dub.selections.json",
        "pubspec.lock", ".dart_tool/package_config.json",
        "Brewfile.lock.json", "flake.lock",
        ".terraform.lock.hcl", "MODULE.bazel.lock",
        "carton.lock",

        # ── Package manifests / dependency declarations ─────────────────────
        # (These are READ by _find_package_manager_files / _extract_packages_from_files
        #  but must NOT be treated as convertible source code.)
        "package.json", "composer.json",
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "requirements-prod.txt", "requirements-base.txt", "constraints.txt",
        "Pipfile", "pyproject.toml", "setup.py", "setup.cfg",
        "tox.ini", "conda.yml", "conda.yaml",
        "environment.yml", "environment.yaml",
        "pom.xml", "build.gradle", "build.gradle.kts",
        "settings.gradle", "settings.gradle.kts",
        "gradle.properties", "ivy.xml", "ivysettings.xml",
        "build.sbt", "plugins.sbt",
        "Cargo.toml",
        "go.mod", "go.work", "Gopkg.toml",
        "Gemfile", "Rakefile", "Podfile", "Brewfile",
        "bower.json", "lerna.json", "nx.json", "turbo.json", "rush.json",
        "pubspec.yaml", "mix.exs", "rebar.config",
        "stack.yaml", "dune-project", "opam", "esy.json",
        "Makefile.PL", "Build.PL", "cpanfile",
        "DESCRIPTION", "Project.toml", "Manifest.toml",
        "dub.json", "dub.sdl",
        "build.zig.zon",
        "shard.yml",
        "project.clj", "deps.edn", "shadow-cljs.edn",
        "elm.json", "psc-package.json", "spago.dhall", "spago.yaml",
        "gleam.toml", "Scarb.toml", "foundry.toml",
        "Move.toml", "anchor.toml",

        # ── Data / config JSON & YAML (never source code) ──────────────────
        "tsconfig.json", "jsconfig.json",
        ".babelrc", "babel.config.json",
        ".eslintrc", ".eslintrc.json",
        ".stylelintrc",
        ".prettierrc", ".prettierrc.json",
        "NuGet.Config", "nuget.config", "global.json",
        "Directory.Build.props", "Directory.Packages.props",
        ".buckconfig",
        "Chart.yaml", "Chart.lock",
        "lein-profiles.clj", "profiles.clj",
        ".condarc",

        # ── VCS / repo metadata ────────────────────────────────────────────
        ".gitignore", ".gitattributes", ".gitmodules", ".gitkeep",
        ".hgignore", ".svnignore",

        # ── Environment / secrets ─────────────────────────────────────────
        ".env", ".env.local", ".env.development", ".env.production",
        ".env.test", ".env.staging", ".env.example", ".env.sample",

        # ── Editor / IDE metadata ─────────────────────────────────────────
        ".editorconfig", ".dockerignore",

        # ── Documentation / licence (plain text, not code) ───────────────
        "README.md", "README.rst", "README.txt", "README",
        "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt", "CHANGELOG",
        "LICENSE", "LICENSE.md", "LICENSE.txt",
        "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
        "NOTICE", "NOTICE.md", "AUTHORS", "AUTHORS.md",
        "SECURITY.md", "SUPPORT.md",

        # ── CI / CD pipeline definitions ──────────────────────────────────
        ".travis.yml", "appveyor.yml", "circle.yml",
        "bitbucket-pipelines.yml", "azure-pipelines.yml",
        "Procfile",
    }

    # ── Extension-level exclusions for data / config formats ───────────────
    # These extensions are NEVER source code regardless of filename.
    DATA_EXTENSIONS = {
        ".json",    # catches package.json, tsconfig.json, *.json data files, etc.
        ".yaml", ".yml",
        ".toml",
        ".lock",
        ".sum",
        ".log",
        ".csv", ".tsv",
        ".env",
        ".ini", ".cfg", ".conf", ".config",
        ".properties",
        ".xml",     # pom.xml, ivy.xml, AndroidManifest.xml, …
        ".gradle",
        ".map",     # source maps
        ".min.js",  # minified – handled via suffix check below
    }

    # ── Suffix patterns (endswith) for generated / minified files ──────────
    EXCLUDED_SUFFIXES = (
        ".min.js", ".min.css",          # minified bundles
        ".generated.ts", ".generated.cs",
        ".d.ts",                        # TypeScript declaration files
        "-lock.json",                   # any *-lock.json
        ".lock.json",
    )

    excluded: set = set()
    remaining_files: List[str] = []

    for file_path in all_files:
        file_str = str(file_path.as_posix())
        name = file_path.name
        name_lower = name.lower()
        suffix = file_path.suffix.lower()

        # 1. Directory exclusion
        if any(part in EXCLUDED_DIRS for part in file_path.parts):
            excluded.add(file_str)
            continue

        # 2. Binary / media extension
        if suffix in BINARY_EXTENSIONS:
            excluded.add(file_str)
            continue

        # 3. Exact filename (case-sensitive first, then case-insensitive)
        if name in EXCLUDED_EXACT or name_lower in {e.lower() for e in EXCLUDED_EXACT}:
            excluded.add(file_str)
            continue

        # 4. Data / config extension (language-agnostic: JSON, YAML, TOML, etc.)
        if suffix in DATA_EXTENSIONS:
            excluded.add(file_str)
            continue

        # 5. Generated / minified suffix patterns
        if any(name_lower.endswith(sfx) for sfx in EXCLUDED_SUFFIXES):
            excluded.add(file_str)
            continue

        remaining_files.append(file_str)

    logger.info(
        f"Rule-based pre-filter: {len(excluded)} files excluded, "
        f"{len(remaining_files)} remain for further analysis"
    )
    return excluded, remaining_files

_LANGUAGE_MAP: dict[str, str] = {
    # ── Extension → canonical language name ────────────────────────────────
    "ada": "ada",
    "adb": "ada",
    "adoc": "asciidoc",
    "ads": "ada",
    "agda": "agda",
    "al": "al",
    "as": "actionscript",
    "asciidoc": "asciidoc",
    "asm": "asm",
    "astro": "astro",
    "awk": "awk",
    "bash": "bash",
    "bat": "batch",
    "bazel": "starlark",
    "bb": "bitbake",
    "bbappend": "bitbake",
    "bbclass": "bitbake",
    "beancount": "beancount",
    "bib": "bibtex",
    "bicep": "bicep",
    "blade": "blade",
    "brs": "brightscript",
    "bsl": "bsl",
    "bzl": "starlark",
    "c": "c",
    "c3": "c3",
    "c3i": "c3",
    "c3t": "c3",
    "caddyfile": "caddy",
    "cairo": "cairo",
    "capnp": "capnp",
    "cbl": "cobol",
    "cc": "cpp",
    "cedar": "cedar",
    "cedarschema": "cedarschema",
    "cel": "cel",
    "cfc": "cfml",
    "cfg": "ini",
    "chatito": "chatito",
    "circom": "circom",
    "cjs": "javascript",
    "ck": "chuck",
    "cl": "commonlisp",
    "clar": "clarity",
    "clj": "clojure",
    "cljc": "clojure",
    "cljs": "clojure",
    "cls": "abl",
    "cmake": "cmake",
    "cmd": "batch",
    "cob": "cobol",
    "cobol": "cobol",
    "conf": "nginx",
    "cook": "cooklang",
    "corn": "corn",
    "cpon": "cpon",
    "cpp": "cpp",
    "cr": "crystal",
    "cs": "c_sharp",
    "css": "css",
    "csv": "csv",
    "cts": "typescript",
    "cu": "cuda",
    "cuda": "cuda",
    "cue": "cue",
    "cxx": "cpp",
    "cylc": "cylc",
    "d": "d",
    "dart": "dart",
    "desktop": "desktop",
    "dhall": "dhall",
    "diff": "diff",
    "dj": "djot",
    "dockerfile": "dockerfile",
    "dot": "dot",
    "dsp": "faust",
    "dtd": "dtd",
    "dts": "devicetree",
    "dtsi": "devicetree",
    "ebnf": "ebnf",
    "el": "elisp",
    "elm": "elm",
    "elv": "elvish",
    "erb": "embedded_template",
    "erl": "erlang",
    "ex": "elixir",
    "exs": "elixir",
    "f": "fortran",
    "f03": "fortran",
    "f08": "fortran",
    "f90": "fortran",
    "f95": "fortran",
    "fish": "fish",
    "fnl": "fennel",
    "fs": "fsharp",
    "fsi": "fsharp_signature",
    "fsx": "fsharp",
    "gd": "gdscript",
    "gdshader": "gdshader",
    "gemspec": "ruby",
    "gitattributes": "gitattributes",
    "gitignore": "gitignore",
    "gleam": "gleam",
    "glsl": "glsl",
    "go": "go",
    "gotmpl": "gotmpl",
    "gql": "graphql",
    "gradle": "groovy",
    "graphql": "graphql",
    "groovy": "groovy",
    "gv": "dot",
    "h": "c",
    "hack": "hack",
    "hare": "hare",
    "hbs": "glimmer",
    "hcl": "hcl",
    "heex": "heex",
    "hjson": "hjson",
    "hlsl": "hlsl",
    "hocon": "hocon",
    "hpp": "cpp",
    "hrl": "erlang",
    "hs": "haskell",
    "htm": "html",
    "html": "html",
    "http": "http",
    "hurl": "hurl",
    "hx": "haxe",
    "hxx": "cpp",
    "idr": "idris",
    "ini": "ini",
    "ino": "arduino",
    "ispc": "ispc",
    "j2": "jinja2",
    "jai": "jai",
    "janet": "janet",
    "java": "java",
    "jinja2": "jinja2",
    "jl": "julia",
    "journal": "ledger",
    "jq": "jq",
    "js": "javascript",
    "json": "json",
    "json5": "json5",
    "jsonnet": "jsonnet",
    "jsx": "javascript",
    "just": "just",
    "kdl": "kdl",
    "kt": "kotlin",
    "kts": "kotlin",
    "lc": "elsa",
    "ldg": "ledger",
    "lds": "linkerscript",
    "lean": "lean",
    "ledger": "ledger",
    "less": "less",
    "libsonnet": "jsonnet",
    "liquid": "liquid",
    "lisp": "commonlisp",
    "ll": "llvm",
    "lua": "lua",
    "luau": "luau",
    "m": "objc",
    "makefile": "make",
    "markdown": "markdown",
    "matlab": "matlab",
    "md": "markdown",
    "mermaid": "mermaid",
    "meson": "meson",
    "mjs": "javascript",
    "mk": "make",
    "ml": "ocaml",
    "mlir": "mlir",
    "mmd": "mermaid",
    "mod": "gomod",
    "mojo": "mojo",
    "move": "move",
    "mts": "typescript",
    "nasm": "nasm",
    "nginx": "nginx",
    "nim": "nim",
    "nims": "nim",
    "ninja": "ninja",
    "nix": "nix",
    "nu": "nu",
    "p": "abl",
    "pas": "pascal",
    "patch": "diff",
    "php": "php",
    "pl": "perl",
    "pm": "perl",
    "t":"perl",
    "test":"perl",
    "proto": "proto",
    "ps1": "powershell",
    "psd1": "powershell",
    "psm1": "powershell",
    "purs": "purescript",
    "py": "python",
    "pyi": "python",
    "pyw": "python",
    "r": "r",
    "rake": "ruby",
    "rb": "ruby",
    "rbw": "ruby",
    "regex": "regex",
    "rkt": "racket",
    "rmd": "r",
    "rs": "rust",
    "s": "asm",
    "sc": "scala",
    "scala": "scala",
    "scss": "scss",
    "sh": "bash",
    "slint": "slint",
    "sol": "solidity",
    "sparql": "sparql",
    "sql": "sql",
    "star": "starlark",
    "sv": "verilog",
    "svelte": "svelte",
    "swift": "swift",
    "tcl": "tcl",
    "tex": "latex",
    "tf": "terraform",
    "thrift": "thrift",
    "toml": "toml",
    "trigger": "apex",
    "ts": "typescript",
    "tsv": "tsv",
    "tsx": "tsx",
    "ttl": "turtle",
    "typ": "typst",
    "v": "v",
    "vhd": "vhdl",
    "vhdl": "vhdl",
    "vim": "viml",
    "vue": "vue",
    "w": "abl",
    "wgsl": "wgsl",
    "xml": "xml",
    "yaml": "yaml",
    "yml": "yaml",
    "zig": "zig",

    # ── Language name aliases → canonical name ──────────────────────────────
    "ada": "ada",
    "assembly": "asm",
    "bash": "bash",
    "c": "c",
    "c#": "c_sharp",
    "c++": "cpp",
    "clojure": "clojure",
    "cmake": "cmake",
    "cobol": "cobol",
    "common lisp": "commonlisp",
    "cpp": "cpp",
    "crystal": "crystal",
    "csharp": "c_sharp",
    "css": "css",
    "dart": "dart",
    "dockerfile": "dockerfile",
    "elixir": "elixir",
    "elm": "elm",
    "emacs lisp": "elisp",
    "erlang": "erlang",
    "f#": "fsharp",
    "fortran": "fortran",
    "fsharp": "fsharp",
    "gleam": "gleam",
    "go": "go",
    "golang": "go",
    "graphql": "graphql",
    "groovy": "groovy",
    "haskell": "haskell",
    "haxe": "haxe",
    "html": "html",
    "java": "java",
    "javascript": "javascript",
    "json": "json",
    "julia": "julia",
    "kotlin": "kotlin",
    "lua": "lua",
    "make": "make",
    "markdown": "markdown",
    "matlab": "matlab",
    "mojo": "mojo",
    "nim": "nim",
    "nix": "nix",
    "nushell": "nu",
    "objc": "objc",
    "objective-c": "objc",
    "ocaml": "ocaml",
    "pascal": "pascal",
    "perl": "perl",
    "php": "php",
    "powershell": "powershell",
    "protobuf": "proto",
    "purescript": "purescript",
    "python": "python",
    "python3": "python",
    "r": "r",
    "ruby": "ruby",
    "rust": "rust",
    "scala": "scala",
    "scheme": "scheme",
    "scss": "scss",
    "shell": "bash",
    "solidity": "solidity",
    "sql": "sql",
    "starlark": "starlark",
    "svelte": "svelte",
    "swift": "swift",
    "terraform": "hcl",
    "toml": "toml",
    "typescript": "typescript",
    "vimscript": "viml",
    "vue": "vue",
    "xml": "xml",
    "yaml": "yaml",
    "zig": "zig",
}

# Special-case filenames with no extension that map directly to a language
_FILENAME_LANGUAGE_MAP: Dict[str, str] = {
    "makefile": "make",
    "dockerfile": "dockerfile",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "vagrantfile": "ruby",
    "guardfile": "ruby",
    "podfile": "ruby",
    "brewfile": "ruby",
    "pipfile": "toml",
    "jenkinsfile": "groovy",
    "cmakelists.txt": "cmake",
    "build.gradle": "groovy",
    "settings.gradle": "groovy",
    ".bashrc": "bash",
    ".bash_profile": "bash",
    ".zshrc": "bash",
    ".profile": "bash",
    ".zshenv": "bash",
    "requirements.txt": "requirements",
    "go.mod": "go",
    "go.sum": "go",
    "cargo.toml": "toml",
    "cargo.lock": "toml",
    "pyproject.toml": "toml",
    ".gitignore": "gitignore",
    ".gitcommit": "gitcommit",
}

EXACT_FILENAMES = {
        # JavaScript / Node.js
        "package.json", "package-lock.json", "yarn.lock", ".yarnrc.yml",
        ".yarnrc", "pnpm-lock.yaml", ".npmrc", "bower.json", ".bowerrc",
        "lerna.json", "nx.json", "turbo.json", "rush.json",

        # Python
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "requirements-prod.txt", "requirements-base.txt",
        "Pipfile", "Pipfile.lock",
        "pyproject.toml", "setup.py", "setup.cfg",
        "poetry.lock", "constraints.txt", "tox.ini",
        "conda.yml", "conda.yaml", "environment.yml", "environment.yaml",

        # PHP
        "composer.json", "composer.lock",

        # Ruby
        "Gemfile", "Gemfile.lock", "gems.rb", "gems.locked",
        ".ruby-version", "Rakefile", "Podfile", "Podfile.lock",
        "Brewfile", "Brewfile.lock.json",

        # JVM (Java / Kotlin / Scala / Groovy)
        "pom.xml", "build.gradle", "build.gradle.kts",
        "settings.gradle", "settings.gradle.kts",
        "gradle.properties", "gradlew", "gradlew.bat",
        "ivy.xml", "ivysettings.xml",
        "build.sbt", "plugins.sbt", "project/build.properties",
        "build.xml",            # Ant

        # Rust
        "Cargo.toml", "Cargo.lock",

        # Go
        "go.mod", "go.sum", "go.work", "go.work.sum", "Gopkg.toml", "Gopkg.lock",

        # .NET / C# / F# / VB
        "packages.config", "paket.dependencies", "paket.lock",
        "Directory.Build.props", "Directory.Packages.props",
        "NuGet.Config", "nuget.config", "global.json",
        ".config/dotnet-tools.json",

        # C / C++
        "conanfile.txt", "conanfile.py", "conan.lock",
        "vcpkg.json", "vcpkg-configuration.json",
        "CMakeLists.txt", "CMakePresets.json", "CMakeUserPresets.json",
        "configure.ac", "configure.in", "Makefile.am", "Makefile.in",
        "meson.build", "meson_options.txt", "meson.options",
        "xmake.lua",
        "Makefile", "makefile", "GNUmakefile",
        "Jamfile", "Jamroot",

        # Swift / Objective-C (non-CocoaPods)
        "Package.swift", "Package.resolved",
        "Cartfile", "Cartfile.resolved",
        ".swift-version",

        # Dart / Flutter
        "pubspec.yaml", "pubspec.lock", ".dart_tool/package_config.json",

        # Elixir / Erlang
        "mix.exs", "mix.lock", "rebar.config", "rebar.lock",
        "hex.pm", "rebar3.config",

        # Haskell
        "stack.yaml", "stack.yaml.lock", "cabal.project",
        "cabal.project.freeze", "cabal.project.local",

        # OCaml
        "dune-project", "dune-workspace", "opam",
        ".ocamlformat", "esy.json",

        # Perl
        "Makefile.PL", "Build.PL", "cpanfile", "cpanfile.snapshot",
        "META.json", "META.yml", "MYMETA.json", "MYMETA.yml",
        "carton.lock",

        # R
        "DESCRIPTION", "renv.lock", "packrat.lock",
        "NAMESPACE", "renv/settings.dcf",

        # Lua
        "rockspec",             # matched by glob below too

        # Nim
        "*.nimble",             # glob below

        # Julia
        "Project.toml", "Manifest.toml",

        # D
        "dub.json", "dub.sdl",

        # Zig
        "build.zig", "build.zig.zon",

        # Crystal
        "shard.yml", "shard.lock",

        # Clojure
        "project.clj", "deps.edn", "build.clj", "shadow-cljs.edn",
        "lein-profiles.clj", "profiles.clj",

        # Scala (additional)
        "mill",

        # Nix
        "flake.nix", "flake.lock", "default.nix", "shell.nix",
        "nix/sources.json", "nix/sources.nix",

        # Containers / DevOps
        "Dockerfile", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "docker-compose.override.yml", "docker-compose.override.yaml",
        "Containerfile",

        # Infrastructure as Code
        "Vagrantfile",
        "Jenkinsfile",
        "Procfile",
        ".travis.yml", "appveyor.yml",
        "circle.yml",
        "bitbucket-pipelines.yml",
        "azure-pipelines.yml",

        # Terraform / OpenTofu
        ".terraform.lock.hcl",

        # Bazel / Buck / Pants
        "WORKSPACE", "WORKSPACE.bazel", "WORKSPACE.bzlmod",
        "BUILD", "BUILD.bazel",
        "MODULE.bazel", "MODULE.bazel.lock",
        ".buckconfig", "BUCK", "TARGETS",
        "pants.toml", "pants.ini",

        # Frontend tooling
        ".babelrc", "babel.config.js", "babel.config.json",
        "webpack.config.js", "webpack.config.ts",
        "rollup.config.js", "rollup.config.ts", "rollup.config.mjs",
        "vite.config.js", "vite.config.ts", "vite.config.mjs",
        "esbuild.config.js", "esbuild.config.mjs",
        "parcel.config", ".parcelrc",
        "tsconfig.json", "jsconfig.json",

        # Linters / Formatters (often declare peer-deps / plugins)
        ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml",
        ".eslintrc.yaml", "eslint.config.js", "eslint.config.mjs",
        ".stylelintrc", "stylelint.config.js",
        "prettier.config.js", "prettier.config.mjs", ".prettierrc",
        ".prettierrc.json", ".prettierrc.yml",
        "pyproject.toml",   # already listed above; harmless duplicate guard below
        ".flake8", ".pylintrc", "mypy.ini", ".mypy.ini",

        # Ruby CI/CD gems
        ".rubocop.yml",

        # Conda / Mamba
        ".condarc",

        # Misc language-specific
        "psc-package.json",     # PureScript
        "elm.json",             # Elm
        "spago.dhall", "spago.yaml",  # PureScript (spago)
        "hie.yaml",             # Haskell IDE
        "reason-cli",           # ReasonML
        "esy.json",             # ReasonML / OCaml
        "gleam.toml",           # Gleam
        "Scarb.toml",           # Cairo
        "foundry.toml",         # Solidity / Foundry
        "hardhat.config.js", "hardhat.config.ts",  # Solidity / Hardhat
        "truffle-config.js",    # Solidity / Truffle
        "anchor.toml",          # Solana / Anchor
        "Move.toml",            # Move / Aptos / Sui
    }