from pathlib import Path


def test_no_websocket_runtime_code():
    root = Path(__file__).parents[1] / "agent_service" / "app"
    hits = []
    for p in root.rglob("*.py"):
        text = p.read_text(errors="ignore").lower()
        if "websocket" in text or "sockethelper" in text or "web_socket" in text:
            hits.append(str(p))
    assert not hits, f"Legacy websocket code remains: {hits}"


def test_stack_analyzer_wrapper_uses_pinned_executable():
    from app.infrastructure.utils.scanner_engine.run_stack_analyser import STACK_ANALYZER_VERSION
    assert STACK_ANALYZER_VERSION == "1.27.6"


def test_dockerfile_recreates_node_package_manager_launchers():
    dockerfile = (Path(__file__).parents[1] / "agent_service" / "Dockerfile").read_text()
    assert "npm-cli.js" in dockerfile
    assert "npx-cli.js" in dockerfile
    assert "ln -sf" in dockerfile
    assert "COPY --from=node_runtime /usr/local/bin/npm" not in dockerfile
    assert "COPY --from=node_runtime /usr/local/bin/npx" not in dockerfile

