from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from evidence_engine.engine import EvidenceEngine
from evidence_engine.exceptions import ControlError
from evidence_engine.models import EvidenceRequest, EvidenceRunResult, OutputFormat, StorageBackendType


class JiraControlDefinition(BaseModel):
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

    @property
    def aql(self) -> str | None:
        value = self.scope.get("aql")
        if isinstance(value, str) and value.strip():
            return value
        object_type_id = self.scope.get("object_type_id")
        if object_type_id is not None:
            return f"objectTypeId = {object_type_id}"
        return None


class JiraControlRunResult(BaseModel):
    control_id: str
    request_id: str
    name: str
    connector: str
    operation: str
    passed: bool
    record_count: int
    minimum_results: int | None = None
    evidence_result: EvidenceRunResult


class EngineLike(Protocol):
    def run(self, request: EvidenceRequest) -> EvidenceRunResult:
        ...


class JiraControlRunner:
    def __init__(self, engine: EngineLike | None = None) -> None:
        self._engine = engine or EvidenceEngine()

    def run_file(
        self,
        control_file: Path | str,
        *,
        output_formats: list[OutputFormat | str] | None = None,
        storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
        output_dir: str | None = None,
    ) -> JiraControlRunResult:
        return self.run(
            load_jira_control(control_file),
            output_formats=output_formats,
            storage_backend=storage_backend,
            output_dir=output_dir,
        )

    def run(
        self,
        control: JiraControlDefinition,
        *,
        output_formats: list[OutputFormat | str] | None = None,
        storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
        output_dir: str | None = None,
    ) -> JiraControlRunResult:
        _validate_jira_control(control)

        request = EvidenceRequest(
            connector=control.connector,
            query=_control_query(control),
            output_formats=output_formats or [OutputFormat.JSON, OutputFormat.CSV],
            storage_backend=storage_backend,
            output_dir=output_dir,
            metadata={
                "control_id": control.id,
                "request_id": control.request_id,
                "control_name": control.name,
                "operation": control.operation,
                "schema_id": control.scope.get("schema_id"),
                "object_type_id": control.scope.get("object_type_id"),
                "workspace_id": control.scope.get("workspace_id"),
                "include_attributes": control.scope.get("include_attributes", True),
                "expected": control.expected,
                "evidence": control.evidence,
            },
        )
        result = self._engine.run(request)
        minimum_results = _minimum_results(control)
        passed = result.record_count >= minimum_results if minimum_results is not None else True

        return JiraControlRunResult(
            control_id=control.id,
            request_id=control.request_id,
            name=control.name,
            connector=control.connector,
            operation=control.operation,
            passed=passed,
            record_count=result.record_count,
            minimum_results=minimum_results,
            evidence_result=result,
        )


def load_jira_control(path: Path | str) -> JiraControlDefinition:
    control_path = Path(path)
    if not control_path.exists():
        raise ControlError(f"Control file not found: {control_path}")

    try:
        payload = yaml.safe_load(control_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ControlError(f"Invalid YAML in control file {control_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ControlError(f"Control file must contain a YAML mapping: {control_path}")

    try:
        return JiraControlDefinition(**payload)
    except ValidationError as exc:
        raise ControlError(f"Invalid control definition in {control_path}: {exc}") from exc


def load_jira_controls(directory: Path | str) -> list[JiraControlDefinition]:
    control_dir = Path(directory)
    if not control_dir.exists():
        raise ControlError(f"Control directory not found: {control_dir}")
    return [load_jira_control(path) for path in sorted(control_dir.glob("*.yaml"))]


def run_jira_control(
    control_file: Path | str,
    *,
    output_formats: list[OutputFormat | str] | None = None,
    storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
    output_dir: str | None = None,
) -> JiraControlRunResult:
    return JiraControlRunner().run_file(
        control_file,
        output_formats=output_formats,
        storage_backend=storage_backend,
        output_dir=output_dir,
    )


def _validate_jira_control(control: JiraControlDefinition) -> None:
    if control.connector != "jira":
        raise ControlError(f"Control connector is not supported by the Jira control runner: {control.connector}")
    if control.operation not in {"search_issues", "fetch_assets"}:
        raise ControlError(f"Unsupported Jira control operation: {control.operation}")
    if control.operation == "search_issues" and not control.jql:
        raise ControlError(f"Jira control {control.request_id} must define scope.jql")
    if control.operation == "fetch_assets" and not control.aql:
        raise ControlError(f"Jira Assets control {control.request_id} must define scope.aql or scope.object_type_id")


def _control_query(control: JiraControlDefinition) -> str:
    if control.operation == "fetch_assets":
        return control.aql or ""
    return control.jql or ""


def _minimum_results(control: JiraControlDefinition) -> int | None:
    value = control.expected.get("minimum_results")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ControlError(f"Control {control.request_id} has invalid expected.minimum_results: {value}") from exc
