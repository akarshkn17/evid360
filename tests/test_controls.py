from pathlib import Path

from evidence_engine.controls.loader import load_control
from evidence_engine.controls.runner import ControlRunner
from evidence_engine.models import EvidenceRequest, EvidenceRunResult


def test_load_control_from_yaml(tmp_path: Path) -> None:
    control_file = tmp_path / "idr-req-001.yaml"
    control_file.write_text(
        """
id: SAMPLE_CONTROL
request_id: IDR-Req-001
name: Sample control
description: Sample Jira control.
connector: jira
operation: search_issues
scope:
  jql: 'summary ~ "sample"'
expected:
  minimum_results: 1
evidence:
  severity: medium
""",
        encoding="utf-8",
    )

    control = load_control(control_file)

    assert control.id == "SAMPLE_CONTROL"
    assert control.connector == "jira"
    assert control.jql == 'summary ~ "sample"'


def test_control_runner_maps_yaml_to_evidence_request(tmp_path: Path) -> None:
    control_file = tmp_path / "idr-req-001.yaml"
    control_file.write_text(
        """
id: SAMPLE_CONTROL
request_id: IDR-Req-001
name: Sample control
description: Sample Jira control.
connector: jira
operation: search_issues
scope:
  jql: 'summary ~ "sample"'
expected:
  minimum_results: 1
evidence:
  severity: medium
""",
        encoding="utf-8",
    )
    engine = FakeEngine()

    result = ControlRunner(engine).run_file(control_file)

    assert result.passed is True
    assert result.record_count == 2
    assert engine.last_request is not None
    assert engine.last_request.query == 'summary ~ "sample"'
    assert engine.last_request.metadata["request_id"] == "IDR-Req-001"


class FakeEngine:
    def __init__(self) -> None:
        self.last_request: EvidenceRequest | None = None

    def run(self, request: EvidenceRequest) -> EvidenceRunResult:
        self.last_request = request
        return EvidenceRunResult(
            run_id="run-1",
            connector=request.connector,
            started_at="2026-04-22T00:00:00+00:00",
            completed_at="2026-04-22T00:00:01+00:00",
            record_count=2,
            storage_backend="local",
            artifact_dir=str(Path("artifacts").resolve()),
            artifact_paths={"evidence.json": str(Path("artifacts/evidence.json").resolve())},
            storage_locations={"evidence.json": str(Path("artifacts/evidence.json").resolve())},
            hashes={"evidence.json": "abc"},
        )
