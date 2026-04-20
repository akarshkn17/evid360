from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from evidence_engine.exceptions import ConfigurationError
from evidence_engine.models import StorageBackendType


def _load_env() -> None:
    load_dotenv()


class AppConfig(BaseModel):
    app_env: str = "dev"
    log_level: str = "INFO"
    default_storage_backend: StorageBackendType = StorageBackendType.LOCAL
    local_artifact_root: Path = Path(".artifacts")
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 3
    jira_page_size: int = 50

    @classmethod
    @lru_cache(maxsize=1)
    def from_env(cls) -> "AppConfig":
        _load_env()
        try:
            return cls(
                app_env=os.getenv("APP_ENV", "dev"),
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                default_storage_backend=os.getenv("DEFAULT_STORAGE_BACKEND", StorageBackendType.LOCAL.value),
                local_artifact_root=Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".artifacts")),
                http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
                http_max_retries=int(os.getenv("HTTP_MAX_RETRIES", "3")),
                jira_page_size=int(os.getenv("JIRA_PAGE_SIZE", "50")),
            )
        except (ValidationError, ValueError) as exc:
            raise ConfigurationError(f"Invalid application configuration: {exc}") from exc


class JiraConfig(BaseModel):
    base_url: str = Field(min_length=1)
    email: str = Field(min_length=1)
    api_token: str = Field(min_length=1, repr=False)

    @classmethod
    def from_env(cls) -> "JiraConfig":
        _load_env()
        try:
            return cls(
                base_url=os.environ["JIRA_BASE_URL"].rstrip("/"),
                email=os.environ["JIRA_EMAIL"],
                api_token=os.environ["JIRA_API_TOKEN"],
            )
        except KeyError as exc:
            raise ConfigurationError(f"Missing Jira configuration: {exc.args[0]}") from exc
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid Jira configuration: {exc}") from exc


class GcpConfig(BaseModel):
    project_id: str = Field(min_length=1)

    @classmethod
    def from_env(cls) -> "GcpConfig":
        _load_env()
        try:
            return cls(project_id=os.environ["GCP_PROJECT_ID"])
        except KeyError as exc:
            raise ConfigurationError(f"Missing GCP configuration: {exc.args[0]}") from exc
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid GCP configuration: {exc}") from exc


class BucketStorageConfig(BaseModel):
    bucket_name: str = Field(min_length=1)

    @classmethod
    def from_env(cls) -> "BucketStorageConfig":
        _load_env()
        try:
            return cls(bucket_name=os.environ["GCS_BUCKET_NAME"])
        except KeyError as exc:
            raise ConfigurationError(f"Missing bucket storage configuration: {exc.args[0]}") from exc
        except ValidationError as exc:
            raise ConfigurationError(f"Invalid bucket storage configuration: {exc}") from exc
