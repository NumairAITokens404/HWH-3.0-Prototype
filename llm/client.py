"""Small Ollama HTTP client with bounded output and typed failure reasons."""

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from config import Settings
from schemas.llm import LLMProposal


class LLMError(RuntimeError):
    pass


class StructuredLLM(Protocol):
    model: str
    def generate(self, messages: list[dict[str, str]]) -> LLMProposal: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.llm_model
        self._opener = build_opener(_NoRedirect)

    def _request(self, path: str, payload: dict | None = None) -> dict:
        request = Request(self.settings.llm_base_url + path,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=self.settings.llm_timeout) as response:
                raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise LLMError("response_too_large")
            body = json.loads(raw)
            if not isinstance(body, dict) or body.get("error"):
                raise LLMError("invalid_server_response")
            return body
        except HTTPError as exc:
            raise LLMError(f"http_{exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise LLMError("connection_failed_or_timeout") from None
        except (ValueError, UnicodeError):
            raise LLMError("invalid_server_json") from None

    def check(self) -> dict:
        models = self._request("/api/tags").get("models", [])
        if not any(item.get("name") == self.model for item in models):
            raise LLMError("model_not_installed")
        return {"model": self.model, "installed": True}

    def generate(self, messages: list[dict[str, str]]) -> LLMProposal:
        # Refuse oversized evidence rather than let Ollama silently truncate it.
        if sum(len(item["content"].encode()) for item in messages) > self.settings.llm_context * 3:
            raise LLMError("prompt_budget_exceeded")
        body = self._request("/api/chat", {
            "model": self.model, "messages": messages,
            "format": LLMProposal.model_json_schema(), "stream": False, "think": False,
            "keep_alive": "5m", "options": {
                "num_ctx": self.settings.llm_context, "num_predict": self.settings.llm_max_tokens,
                "temperature": 0, "seed": 42,
            },
        })
        if not body.get("done") or body.get("done_reason") == "length":
            raise LLMError("incomplete_generation")
        try:
            return LLMProposal.model_validate_json(body["message"]["content"])
        except (KeyError, TypeError, ValueError):
            raise LLMError("invalid_proposal") from None


def create_llm(settings: Settings) -> StructuredLLM | None:
    return OllamaClient(settings) if settings.llm_provider == "ollama" else None
