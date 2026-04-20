# agents.md

## Objective

Build a **simple, extensible evidence collection engine** that can collect evidence from multiple services such as **Jira** and **GCP**, store the collected evidence as **JSON and CSV**, and generate **file hashes** for integrity verification.

The project must be designed so that:

- collectors are reusable and independent
- evidence orchestration is separate from source-specific logic
- the system can be called from:
  - a CLI script
  - another Python program
  - a future agent-based workflow
- storage can be switched between:
  - local filesystem for development and testing
  - cloud bucket storage for later use
- the first implemented connector should be **Jira**, using the existing reference repo only as guidance, not as something to copy blindly

Keep the implementation **small, clean, and production-minded**. Do not overengineer.

---

## What to Build

Create a Python project named `trace360` with a package called `evidence_engine`.

The engine should support this flow:

1. A user runs a CLI command or calls a Python API.
2. The request contains:
   - connector name, for example `jira`
   - a query or task description
   - output destination settings
3. The engine routes the request to the correct collector.
4. The collector fetches raw data from the source system.
5. The data is normalized into a common evidence structure.
6. The engine writes artifacts as:
   - `*.json`
   - `*.csv` when tabular output is possible
7. The engine computes SHA-256 hashes for each artifact.
8. The engine writes a manifest file containing metadata and hashes.
9. The engine stores artifacts using the configured storage backend:
   - local filesystem first
   - bucket storage through a separate backend interface

---

## Scope for First Version

Implement only what is necessary for a clean v1.

### Required in v1

- core evidence engine
- pluggable connector interface
- Jira connector
- placeholder or minimal GCP connector scaffold
- local storage backend
- cloud bucket storage backend abstraction
- JSON artifact output
- CSV artifact output
- SHA-256 hashing
- manifest generation
- CLI entrypoint
- Python API entrypoint
- configuration via environment variables
- structured logging
- basic tests

### Explicitly avoid in v1

Do **not** build these unless absolutely needed:

- frontend UI
- MCP server
- agent framework inside the project
- workflow engine
- message queue
- database
- plugin auto-discovery magic
- overly generic abstractions
- asynchronous distributed architecture
- Kubernetes deployment logic

This project is an **evidence collector library + CLI**, not a full platform.

---

## Recommended Design

Use a simple layered design.

### 1. Connector layer
Each connector knows how to fetch data from one source.

Examples:
- Jira collector
- GCP collector later

Each connector should:
- accept a typed request object
- return normalized evidence records plus raw metadata
- not write files directly
- not know whether storage is local or cloud

### 2. Engine layer
The engine coordinates the run.

Responsibilities:
- validate input
- choose connector
- invoke collector
- normalize output shape
- serialize artifacts
- hash files
- create manifest
- send artifacts to configured storage backend
- return a run summary

### 3. Storage layer
Storage must be swappable.

Implement:
- `LocalStorageBackend`
- `BucketStorageBackend`

The storage layer should only deal with saving already-created artifacts.

### 4. CLI/API layer
Provide:
- a CLI for human use
- a Python API for scripts or agent callers

The CLI should be thin and simply call the engine.

---

## Recommended Project Structure

Use this simplified structure:

```text
trace360/
├── evidence_engine/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── logging_config.py
│   ├── engine.py
│   ├── models.py
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── jira/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── collector.py
│   │   │   └── normalize.py
│   │   └── gcp/
│   │       ├── __init__.py
│   │       ├── collector.py
│   │       └── normalize.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── local.py
│   │   └── bucket.py
│   ├── artifacts/
│   │   ├── __init__.py
│   │   ├── writer.py
│   │   ├── hashing.py
│   │   └── manifest.py
│   └── services/
│       ├── __init__.py
│       └── registry.py
├── tests/
│   ├── test_engine.py
│   ├── test_hashing.py
│   ├── test_manifest.py
│   └── test_jira_normalize.py
├── .env.example
├── README.md
├── pyproject.toml
└── uv.lock
```

