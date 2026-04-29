from datetime import UTC, datetime

from evidence_engine.config import AppConfig, JiraConfig
from evidence_engine.connectors.jira.collector import JiraCollector
from evidence_engine.models import EvidenceRequest, RunContext


class FakeJiraClient:
    def search_issues(self, *, jql: str, fields: list[str], expand: list[str], page_size: int) -> tuple[list[dict], dict]:
        issue = {
            "id": "10001" if "change request" in jql else "10002",
            "key": "IT-100" if "change request" in jql else "IT-200",
            "self": "https://example.atlassian.net/rest/api/3/issue/10001",
            "fields": {
                "summary": "Change request" if "change request" in jql else "Risk update",
                "description": "Example",
                "project": {"key": "IT", "name": "IT Operations"},
                "issuetype": {"name": "Task"},
                "status": {"name": "Done"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Jordan"},
                "reporter": {"displayName": "Morgan"},
                "creator": {"displayName": "Morgan"},
                "labels": ["ops"],
                "components": [{"name": "Endpoints"}],
                "created": "2026-04-10T10:00:00.000+0000",
                "updated": "2026-04-12T10:00:00.000+0000",
                "resolutiondate": "2026-04-13T10:00:00.000+0000",
                "duedate": "2026-04-20",
            },
        }
        return [issue], {"page_count": 1, "page_size": page_size}


def test_collect_multi_jql_scopes_merges_results() -> None:
    collector = JiraCollector(
        JiraConfig(base_url="https://example.atlassian.net", email="user@example.com", api_token="token"),
        AppConfig(),
    )
    collector._client = FakeJiraClient()  # type: ignore[assignment]

    request = EvidenceRequest(
        connector="jira",
        query='change_requests: summary ~ "change request" | risk_updates: summary ~ "risk update"',
        metadata={
            "jql_queries": [
                {"name": "change_requests", "jql": 'summary ~ "change request"'},
                {"name": "risk_updates", "jql": 'summary ~ "risk update"'},
            ]
        },
    )

    result = collector.collect(
        request,
        RunContext(run_id="run-1", started_at=datetime(2026, 4, 29, tzinfo=UTC)),
    )

    assert len(result.records) == 2
    assert result.records[0].attributes["query_scope_name"] == "change_requests"
    assert result.records[1].attributes["query_scope_name"] == "risk_updates"
    assert result.source_metadata["scope_count"] == 2
    assert len(result.source_metadata["query_scopes"]) == 2
