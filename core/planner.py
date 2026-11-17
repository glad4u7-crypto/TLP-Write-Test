from core.models import Task

def create_plan(task: Task) -> list[str]:
    if not task.description.strip():
        raise ValueError("Cannot plan an empty task.")
    return [
        "Clarify the desired outcome and constraints.",
        "Inspect relevant project context and available tools.",
        "Prepare a proposed change or result.",
        "Run appropriate checks and report evidence.",
    ]
