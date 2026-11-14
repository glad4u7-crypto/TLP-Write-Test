import pytest

from core.brain import AIBrain
from core.providers.rule_based import RuleBasedProvider


def test_rule_based_provider_creates_plan_without_network():
    result = RuleBasedProvider().generate("Review the repository")
    assert "Review the repository" in result
    assert "does not access the network" in result


def test_rule_based_provider_rejects_empty_prompt():
    with pytest.raises(ValueError, match="Prompt"):
        RuleBasedProvider().generate("  ")


def test_brain_works_with_free_provider():
    result = AIBrain(RuleBasedProvider()).respond("Prepare a test plan")
    assert "Free task plan" in result
    assert "Prepare a test plan" in result
