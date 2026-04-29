from pathlib import Path

from evidence_engine.config import AppConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.engine import EvidenceEngine
from evidence_engine.models import BaseEvidenceRecord, CollectionResult, EvidenceRequest, RunContext, StorageBackendType
from evidence_engine.services.registry import ConnectorRegistry
from evidence_engine.storage.base import BaseStorageBackend


class FakeCollector(BaseCollector):
    name = "fake"

    def collect(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        record = BaseEvidenceRecord(
            evidence_id="REC-1",
            source_system="fake",
            record_type="record",
            title="Example",
            status="open",
            created_at="2026-04-20T00:00:00+00:00",
            updated_at="2026-04-20T00:00:00+00:00",
            owner="owner",
            tags=["sample"],
            raw_ref="REC-1",
            collected_at=run_context.started_at_iso,
            attributes={"category": "demo"},
        )
        return CollectionResult(
            records=[record],
            source_metadata={"query": request.query},
            raw_records=[{"id": "REC-1"}],
            csv_attribute_fields=["category"],
        )


class FakeRegistry(ConnectorRegistry):
    def __init__(self) -> None:
        pass

    def get(self, name: str) -> BaseCollector:
        return FakeCollector()


class FakeStorage(BaseStorageBackend):
    name = "local"

    def store(self, artifact_root_dir: Path, artifact_paths: dict[str, Path], storage_prefix: str) -> dict[str, str]:
        return {name: str(path) for name, path in artifact_paths.items()}


def test_engine_run_writes_artifacts(tmp_path: Path) -> None:
    config = AppConfig(local_artifact_root=tmp_path)
    engine = EvidenceEngine(
        config=config,
        registry=FakeRegistry(),
        storage_factory=lambda storage_backend: FakeStorage(),
    )
    request = EvidenceRequest(
        connector="fake",
        query="collect demo evidence",
        output_formats=["json", "csv"],
        storage_backend=StorageBackendType.LOCAL,
        metadata={"request_id": "IDR-Req-001"},
    )

    result = engine.run(request)

    assert result.record_count == 1
    assert "evidence.json" in result.artifact_paths
    assert "evidence.csv" in result.artifact_paths
    assert "manifest.json" in result.artifact_paths
    assert Path(result.artifact_paths["manifest.json"]).exists()
    assert "IDR-Req-001" in result.artifact_root_dir


def test_engine_run_uses_ad_hoc_root_when_request_id_missing(tmp_path: Path) -> None:
    config = AppConfig(local_artifact_root=tmp_path)
    engine = EvidenceEngine(
        config=config,
        registry=FakeRegistry(),
        storage_factory=lambda storage_backend: FakeStorage(),
    )
    request = EvidenceRequest(
        connector="fake",
        query="collect demo evidence",
        output_formats=["json"],
        storage_backend=StorageBackendType.LOCAL,
    )

    result = engine.run(request)

    assert "ad-hoc" in result.artifact_root_dir
