from typing import Protocol


class ProviderError(RuntimeError):
    """Safe, user-facing provider error without credential disclosure."""


class ModelProvider(Protocol):
    def generate(self, prompt: str, instructions: str = "") -> str: ...
