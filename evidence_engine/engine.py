from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from evidence_engine.artifacts.hashing import sha256_file
from evidence_engine.artifacts.manifest import build_manifest
from evidence_engine.artifacts.writer import write_csv_artifact, write_json_artifact
from evidence_engine.config import AppConfig, BucketStorageConfig
from evidence_engine.logging_config import configure_logging
from evidence_engine.models import CollectionResult, EvidenceRequest, EvidenceRunResult, OutputFormat, RunContext, StorageBackendType
from evidence_engine.services.registry import ConnectorRegistry
from evidence_engine.storage.base import BaseStorageBackend
from evidence_engine.storage.bucket import BucketStorageBackend
from evidence_engine.storage.local import LocalStorageBackend


class EvidenceEngine:
    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        registry: ConnectorRegistry | None = None,
        storage_factory: Callable[[StorageBackendType], BaseStorageBackend] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config or AppConfig.from_env()
        configure_logging(self._config.log_level)
        self._logger = logger or logging.getLogger("evidence_engine")
        self._registry = registry or ConnectorRegistry(self._config)
        self._storage_factory = storage_factory or self._default_storage_factory

    def run(self, request: EvidenceRequest) -> EvidenceRunResult:
        run_context = RunContext()
        self._log(
            "engine_start",
            run_context,
            request.connector,
            query=request.query,
            storage_backend=request.storage_backend.value,
        )

        collector = self._registry.get(request.connector)
        self._log("collector_selected", run_context, request.connector)

        collection_result = collector.collect(request, run_context)
        self._log("fetch_complete", run_context, request.connector, record_count=len(collection_result.records))

        artifact_dir = self._build_artifact_dir(request.connector, run_context, request.output_dir)
        artifact_paths, hashes = self._write_artifacts(
            artifact_dir=artifact_dir,
            request=request,
            run_context=run_context,
            collection_result=collection_result,
        )

        storage_backend = self._storage_factory(request.storage_backend)
        self._log("storage_start", run_context, request.connector, storage_backend=storage_backend.name)
        storage_locations = storage_backend.store(request.connector, run_context.run_id, artifact_dir, artifact_paths)
        self._log("storage_complete", run_context, request.connector, stored_artifact_count=len(storage_locations))

        completed_at = datetime.now(UTC).isoformat()
        self._log(
            "engine_complete",
            run_context,
            request.connector,
            record_count=len(collection_result.records),
            artifact_dir=str(artifact_dir.resolve()),
            completed_at=completed_at,
        )
        return EvidenceRunResult(
            run_id=run_context.run_id,
            connector=request.connector,
            started_at=run_context.started_at_iso,
            completed_at=completed_at,
            record_count=len(collection_result.records),
            storage_backend=storage_backend.name,
            artifact_dir=str(artifact_dir.resolve()),
            artifact_paths={name: str(path.resolve()) for name, path in artifact_paths.items()},
            storage_locations=storage_locations,
            hashes=hashes,
        )

    def _write_artifacts(
        self,
        *,
        artifact_dir: Path,
        request: EvidenceRequest,
        run_context: RunContext,
        collection_result: CollectionResult,
    ) -> tuple[dict[str, Path], dict[str, str]]:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths: dict[str, Path] = {}
        hashes: dict[str, str] = {}

        evidence_path = artifact_dir / "evidence.json"
        self._log("artifact_write_start", run_context, request.connector, artifact=evidence_path.name)
        evidence_payload = {
            "request": request.model_dump(mode="json"),
            "run": {"run_id": run_context.run_id, "started_at": run_context.started_at_iso},
            "records": [record.model_dump(mode="json") for record in collection_result.records],
            "source_metadata": collection_result.source_metadata,
            "raw_records": collection_result.raw_records,
        }
        write_json_artifact(evidence_path, evidence_payload)
        artifact_paths["evidence.json"] = evidence_path
        hashes["evidence.json"] = sha256_file(evidence_path)
        self._log("hash_generated", run_context, request.connector, artifact=evidence_path.name)

        if OutputFormat.CSV in request.output_formats:
            csv_path = artifact_dir / "evidence.csv"
            self._log("artifact_write_start", run_context, request.connector, artifact=csv_path.name)
            write_csv_artifact(csv_path, collection_result.records, collection_result.csv_attribute_fields)
            artifact_paths["evidence.csv"] = csv_path
            hashes["evidence.csv"] = sha256_file(csv_path)
            self._log("hash_generated", run_context, request.connector, artifact=csv_path.name)

        hashes_path = artifact_dir / "hashes.json"
        self._log("artifact_write_start", run_context, request.connector, artifact=hashes_path.name)
        write_json_artifact(hashes_path, {"algorithm": "sha256", "hashes": hashes})
        artifact_paths["hashes.json"] = hashes_path
        hashes["hashes.json"] = sha256_file(hashes_path)
        self._log("hash_generated", run_context, request.connector, artifact=hashes_path.name)

        manifest = build_manifest(
            run_id=run_context.run_id,
            connector=request.connector,
            timestamp=run_context.started_at_iso,
            query=request.query,
            artifact_files=list(artifact_paths.keys()) + ["manifest.json"],
            record_count=len(collection_result.records),
            storage_backend=request.storage_backend.value,
            hashes=hashes,
        )
        manifest_path = artifact_dir / "manifest.json"
        self._log("artifact_write_start", run_context, request.connector, artifact=manifest_path.name)
        write_json_artifact(manifest_path, manifest.model_dump(mode="json"))
        artifact_paths["manifest.json"] = manifest_path
        hashes["manifest.json"] = sha256_file(manifest_path)
        self._log("hash_generated", run_context, request.connector, artifact=manifest_path.name)

        return artifact_paths, hashes

    def _build_artifact_dir(self, connector: str, run_context: RunContext, output_dir: str | None) -> Path:
        root = Path(output_dir) if output_dir else self._config.local_artifact_root
        return (
            root
            / connector
            / f"{run_context.started_at.year:04d}"
            / f"{run_context.started_at.month:02d}"
            / f"{run_context.started_at.day:02d}"
            / run_context.run_id
        )

    def _default_storage_factory(self, storage_backend: StorageBackendType) -> BaseStorageBackend:
        if storage_backend == StorageBackendType.LOCAL:
            return LocalStorageBackend()
        return BucketStorageBackend(BucketStorageConfig.from_env())

    def _log(self, message: str, run_context: RunContext, connector: str, **fields: object) -> None:
        self._logger.info(message, extra={"run_id": run_context.run_id, "connector": connector, **fields})
