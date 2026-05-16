import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, create_model

from core.config import settings

log = logging.getLogger(__name__)


def override_field_descriptions_from_schema(
    base_model: type[BaseModel],
    args_schema: dict[str, Any],
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for name, field in base_model.model_fields.items():
        annotation = field.annotation or Any
        default = field.default if not field.is_required() else ...
        description = field.description
        spec = args_schema.get(name) if isinstance(args_schema, dict) else None
        if isinstance(spec, dict):
            configured_description = spec.get("description")
            if (
                isinstance(configured_description, str)
                and configured_description.strip()
            ):
                description = configured_description
        fields[name] = (annotation, Field(default, description=description))
    return create_model(base_model.__name__, **fields)  # type: ignore[arg-type]


def _load_config() -> dict[str, Any]:
    config_path = Path(settings.AGENT_CONFIG_PATH)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        log.warning("Config file not found at %s", config_path)
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}
    except Exception as exc:
        log.error("Error loading config file: %s", exc)
        return {}


def get_tool_config(tool_name: str) -> dict[str, Any]:
    for tool_config in _load_config().get("tools", []):
        if tool_config.get("name") == tool_name:
            return tool_config
    return {}
