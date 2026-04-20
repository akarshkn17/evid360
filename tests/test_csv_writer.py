from pathlib import Path

from evidence_engine.artifacts.writer import write_csv_artifact
from evidence_engine.models import BaseEvidenceRecord


def test_write_csv_artifact(tmp_path: Path) -> None:
    path = tmp_path / "evidence.csv"
    record = BaseEvidenceRecord(
        evidence_id="JIRA-1",
        source_system="jira",
        record_type="issue",
        title="Hardware request",
        status="Open",
        created_at="2026-04-19T10:00:00Z",
        updated_at="2026-04-20T10:00:00Z",
        owner="Alice",
        tags=["hardware"],
        raw_ref="https://example.atlassian.net/rest/api/3/issue/1",
        collected_at="2026-04-20T10:00:00+00:00",
        attributes={"project_key": "IT"},
    )

    write_csv_artifact(path, [record], ["project_key"])

    content = path.read_text(encoding="utf-8")
    assert "evidence_id,source_system,record_type,title" in content
    assert "JIRA-1,jira,issue,Hardware request" in content
    assert "IT" in content

