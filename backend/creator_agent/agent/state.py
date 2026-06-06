from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    target: dict[str, Any]
    step_count: int = 0
    tool_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
