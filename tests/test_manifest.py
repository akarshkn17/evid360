from evidence_engine.artifacts.manifest import build_manifest


def test_build_manifest() -> None:
    manifest = build_manifest(
        run_id="run-123",
        connector="jira",
        timestamp="2026-04-20T00:00:00+00:00",
        query="project = IT",
        artifact_files=["evidence.json", "manifest.json"],
        record_count=2,
        storage_backend="local",
        hashes={"evidence.json": "abc"},
    )

    assert manifest.run_id == "run-123"
    assert manifest.hash_algorithm == "sha256"
    assert manifest.hashes["evidence.json"] == "abc"

