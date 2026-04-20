from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from evidence_engine.models import BaseEvidenceRecord


CSV_ATTRIBUTE_FIELDS = [
    "issue_id",
    "project_key",
    "project_name",
    "issue_type",
    "priority",
    "reporter",
    "creator",
    "components",
    "resolved",
    "due_date",
]


def normalize_issue(issue: dict[str, Any], collected_at: datetime) -> BaseEvidenceRecord:
    fields = issue.get("fields", {})
    assignee = fields.get("assignee") or {}
    status = fields.get("status") or {}
    project = fields.get("project") or {}
    issue_type = fields.get("issuetype") or {}
    priority = fields.get("priority") or {}
    reporter = fields.get("reporter") or {}
    creator = fields.get("creator") or {}
    components = fields.get("components") or []

    return BaseEvidenceRecord(
        evidence_id=issue.get("key", issue.get("id", "")),
        source_system="jira",
        record_type="issue",
        title=fields.get("summary") or issue.get("key", "untitled issue"),
        status=status.get("name"),
        created_at=fields.get("created"),
        updated_at=fields.get("updated"),
        owner=assignee.get("displayName"),
        tags=fields.get("labels") or [],
        raw_ref=issue.get("self"),
        collected_at=collected_at.astimezone(UTC).isoformat(),
        attributes={
            "issue_id": issue.get("id"),
            "project_key": project.get("key"),
            "project_name": project.get("name"),
            "issue_type": issue_type.get("name"),
            "priority": priority.get("name"),
            "description": _extract_description(fields.get("description")),
            "reporter": reporter.get("displayName"),
            "creator": creator.get("displayName"),
            "components": [component.get("name") for component in components if component.get("name")],
            "resolved": fields.get("resolutiondate"),
            "due_date": fields.get("duedate"),
        },
    )


def _extract_description(description: Any) -> str | None:
    if description is None:
        return None
    if isinstance(description, str):
        return description
    if isinstance(description, dict):
        text_fragments: list[str] = []
        _walk_document(description, text_fragments)
        return " ".join(part for part in text_fragments if part).strip() or None
    return str(description)


def _walk_document(node: Any, text_fragments: list[str]) -> None:
    if isinstance(node, dict):
        text = node.get("text")
        if text:
            text_fragments.append(text)
        for child in node.get("content", []):
            _walk_document(child, text_fragments)
    elif isinstance(node, list):
        for item in node:
            _walk_document(item, text_fragments)

