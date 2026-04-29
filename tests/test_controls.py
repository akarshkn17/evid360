from pathlib import Path
import json

from evidence_engine.config import AppConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.controls.jira import JiraControlRunner, load_jira_control
from evidence_engine.engine import EvidenceEngine
from evidence_engine.models import BaseEvidenceRecord, CollectionResult, EvidenceRequest, EvidenceRunResult, RunContext
from evidence_engine.services.registry import ConnectorRegistry
from evidence_engine.storage.base import BaseStorageBackend


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


def test_control_runner_maps_multi_jql_yaml_to_evidence_request(tmp_path: Path) -> None:
    control_file = tmp_path / "idr-req-200.yaml"
    control_file.write_text(
        """
id: MULTI_SCOPE_CONTROL
request_id: IDR-Req-200
name: Multi-scope control
description: Sample Jira control with multiple JQL scopes.
connector: jira
operation: search_issues
scope:
  jql_queries:
    - name: change_requests
      jql: 'summary ~ "change request"'
    - name: risk_updates
      jql: 'summary ~ "risk update"'
expected:
  minimum_results: 1
evidence:
  severity: medium
""",
        encoding="utf-8",
    )
    control = load_jira_control(control_file)

    assert [scope.model_dump(mode="json") for scope in control.jql_queries] == [
        {"name": "change_requests", "jql": 'summary ~ "change request"'},
        {"name": "risk_updates", "jql": 'summary ~ "risk update"'},
    ]


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


def test_control_runner_writes_request_first_scoped_artifacts(tmp_path: Path) -> None:
    control_file = tmp_path / "idr-req-200.yaml"
    control_file.write_text(
        """
id: MULTI_SCOPE_CONTROL
request_id: IDR-Req-200
name: Multi-scope control
description: Sample Jira control with multiple JQL scopes.
connector: jira
operation: search_issues
scope:
  jql_queries:
    - name: change_requests
      jql: 'summary ~ "change request"'
    - name: risk_updates
      jql: 'summary ~ "risk update"'
expected:
  minimum_results: 1
evidence:
  severity: medium
""",
        encoding="utf-8",
    )
    engine = EvidenceEngine(
        config=AppConfig(local_artifact_root=tmp_path),
        registry=FakeRegistry(),
        storage_factory=lambda storage_backend: FakeStorage(),
    )

    result = JiraControlRunner(engine).run_file(control_file)

    root_dir = Path(result.evidence_result.artifact_root_dir)
    assert "IDR-Req-200" in str(root_dir)
    assert (root_dir / "control-summary.json").exists()
    assert (root_dir / "control-hashes.json").exists()
    assert (root_dir / "scopes" / "change_requests" / "manifest.json").exists()
    assert (root_dir / "scopes" / "risk_updates" / "manifest.json").exists()

    summary = json.loads((root_dir / "control-summary.json").read_text(encoding="utf-8"))
    assert summary["request_id"] == "IDR-Req-200"
    assert summary["scope_count"] == 2
    assert summary["total_record_count"] == 2

    scope_manifest = json.loads((root_dir / "scopes" / "change_requests" / "manifest.json").read_text(encoding="utf-8"))
    assert scope_manifest["metadata"]["request_id"] == "IDR-Req-200"
    assert scope_manifest["metadata"]["scope_name"] == "change_requests"


class FakeEngine:
    def __init__(self) -> None:
        self.last_request: EvidenceRequest | None = None

    def run(self, request: EvidenceRequest, **kwargs: object) -> EvidenceRunResult:
        self.last_request = request
        return EvidenceRunResult(
            run_id="run-1",
            connector=request.connector,
            started_at="2026-04-22T00:00:00+00:00",
            completed_at="2026-04-22T00:00:01+00:00",
            record_count=2,
            storage_backend="local",
            artifact_root_dir=str(Path("artifacts").resolve()),
            artifact_dir=str(Path("artifacts").resolve()),
            artifact_paths={"evidence.json": str(Path("artifacts/evidence.json").resolve())},
            storage_locations={"evidence.json": str(Path("artifacts/evidence.json").resolve())},
            hashes={"evidence.json": "abc"},
            metadata={"storage_prefix": "ad-hoc/jira/2026/04/22/run-1"},
        )


class FakeCollector(BaseCollector):
    name = "jira"

    def collect(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        scope_name = request.metadata.get("scope_name") or "default"
        record = BaseEvidenceRecord(
            evidence_id=f"REC-{scope_name}",
            source_system="jira",
            record_type="issue",
            title=f"Record for {scope_name}",
            status="open",
            created_at=run_context.started_at_iso,
            updated_at=run_context.started_at_iso,
            owner="owner",
            tags=["sample"],
            raw_ref=f"REC-{scope_name}",
            collected_at=run_context.started_at_iso,
            attributes={"query_scope_name": scope_name, "query_scope_jql": request.query},
        )
        return CollectionResult(
            records=[record],
            source_metadata={"query": request.query, "scope_name": scope_name},
            raw_records=[{"id": f"REC-{scope_name}"}],
            csv_attribute_fields=["query_scope_name", "query_scope_jql"],
        )


class FakeRegistry(ConnectorRegistry):
    def __init__(self) -> None:
        pass

    def get(self, name: str) -> BaseCollector:
        return FakeCollector()


class FakeStorage(BaseStorageBackend):
    name = "local"

    def store(self, artifact_root_dir: Path, artifact_paths: dict[str, Path], storage_prefix: str) -> dict[str, str]:
        return {name: str(path.resolve()) for name, path in artifact_paths.items()}
