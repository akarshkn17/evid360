from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from evidence_engine.controls.models import ControlDefinition
from evidence_engine.exceptions import ControlError


def load_control(path: Path | str) -> ControlDefinition:
    control_path = Path(path)
    if not control_path.exists():
        raise ControlError(f"Control file not found: {control_path}")

    try:
        payload = yaml.safe_load(control_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ControlError(f"Invalid YAML in control file {control_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ControlError(f"Control file must contain a YAML mapping: {control_path}")

    try:
        return ControlDefinition(**payload)
    except ValidationError as exc:
        raise ControlError(f"Invalid control definition in {control_path}: {exc}") from exc


def load_controls(directory: Path | str, connector: str | None = None) -> list[ControlDefinition]:
    control_dir = Path(directory)
    if not control_dir.exists():
        raise ControlError(f"Control directory not found: {control_dir}")

    controls = [load_control(path) for path in sorted(control_dir.glob("*.yaml"))]
    if connector:
        controls = [control for control in controls if control.connector == connector]
    return controls

