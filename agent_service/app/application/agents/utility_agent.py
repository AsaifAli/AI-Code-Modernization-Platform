# app/application/agents/utility_agent.py
import json
import logging
import re
from textwrap import dedent
from typing import Any, Dict

from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model
from app.infrastructure.utils.token_tracker import track_tokens
from app.infrastructure.utils.Constants.app_constants import AgentConstants

logger = logging.getLogger(__name__)

utility_agent = Agent(
    name="Utility Agent",
    model=model,
    markdown=False,
    description="Utility agent that can perform simple tasks",
    instructions="Follow task instructions exactly.",
    use_json_mode=True,
)

_STACK_DETECTION_PROMPT = dedent("""
You are a migration and project analysis assistant.
Given a free-form user description, extract the target technology stack.

Return ONLY a valid JSON object with exactly these keys:

{
  "target_language": "string",
  "target_framework": "string",
  "target_architecture": "string",
  "is_frontend": true or false,
  "target_frontend": "string",
  "target_frontend_architecture": "string",
  "execution_mode": "string",
  "unit_test_framework": "string"
}

Field rules:

target_language:
  - The backend/primary programming language to migrate TO.
  - Examples: python, javascript, typescript, java, c#, go, php, ruby, rust, c++
  - If not specified, use "python".

target_framework:
  - The framework or library that is the primary target of the task.
  - IMPORTANT: Read the description carefully — the framework may be explicitly named.
  - Testing/automation frameworks are valid: playwright, pytest, jest, google test, gtest, selenium, cypress, mocha
  - Backend frameworks: fastapi, django, flask, express, nestjs, spring boot, laravel, gin
  - Do NOT default to fastapi or express if another framework is mentioned.
  - If description mentions "playwright" → target_framework = "playwright"
  - If description mentions "google test" or "gtest" → target_framework = "google test"
  - If description mentions "pytest" → target_framework = "pytest"
  - If no framework is detectable, use "fastapi" for python or "express" for javascript.

target_architecture:
  - Software architecture pattern: layered, hexagonal, microservices, clean architecture, mvc
  - Default: "layered"

is_frontend:
  - true if the task involves frontend migration, frontend code generation, or both backend and frontend.
  - If description mentions react, vue, angular, svelte, nextjs, nuxt → is_frontend = true
  - Default: false

target_frontend:
  - Frontend framework/library: react, vue, angular, svelte, nextjs, nuxt
  - Only set if is_frontend is true. Otherwise empty string.

target_frontend_architecture:
  - Frontend architecture: component-based, micro-frontend, layered
  - Default: "layered"

execution_mode:
  - "unit_test_generation" if the task is about generating unit tests (keywords: unit test, generate tests, test cases, google test, pytest, jest, mocha)
  - "code_migration" for all other migration and conversion tasks
  - Default: "code_migration"

unit_test_framework:
  - The test framework when execution_mode is unit_test_generation.
  - Examples: google test, pytest, jest, mocha, junit
  - Empty string if not a test generation task.

Examples:

Description: "Migrate my perl selenium to playwright python"
Result:
{
  "target_language": "python",
  "target_framework": "playwright",
  "target_architecture": "layered",
  "is_frontend": false,
  "target_frontend": "",
  "target_frontend_architecture": "layered",
  "execution_mode": "code_migration",
  "unit_test_framework": ""
}

Description: "Generate Google Test Unit Test cases of my c++ application"
Result:
{
  "target_language": "c++",
  "target_framework": "google test",
  "target_architecture": "layered",
  "is_frontend": false,
  "target_frontend": "",
  "target_frontend_architecture": "layered",
  "execution_mode": "unit_test_generation",
  "unit_test_framework": "google test"
}

Description: "Migrate my perl cgi application to python and react"
Result:
{
  "target_language": "python",
  "target_framework": "fastapi",
  "target_architecture": "layered",
  "is_frontend": true,
  "target_frontend": "react",
  "target_frontend_architecture": "layered",
  "execution_mode": "code_migration",
  "unit_test_framework": ""
}

Description: "Convert my Java monolith to Python microservices using FastAPI"
Result:
{
  "target_language": "python",
  "target_framework": "fastapi",
  "target_architecture": "microservices",
  "is_frontend": false,
  "target_frontend": "",
  "target_frontend_architecture": "layered",
  "execution_mode": "code_migration",
  "unit_test_framework": ""
}

Description: "Generate pytest unit tests for my Django application"
Result:
{
  "target_language": "python",
  "target_framework": "pytest",
  "target_architecture": "layered",
  "is_frontend": false,
  "target_frontend": "",
  "target_frontend_architecture": "layered",
  "execution_mode": "unit_test_generation",
  "unit_test_framework": "pytest"
}

Now extract from the following description:
""").strip()

