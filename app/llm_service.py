
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


llm_settings = LLMSettings()


def validate_llm_settings() -> None:
    """Ensure the OpenRouter API key is configured."""
    if not llm_settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is missing. "
            "Configure it in your local .env file."
        )


def chat_completion(message: str) -> str:
    """Send a message to OpenRouter and return the model response."""
    validate_llm_settings()

    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    url = (
        f"{llm_settings.openrouter_base_url.rstrip('/')}"
        "/chat/completions"
    )

    payload = {
        "model": llm_settings.openrouter_model,
        "messages": [
            {
                "role": "user",
                "content": message.strip(),
            }
        ],
        "max_tokens": 1600,
    }

    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": (
                f"Bearer {llm_settings.openrouter_api_key}"
            ),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        choices = result.get("choices", [])
        if not choices:
            raise RuntimeError(
                "OpenRouter returned no response choices."
            )

        choice = choices[0]
        response_message = choice.get("message", {})
        content = response_message.get("content") or ""
        finish_reason = choice.get("finish_reason", "unknown")

        if not content.strip():
            raise RuntimeError(
                "OpenRouter returned an empty response. "
                f"Finish reason: {finish_reason}"
            )

        if finish_reason == "length":
            print(
                "Warning: The response reached its output token limit. "
                "Consider reducing the prompt or increasing max_tokens."
            )

        return content.strip()

    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenRouter returned HTTP {exc.code}: {details[:1000]}"
        ) from None

    except URLError as exc:
        raise RuntimeError(
            f"Could not connect to OpenRouter: {exc.reason}"
        ) from None

    except (json.JSONDecodeError, TypeError, IndexError, KeyError) as exc:
        raise RuntimeError(
            "OpenRouter returned an unexpected response "
            f"({type(exc).__name__})."
        ) from None
