from __future__ import annotations

from evidence_engine.config import AppConfig, JiraConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.connectors.jira.client import JiraClient
from evidence_engine.connectors.jira.normalize import CSV_ATTRIBUTE_FIELDS, normalize_issue
from evidence_engine.models import CollectionResult, EvidenceRequest, RunContext


class JiraCollector(BaseCollector):
    name = "jira"
    default_fields = [
        "summary",
        "description",
        "project",
        "issuetype",
        "status",
        "priority",
        "assignee",
        "reporter",
        "creator",
        "labels",
        "components",
        "created",
        "updated",
        "resolutiondate",
        "duedate",
    ]

    def __init__(self, config: JiraConfig, app_config: AppConfig) -> None:
        self._client = JiraClient(
            config=config,
            timeout_seconds=app_config.http_timeout_seconds,
            max_retries=app_config.http_max_retries,
        )
        self._app_config = app_config

    def collect(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        page_size = request.page_size or self._app_config.jira_page_size
        raw_issues, source_metadata = self._client.search_issues(
            jql=request.query,
            fields=self.default_fields,
            expand=request.expand_fields,
            page_size=page_size,
        )
        records = [normalize_issue(issue, run_context.started_at) for issue in raw_issues]
        source_metadata = {
            **source_metadata,
            "query": request.query,
            "fetched_at": run_context.started_at_iso,
            "source_system": self.name,
        }
        return CollectionResult(
            records=records,
            source_metadata=source_metadata,
            raw_records=raw_issues,
            csv_attribute_fields=CSV_ATTRIBUTE_FIELDS,
        )