_FALLBACK_STACK: Dict[str, Any] = {
    "target_language": "python",
    "target_framework": "fastapi",
    "target_architecture": "layered",
    "is_frontend": False,
    "target_frontend": "",
    "target_frontend_architecture": "layered",
    "execution_mode": "code_migration",
    "unit_test_framework": "",
}


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _apply_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply safety defaults to any missing or empty fields from LLM response."""
    def _str(val) -> str:
        return str(val).strip().lower() if val else ""

    def _bool(val) -> bool:
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in {"true", "1", "yes"}

    target_language = _str(payload.get("target_language")) or _FALLBACK_STACK["target_language"]
    target_framework = _str(payload.get("target_framework")) or (
        "fastapi" if target_language == "python" else _FALLBACK_STACK["target_framework"]
    )
    target_architecture = _str(payload.get("target_architecture")) or _FALLBACK_STACK["target_architecture"]
    is_frontend = _bool(payload.get("is_frontend", False))
    target_frontend = _str(payload.get("target_frontend")) or ("react" if is_frontend else "")
    target_frontend_architecture = _str(payload.get("target_frontend_architecture")) or _FALLBACK_STACK["target_frontend_architecture"]
    execution_mode = _str(payload.get("execution_mode")) or _FALLBACK_STACK["execution_mode"]
    unit_test_framework = _str(payload.get("unit_test_framework")) or ""

    return {
        "target_language": target_language,
        "target_framework": target_framework,
        "target_architecture": target_architecture,
        "is_frontend": is_frontend,
        "target_frontend": target_frontend,
        "target_frontend_architecture": target_frontend_architecture,
        "execution_mode": execution_mode,
        "unit_test_framework": unit_test_framework,
    }




def _deterministic_target_hints(description: str) -> Dict[str, Any]:
    """Extract explicit target-language/framework hints before invoking an LLM.

    This prevents a provider failure from silently changing an explicit request
    such as "convert Python to Java" into the default Python target.
    """
    text = str(description or "").strip().lower()
    hints: Dict[str, Any] = {}

    language_aliases = {
        "python": "python", "py": "python", "javascript": "javascript",
        "js": "javascript", "typescript": "typescript", "ts": "typescript",
        "java": "java", "c#": "c#", "csharp": "c#", "go": "go",
        "golang": "go", "php": "php", "ruby": "ruby", "rust": "rust",
        "c++": "c++", "cpp": "c++",
    }
    m = re.search(r"\b(?:to|into|target)\s+(python|py|javascript|js|typescript|ts|java|c#|csharp|go|golang|php|ruby|rust|c\+\+)\b", text)
    if m:
        hints["target_language"] = language_aliases[m.group(1)]

    framework_aliases = (
        "spring boot", "fastapi", "django", "flask", "express", "nestjs",
        "laravel", "gin", "playwright", "pytest", "jest", "mocha", "google test", "gtest",
    )
    for framework in framework_aliases:
        if framework in text:
            hints["target_framework"] = framework
            break

    return hints

def detect_target_stack_from_description(description: str) -> Dict[str, Any]:
    """
    Infer migration target stack from free-form description using the LLM.
    Falls back to python / fastapi / layered if the LLM call fails or returns empty.
    """
    if not description or not str(description).strip():
        return dict(_FALLBACK_STACK)

    deterministic_hints = _deterministic_target_hints(description)

    original_instructions = getattr(utility_agent, "instructions", None)
    try:
        utility_agent.instructions = "Return ONLY valid JSON. No prose, no markdown fences."
        utility_agent.output_schema = None

        prompt = f"{_STACK_DETECTION_PROMPT}\n\n{description.strip()}"
        response = utility_agent.run(input=prompt)
        track_tokens(response, source="stack_detection", prompt_name="detect_target_stack")
        raw = getattr(response, "content", "") or ""
        payload = _extract_first_json_object(raw)

        if not payload:
            logger.warning("LLM returned no parseable JSON for stack detection; using deterministic hints/defaults.")
            merged = dict(_FALLBACK_STACK)
            merged.update(deterministic_hints)
            return _apply_defaults(merged)

        payload.update(deterministic_hints)
        return _apply_defaults(payload)

    except Exception as exc:
        logger.warning("Stack detection LLM call failed (%s); using deterministic hints/defaults.", exc)
        merged = dict(_FALLBACK_STACK)
        merged.update(deterministic_hints)
        return _apply_defaults(merged)
    finally:
        if original_instructions is not None:
            utility_agent.instructions = original_instructions
