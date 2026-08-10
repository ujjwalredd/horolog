"""Schema-enforced extraction, across any LLM you can point it at.

Two providers, because the two wire formats are genuinely different — this is
not an abstraction invented for symmetry:

    openai      `response_format: {type: "json_schema", ...}`
                Ollama, vLLM, SGLang, llama.cpp, OpenAI, Groq, Together —
                anything speaking the OpenAI chat-completions shape.
    anthropic   `output_config: {format: {type: "json_schema", ...}}`
                via the official SDK. Anthropic is not OpenAI-compatible and
                a shim would be a second thing to keep correct.

In every case the schema is enforced *at decode time*: the server masks tokens
that would break the grammar, so malformed JSON is unrepresentable rather than
merely discouraged. That is the zero-hallucination guarantee's first layer.
Layers two and three are Pydantic validation below, and the fact that nothing
here can write to a calendar — see `solver/` for who actually places time.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from horolog.settings import settings


class ExtractionFailed(RuntimeError):
    """The model could not produce a valid object, even after a repair round."""


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON Schema, tightened for constrained decoding.

    Both providers reject schemas that allow unlisted keys, and OpenAI's strict
    mode additionally requires every property to be listed in `required` —
    optionality is expressed as a `null` union instead, which Pydantic already
    emits for `X | None`. Numeric and length bounds are dropped: neither engine
    supports them, and leaving them in gets the whole schema refused. Those
    bounds are still enforced — by the Pydantic model, one layer down.
    """
    schema = model.model_json_schema()

    def tighten(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for unsupported in (
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
                "minLength",
                "maxLength",
                "multipleOf",
                "minItems",
                "maxItems",
                "format",
            ):
                node.pop(unsupported, None)
            for value in node.values():
                tighten(value)
        elif isinstance(node, list):
            for item in node:
                tighten(item)

    tighten(schema)
    return schema


class Provider(Protocol):
    async def complete(self, system: str, user: str, schema: dict[str, Any], name: str) -> str:
        """Return a JSON string conforming to `schema`."""
        ...


class OpenAICompatible:
    """Ollama, vLLM, SGLang, llama.cpp, OpenAI, and anything else that speaks
    `/chat/completions`. Raw HTTP rather than the `openai` package: this is one
    POST, and a whole SDK to reach one endpoint earns nothing."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout: float) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._key = api_key
        self._timeout = timeout

    async def complete(self, system: str, user: str, schema: dict[str, Any], name: str) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": schema, "strict": True},
            },
            "temperature": 0,
        }
        # Local servers (Ollama, llama.cpp) take no key at all — an empty key
        # would still produce "Bearer " with nothing after it, which httpx's
        # header validation rejects outright before the request is even sent.
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            response = await http.post(self._url, json=body, headers=headers)
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])


class AnthropicProvider:
    """Claude via the official SDK.

    Anthropic spells structured output `output_config.format`, not
    `response_format` — the OpenAI-compatible path above cannot be pointed at it.
    """

    def __init__(self, model: str, api_key: str, timeout: float) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Anthropic provider selected but the SDK is missing. "
                "Install it with: pip install 'horolog[anthropic]'"
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key or None, timeout=timeout)
        self._model = model

    async def complete(self, system: str, user: str, schema: dict[str, Any], name: str) -> str:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if message.stop_reason == "refusal":
            raise ExtractionFailed("the model declined to answer")
        return "".join(block.text for block in message.content if block.type == "text")


def build_provider() -> Provider:
    cfg = settings()
    if cfg.llm_provider == "anthropic":
        return AnthropicProvider(cfg.llm_model, cfg.llm_api_key, cfg.llm_timeout_s)
    return OpenAICompatible(cfg.llm_base_url, cfg.llm_model, cfg.llm_api_key, cfg.llm_timeout_s)


async def extract[Model: BaseModel](
    schema_model: type[Model], system: str, user: str, provider: Provider | None = None
) -> Model:
    """Fill `schema_model` from `user` text, or raise.

    Grammar-constrained decoding guarantees the *shape*; it says nothing about
    whether the values make sense together. So the result is validated, and one
    repair round is offered with the validation error fed back — models correct
    a named field error reliably, and it costs one round trip. A second failure
    is surfaced rather than papered over, so the caller can fall back to a form.
    """
    provider = provider or build_provider()
    schema = strict_schema(schema_model)
    name = schema_model.__name__

    raw = await provider.complete(system, user, schema, name)
    try:
        return schema_model.model_validate_json(raw)
    except ValidationError as first:
        repair = (
            f"{user}\n\nYour previous answer was rejected:\n{first}\n"
            "Return a corrected object. Change only the invalid fields."
        )
        raw = await provider.complete(system, repair, schema, name)
        try:
            return schema_model.model_validate_json(raw)
        except ValidationError as second:
            raise ExtractionFailed(
                f"model could not produce a valid {name} after a repair round: {second}"
            ) from second
    except json.JSONDecodeError as exc:
        raise ExtractionFailed(f"provider returned non-JSON for {name}: {raw[:200]!r}") from exc
