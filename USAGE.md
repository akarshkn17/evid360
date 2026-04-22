# trace360 Usage Guide

This guide shows how to install, configure, and run `trace360` from the CLI or from Python.

## What `trace360` does

`trace360` collects evidence from a connector such as Jira, normalizes it into a shared evidence model, writes artifacts locally, computes SHA-256 hashes, builds a manifest, and optionally uploads those artifacts to bucket storage.

## Prerequisites

- Python 3.11+
- `uv`
- Valid credentials for the connector you want to use

## Install

From the project root:

```bash
uv sync --extra dev
```

This creates `.venv`, installs the package, and installs test dependencies.

## Configure Environment Variables

Create a local `.env` file from [.env.example](C:\Users\akars\Desktop\mydata\vibecoding\trace360\.env.example).

Example:

```env
APP_ENV=dev
LOG_LEVEL=INFO
DEFAULT_STORAGE_BACKEND=local
LOCAL_ARTIFACT_ROOT=.artifacts
HTTP_TIMEOUT_SECONDS=30
HTTP_MAX_RETRIES=3
JIRA_PAGE_SIZE=50

JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

GCP_PROJECT_ID=your-gcp-project-id
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

## CLI Usage

The CLI entrypoint is defined in [evidence_engine/cli.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\cli.py).

General shape:

```bash
uv run trace360 collect <connector> --query "<query>"
```

### Jira examples

Collect Jira evidence using both JSON and CSV output:

```bash
uv run trace360 collect jira --query "project = IT AND text ~ 'hardware' AND created >= -365d"
```

Collect Jira evidence and force explicit output formats:

```bash
uv run trace360 collect jira \
  --query "project = IT ORDER BY created DESC" \
  --format json \
  --format csv
```

Write artifacts to a custom directory:

```bash
uv run trace360 collect jira \
  --query "project = IT AND status != Done" \
  --output-dir custom-artifacts
```

Override the default page size:

```bash
uv run trace360 collect jira \
  --query "project = IT ORDER BY updated DESC" \
  --page-size 100
```

Request Jira expanded fields:

```bash
uv run trace360 collect jira \
  --query "project = IT AND labels = hardware" \
  --expand renderedFields
```

Use bucket storage instead of local-only output:

```bash
uv run trace360 collect jira \
  --query "project = IT" \
  --storage bucket
```

### GCP scaffold example

The GCP connector is intentionally minimal in v1. It currently returns basic project metadata so the connector contract is in place.

```bash
uv run trace360 collect gcp --query "project metadata snapshot"
```

## Jira Control YAML Usage

Jira controls can be defined as YAML files under [evidence_engine/controls/jira](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\controls\jira).

Each Jira control uses this shape:

```yaml
id: DISASTER_RECOVERY_PLAN_AND_REPORT
request_id: IDR-Req-027

name: Disaster recovery plan and report
description: Retrieve evidence of disaster recovery planning and reporting.

connector: jira
operation: search_issues

scope:
  jql: 'summary ~ "disaster recovery" OR summary ~ "DR report" ORDER BY updated DESC'

expected:
  minimum_results: 1

evidence:
  requires_screenshot: true
  severity: high
  category: disaster_recovery
```

Run one Jira control:

```bash
uv run trace360 collect-control evidence_engine\controls\jira\idr-req-027.yaml --storage local
```

Run the JSM Assets inventory control:

```bash
uv run trace360 collect-control evidence_engine\controls\jira\idr-req-007.yaml --storage local
```

For `IDR-Req-007`, update the YAML file for your Jira Service Management Assets configuration before running against your organization:

- `scope.schema_id`
- `scope.object_type_id`
- `scope.aql`
- optional `scope.workspace_id`

Run one Jira control and upload artifacts to GCS:

```bash
uv run trace360 collect-control evidence_engine\controls\jira\idr-req-027.yaml --storage bucket
```

The control command:

- loads the YAML file
- reads `scope.jql`
- calls the Jira connector
- writes normal evidence artifacts
- evaluates `expected.minimum_results`
- returns `passed: true` or `passed: false`

## CLI Options

Current supported options:

- `connector`: connector name such as `jira` or `gcp`
- `--query`: required connector query or task description
- `--format`: one or more output formats, currently `json` and `csv`
- `--storage`: `local` or `bucket`
- `--output-dir`: override the local artifact root
- `--expand`: connector-specific expanded fields
- `--page-size`: optional page size override

## CLI Output

Successful runs print a JSON summary to stdout.

Example shape:

```json
{
  "run_id": "f4dc76ca-0f92-49c4-bdbf-36d5f06ca0cd",
  "connector": "jira",
  "record_count": 42,
  "storage_backend": "local",
  "artifact_dir": "C:\\path\\to\\trace360\\.artifacts\\jira\\2026\\04\\20\\f4dc76ca-0f92-49c4-bdbf-36d5f06ca0cd",
  "artifacts": {
    "evidence.json": "C:\\path\\to\\evidence.json",
    "evidence.csv": "C:\\path\\to\\evidence.csv",
    "hashes.json": "C:\\path\\to\\hashes.json",
    "manifest.json": "C:\\path\\to\\manifest.json"
  }
}
```

## Python API Usage

The main engine entrypoint is [evidence_engine/engine.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\engine.py).

Basic example:

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

print(result.run_id)
print(result.record_count)
print(result.artifact_dir)
print(result.artifact_paths)
print(result.hashes)
```

