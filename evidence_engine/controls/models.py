from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from evidence_engine.models import EvidenceRunResult


class ControlDefinition(BaseModel):
    id: str
    request_id: str
    name: str
    description: str
    connector: str
    operation: str
    scope: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("connector")
    @classmethod
    def normalize_connector(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("operation")
    @classmethod
    def normalize_operation(cls, value: str) -> str:
        return value.strip()

    @property
    def jql(self) -> str | None:
        value = self.scope.get("jql")
        return value if isinstance(value, str) and value.strip() else None


class ControlRunResult(BaseModel):
    control_id: str
    request_id: str
    name: str
    connector: str
    operation: str
    passed: bool
    record_count: int
    minimum_results: int | None = None
    evidence_result: EvidenceRunResult

