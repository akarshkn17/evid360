from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from evidence_engine.models import BaseEvidenceRecord


CSV_ATTRIBUTE_FIELDS = [
    "query_scope_name",
    "query_scope_jql",
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

ASSET_CSV_ATTRIBUTE_FIELDS = [
    "asset_id",
    "object_key",
    "object_type_id",
    "object_type_name",
    "schema_id",
    "schema_name",
    "workspace_id",
    "asset_attributes",
]


def normalize_issue(
    issue: dict[str, Any],
    collected_at: datetime,
    *,
    query_scope_name: str | None = None,
    query_scope_jql: str | None = None,
) -> BaseEvidenceRecord:
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
            "query_scope_name": query_scope_name,
            "query_scope_jql": query_scope_jql,
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


def normalize_asset(
    asset: dict[str, Any],
    collected_at: datetime,
    *,
    workspace_id: str | None = None,
    schema_id: int | None = None,
    schema_name: str | None = None,
) -> BaseEvidenceRecord:
    object_type = asset.get("objectType") or {}
    asset_id = str(asset.get("id") or asset.get("globalId") or asset.get("objectKey") or "")
    object_key = asset.get("objectKey")
    label = asset.get("label") or asset.get("name") or object_key or asset_id

    return BaseEvidenceRecord(
        evidence_id=object_key or asset_id,
        source_system="jira",
        record_type="asset",
        title=label,
        status=asset.get("status", {}).get("name") if isinstance(asset.get("status"), dict) else asset.get("status"),
        created_at=asset.get("created"),
        updated_at=asset.get("updated"),
        owner=None,
        tags=[],
        raw_ref=asset.get("_links", {}).get("self") or asset.get("self"),
        collected_at=collected_at.astimezone(UTC).isoformat(),
        attributes={
            "asset_id": asset_id,
            "object_key": object_key,
            "object_type_id": object_type.get("id") or asset.get("objectTypeId"),
            "object_type_name": object_type.get("name"),
            "schema_id": schema_id,
            "schema_name": schema_name,
            "workspace_id": workspace_id,
            "asset_attributes": _flatten_asset_attributes(asset.get("attributes", [])),
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


def _flatten_asset_attributes(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for attribute in attributes:
        attribute_meta = attribute.get("objectTypeAttribute") or {}
        name = attribute_meta.get("name") or attribute.get("name") or str(attribute.get("objectTypeAttributeId"))
        values = [_asset_attribute_value(value) for value in attribute.get("objectAttributeValues", [])]
        cleaned_values = [value for value in values if value is not None]
        if not name:
            continue
        flattened[name] = cleaned_values[0] if len(cleaned_values) == 1 else cleaned_values
    return flattened


def _asset_attribute_value(value: dict[str, Any]) -> Any:
    for key in ("displayValue", "searchValue", "value"):
        if value.get(key) is not None:
            return value[key]
    referenced_object = value.get("referencedObject")
    if isinstance(referenced_object, dict):
        return referenced_object.get("label") or referenced_object.get("objectKey")
    user = value.get("user")
    if isinstance(user, dict):
        return user.get("displayName") or user.get("emailAddress") or user.get("accountId")
    return None
