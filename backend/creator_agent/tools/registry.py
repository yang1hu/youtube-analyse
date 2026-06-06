from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, handler: Callable[..., Any]) -> None:
        self._tools[name] = ToolDefinition(name=name, description=description, handler=handler)

    def names(self) -> list[str]:
        return list(self._tools)

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(name)

        return self._tools[name].handler(**kwargs)
