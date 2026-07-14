"""
LangChain ChatModel 封装。

将阿里云百炼（DashScope）OpenAI 兼容接口包装为 LangChain 的 ChatOpenAI，
供 create_react_agent 等 LangGraph 原语直接使用（支持流式与 tool calling）。
"""

from langchain_openai import ChatOpenAI

from backend.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    LLM_MODEL,
)


def get_chat_model(temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    """
    构造一个指向 DashScope 的 ChatOpenAI 实例。

    DashScope 提供 OpenAI 兼容的 /chat/completions 接口，
    因此可直接用 langchain-openai 的 ChatOpenAI 透传 base_url。
    """
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=temperature,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        streaming=streaming,
        max_tokens=4096,
    )
