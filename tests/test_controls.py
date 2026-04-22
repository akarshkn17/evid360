from pathlib import Path

from evidence_engine.controls.jira import JiraControlRunner, load_jira_control
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

    control = load_jira_control(control_file)

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

    result = JiraControlRunner(engine).run_file(control_file)

    assert result.passed is True
    assert result.record_count == 2
    assert engine.last_request is not None
    assert engine.last_request.query == 'summary ~ "sample"'
    assert engine.last_request.metadata["request_id"] == "IDR-Req-001"


def test_control_runner_maps_assets_yaml_to_evidence_request(tmp_path: Path) -> None:
    control_file = tmp_path / "idr-req-007.yaml"
    control_file.write_text(
        """
id: JSM_ASSETS_INVENTORY
request_id: IDR-Req-007
name: Jira Service Management assets inventory
description: Retrieve JSM Assets objects.
connector: jira
operation: fetch_assets
scope:
  schema_id: 4
  object_type_id: 34
  aql: 'objectTypeId = 34'
  include_attributes: true
expected:
  minimum_results: 1
evidence:
  severity: high
""",
        encoding="utf-8",
    )
    engine = FakeEngine()

    result = JiraControlRunner(engine).run_file(control_file)

    assert result.passed is True
    assert engine.last_request is not None
    assert engine.last_request.query == "objectTypeId = 34"
    assert engine.last_request.metadata["operation"] == "fetch_assets"
    assert engine.last_request.metadata["schema_id"] == 4
    assert engine.last_request.metadata["object_type_id"] == 34


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
