from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from researchmate_api.config import Settings
from researchmate_api.services.llm import (
    NvidiaChatProvider,
    ProviderConfigurationError,
    ProviderRequestError,
)


class FakeCompletions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeClient:
    def __init__(self, response: object) -> None:
        self.completions = FakeCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)


def nvidia_settings() -> Settings:
    return Settings(
        app_env="test",
        llm_provider="nvidia",
        nvidia_api_key=SecretStr("fake-test-key"),
    )


def test_non_streaming_completion_uses_approved_model_parameters() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Grounded result", reasoning_content="Checked evidence")
            )
        ],
        model="z-ai/glm-5.2",
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
    )
    client = FakeClient(response)
    provider = NvidiaChatProvider(nvidia_settings(), client=client)

    result = provider.complete([{"role": "user", "content": "Summarize the evidence"}])

    assert result.content == "Grounded result"
    assert result.reasoning == "Checked evidence"
    assert (result.prompt_tokens, result.completion_tokens) == (12, 4)
    assert client.completions.calls == [
        {
            "model": "z-ai/glm-5.2",
            "messages": [{"role": "user", "content": "Summarize the evidence"}],
            "temperature": 1.0,
            "top_p": 1.0,
            "max_tokens": 16_384,
            "seed": 42,
            "stream": False,
        }
    ]


def test_stream_skips_empty_chunks_and_separates_reasoning_from_content() -> None:
    chunks = [
        SimpleNamespace(choices=[]),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(reasoning_content="Reason", content=None))]
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(reasoning_content=None, content="Answer"))]
        ),
    ]
    provider = NvidiaChatProvider(nvidia_settings(), client=FakeClient(chunks))

    assert [(chunk.kind, chunk.text) for chunk in provider.stream([])] == [
        ("reasoning", "Reason"),
        ("content", "Answer"),
    ]


def test_provider_cannot_start_without_nvidia_configuration() -> None:
    with pytest.raises(ProviderConfigurationError):
        NvidiaChatProvider(Settings(app_env="test", llm_provider="fake"), client=FakeClient([]))


def test_timeout_is_normalized_without_leaking_provider_details() -> None:
    provider = NvidiaChatProvider(
        nvidia_settings(),
        client=FakeClient(TimeoutError("secret upstream diagnostic")),
    )

    with pytest.raises(ProviderRequestError) as raised:
        provider.complete([])

    assert raised.value.retryable is True
    assert str(raised.value) == "LLM provider request failed"