---

## Why This Structure

Use this structure because it keeps responsibilities clear:

- `connectors/` = source-specific fetch logic
- `storage/` = where artifacts go
- `artifacts/` = serialization, hashes, manifest creation
- `engine.py` = orchestration only
- `cli.py` = thin command layer
- `models.py` = shared typed contracts

Do **not** mix storage logic inside collectors.
Do **not** mix hashing logic inside connectors.
Do **not** let the CLI contain business logic.

---

## Design Review of the Proposed Structure

Your current structure is heading in the right direction, but it should be simplified.

### Good parts in your draft

- `connectors` folder is the correct idea
- `core` for shared logic is reasonable
- keeping `cli.py` at package root is fine
- separating Jira and GCP connectors is good
- `.env.example`, `README.md`, and `pyproject.toml` are correct

### Changes recommended

1. Rename `core/runner.py` to `engine.py`
   - clearer and simpler

2. Move hashing into an `artifacts/` area instead of generic `core/`
   - hashing belongs to artifact handling

3. Add a dedicated `storage/` package
   - local vs bucket storage should not live inside collectors

4. Add `config.py` and `logging_config.py`
   - keep configuration and logging setup centralized

5. Avoid `controls/` in v1 unless you are actually building compliance control definitions now
   - if those YAML files are only examples, they can stay under `examples/` or `samples/`
   - otherwise they distract from the engine itself

6. Add a connector `base.py`
   - all collectors should follow one interface

7. Keep normalization separate from collection
   - `collector.py` fetches
   - `normalize.py` transforms

### Recommendation on `controls/`

For v1, **remove `controls/` from the main build scope** unless you already need control-driven execution. Build a clean engine first. Control mapping can be added later.

---

## Functional Requirements

### Common behavior

The engine must support a request like:

- connector: `jira`
- task: `fetch all jira tickets related to hardware from past 365 days`
- output formats: `json,csv`
- storage backend: `local` or `bucket`

The result should produce:

- normalized records
- JSON artifact
- CSV artifact when possible
- manifest JSON
- SHA-256 hash values for each file
- final run summary returned to the caller

### Jira connector requirements

Implement Jira first.

The Jira connector should:
- authenticate using environment variables
- support JQL-based search
- fetch issue lists
- fetch key issue fields needed for evidence
- normalize issues into flat records suitable for CSV
- preserve raw response data in JSON output where useful
- handle pagination safely
- handle API failures clearly
- use timeouts and retries

Suggested Jira env vars:
- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

### GCP connector requirements

For v1, the GCP connector can be a scaffold or very minimal collector.

Possible minimal example:
- collect bucket metadata
- or collect project-level metadata

Do not build too much here yet.

---

## Artifact Requirements

For each run, create a deterministic artifact folder structure like:

```text
.artifacts/<connector>/<yyyy>/<mm>/<dd>/<run_id>/
```

Example output:

```text
.artifacts/jira/2026/04/20/<run_id>/
├── evidence.json
├── evidence.csv
├── manifest.json
└── hashes.json
```

### `evidence.json`
Should contain:
- request metadata
- normalized records
- optional raw source metadata

### `evidence.csv`
Should contain:
- flattened tabular version of normalized records

### `manifest.json`
Should contain:
- run ID
- connector name
- timestamp
- query/task text
- artifact file names
- record count
- storage backend used
- hash algorithm
- hashes for each artifact

### Hashing
Use:
- SHA-256 only

Hash every generated artifact file after writing it.

---

## Python API Shape

Provide a simple Python API.

Example target usage:

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

---

## CLI Requirements

Use `Typer` or `argparse`. Prefer `Typer` for simplicity and readability.

Target CLI examples:

```bash
uv run trace360 collect jira --query "project = IT AND text ~ 'hardware' AND created >= -365d"
```

Optional flags:

```bash
--format json
--format csv
--storage local
--output-dir .artifacts
```

The CLI should:
- validate arguments
- call the engine
- print a concise summary
- exit with proper non-zero codes on failure

