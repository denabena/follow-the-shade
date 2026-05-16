import importlib.util
import inspect
import logging
import os
from typing import Any

from langchain_core.tools import BaseTool

log = logging.getLogger(__name__)


class ToolRegistry:
    """Discover and instantiate LangChain tools under src/tools."""

    def __init__(self, dependencies: dict[str, Any], agents: list[dict[str, Any]]):
        self.agents = agents
        self.dependencies = dependencies
        self._tool_classes = self._discover_tool_classes()
        self._tool_cache: dict[str, BaseTool] = {}

    def _discover_tool_classes(self) -> dict[str, Any]:
        tools_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "tools")
        )
        if not os.path.isdir(tools_dir):
            log.warning("Tool directory '%s' not found.", tools_dir)
            return {}

        tool_classes: dict[str, Any] = {}
        for root, dirs, files in os.walk(tools_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for filename in files:
                if not filename.endswith(".py") or filename == "__init__.py":
                    continue

                rel_path = os.path.relpath(os.path.join(root, filename), tools_dir)
                module_name = (
                    f"tools.{os.path.splitext(rel_path)[0].replace(os.sep, '.')}"
                )
                module_path = os.path.join(root, filename)
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, module_path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for item_name in dir(module):
                        item = getattr(module, item_name)
                        if (
                            inspect.isclass(item)
                            and issubclass(item, BaseTool)
                            and item is not BaseTool
                        ):
                            tool_name = self._get_tool_name(item)
                            if tool_name:
                                tool_classes[tool_name] = item
                        elif isinstance(item, BaseTool):
                            tool_classes[item.name] = item
                except Exception as exc:
                    log.error(
                        "Error discovering tool classes in '%s': %s", module_path, exc
                    )
        return tool_classes

    def _get_tool_name(self, cls: type) -> str | None:
        value = cls.__dict__.get("name")
        if isinstance(value, str) and value:
            return value

        fields = getattr(cls, "model_fields", None)
        if fields and "name" in fields:
            default = fields["name"].default
            if isinstance(default, str) and default:
                return default
        return None

    def get_tool(self, name: str) -> BaseTool | None:
        if name in self._tool_cache:
            return self._tool_cache[name]
        if name not in self._tool_classes:
            return None

        tool_class = self._tool_classes[name]
        if isinstance(tool_class, BaseTool):
            self._tool_cache[name] = tool_class
            return tool_class

        try:
            signature = inspect.signature(tool_class.__init__)
            params = [
                p
                for p in signature.parameters.values()
                if p.name != "self"
                and p.kind
                not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            ]
            kwargs = {
                p.name: self.dependencies[p.name]
                for p in params
                if p.name in self.dependencies
            }
            missing = [
                p.name
                for p in params
                if p.default is inspect._empty and p.name not in kwargs
            ]
            if missing:
                log.warning(
                    "Tool '%s' missing required deps: %s. Available: %s",
                    name,
                    missing,
                    list(self.dependencies.keys()),
                )
                return None

            tool = tool_class(**kwargs)
            self._tool_cache[name] = tool
            return tool
        except Exception as exc:
            log.error("Error initializing tool '%s': %s", name, exc)
            return None

    async def initialize_async_tools(self) -> None:
        for tool_name, tool in self._tool_cache.items():
            initializer = getattr(tool, "ainitialize", None)
            if initializer is None:
                continue
            log.info("Initializing tool '%s'.", tool_name)
            await initializer()

    async def shutdown_async_tools(self) -> None:
        for tool_name, tool in self._tool_cache.items():
            closer = getattr(tool, "aclose", None)
            if closer is None:
                continue
            log.info("Closing tool '%s'.", tool_name)
            await closer()
