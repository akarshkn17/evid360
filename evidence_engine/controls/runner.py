from __future__ import annotations

from pathlib import Path
from typing import Protocol

from evidence_engine.controls.loader import load_control
from evidence_engine.controls.models import ControlDefinition, ControlRunResult
from evidence_engine.engine import EvidenceEngine
from evidence_engine.exceptions import ControlError
from evidence_engine.models import EvidenceRequest, EvidenceRunResult, OutputFormat, StorageBackendType


class EngineLike(Protocol):
    def run(self, request: EvidenceRequest) -> EvidenceRunResult:
        ...


class ControlRunner:
    def __init__(self, engine: EngineLike | None = None) -> None:
        self._engine = engine or EvidenceEngine()

    def run_file(
        self,
        control_file: Path | str,
        *,
        output_formats: list[OutputFormat | str] | None = None,
        storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
        output_dir: str | None = None,
    ) -> ControlRunResult:
        return self.run(
            load_control(control_file),
            output_formats=output_formats,
            storage_backend=storage_backend,
            output_dir=output_dir,
        )

    def run(
        self,
        control: ControlDefinition,
        *,
        output_formats: list[OutputFormat | str] | None = None,
        storage_backend: StorageBackendType | str = StorageBackendType.LOCAL,
        output_dir: str | None = None,
    ) -> ControlRunResult:
        if control.connector != "jira":
            raise ControlError(f"Control connector is not supported by the Jira control runner: {control.connector}")
        if control.operation != "search_issues":
            raise ControlError(f"Unsupported Jira control operation: {control.operation}")
        if not control.jql:
            raise ControlError(f"Jira control {control.request_id} must define scope.jql")

        request = EvidenceRequest(
            connector=control.connector,
            query=control.jql,
            output_formats=output_formats or [OutputFormat.JSON, OutputFormat.CSV],
            storage_backend=storage_backend,
            output_dir=output_dir,
            metadata={
                "control_id": control.id,
                "request_id": control.request_id,
                "control_name": control.name,
                "operation": control.operation,
                "expected": control.expected,
                "evidence": control.evidence,
            },
        )
        result = self._engine.run(request)
        minimum_results = _minimum_results(control)
        passed = result.record_count >= minimum_results if minimum_results is not None else True

        return ControlRunResult(
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


def _minimum_results(control: ControlDefinition) -> int | None:
    value = control.expected.get("minimum_results")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ControlError(f"Control {control.request_id} has invalid expected.minimum_results: {value}") from exc

