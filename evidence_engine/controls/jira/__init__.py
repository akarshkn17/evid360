from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from evidence_engine.artifacts.hashing import sha256_file
from evidence_engine.artifacts.writer import write_json_artifact
from evidence_engine.config import BucketStorageConfig
from evidence_engine.engine import EvidenceEngine
from evidence_engine.exceptions import ControlError
from evidence_engine.models import EvidenceRequest, EvidenceRunResult, OutputFormat, RunContext, StorageBackendType
from evidence_engine.storage.bucket import BucketStorageBackend
from evidence_engine.storage.local import LocalStorageBackend


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
    def jql_queries(self) -> list["JiraQueryScope"]:
        raw_value = self.scope.get("jql_queries")
        if raw_value is None:
            return []
        if not isinstance(raw_value, list):
            raise ControlError(f"Jira control {self.request_id} must define scope.jql_queries as a list")
        scopes: list[JiraQueryScope] = []
        for index, item in enumerate(raw_value, start=1):
            if not isinstance(item, dict):
                raise ControlError(
                    f"Jira control {self.request_id} has invalid jql_queries entry at position {index}: {item}"
                )
            try:
                scopes.append(JiraQueryScope(**item))
            except ValidationError as exc:
                raise ControlError(
                    f"Jira control {self.request_id} has invalid jql_queries entry at position {index}: {exc}"
                ) from exc
        return scopes

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


