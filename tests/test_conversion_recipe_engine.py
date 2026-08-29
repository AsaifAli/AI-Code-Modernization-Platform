from app.infrastructure.utils.conversion_recipe_engine import RecipeContext, build_conversion_rules, sanitize_generated_code, validate_target_fragment

def test_sanitize_generated_code():
    raw="\ufeff```python\n\ndef add(a,b):   \n    return a+b   \n\n```\n"
    assert sanitize_generated_code(raw)=="def add(a,b):\n    return a+b\n"

def test_rules():
    rules=build_conversion_rules(RecipeContext("python","typescript","nextjs","layered"))
    assert "TARGET LANGUAGE: typescript" in rules
    assert "do not invent packages" in rules

def test_python_validation():
    assert validate_target_fragment("def add(a,b):\n    return a+b\n","python").valid
    bad=validate_target_fragment("def add(a,b):\nreturn a+b\n","python")
    assert not bad.valid and bad.validator=="python-ast"
