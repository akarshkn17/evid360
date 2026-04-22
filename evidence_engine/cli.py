from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from evidence_engine.controls.jira import JiraControlRunner
from evidence_engine.engine import EvidenceEngine
from evidence_engine.exceptions import EvidenceEngineError
from evidence_engine.models import EvidenceRequest, EvidenceRunResult

app = typer.Typer(help="Evidence collection engine CLI.")


@app.callback()
def main() -> None:
    """trace360 command group."""


@app.command()
def collect(
    connector: str = typer.Argument(..., help="Connector name such as jira or gcp."),
    query: str = typer.Option(..., "--query", help="Connector query or task description."),
    format: list[str] = typer.Option(["json", "csv"], "--format", help="Artifact output format."),
    storage: str = typer.Option("local", "--storage", help="Storage backend: local or bucket."),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Override the local artifact root."),
    expand: list[str] = typer.Option([], "--expand", help="Connector-specific fields to expand."),
    page_size: int | None = typer.Option(None, "--page-size", help="Optional page size override."),
) -> None:
    try:
        request = EvidenceRequest(
            connector=connector,
            query=query,
            output_formats=format,
            storage_backend=storage,
            output_dir=output_dir,
            expand_fields=expand,
            page_size=page_size,
        )
        result = EvidenceEngine().run(request)
    except (ValidationError, EvidenceEngineError) as exc:
        _exit_with_error(exc)

    _print_json(_run_result_payload(result))


@app.command("collect-control")
def collect_control(
    control_file: Path = typer.Argument(..., help="Path to a Jira YAML control file."),
    format: list[str] = typer.Option(["json", "csv"], "--format", help="Artifact output format."),
    storage: str = typer.Option("local", "--storage", help="Storage backend: local or bucket."),
    output_dir: str | None = typer.Option(None, "--output-dir", help="Override the local artifact root."),
) -> None:
    try:
        result = JiraControlRunner().run_file(
            control_file,
            output_formats=format,
            storage_backend=storage,
            output_dir=output_dir,
        )
    except (ValidationError, EvidenceEngineError) as exc:
        _exit_with_error(exc)

    _print_json(
        {
            "control_id": result.control_id,
            "request_id": result.request_id,
            "name": result.name,
            "passed": result.passed,
            "record_count": result.record_count,
            "minimum_results": result.minimum_results,
            **_run_result_payload(result.evidence_result),
        }
    )


def _run_result_payload(result: EvidenceRunResult) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "connector": result.connector,
        "record_count": result.record_count,
        "storage_backend": result.storage_backend,
        "artifact_dir": result.artifact_dir,
        "artifacts": result.artifact_paths,
        "storage_locations": result.storage_locations,
    }


def _print_json(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _exit_with_error(exc: Exception) -> None:
    typer.echo(f"error: {exc}", err=True)
    raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