---

## Coding Standards

Follow these implementation rules strictly.

### General
- Use Python 3.11+
- Use `uv` for dependency management
- Use type hints throughout
- Use small focused modules
- Prefer explicit code over clever abstractions
- Keep functions short and readable
- Avoid global mutable state

### Validation and models
- Use `pydantic` models for request and result objects
- validate config early at startup

### HTTP
- Use `httpx`
- set explicit timeout values
- add retry logic for transient errors
- surface clear error messages

### Logging
- use structured logging
- include `run_id` in all important log lines
- log start, end, duration, connector, record count, storage target, and failures
- never log secrets

### Error handling
- create a small exception hierarchy
- fail loudly and clearly
- do not swallow exceptions silently

### Security
- do not hardcode credentials
- read secrets from environment variables
- keep `.env.example` safe and minimal
- do not log tokens
- do not write secrets into artifacts

---

## Logging Expectations

Every run should log at least:

- engine start
- selected connector
- request summary
- fetch start
- fetch success/failure
- artifact write start/end
- hash generation
- storage upload start/end
- final run summary

Use JSON-style structured logs so they are easy to parse later.

---

## Testing Requirements

Create a small but meaningful test suite.

Must include tests for:
- hash generation
- manifest generation
- CSV writing
- engine orchestration using mocked connector/storage
- Jira normalization logic
- config validation

Avoid fragile integration tests unless clearly marked.

---

## README Requirements

Write a clean README with:

1. project purpose
2. architecture overview
3. folder structure
4. setup with `uv`
5. environment variables
6. example CLI usage
7. example Python API usage
8. artifact output explanation
9. hashing explanation
10. future extension notes

---

## `.env.example` Requirements

Include only safe placeholder values such as:

```env
APP_ENV=dev
LOG_LEVEL=INFO
DEFAULT_STORAGE_BACKEND=local
LOCAL_ARTIFACT_ROOT=.artifacts

JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

GCP_PROJECT_ID=your-gcp-project-id
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

---


---

## Jira Fetching Features to Implement in v1

The Jira connector should implement these practical features for evidence collection:

- JQL-based issue search
- pagination support across all results
- configurable page size
- fetch only required fields by default for efficiency
- optional inclusion of selected expanded fields when needed
- normalization of Jira issues into a common evidence model
- flattening of nested Jira fields for CSV output
- preservation of key raw source metadata in JSON output
- request metadata capture, including source, query, run time, and fetch timestamp
- retry with backoff for transient HTTP failures
- explicit timeout configuration
- safe authentication through environment variables
- clear handling of empty-result collections
- consistent error messages for invalid JQL, auth failure, permission issues, and rate limiting
- deterministic artifact naming and folder layout
- SHA-256 hashing for JSON, CSV, and manifest outputs
- local storage backend support
- bucket storage backend support through the common storage interface

### Minimum Jira fields to fetch and normalize

Fetch a practical default set of Jira fields such as:

- issue key
- issue id
- summary
- description when available
- project key / project name
- issue type
- status
- priority
- assignee
- reporter
- creator when available
- labels
- components
- created
- updated
- resolved
- due date when available

Do not fetch every field by default. Keep the first version efficient and predictable.

---

## Important Technical Refinements

These must be implemented explicitly.

### 1. Connector Registry must use lazy loading

In `services/registry.py`, implement a **lazy-loading factory pattern**.

Requirements:
- do not import or initialize all connectors at engine startup
- only construct the requested connector when `request.connector` is selected
- connector-specific configuration must only be validated when that connector is requested
- this prevents unused connectors like GCP from failing due to missing credentials during a Jira-only run

Preferred pattern:
- registry maps connector names to lightweight factory callables
- engine asks registry for a connector instance only when needed

Example shape:

```python
class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories = {
            "jira": lambda: JiraCollector(),
            "gcp": lambda: GcpCollector(),
        }

    def get(self, name: str) -> BaseCollector:
        try:
            return self._factories[name]()
        except KeyError as exc:
            raise UnsupportedConnectorError(name) from exc
