import pytest

from evidence_engine.config import AppConfig, JiraConfig
from evidence_engine.exceptions import ConfigurationError


def test_app_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DEFAULT_STORAGE_BACKEND", raising=False)
    AppConfig.from_env.cache_clear()

    config = AppConfig.from_env()

    assert config.app_env == "dev"
    assert config.default_storage_backend.value == "local"


def test_jira_config_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_BASE_URL", "")
    monkeypatch.setenv("JIRA_EMAIL", "")
    monkeypatch.setenv("JIRA_API_TOKEN", "")

    with pytest.raises(ConfigurationError):
        JiraConfig.from_env()
