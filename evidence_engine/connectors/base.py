from __future__ import annotations

from abc import ABC, abstractmethod

from evidence_engine.models import CollectionResult, EvidenceRequest, RunContext


class BaseCollector(ABC):
    name: str

    @abstractmethod
    def collect(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        raise NotImplementedError

