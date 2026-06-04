"""
Unified LLM client — routes to Anthropic or OpenAI based on config/settings.json.

Both providers use the same message format (list of {role, content} dicts).
The only structural difference is that OpenAI expects the system prompt as the
first message with role "system", while Anthropic takes it as a separate parameter.
"""

from utils.settings import load_settings

_anthropic_client = None
_openai_client = None

PROVIDER_MODELS = {
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-opus-4-7",
        "claude-haiku-4-5-20251001",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
    ],
}


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic()
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI()
    return _openai_client


def chat(messages: list, system: str = "", max_tokens: int = 2048) -> str:
    """
    Call the configured LLM and return the response text.

    messages: list of {"role": "user"|"assistant", "content": str}
    system:   system/developer prompt (provider-agnostic)
    """
    settings = load_settings()
    provider = settings["provider"]
    model = settings["model"]

    if provider == "anthropic":
        response = _get_anthropic().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    elif provider == "openai":
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(messages)

        response = _get_openai().chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=oai_messages,
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unknown provider '{provider}'. Must be 'anthropic' or 'openai'.")