class JiraQueryScope(BaseModel):
    name: str | None = None
    jql: str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("jql")
    @classmethod
    def validate_jql(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("jql must not be empty")
        return cleaned


class EngineLike(Protocol):
    def run(self, request: EvidenceRequest, **kwargs: object) -> EvidenceRunResult:
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
        if control.operation == "search_issues" and len(control.jql_queries) > 1:
            return self._run_multi_scope(
                control,
                output_formats=output_formats,
                storage_backend=storage_backend,
                output_dir=output_dir,
            )

        request = EvidenceRequest(
            connector=control.connector,
            query=_control_query_summary(control),
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
                "jql_queries": [scope.model_dump(mode="json") for scope in control.jql_queries],
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

    def _run_multi_scope(
        self,
        control: JiraControlDefinition,
        *,
        output_formats: list[OutputFormat | str] | None = None,
        storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
        output_dir: str | None = None,
    ) -> JiraControlRunResult:
        if not isinstance(self._engine, EvidenceEngine):
            raise ControlError("Multi-scope control execution requires the concrete EvidenceEngine")

        run_context = RunContext()
        scope_results: list[tuple[JiraQueryScope, EvidenceRunResult]] = []
        combined_artifact_paths: dict[str, str] = {}
        combined_hashes: dict[str, str] = {}
        total_record_count = 0

        for index, scope in enumerate(control.jql_queries, start=1):
            scope_name = scope.name or f"scope_{index}"
            scope_subdir = f"scopes/{_safe_scope_name(scope_name)}"
            request = EvidenceRequest(
                connector=control.connector,
                query=scope.jql,
                output_formats=output_formats or [OutputFormat.JSON, OutputFormat.CSV],
                storage_backend=StorageBackendType.LOCAL,
                output_dir=output_dir,
                metadata={
                    "control_id": control.id,
                    "request_id": control.request_id,
                    "control_name": control.name,
                    "operation": control.operation,
                    "scope_name": scope_name,
                    "scope_query": scope.jql,
                    "expected": control.expected,
                    "evidence": control.evidence,
                },
            )
            result = self._engine.run(
                request,
                run_context=run_context,
                artifact_subdir=scope_subdir,
                upload=False,
            )
            scope_results.append((scope, result))
            total_record_count += result.record_count
            combined_artifact_paths.update(result.artifact_paths)
            combined_hashes.update(result.hashes)

        if not scope_results:
            raise ControlError(f"Jira control {control.request_id} does not contain any scopes to execute")

        root_dir = Path(scope_results[0][1].artifact_root_dir)
        summary_path = root_dir / "control-summary.json"
        summary = _build_control_summary(control, run_context.run_id, scope_results, total_record_count)
        write_json_artifact(summary_path, summary)
        combined_artifact_paths["control-summary.json"] = str(summary_path.resolve())
        combined_hashes["control-summary.json"] = sha256_file(summary_path)

        control_hashes_path = root_dir / "control-hashes.json"
        write_json_artifact(control_hashes_path, {"algorithm": "sha256", "hashes": combined_hashes})
        combined_artifact_paths["control-hashes.json"] = str(control_hashes_path.resolve())
        combined_hashes["control-hashes.json"] = sha256_file(control_hashes_path)

        storage_backend_instance = self._storage_backend(storage_backend)
        storage_locations = storage_backend_instance.store(
            root_dir,
            {key: Path(path) for key, path in combined_artifact_paths.items()},
            _storage_prefix(scope_results[0][1]),
        )

        minimum_results = _minimum_results(control)
        passed = total_record_count >= minimum_results if minimum_results is not None else True

        evidence_result = EvidenceRunResult(
            run_id=run_context.run_id,
            connector=control.connector,
            started_at=scope_results[0][1].started_at,
            completed_at=max(result.completed_at for _, result in scope_results),
            record_count=total_record_count,
            storage_backend=storage_backend_instance.name,
            artifact_root_dir=str(root_dir.resolve()),
            artifact_dir=str(root_dir.resolve()),
            artifact_paths=combined_artifact_paths,
            storage_locations=storage_locations,
            hashes=combined_hashes,
            metadata={
                "request_id": control.request_id,
                "control_id": control.id,
                "operation": control.operation,
                "scope_count": len(scope_results),
            },
        )

        return JiraControlRunResult(
            control_id=control.id,
            request_id=control.request_id,
            name=control.name,
            connector=control.connector,
            operation=control.operation,
            passed=passed,
            record_count=total_record_count,
            minimum_results=minimum_results,
            evidence_result=evidence_result,
        )

    def _storage_backend(self, storage_backend: StorageBackendType | str) -> LocalStorageBackend | BucketStorageBackend:
        backend = storage_backend if isinstance(storage_backend, StorageBackendType) else StorageBackendType(storage_backend)
        if backend == StorageBackendType.LOCAL:
            return LocalStorageBackend()
        return BucketStorageBackend(BucketStorageConfig.from_env())


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
    if control.operation == "search_issues" and not control.jql and not control.jql_queries:
        raise ControlError(f"Jira control {control.request_id} must define scope.jql")
    if control.operation == "fetch_assets" and not control.aql:
        raise ControlError(f"Jira Assets control {control.request_id} must define scope.aql or scope.object_type_id")


def _control_query_summary(control: JiraControlDefinition) -> str:
    if control.operation == "fetch_assets":
        return control.aql or ""
    if control.jql:
        return control.jql
    return " | ".join(
        f"{scope.name}: {scope.jql}" if scope.name else scope.jql
        for scope in control.jql_queries
    )


def _minimum_results(control: JiraControlDefinition) -> int | None:
    value = control.expected.get("minimum_results")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ControlError(f"Control {control.request_id} has invalid expected.minimum_results: {value}") from exc


def _safe_scope_name(value: str) -> str:
    return value.strip().replace(" ", "_").replace("/", "-").replace("\\", "-")


def _storage_prefix(result: EvidenceRunResult) -> str:
    prefix = result.metadata.get("storage_prefix")
    if not isinstance(prefix, str):
        raise ControlError("Missing storage prefix for control artifact upload")
    return prefix


def _build_control_summary(
    control: JiraControlDefinition,
    run_id: str,
    scope_results: list[tuple[JiraQueryScope, EvidenceRunResult]],
    total_record_count: int,
) -> dict[str, object]:
    minimum_results = _minimum_results(control)
    return {
        "request_id": control.request_id,
        "control_id": control.id,
        "control_name": control.name,
        "connector": control.connector,
        "operation": control.operation,
        "run_id": run_id,
        "scope_count": len(scope_results),
        "total_record_count": total_record_count,
        "minimum_results": minimum_results,
        "passed": total_record_count >= minimum_results if minimum_results is not None else True,
        "scopes": [
            {
                "scope_name": scope.name or f"scope_{index}",
                "scope_query": scope.jql,
                "record_count": result.record_count,
                "artifact_dir": result.artifact_dir,
                "artifact_root_dir": result.artifact_root_dir,
                "artifacts": result.artifact_paths,
            }
            for index, (scope, result) in enumerate(scope_results, start=1)
        ],
    }
