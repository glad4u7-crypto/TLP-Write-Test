"""Metadata-only allow-list for APAA tools.

This module deliberately does not load plugins, import handlers, or execute tools.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    name: str
    description: str
    category: str
    read_only: bool
    requires_approval: bool = True
    enabled: bool = False

    def __post_init__(self) -> None:
        for field_name in ("tool_id", "name", "description", "category"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty.")
        if self.enabled:
            raise ValueError("Tool execution cannot be enabled in this registry.")
        if self.read_only and self.requires_approval:
            # Conservative default is acceptable; approval may still be required.
            return


class ToolRegistry:
    """In-memory catalog; registration never makes a tool executable."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not isinstance(spec, ToolSpec):
            raise TypeError("Only ToolSpec entries may be registered.")
        if spec.tool_id in self._tools:
            raise ValueError("Tool ID is already registered.")
        self._tools[spec.tool_id] = spec

    def get(self, tool_id: str) -> ToolSpec | None:
        return self._tools.get(tool_id)

    def list_tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools[key] for key in sorted(self._tools))


def build_default_registry() -> ToolRegistry:
    """Return documented capability metadata; no handlers are attached."""
    registry = ToolRegistry()
    entries = (
        ToolSpec(
            "repository.inspect_zip",
            "Inspect repository ZIP",
            "Read-only, bounded inspection of a user-uploaded ZIP archive.",
            "local_read",
            read_only=True,
            requires_approval=False,
        ),
        ToolSpec(
            "web.search",
            "Search public web",
            "Search public pages; browser execution is currently unavailable.",
            "external_read",
            read_only=True,
            requires_approval=True,
        ),
        ToolSpec(
            "browser.navigate",
            "Navigate browser",
            "Open a user-approved destination after browser security qualification.",
            "external_read",
            read_only=True,
            requires_approval=True,
        ),
        ToolSpec(
            "file.modify",
            "Modify a file",
            "Potentially changes user-controlled file contents.",
            "local_mutation",
            read_only=False,
            requires_approval=True,
        ),
    )
    for entry in entries:
        registry.register(entry)
    return registry
