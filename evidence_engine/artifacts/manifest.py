from __future__ import annotations

from evidence_engine.models import RunManifest


def build_manifest(
    *,
    run_id: str,
    connector: str,
    timestamp: str,
    query: str,
    artifact_files: list[str],
    record_count: int,
    storage_backend: str,
    hashes: dict[str, str],
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        connector=connector,
        timestamp=timestamp,
        query=query,
        artifact_files=artifact_files,
        record_count=record_count,
        storage_backend=storage_backend,
        hash_algorithm="sha256",
        hashes=hashes,
    )

