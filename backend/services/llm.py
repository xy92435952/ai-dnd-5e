"""LLM 工厂函数 — 所有 Graph 共用"""

from langchain_openai import ChatOpenAI
from config import settings


def get_llm(temperature: float = 0.7, max_tokens: int = 4000) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
