from __future__ import annotations

from pathlib import Path

from evidence_engine.storage.base import BaseStorageBackend


class LocalStorageBackend(BaseStorageBackend):
    name = "local"

    def store(self, artifact_root_dir: Path, artifact_paths: dict[str, Path], storage_prefix: str) -> dict[str, str]:
        return {name: str(path.resolve()) for name, path in artifact_paths.items()}
