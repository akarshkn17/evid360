from __future__ import annotations

from collections.abc import Callable

from evidence_engine.config import AppConfig, GcpConfig, JiraConfig
from evidence_engine.connectors.base import BaseCollector
from evidence_engine.connectors.gcp.collector import GcpCollector
from evidence_engine.connectors.jira.collector import JiraCollector
from evidence_engine.exceptions import UnsupportedConnectorError


class ConnectorRegistry:
    def __init__(self, app_config: AppConfig | None = None) -> None:
        self._app_config = app_config or AppConfig.from_env()
        self._factories: dict[str, Callable[[], BaseCollector]] = {
            "jira": lambda: JiraCollector(JiraConfig.from_env(), self._app_config),
            "gcp": lambda: GcpCollector(GcpConfig.from_env()),
        }

    def get(self, name: str) -> BaseCollector:
        try:
            return self._factories[name.lower()]()
        except KeyError as exc:
            raise UnsupportedConnectorError(name) from exc

