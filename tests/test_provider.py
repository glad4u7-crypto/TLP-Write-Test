import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from core.brain import AIBrain
from core.providers.openai_responses import OpenAIResponsesProvider, ProviderError


def test_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AGENT_PAID_PROVIDER_COST_APPROVED", "true")
    provider = OpenAIResponsesProvider(api_key="")
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        provider.generate("Hello")


def test_provider_rejects_empty_prompt():
    provider = OpenAIResponsesProvider(api_key="test-key")
    with pytest.raises(ValueError, match="Prompt"):
        provider.generate("  ")


def test_provider_extracts_output_text(monkeypatch):
    monkeypatch.setenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AGENT_PAID_PROVIDER_COST_APPROVED", "true")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"output_text": "Hello from model"}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("core.providers.openai_responses.urlopen", fake_urlopen)
    provider = OpenAIResponsesProvider(api_key="secret-test", model="gpt-test", timeout=12)
    assert provider.generate("Hi", "Be concise") == "Hello from model"
    assert captured["url"].endswith("/v1/responses")
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["payload"]["instructions"] == "Be concise"
    assert captured["authorization"] == "Bearer secret-test"
    assert captured["timeout"] == 12


def test_provider_extracts_nested_output(monkeypatch):
    monkeypatch.setenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AGENT_PAID_PROVIDER_COST_APPROVED", "true")
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"output": [{"type": "message", "content": [{"type": "output_text", "text": "Nested answer"}]}]}).encode()
    monkeypatch.setattr("core.providers.openai_responses.urlopen", lambda *args, **kwargs: FakeResponse())
    assert OpenAIResponsesProvider(api_key="key").generate("Hi") == "Nested answer"


def test_provider_sanitizes_http_error(monkeypatch):
    monkeypatch.setenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("AGENT_PAID_PROVIDER_COST_APPROVED", "true")
    def fail(*args, **kwargs):
        raise HTTPError("https://api.openai.com", 401, "Unauthorized", {}, BytesIO(b"secret"))
    monkeypatch.setattr("core.providers.openai_responses.urlopen", fail)
    with pytest.raises(ProviderError, match="HTTP 401") as error:
        OpenAIResponsesProvider(api_key="key").generate("Hi")
    assert "secret" not in str(error.value)


def test_brain_uses_provider_and_rejects_blank_message():
    class FakeProvider:
        def generate(self, prompt, instructions=""):
            assert prompt == "Plan this project"
            assert "explicit approval" in instructions
            return "A safe plan"
    brain = AIBrain(FakeProvider())
    assert brain.respond(" Plan this project ") == "A safe plan"
    with pytest.raises(ValueError):
        brain.respond(" ")



def test_provider_is_disabled_without_both_explicit_opt_ins(monkeypatch):
    monkeypatch.delenv("AGENT_EXTERNAL_PROVIDER_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_PAID_PROVIDER_COST_APPROVED", raising=False)

    def unexpected_network_call(*args, **kwargs):
        pytest.fail("Network call must not happen while provider is disabled.")

    monkeypatch.setattr("core.providers.openai_responses.urlopen", unexpected_network_call)
    provider = OpenAIResponsesProvider(api_key="test-key")
    with pytest.raises(ProviderError, match="provider is disabled"):
        provider.generate("Hello")


def test_provider_requires_cost_approval_even_when_enabled(monkeypatch):
    monkeypatch.setenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "true")
    monkeypatch.delenv("AGENT_PAID_PROVIDER_COST_APPROVED", raising=False)

    def unexpected_network_call(*args, **kwargs):
        pytest.fail("Network call must not happen without cost approval.")

    monkeypatch.setattr("core.providers.openai_responses.urlopen", unexpected_network_call)
    provider = OpenAIResponsesProvider(api_key="test-key")
    with pytest.raises(ProviderError, match="cost approval"):
        provider.generate("Hello")
