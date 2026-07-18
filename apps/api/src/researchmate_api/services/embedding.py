from __future__ import annotations

from typing import Any, Literal

from researchmate_api.config import Settings
from researchmate_api.services.llm import ProviderConfigurationError, ProviderRequestError
from researchmate_api.observability import provider_observation


EmbeddingInputType = Literal["query", "passage"]


class NvidiaEmbeddingProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if settings.embedding_provider != "nvidia" or settings.nvidia_api_key is None:
            raise ProviderConfigurationError("NVIDIA embedding provider is not configured")
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

    def embed(self, texts: list[str], *, input_type: EmbeddingInputType) -> list[list[float]]:
        if not texts:
            return []
        try:
            with provider_observation(
                self.settings,
                name="nvidia.embedding",
                observation_type="embedding",
                model=self.settings.nvidia_embedding_model,
                metadata={
                    "input_count": len(texts),
                    "input_chars": sum(len(text) for text in texts),
                    "input_type": input_type,
                },
            ) as observation:
                response = self.client.embeddings.create(
                    model=self.settings.nvidia_embedding_model,
                    input=texts,
                    encoding_format="float",
                    extra_body={"input_type": input_type, "truncate": "END"},
                )
                usage = getattr(response, "usage", None)
                observation.update(
                    usage_details={"input": int(getattr(usage, "prompt_tokens", 0) or 0)}
                )
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
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        if len(vectors) != len(texts) or any(
            len(vector) != self.settings.embedding_dimension for vector in vectors
        ):
            raise ValueError("Embedding provider returned an unexpected vector shape")
        return vectors
