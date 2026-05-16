import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from core.config import settings

log = logging.getLogger(__name__)


class ModelFactory:
    """Factory for creating chat model instances from YAML config."""

    def __init__(self, model_configs: list[dict[str, Any]]):
        self._models: dict[str, BaseChatModel] = {}
        self._configs = {cfg["name"]: cfg for cfg in model_configs}

    def get_model(self, name: str) -> BaseChatModel:
        if name not in self._models:
            if name not in self._configs:
                raise ValueError(f"Model with name '{name}' is not defined.")

            config = self._configs[name]
            provider = config.get("provider")
            parameters = dict(config.get("parameters", {}) or {})

            if provider != "openai":
                raise ValueError(
                    f"Unsupported provider '{provider}' for model '{name}'."
                )

            from langchain_openai import ChatOpenAI

            if settings.OPENAI_API_KEY and "api_key" not in parameters:
                parameters["api_key"] = settings.OPENAI_API_KEY

            log.info("Creating model instance: %s", name)
            self._models[name] = ChatOpenAI(**parameters)

        return self._models[name]
