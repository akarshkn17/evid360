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
