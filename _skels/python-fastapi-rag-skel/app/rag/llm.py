from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from .config import RagSettings


@lru_cache(maxsize=2)
def _build_llm(provider: str, model: str, base_url: str, temperature: float, api_key: str) -> BaseChatModel:
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
    )


def get_llm(settings: RagSettings) -> BaseChatModel:
    if settings.llm_provider == "openai":
        return _build_llm(
            "openai",
            settings.openai_model,
            "",
            settings.ollama_temperature,
            settings.openai_api_key,
        )
    return _build_llm(
        "ollama",
        settings.ollama_model,
        settings.ollama_base_url,
        settings.ollama_temperature,
        "",
    )
