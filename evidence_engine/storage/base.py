from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseStorageBackend(ABC):
    name: str

    @abstractmethod
    def store(self, connector: str, run_id: str, artifact_dir: Path, artifact_paths: dict[str, Path]) -> dict[str, str]:
        raise NotImplementedError