```

### 2. Normalization must follow a shared contract

In `models.py`, define a `BaseEvidenceRecord` model that all connector normalizers must produce.

Purpose:
- make JSON output consistent
- make CSV columns predictable
- avoid source-specific column names leaking into audit artifacts

At minimum, the normalized model should contain common fields such as:

- `evidence_id`
- `source_system`
- `record_type`
- `title`
- `status`
- `created_at`
- `updated_at`
- `owner`
- `tags`
- `raw_ref`
- `collected_at`

Connector-specific values should be mapped into these fields.
Examples:
- Jira `key` -> `evidence_id`
- GCP `resource_id` -> `evidence_id`

If additional source-specific fields are needed, allow an `attributes: dict[str, Any]` field for extra normalized metadata.
For CSV output:
- keep top-level common columns stable
- flatten selected `attributes` fields only when they are explicitly approved for tabular output

### 3. Writes must be atomic and manifest must be written last

The storage/artifact flow must guarantee consistency.

Rules:
- write `evidence.json` first
- write `evidence.csv` second when requested
- compute hashes only after each file is fully written
- write `hashes.json` only after evidence artifacts exist
- write `manifest.json` last

Why:
- if the run crashes halfway, there must never be a manifest claiming files exist when they do not

Implementation expectations:
- write to temporary files first, then atomically rename into final paths
- only include files in the manifest that were successfully written and hashed
- if upload to bucket storage is enabled, upload artifacts only after local atomic creation succeeds
- the manifest should reflect the final successful state of the run

Recommended local write pattern:

```python
with tempfile.NamedTemporaryFile(delete=False, dir=target_dir) as tmp:
    tmp.write(payload_bytes)
    tmp.flush()
    os.fsync(tmp.fileno())

os.replace(tmp.name, final_path)
```

---

## Implementation Notes for Codex

When building v1, prioritize this sequence:

1. shared models and exceptions
2. connector base interface
3. lazy connector registry
4. artifact writers with atomic local writes
5. hashing and manifest generation
6. local storage backend
7. Jira client and Jira collector
8. Jira normalizer to shared evidence model
9. CLI and Python API
10. tests

Do not build the GCP connector fully before Jira is working end-to-end.

## Dependencies

Keep dependencies minimal.

Suggested dependencies:
- `pydantic`
- `httpx`
- `typer`
- `python-dotenv`
- `google-cloud-storage`
- `pytest`

Optional:
- `structlog`

Do not add heavy frameworks unless there is a real need.

---

## Implementation Sequence

Build in this order:

1. project scaffolding
2. config and logging
3. shared models
4. connector base interface
5. storage base interface
6. local storage backend
7. artifact writer + hashing + manifest
8. core engine orchestration
9. Jira client + collector + normalization
10. CLI wiring
11. tests
12. README polish
13. minimal GCP scaffold

---

## Non-Goals

These are not part of the first build:

- natural-language to JQL conversion inside this project
- built-in agent orchestration
- web UI
- multi-tenant architecture
- distributed processing
- database-backed run history
- advanced control-policy engine

The project should be ready to be **called by an external agent later**, but should not embed that complexity now.

---

## Quality Bar

The final code should feel like:
- simple to understand
- easy to extend
- safe with credentials
- clear in logs
- testable
- reusable from scripts or future agents

If there is a choice between a fancy abstraction and a clear implementation, choose the clear implementation.

---

## Final Instruction to Codex

Generate the project as a clean Python package using `uv`.

Prioritize:
- correctness
- readability
- simple architecture
- structured logging
- strong typing
- minimal dependencies
- clean separation of connectors, engine, storage, and artifacts

Do not overbuild. Deliver a working v1 that supports:
- Jira evidence collection
- JSON and CSV artifacts
- SHA-256 hashing
- local storage
- bucket storage abstraction
- CLI + Python API usage

