"""Minimal OpenAI Responses API adapter using only the Python standard library."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.providers.base import ProviderError


class OpenAIResponsesProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 30):
        key = os.getenv("OPENAI_API_KEY", "") if api_key is None else api_key
        selected_model = os.getenv("AGENT_MODEL", "gpt-6-luna") if model is None else model
        self.api_key = key.strip()
        self.model = selected_model.strip()
        self.timeout = timeout
        if not self.model:
            raise ValueError("Model name must not be empty.")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

    def generate(self, prompt: str, instructions: str = "") -> str:
        if not prompt.strip():
            raise ValueError("Prompt must not be empty.")
        external_enabled = os.getenv("AGENT_EXTERNAL_PROVIDER_ENABLED", "").strip().lower() == "true"
        cost_approved = os.getenv("AGENT_PAID_PROVIDER_COST_APPROVED", "").strip().lower() == "true"
        if not (external_enabled and cost_approved):
            raise ProviderError(
                "External provider is disabled. Explicit provider opt-in and paid-cost approval are both required."
            )
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured. Add it to the runtime environment.")

        payload = {"model": self.model, "input": prompt, "max_output_tokens": 600}
        if instructions.strip():
            payload["instructions"] = instructions.strip()
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ProviderError(f"OpenAI API returned HTTP {exc.code}. Check model access and API billing.") from None
        except URLError:
            raise ProviderError("Could not reach the OpenAI API. Check network connectivity.") from None
        except TimeoutError:
            raise ProviderError("The OpenAI API request timed out.") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("The OpenAI API returned an invalid response.") from None

        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        chunks = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                        chunks.append(content["text"])
        result = "\n".join(chunks).strip()
        if not result:
            raise ProviderError("The model response did not contain text output.")
        return result
