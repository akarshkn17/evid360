from __future__ import annotations

from datetime import UTC, datetime

from evidence_engine.models import BaseEvidenceRecord


def normalize_project_metadata(project_id: str, collected_at: datetime) -> BaseEvidenceRecord:
    return BaseEvidenceRecord(
        evidence_id=project_id,
        source_system="gcp",
        record_type="project_metadata",
        title=f"GCP project metadata for {project_id}",
        status="available",
        created_at=None,
        updated_at=None,
        owner=None,
        tags=[],
        raw_ref=project_id,
        collected_at=collected_at.astimezone(UTC).isoformat(),
        attributes={"project_id": project_id},
    )

