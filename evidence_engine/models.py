from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class OutputFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


class StorageBackendType(str, Enum):
    LOCAL = "local"
    BUCKET = "bucket"


class EvidenceRequest(BaseModel):
    connector: str
    query: str
    output_formats: list[OutputFormat | str] = Field(default_factory=lambda: [OutputFormat.JSON, OutputFormat.CSV])
    storage_backend: StorageBackendType | str = StorageBackendType.LOCAL
    output_dir: str | None = None
    expand_fields: list[str] = Field(default_factory=list)
    page_size: int | None = None

    @field_validator("connector")
    @classmethod
    def validate_connector(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("connector must not be empty")
        return cleaned

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        return cleaned

    @field_validator("output_formats")
    @classmethod
    def validate_output_formats(cls, value: list[OutputFormat | str]) -> list[OutputFormat]:
        if not value:
            raise ValueError("output_formats must contain at least one format")
        normalized = [item if isinstance(item, OutputFormat) else OutputFormat(item) for item in value]
        deduplicated: list[OutputFormat] = []
        for item in normalized:
            if item not in deduplicated:
                deduplicated.append(item)
        return deduplicated

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: StorageBackendType | str) -> StorageBackendType:
        return value if isinstance(value, StorageBackendType) else StorageBackendType(value)


class BaseEvidenceRecord(BaseModel):
    evidence_id: str
    source_system: str
    record_type: str
    title: str
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    raw_ref: str | None = None
    collected_at: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class CollectionResult(BaseModel):
    records: list[BaseEvidenceRecord] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    raw_records: list[dict[str, Any]] = Field(default_factory=list)
    csv_attribute_fields: list[str] = Field(default_factory=list)


class ArtifactDescriptor(BaseModel):
    name: str
    path: Path
    sha256: str | None = None


class RunManifest(BaseModel):
    run_id: str
    connector: str
    timestamp: str
    query: str
    artifact_files: list[str]
    record_count: int
    storage_backend: str
    hash_algorithm: str
    hashes: dict[str, str]


class EvidenceRunResult(BaseModel):
    run_id: str
    connector: str
    started_at: str
    completed_at: str
    record_count: int
    storage_backend: str
    artifact_dir: str
    artifact_paths: dict[str, str]
    storage_locations: dict[str, str]
    hashes: dict[str, str]


class RunContext(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def started_at_iso(self) -> str:
        return self.started_at.isoformat()

