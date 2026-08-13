def test_repair_loop_revalidates_semantics_after_edit(monkeypatch, tmp_path):
    import app.infrastructure.utils.Agent_helpers.post_migration_helper as helper

    calls = {"quality": 0, "semantic": 0, "repair": 0}

    class Ctx:
        def get(self, default=""):
            return default

    monkeypatch.setattr(helper, "get_migration_directory", lambda **_: tmp_path)
    migrated = tmp_path / "Migrated Code"
    migrated.mkdir()
    monkeypatch.setattr(helper, "normalize_imports_in_tree", lambda _: {})
    monkeypatch.setattr(helper, "build_dependency_topology_report", lambda *a, **k: {"status": "not_available"})
    monkeypatch.setattr(helper, "security_scan", lambda *a, **k: {"status": "passed"})
    monkeypatch.setattr(helper, "provenance_manifest", lambda *a, **k: {})
    monkeypatch.setattr(helper, "traceability_matrix", lambda *a, **k: {})
    monkeypatch.setattr(helper, "analyze_migrated_architecture", lambda *a, **k: {})
    monkeypatch.setattr(helper, "generate_migration_comparison_report", lambda *a, **k: {})
    monkeypatch.setattr(helper, "generate_showcase_bundle", lambda *a, **k: {})
    monkeypatch.setattr(helper, "publish_progress", lambda *a, **k: None)
    monkeypatch.setattr(helper, "source_path_ctx", Ctx())

    def semantic(*args, **kwargs):
        calls["semantic"] += 1
        if calls["semantic"] == 1:
            return {"status": "partial", "contract": {"coverage_percent": 70}, "execution": {"status": "failed"}, "behavioral_probes": {"status": "failed"}}
        return {"status": "verified", "contract": {"coverage_percent": 100}, "execution": {"status": "passed"}, "behavioral_probes": {"status": "passed"}}

    monkeypatch.setattr(helper, "verify_migration_semantics", semantic)

    def quality(*args, **kwargs):
        calls["quality"] += 1
        return {"status": "passed", "release_ready": True, "target_stack": {"stack": "node"}, "checks": []}

    monkeypatch.setattr(helper, "validate_migrated_project", quality)

    def repair(*args, **kwargs):
        calls["repair"] += 1
        return {"status": "completed", "attempt": kwargs.get("attempt", 1)}

    monkeypatch.setattr(helper, "_repair_with_agno", repair)

    result = helper.run_post_migration_pipeline("smoke")
    assert result["status"] == "ready"
    assert calls["repair"] == 1
    assert calls["semantic"] == 2
    assert calls["quality"] == 2
