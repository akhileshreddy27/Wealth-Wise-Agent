"""Chat model factory. Every supported provider speaks the OpenAI chat API, so one client covers them all.

Configure with LLM_PROVIDER plus a key (GROQ_API_KEY for Groq). With no key the AI features
report themselves as disabled and the app falls back to rule-based text.
"""
from langchain_core.language_models import BaseChatModel

from app.core.config import settings

PROVIDERS = {
    #             base URL                                               default model                            needs key
    "groq":       ("https://api.groq.com/openai/v1",                     "llama-3.3-70b-versatile",               True),
    "ollama":     ("http://localhost:11434/v1",                          "llama3.1:8b",                           False),
    "openrouter": ("https://openrouter.ai/api/v1",                       "meta-llama/llama-3.3-70b-instruct:free", True),
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash",               True),
}

_override: BaseChatModel | None = None   # tests inject a scripted fake model here


def set_llm(model: BaseChatModel | None) -> None:
    global _override
    _override = model


def _config() -> tuple[str, str, str, str | None]:
    provider = settings.llm_provider.lower()
    base_url, model, needs_key = PROVIDERS.get(provider, ("", "", True))
    key = settings.llm_api_key or (settings.groq_api_key if provider == "groq" else "")
    if not needs_key:
        key = key or "not-needed"
    return provider, settings.llm_base_url or base_url, settings.llm_model or model, key or None


def llm_status() -> dict:
    if _override is not None:
        return {"enabled": True, "provider": "test", "model": "fake"}
    provider, base_url, model, key = _config()
    enabled = provider in PROVIDERS and bool(key)
    reason = None if enabled else (
        "AI is turned off (LLM_PROVIDER=none)." if provider == "none" else
        f"Unknown LLM_PROVIDER '{provider}'." if provider not in PROVIDERS else
        f"No API key: set {'GROQ_API_KEY' if provider == 'groq' else 'LLM_API_KEY'} in backend/.env.")
    return {"enabled": enabled, "provider": provider, "model": model if enabled else None, "reason": reason}


def get_llm(temperature: float = 0.2) -> BaseChatModel | None:
    """The configured chat model, or None when AI is disabled."""
    if _override is not None:
        return _override
    if not llm_status()["enabled"]:
        return None
    from langchain_openai import ChatOpenAI   # imported lazily: only needed when AI is on

    _, base_url, model, key = _config()
    return ChatOpenAI(model=model, base_url=base_url, api_key=key, temperature=temperature,
                      timeout=45, max_retries=1)
