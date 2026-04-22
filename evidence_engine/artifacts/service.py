from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from evidence_engine.artifacts.hashing import sha256_file
from evidence_engine.artifacts.manifest import build_manifest
from evidence_engine.artifacts.writer import write_csv_artifact, write_json_artifact
from evidence_engine.models import CollectionResult, EvidenceRequest, OutputFormat, RunContext


LogEvent = Callable[[str, RunContext, str], None]


@dataclass(frozen=True)
class ArtifactWriteResult:
    artifact_dir: Path
    artifact_paths: dict[str, Path]
    hashes: dict[str, str]


class ArtifactService:
    def __init__(self, artifact_root: Path) -> None:
        self._artifact_root = artifact_root

    def write_all(
        self,
        *,
        request: EvidenceRequest,
        run_context: RunContext,
        collection_result: CollectionResult,
        log_event: Callable[..., None],
    ) -> ArtifactWriteResult:
        artifact_dir = self._build_artifact_dir(request.connector, run_context, request.output_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths: dict[str, Path] = {}
        hashes: dict[str, str] = {}

        evidence_path = artifact_dir / "evidence.json"
        log_event("artifact_write_start", run_context, request.connector, artifact=evidence_path.name)
        write_json_artifact(evidence_path, _evidence_payload(request, run_context, collection_result))
        artifact_paths["evidence.json"] = evidence_path
        hashes["evidence.json"] = sha256_file(evidence_path)
        log_event("hash_generated", run_context, request.connector, artifact=evidence_path.name)

        if OutputFormat.CSV in request.output_formats:
            csv_path = artifact_dir / "evidence.csv"
            log_event("artifact_write_start", run_context, request.connector, artifact=csv_path.name)
            write_csv_artifact(csv_path, collection_result.records, collection_result.csv_attribute_fields)
            artifact_paths["evidence.csv"] = csv_path
            hashes["evidence.csv"] = sha256_file(csv_path)
            log_event("hash_generated", run_context, request.connector, artifact=csv_path.name)

        hashes_path = artifact_dir / "hashes.json"
        log_event("artifact_write_start", run_context, request.connector, artifact=hashes_path.name)
        write_json_artifact(hashes_path, {"algorithm": "sha256", "hashes": hashes})
        artifact_paths["hashes.json"] = hashes_path
        hashes["hashes.json"] = sha256_file(hashes_path)
        log_event("hash_generated", run_context, request.connector, artifact=hashes_path.name)

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
        log_event("artifact_write_start", run_context, request.connector, artifact=manifest_path.name)
        write_json_artifact(manifest_path, manifest.model_dump(mode="json"))
        artifact_paths["manifest.json"] = manifest_path
        hashes["manifest.json"] = sha256_file(manifest_path)
        log_event("hash_generated", run_context, request.connector, artifact=manifest_path.name)

        return ArtifactWriteResult(artifact_dir=artifact_dir, artifact_paths=artifact_paths, hashes=hashes)

    def _build_artifact_dir(self, connector: str, run_context: RunContext, output_dir: str | None) -> Path:
        root = Path(output_dir) if output_dir else self._artifact_root
        return (
            root
            / connector
            / f"{run_context.started_at.year:04d}"
            / f"{run_context.started_at.month:02d}"
            / f"{run_context.started_at.day:02d}"
            / run_context.run_id
        )


def _evidence_payload(
    request: EvidenceRequest,
    run_context: RunContext,
    collection_result: CollectionResult,
) -> dict[str, object]:
    return {
        "request": request.model_dump(mode="json"),
        "run": {"run_id": run_context.run_id, "started_at": run_context.started_at_iso},
        "records": [record.model_dump(mode="json") for record in collection_result.records],
        "source_metadata": collection_result.source_metadata,
        "raw_records": collection_result.raw_records,
    }
