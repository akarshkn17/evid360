from __future__ import annotations

from evidence_engine.config import AppConfig, JiraConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.connectors.jira.client import JiraClient
from evidence_engine.connectors.jira.normalize import (
    ASSET_CSV_ATTRIBUTE_FIELDS,
    CSV_ATTRIBUTE_FIELDS,
    normalize_asset,
    normalize_issue,
)
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
        if request.metadata.get("operation") == "fetch_assets":
            return self._collect_assets(request, run_context)
        return self._collect_issues(request, run_context)

    def _collect_issues(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
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

    def _collect_assets(self, request: EvidenceRequest, run_context: RunContext) -> CollectionResult:
        page_size = request.page_size or self._app_config.jira_page_size
        schema_id = _optional_int(request.metadata.get("schema_id"))
        object_type_id = _optional_int(request.metadata.get("object_type_id"))
        include_attributes = bool(request.metadata.get("include_attributes", True))
        workspace_id = request.metadata.get("workspace_id")

        raw_assets, source_metadata = self._client.fetch_assets(
            aql=request.query,
            page_size=page_size,
            include_attributes=include_attributes,
            schema_id=schema_id,
            object_type_id=object_type_id,
            workspace_id=workspace_id if isinstance(workspace_id, str) and workspace_id else None,
        )
        schema = source_metadata.get("schema") or {}
        records = [
            normalize_asset(
                asset,
                run_context.started_at,
                workspace_id=source_metadata.get("workspace_id"),
                schema_id=schema_id,
                schema_name=schema.get("name") if isinstance(schema, dict) else None,
            )
            for asset in raw_assets
        ]
        source_metadata = {
            **source_metadata,
            "query": request.query,
            "fetched_at": run_context.started_at_iso,
            "source_system": self.name,
            "operation": "fetch_assets",
        }
        return CollectionResult(
            records=records,
            source_metadata=source_metadata,
            raw_records=raw_assets,
            csv_attribute_fields=ASSET_CSV_ATTRIBUTE_FIELDS,
        )


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
