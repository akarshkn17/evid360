from __future__ import annotations

import time
from typing import Any

import httpx

from evidence_engine.config import JiraConfig
from evidence_engine.exceptions import CollectionError


class JiraClient:
    def __init__(self, config: JiraConfig, timeout_seconds: float, max_retries: int) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def search_issues(
        self,
        *,
        jql: str,
        fields: list[str],
        expand: list[str],
        page_size: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        next_page_token: str | None = None
        page_count = 0
        with httpx.Client(
            base_url=self._config.base_url,
            auth=(self._config.email, self._config.api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self._timeout_seconds,
        ) as client:
            while True:
                payload = {
                    "jql": jql,
                    "maxResults": page_size,
                    "fields": fields,
                    "fieldsByKeys": False,
                }
                if expand:
                    payload["expand"] = ",".join(expand)
                if next_page_token:
                    payload["nextPageToken"] = next_page_token
                response = self._request_with_retry(client, "POST", "/rest/api/3/search/jql", json=payload)
                body = response.json()
                batch = body.get("issues", [])
                issues.extend(batch)
                page_count += 1
                next_page_token = body.get("nextPageToken")
                is_last = body.get("isLast")
                if not batch or is_last is True or not next_page_token:
                    break
        return issues, {
            "issue_count": len(issues),
            "page_count": page_count,
            "page_size": page_size,
            "expand": expand,
            "fields": fields,
        }

    def fetch_assets(
        self,
        *,
        aql: str,
        page_size: int,
        include_attributes: bool = True,
        schema_id: int | None = None,
        object_type_id: int | None = None,
        workspace_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        with httpx.Client(
            base_url=self._config.base_url,
            auth=(self._config.email, self._config.api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self._timeout_seconds,
        ) as client:
            resolved_workspace_id = workspace_id or self._get_assets_workspace_id(client)
            schema = self._get_assets_schema(client, resolved_workspace_id, schema_id) if schema_id else None
            object_type = (
                self._get_assets_object_type(client, resolved_workspace_id, object_type_id) if object_type_id else None
            )
            objects, page_count = self._fetch_assets_objects(
                client,
                workspace_id=resolved_workspace_id,
                aql=aql,
                page_size=page_size,
                include_attributes=include_attributes,
            )

        return objects, {
            "asset_count": len(objects),
            "page_count": page_count,
            "page_size": page_size,
            "workspace_id": resolved_workspace_id,
            "schema_id": schema_id,
            "object_type_id": object_type_id,
            "aql": aql,
            "include_attributes": include_attributes,
            "schema": schema,
            "object_type": object_type,
        }

    def _get_assets_workspace_id(self, client: httpx.Client) -> str:
        response = self._request_with_retry(client, "GET", "/rest/servicedeskapi/assets/workspace")
        values = response.json().get("values", [])
        if not values or not values[0].get("workspaceId"):
            raise CollectionError("No Jira Service Management Assets workspace was found")
        return values[0]["workspaceId"]

    def _get_assets_schema(
        self,
        client: httpx.Client,
        workspace_id: str,
        schema_id: int | None,
    ) -> dict[str, Any] | None:
        if schema_id is None:
            return None
        response = self._request_with_retry(
            client,
            "GET",
            f"/gateway/api/jsm/assets/workspace/{workspace_id}/v1/objectschema/{schema_id}",
        )
        return response.json()

    def _get_assets_object_type(
        self,
        client: httpx.Client,
        workspace_id: str,
        object_type_id: int | None,
    ) -> dict[str, Any] | None:
        if object_type_id is None:
            return None
        response = self._request_with_retry(
            client,
            "GET",
            f"/gateway/api/jsm/assets/workspace/{workspace_id}/v1/objecttype/{object_type_id}",
        )
        return response.json()

    def _fetch_assets_objects(
        self,
        client: httpx.Client,
        *,
        workspace_id: str,
        aql: str,
        page_size: int,
        include_attributes: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        objects: list[dict[str, Any]] = []
        start_at = 0
        page_count = 0
        while True:
            response = self._request_with_retry(
                client,
                "POST",
                f"/gateway/api/jsm/assets/workspace/{workspace_id}/v1/object/aql",
                params={
                    "startAt": start_at,
                    "maxResults": page_size,
                    "includeAttributes": str(include_attributes).lower(),
                },
                json={"qlQuery": aql},
            )
            body = response.json()
            batch = body.get("values", [])
            objects.extend(batch)
            page_count += 1
            if not batch or body.get("isLastPage", False):
                break
            start_at += len(batch)
        return objects, page_count

    def _request_with_retry(self, client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(1, self._max_retries + 2):
            try:
                response = client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                if attempt > self._max_retries:
                    raise CollectionError(f"Jira request failed after retries: {exc}") from exc
                time.sleep(min(2 ** (attempt - 1), 8))
                continue

            if response.status_code < 400:
                return response

            if response.status_code in {401, 403}:
                raise CollectionError("Jira authentication or permission failure")
            if response.status_code == 400:
                raise CollectionError(f"Invalid Jira query or request: {response.text}")
            if response.status_code == 429:
                if attempt > self._max_retries:
                    raise CollectionError("Jira rate limit exceeded after retries")
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = float(retry_after) if retry_after else min(2 ** (attempt - 1), 8)
                time.sleep(sleep_seconds)
                continue
            if 500 <= response.status_code < 600:
                if attempt > self._max_retries:
                    raise CollectionError(f"Jira server error after retries: {response.status_code}")
                time.sleep(min(2 ** (attempt - 1), 8))
                continue
            raise CollectionError(f"Unexpected Jira API error: {response.status_code} {response.text}")
        raise CollectionError("Jira request failed")
