from datetime import UTC, datetime

from evidence_engine.connectors.jira.normalize import normalize_asset, normalize_issue


def test_normalize_issue() -> None:
    issue = {
        "id": "10001",
        "key": "IT-12",
        "self": "https://example.atlassian.net/rest/api/3/issue/10001",
        "fields": {
            "summary": "Replace laptop battery",
            "description": "Battery is failing",
            "project": {"key": "IT", "name": "IT Operations"},
            "issuetype": {"name": "Task"},
            "status": {"name": "Done"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Jordan"},
            "reporter": {"displayName": "Morgan"},
            "creator": {"displayName": "Morgan"},
            "labels": ["hardware", "laptop"],
            "components": [{"name": "Endpoints"}],
            "created": "2026-04-10T10:00:00.000+0000",
            "updated": "2026-04-12T10:00:00.000+0000",
            "resolutiondate": "2026-04-13T10:00:00.000+0000",
            "duedate": "2026-04-20",
        },
    }

    record = normalize_issue(issue, datetime(2026, 4, 20, tzinfo=UTC))

    assert record.evidence_id == "IT-12"
    assert record.source_system == "jira"
    assert record.title == "Replace laptop battery"
    assert record.owner == "Jordan"
    assert record.attributes["project_key"] == "IT"
    assert record.attributes["components"] == ["Endpoints"]


def test_normalize_asset() -> None:
    asset = {
        "id": "100",
        "objectKey": "ASSET-100",
        "label": "Laptop 100",
        "objectType": {"id": "34", "name": "Laptop"},
        "created": "2026-04-10T10:00:00.000Z",
        "updated": "2026-04-12T10:00:00.000Z",
        "attributes": [
            {
                "objectTypeAttribute": {"name": "Serial Number"},
                "objectAttributeValues": [{"displayValue": "SN-123"}],
            },
            {
                "objectTypeAttribute": {"name": "Owner"},
                "objectAttributeValues": [{"displayValue": "Jordan"}],
            },
        ],
    }

    record = normalize_asset(
        asset,
        datetime(2026, 4, 20, tzinfo=UTC),
        workspace_id="workspace-1",
        schema_id=4,
        schema_name="Hardware",
    )

    assert record.evidence_id == "ASSET-100"
    assert record.record_type == "asset"
    assert record.title == "Laptop 100"
    assert record.attributes["object_type_id"] == "34"
    assert record.attributes["schema_id"] == 4
    assert record.attributes["asset_attributes"]["Serial Number"] == "SN-123"
