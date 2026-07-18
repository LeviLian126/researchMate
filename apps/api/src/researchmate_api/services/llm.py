from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from researchmate_api.config import Settings
from researchmate_api.observability import provider_observation


class ChatCompletionClient(Protocol):
    chat: Any


class ChatProvider(Protocol):
    def complete(self, messages: Iterable[dict[str, str]]) -> "LLMResult": ...


@dataclass(frozen=True)
class LLMChunk:
    kind: Literal["reasoning", "content"]
    text: str


@dataclass(frozen=True)
class LLMResult:
    content: str
    reasoning: str | None
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderRequestError(RuntimeError):
    def __init__(self, *, retryable: bool) -> None:
        super().__init__("LLM provider request failed")
        self.retryable = retryable


class NvidiaChatProvider:
    """OpenAI-compatible NVIDIA NIM chat adapter with explicit, bounded configuration."""

    def __init__(self, settings: Settings, client: ChatCompletionClient | None = None) -> None:
        if settings.llm_provider != "nvidia" or settings.nvidia_api_key is None:
            raise ProviderConfigurationError("NVIDIA chat provider is not configured")
        self.settings = settings
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                base_url=settings.nvidia_base_url,
                api_key=settings.nvidia_api_key.get_secret_value(),
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
        self.client = client

    def _request(self, messages: Iterable[dict[str, str]], *, stream: bool) -> Any:
        safe_messages = list(messages)
        try:
            with provider_observation(
                self.settings,
                name="nvidia.chat.completion",
                observation_type="generation",
                model=self.settings.nvidia_model,
                metadata={
                    "message_count": len(safe_messages),
                    "input_chars": sum(len(item.get("content", "")) for item in safe_messages),
                    "stream": stream,
                    "max_tokens": self.settings.llm_max_tokens,
                },
            ) as observation:
                response = self.client.chat.completions.create(
                    model=self.settings.nvidia_model,
                    messages=safe_messages,
                    temperature=self.settings.llm_temperature,
                    top_p=self.settings.llm_top_p,
                    max_tokens=self.settings.llm_max_tokens,
                    seed=self.settings.llm_seed,
                    stream=stream,
                )
                if not stream:
                    usage = getattr(response, "usage", None)
                    observation.update(
                        usage_details={
                            "input": int(getattr(usage, "prompt_tokens", 0) or 0),
                            "output": int(getattr(usage, "completion_tokens", 0) or 0),
                        }
                    )
                return response
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            retryable = isinstance(exc, (TimeoutError, ConnectionError)) or status_code in {
                408,
                409,
                429,
                500,
                502,
                503,
                504,
            }
            raise ProviderRequestError(retryable=retryable) from exc

    def complete(self, messages: Iterable[dict[str, str]]) -> LLMResult:
        completion = self._request(messages, stream=False)
        choices = getattr(completion, "choices", None) or []
        if not choices or getattr(choices[0], "message", None) is None:
            raise ValueError("LLM provider returned no completion choice")
        message = choices[0].message
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM provider returned empty content")
        reasoning = getattr(message, "reasoning_content", None)
        usage = getattr(completion, "usage", None)
        return LLMResult(
            content=content,
            reasoning=reasoning if isinstance(reasoning, str) and reasoning else None,
            model=str(getattr(completion, "model", self.settings.nvidia_model)),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

    def stream(self, messages: Iterable[dict[str, str]]) -> Iterator[LLMChunk]:
        for chunk in self._request(messages, stream=True):
            choices = getattr(chunk, "choices", None) or []
            if not choices or getattr(choices[0], "delta", None) is None:
                continue
            delta = choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning, str) and reasoning:
                yield LLMChunk(kind="reasoning", text=reasoning)
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                yield LLMChunk(kind="content", text=content)


def build_nvidia_chat_provider(settings: Settings) -> NvidiaChatProvider:
    return NvidiaChatProvider(settings)
