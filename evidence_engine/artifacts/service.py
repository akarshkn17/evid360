from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re

from evidence_engine.artifacts.hashing import sha256_file
from evidence_engine.artifacts.manifest import build_manifest
from evidence_engine.artifacts.writer import write_csv_artifact, write_json_artifact
from evidence_engine.models import CollectionResult, EvidenceRequest, OutputFormat, RunContext


LogEvent = Callable[[str, RunContext, str], None]


@dataclass(frozen=True)
class ArtifactWriteResult:
    artifact_root_dir: Path
    artifact_dir: Path
    artifact_paths: dict[str, Path]
    hashes: dict[str, str]
    storage_prefix: str


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
        artifact_subdir: str | None = None,
    ) -> ArtifactWriteResult:
        artifact_root_dir, storage_prefix = self._build_artifact_root(request, run_context)
        artifact_dir = artifact_root_dir / artifact_subdir if artifact_subdir else artifact_root_dir
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths: dict[str, Path] = {}
        hashes: dict[str, str] = {}
        manifest_metadata = _manifest_metadata(request, artifact_subdir)

        evidence_path = artifact_dir / "evidence.json"
        log_event("artifact_write_start", run_context, request.connector, artifact=evidence_path.name)
        write_json_artifact(evidence_path, _evidence_payload(request, run_context, collection_result))
        evidence_key = _relative_key(artifact_root_dir, evidence_path)
        artifact_paths[evidence_key] = evidence_path
        hashes[evidence_key] = sha256_file(evidence_path)
        log_event("hash_generated", run_context, request.connector, artifact=evidence_path.name)

        if OutputFormat.CSV in request.output_formats:
            csv_path = artifact_dir / "evidence.csv"
            log_event("artifact_write_start", run_context, request.connector, artifact=csv_path.name)
            write_csv_artifact(csv_path, collection_result.records, collection_result.csv_attribute_fields)
            csv_key = _relative_key(artifact_root_dir, csv_path)
            artifact_paths[csv_key] = csv_path
            hashes[csv_key] = sha256_file(csv_path)
            log_event("hash_generated", run_context, request.connector, artifact=csv_path.name)

        hashes_path = artifact_dir / "hashes.json"
        log_event("artifact_write_start", run_context, request.connector, artifact=hashes_path.name)
        write_json_artifact(hashes_path, {"algorithm": "sha256", "hashes": hashes})
        hashes_key = _relative_key(artifact_root_dir, hashes_path)
        artifact_paths[hashes_key] = hashes_path
        hashes[hashes_key] = sha256_file(hashes_path)
        log_event("hash_generated", run_context, request.connector, artifact=hashes_path.name)

        manifest = build_manifest(
            run_id=run_context.run_id,
            connector=request.connector,
            timestamp=run_context.started_at_iso,
            query=request.query,
            artifact_files=list(artifact_paths.keys()) + [_relative_key(artifact_root_dir, artifact_dir / "manifest.json")],
            record_count=len(collection_result.records),
            storage_backend=request.storage_backend.value,
            hashes=hashes,
            metadata=manifest_metadata,
        )
        manifest_path = artifact_dir / "manifest.json"
        log_event("artifact_write_start", run_context, request.connector, artifact=manifest_path.name)
        write_json_artifact(manifest_path, manifest.model_dump(mode="json"))
        manifest_key = _relative_key(artifact_root_dir, manifest_path)
        artifact_paths[manifest_key] = manifest_path
        hashes[manifest_key] = sha256_file(manifest_path)
        log_event("hash_generated", run_context, request.connector, artifact=manifest_path.name)

        return ArtifactWriteResult(
            artifact_root_dir=artifact_root_dir,
            artifact_dir=artifact_dir,
            artifact_paths=artifact_paths,
            hashes=hashes,
            storage_prefix=storage_prefix,
        )

    def _build_artifact_root(self, request: EvidenceRequest, run_context: RunContext) -> tuple[Path, str]:
        root = Path(request.output_dir) if request.output_dir else self._artifact_root
        request_root = _sanitize_path_component(_request_root_name(request))
        parts = [
            request_root,
            request.connector,
            f"{run_context.started_at.year:04d}",
            f"{run_context.started_at.month:02d}",
            f"{run_context.started_at.day:02d}",
            run_context.run_id,
        ]
        return root.joinpath(*parts), "/".join(parts)


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


def _request_root_name(request: EvidenceRequest) -> str:
    request_id = request.metadata.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    return "ad-hoc"


def _sanitize_path_component(value: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]+', "-", value).strip()
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or "unknown"


def _relative_key(root_dir: Path, path: Path) -> str:
    return path.relative_to(root_dir).as_posix()


def _manifest_metadata(request: EvidenceRequest, artifact_subdir: str | None) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in ("request_id", "control_id", "control_name", "operation", "scope_name", "scope_query"):
        value = request.metadata.get(key)
        if value is not None:
            metadata[key] = value
    if artifact_subdir:
        metadata["artifact_subdir"] = artifact_subdir
    return metadata
