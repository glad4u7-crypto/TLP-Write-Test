"""AI Brain orchestration layer; delegates language generation to a provider."""
from core.providers.openai_responses import ModelProvider


class AIBrain:
    def __init__(self, provider: ModelProvider):
        self.provider = provider

    def respond(self, user_message: str) -> str:
        if not user_message.strip():
            raise ValueError("Message must not be empty.")
        return self.provider.generate(
            user_message.strip(),
            instructions=(
                "You are the planning brain of a general-purpose development agent. "
                "Help the user reason, plan, inspect, and explain. Do not claim to have "
                "executed tools or changed files. Clearly identify actions that require "
                "explicit approval. Be concise and factual."
            ),
        )
