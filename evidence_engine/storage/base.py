from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseStorageBackend(ABC):
    name: str

    @abstractmethod
    def store(self, artifact_root_dir: Path, artifact_paths: dict[str, Path], storage_prefix: str) -> dict[str, str]:
        raise NotImplementedError
