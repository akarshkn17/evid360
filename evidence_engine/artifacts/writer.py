from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from evidence_engine.exceptions import ArtifactError
from evidence_engine.models import BaseEvidenceRecord


COMMON_CSV_FIELDS = [
    "evidence_id",
    "source_system",
    "record_type",
    "title",
    "status",
    "created_at",
    "updated_at",
    "owner",
    "tags",
    "raw_ref",
    "collected_at",
]


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    _write_bytes_atomic(path, json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8"))


def write_csv_artifact(path: Path, records: list[BaseEvidenceRecord], attribute_fields: list[str]) -> None:
    rows = [_record_to_csv_row(record, attribute_fields) for record in records]
    fieldnames = COMMON_CSV_FIELDS + attribute_fields
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name
    try:
        os.replace(temp_name, path)
    except OSError as exc:
        raise ArtifactError(f"Failed to write CSV artifact {path}: {exc}") from exc


def _record_to_csv_row(record: BaseEvidenceRecord, attribute_fields: list[str]) -> dict[str, Any]:
    base_row = {
        "evidence_id": record.evidence_id,
        "source_system": record.source_system,
        "record_type": record.record_type,
        "title": record.title,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "owner": record.owner,
        "tags": ",".join(record.tags),
        "raw_ref": record.raw_ref,
        "collected_at": record.collected_at,
    }
    for field in attribute_fields:
        value = record.attributes.get(field)
        if isinstance(value, list):
            base_row[field] = ",".join(str(item) for item in value)
        else:
            base_row[field] = value
    return base_row


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name
    try:
        os.replace(temp_name, path)
    except OSError as exc:
        raise ArtifactError(f"Failed to write artifact {path}: {exc}") from exc
