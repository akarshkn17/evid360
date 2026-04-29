from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from evidence_engine.artifacts.service import ArtifactService
from evidence_engine.config import AppConfig, BucketStorageConfig
from evidence_engine.logging_config import configure_logging
from evidence_engine.models import EvidenceRequest, EvidenceRunResult, RunContext, StorageBackendType
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
        self._artifact_service = ArtifactService(self._config.local_artifact_root)

    def run(
        self,
        request: EvidenceRequest,
        *,
        run_context: RunContext | None = None,
        artifact_subdir: str | None = None,
        upload: bool = True,
    ) -> EvidenceRunResult:
        run_context = run_context or RunContext()
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

        artifact_result = self._artifact_service.write_all(
            request=request,
            run_context=run_context,
            collection_result=collection_result,
            log_event=self._log,
            artifact_subdir=artifact_subdir,
        )

        storage_backend = self._storage_factory(request.storage_backend) if upload else LocalStorageBackend()
        self._log("storage_start", run_context, request.connector, storage_backend=storage_backend.name)
        storage_locations = storage_backend.store(
            artifact_result.artifact_root_dir,
            artifact_result.artifact_paths,
            artifact_result.storage_prefix,
        )
        self._log("storage_complete", run_context, request.connector, stored_artifact_count=len(storage_locations))

        completed_at = datetime.now(UTC).isoformat()
        self._log(
            "engine_complete",
            run_context,
            request.connector,
            record_count=len(collection_result.records),
            artifact_dir=str(artifact_result.artifact_root_dir.resolve()),
            completed_at=completed_at,
        )
        return EvidenceRunResult(
            run_id=run_context.run_id,
            connector=request.connector,
            started_at=run_context.started_at_iso,
            completed_at=completed_at,
            record_count=len(collection_result.records),
            storage_backend=storage_backend.name,
            artifact_root_dir=str(artifact_result.artifact_root_dir.resolve()),
            artifact_dir=str(artifact_result.artifact_dir.resolve()),
            artifact_paths={name: str(path.resolve()) for name, path in artifact_result.artifact_paths.items()},
            storage_locations=storage_locations,
            hashes=artifact_result.hashes,
            metadata={
                "request_id": request.metadata.get("request_id"),
                "control_id": request.metadata.get("control_id"),
                "operation": request.metadata.get("operation"),
                "scope_name": request.metadata.get("scope_name"),
                "scope_query": request.metadata.get("scope_query"),
                "storage_prefix": artifact_result.storage_prefix,
                "artifact_subdir": artifact_subdir,
            },
        )

    def _default_storage_factory(self, storage_backend: StorageBackendType) -> BaseStorageBackend:
        if storage_backend == StorageBackendType.LOCAL:
            return LocalStorageBackend()
        return BucketStorageBackend(BucketStorageConfig.from_env())

    def _log(self, message: str, run_context: RunContext, connector: str, **fields: object) -> None:
        self._logger.info(message, extra={"run_id": run_context.run_id, "connector": connector, **fields})
