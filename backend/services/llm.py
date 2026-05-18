"""LLM 工厂函数 — 所有 Graph 共用"""

from langchain_openai import ChatOpenAI
from config import settings


def resolve_model(task: str = "dm") -> str:
    if task == "fast" and settings.llm_fast_model:
        return settings.llm_fast_model
    if task == "module" and settings.llm_module_model:
        return settings.llm_module_model
    return settings.llm_model


def build_llm_kwargs(temperature: float = 0.7, max_tokens: int = 4000, task: str = "dm") -> dict:
    return {
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
        "model": resolve_model(task),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def get_llm(temperature: float = 0.7, max_tokens: int = 4000, task: str = "dm") -> ChatOpenAI:
    return ChatOpenAI(**build_llm_kwargs(temperature=temperature, max_tokens=max_tokens, task=task))
