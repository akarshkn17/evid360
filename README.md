# trace360

`trace360` is a small, production-minded evidence collection engine for collecting records from source systems such as Jira, serializing them into audit-friendly artifacts, hashing the generated files, and optionally uploading the results to bucket storage.

## Purpose

The project is designed to keep source-specific collection logic separate from orchestration and storage concerns. A connector fetches and normalizes evidence, the engine coordinates the run, artifact utilities serialize and hash files, and storage backends decide where completed artifacts end up.

## Architecture Overview

- `connectors/`: Source-specific clients, collectors, and normalizers.
- `engine.py`: Orchestrates a collection run end-to-end.
- `artifacts/`: Writes JSON and CSV outputs, computes SHA-256 hashes, and builds manifests.
- `storage/`: Swappable storage backends for local files and bucket uploads.
- `services/registry.py`: Lazy connector registry so only the requested connector is initialized.
- `cli.py`: Thin Typer-based command line entrypoint.

## Folder Structure

```text
trace360/
├── evidence_engine/
│   ├── artifacts/
│   ├── connectors/
│   ├── services/
│   ├── storage/
│   ├── cli.py
│   ├── config.py
│   ├── engine.py
│   ├── exceptions.py
│   ├── logging_config.py
│   └── models.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

## Setup

```bash
uv sync --extra dev
```

For a step-by-step run guide, see [USAGE.md](C:\Users\akars\Desktop\mydata\vibecoding\trace360\USAGE.md).

## Environment Variables

Copy `.env.example` into a local `.env` file and set the values needed for the connector or storage backend you plan to use.

Key variables:

- `DEFAULT_STORAGE_BACKEND`
- `LOCAL_ARTIFACT_ROOT`
- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `GCP_PROJECT_ID`
- `GCS_BUCKET_NAME`

## CLI Usage

Collect Jira evidence into JSON and CSV:

```bash
uv run trace360 collect jira --query "project = IT AND text ~ 'hardware' AND created >= -365d"
```

Select formats and storage explicitly:

```bash
uv run trace360 collect jira \
  --query "project = IT ORDER BY created DESC" \
  --format json \
  --format csv \
  --storage local \
  --output-dir .artifacts
```

## Python API Usage

```python
from evidence_engine.engine import EvidenceEngine
from evidence_engine.models import EvidenceRequest

engine = EvidenceEngine()
request = EvidenceRequest(
    connector="jira",
    query="project = IT AND text ~ 'hardware' AND created >= -365d",
    output_formats=["json", "csv"],
    storage_backend="local",
)
result = engine.run(request)
print(result.artifact_paths)
```

## Artifact Output

Ad-hoc runs are written into:

```text
.artifacts/ad-hoc/<connector>/<yyyy>/<mm>/<dd>/<run_id>/
```

Control-driven runs are written into:

```text
.artifacts/<request_id>/<connector>/<yyyy>/<mm>/<dd>/<run_id>/
```

Typical single-scope output:

```text
.artifacts/IDR-Req-027/jira/2026/04/29/<run_id>/
├── evidence.json
├── evidence.csv
├── hashes.json
└── manifest.json
```

Multi-scope controls additionally create `control-summary.json`, `control-hashes.json`, and `scopes/<scope_name>/...` subfolders.

`evidence.json` contains request metadata, normalized evidence records, and source metadata. `evidence.csv` contains a tabular view of the normalized records. `hashes.json` records SHA-256 hashes for generated evidence artifacts. `manifest.json` captures the run summary and file inventory.

## Hashing

The engine computes SHA-256 hashes after each evidence artifact is fully written. The manifest stores the hash algorithm and the hash values that were successfully generated during the run.

## Extension Notes

- Add new connectors by implementing `BaseCollector` and registering a lazy factory in `services/registry.py`.
- Add new storage targets by implementing `BaseStorageBackend`.
- Keep collector logic focused on fetch and normalization only. Artifact creation and storage should remain outside the connector.
