"""Deterministic built-in provider; makes no network or paid API calls."""

from core.providers.base import ModelProvider


class RuleBasedProvider:
    """A small offline provider for safe task planning."""

    def generate(self, prompt: str, instructions: str = "") -> str:
        task = prompt.strip()
        if not task:
            raise ValueError("Prompt must not be empty.")

        return "\n".join(
            [
                "### Free task plan",
                "",
                f"**Task:** {task}",
                "",
                "1. Define the expected result and constraints.",
                "2. Inspect the relevant files and project state.",
                "3. Prepare the smallest safe change.",
                "4. Run focused tests and inspect their results.",
                "5. Record evidence and the next checkpoint.",
                "",
                "**Safety:** This built-in planner does not access the network, call an AI API, "
                "run shell commands, or modify external projects.",
                "",
                "**Note:** This is deterministic planning logic, not a generative language model.",
            ]
        )
