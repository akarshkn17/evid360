from __future__ import annotations

from evidence_engine.config import GcpConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.connectors.gcp.normalize import normalize_project_metadata
from evidence_engine.models import CollectionResult, EvidenceRequest, RunContext


class GcpCollector(BaseCollector):
    name = "gcp"

    def __init__(self, config: GcpConfig) -> None:
        self._config = config

    def collect(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        record = normalize_project_metadata(self._config.project_id, run_context.started_at)
        metadata = {
            "query": request.query,
            "source_system": self.name,
            "fetched_at": run_context.started_at_iso,
            "note": "Minimal GCP scaffold for v1. Extend this collector with real API calls as needed.",
        }
        return CollectionResult(records=[record], source_metadata=metadata, raw_records=[], csv_attribute_fields=["project_id"])