Custom output directory:

```python
from evidence_engine.engine import EvidenceEngine
from evidence_engine.models import EvidenceRequest

engine = EvidenceEngine()
request = EvidenceRequest(
    connector="jira",
    query="project = IT ORDER BY created DESC",
    output_formats=["json"],
    storage_backend="local",
    output_dir="custom-artifacts",
)
result = engine.run(request)
```

## Artifact Layout

Artifacts are written to a deterministic directory:

```text
.artifacts/<connector>/<yyyy>/<mm>/<dd>/<run_id>/
```

Example:

```text
.artifacts/jira/2026/04/20/<run_id>/
├── evidence.json
├── evidence.csv
├── hashes.json
└── manifest.json
```

## Artifact Meanings

### `evidence.json`

Contains:

- request metadata
- run metadata
- normalized records
- source metadata
- raw records returned by the collector

### `evidence.csv`

Contains:

- flattened tabular evidence rows
- shared top-level evidence fields
- selected connector-specific attribute fields

If CSV output is not requested, this file is not created.

### `hashes.json`

Contains:

- the hash algorithm
- SHA-256 values for the evidence artifacts created earlier in the run

### `manifest.json`

Contains:

- run ID
- connector
- timestamp
- query
- artifact filenames
- record count
- storage backend
- hash algorithm
- hash values known at manifest creation time

`manifest.json` is written last so the run never reports a completed manifest before the other artifacts exist.

## Jira Notes

The Jira connector:

- authenticates with `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`
- uses JQL through the Jira search API
- paginates through all results
- fetches a focused default field set
- normalizes Jira issues into the shared evidence record shape

Default Jira fields include:

- issue key
- issue id
- summary
- description
- project
- issue type
- status
- priority
- assignee
- reporter
- creator
- labels
- components
- created
- updated
- resolution date
- due date

## Storage Notes

### Local storage

Local storage is the default backend. Artifact paths in the final run result point to the local files created during the run.

### Bucket storage

Bucket storage uploads the completed local artifacts after they are written and hashed successfully. For bucket mode, set at least:

- `GCS_BUCKET_NAME`
- `GOOGLE_APPLICATION_CREDENTIALS`

The returned storage locations use `gs://...` paths.

## Logging

Structured logging is configured centrally in [evidence_engine/logging_config.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\logging_config.py).

Important run events include:

- engine start
- connector selection
- fetch completion
- artifact writes
- hash generation
- storage start and completion
- final run completion

Each important log line includes `run_id` and `connector`.

## Troubleshooting

### Missing Jira credentials

If Jira env vars are missing, the run fails during Jira connector creation with a configuration error. Set:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

### Invalid JQL

If Jira rejects the query, the run fails with a `CollectionError` describing the invalid request.

### Bucket backend dependency issues

If you choose `--storage bucket` before dependencies are installed, or without cloud auth configured, the run fails clearly at storage backend initialization or upload time.

### Empty results

Empty collections are still valid runs. `evidence.json`, `hashes.json`, and `manifest.json` are still written. `evidence.csv` contains only the header row when CSV output is requested.

## Running Tests

From the project root:

```bash
uv run pytest
```

## Good Starting Points

If you want to inspect the implementation while using the guide, start with:

- [evidence_engine/cli.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\cli.py)
- [evidence_engine/engine.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\engine.py)
- [evidence_engine/connectors/jira/collector.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\connectors\jira\collector.py)
- [evidence_engine/artifacts/writer.py](C:\Users\akars\Desktop\mydata\vibecoding\trace360\evidence_engine\artifacts\writer.py)
