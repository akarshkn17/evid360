from __future__ import annotations

from pathlib import Path

from evidence_engine.config import BucketStorageConfig
from evidence_engine.exceptions import StorageError
from evidence_engine.storage.base import BaseStorageBackend


class BucketStorageBackend(BaseStorageBackend):
    name = "bucket"

    def __init__(self, config: BucketStorageConfig) -> None:
        self._config = config
        try:
            from google.cloud import storage
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment setup
            raise StorageError(
                "google-cloud-storage is not installed. Run `uv sync` before using the bucket backend."
            ) from exc
        self._client = storage.Client()

    def store(self, connector: str, run_id: str, artifact_dir: Path, artifact_paths: dict[str, Path]) -> dict[str, str]:
        bucket = self._client.bucket(self._config.bucket_name)
        stored_locations: dict[str, str] = {}
        prefix = f"{connector}/{run_id}"
        try:
            for name, path in artifact_paths.items():
                blob_name = f"{prefix}/{path.name}"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(str(path))
                stored_locations[name] = f"gs://{self._config.bucket_name}/{blob_name}"
        except Exception as exc:  # pragma: no cover - network and SDK failures are environment specific
            raise StorageError(f"Failed to upload artifacts to bucket {self._config.bucket_name}: {exc}") from exc
        return stored_locations
