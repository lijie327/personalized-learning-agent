"""
大语言模型与 Embedding 封装模块
基于阿里云百炼 (DashScope) API (OpenAI 兼容模式)。
"""

import base64
from pathlib import Path
from typing import Generator, List, Optional

from openai import OpenAI

from backend.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL, EMBEDDING_MODEL, VISION_MODEL


# ---------------------------------------------------------------------------
#  QwenLLM —— 对话模型
# ---------------------------------------------------------------------------

class QwenLLM:
    """
    阿里云百炼大语言模型封装。

    基于 OpenAI SDK 调用 DashScope API（兼容模式），
    提供同步调用 (invoke) 和流式输出 (stream)。
    """

    def __init__(
        self,
        model: str = LLM_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
        )

    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list[dict]:
        """构造 OpenAI 兼容的消息列表。"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_messages_with_history(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        构造带对话历史的消息列表。

        Args:
            prompt: 当前用户问题。
            system_prompt: 系统提示词。
            history: 之前的对话消息列表，格式为 [{"role": "user/assistant", "content": "..."}]。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return messages

    # ------------------------------------------------------------------
    #  公开方法
    # ------------------------------------------------------------------

    def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """同步调用，返回完整回复文本。"""
        messages = self._build_messages(prompt, system_prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        return response.choices[0].message.content or ""

    def invoke_with_history(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """同步调用，带对话历史。"""
        messages = self._build_messages_with_history(prompt, system_prompt, history)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """流式调用，逐步产出回复文本片段。"""
        messages = self._build_messages(prompt, system_prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def stream_with_history(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> Generator[str, None, None]:
        """流式调用，带对话历史。"""
        messages = self._build_messages_with_history(prompt, system_prompt, history)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


# ---------------------------------------------------------------------------
#  QwenEmbeddings —— 向量模型（DashScope API）
# ---------------------------------------------------------------------------

class QwenEmbeddings:
    """
    阿里云百炼向量模型封装。

    通过 DashScope API（OpenAI 兼容模式）调用 text-embedding-v2 等模型，
    无需本地下载模型文件。
    """

    def __init__(self, model: str = EMBEDDING_MODEL):
        self.model = model
        self.client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化多个文档。

        优先使用单次 API 调用批量处理（大幅减少网络开销），
        若单个文本过长或批量调用失败，回退到逐条处理。
        """
        if not texts:
            return []

        try:
            # DashScope API (OpenAI 兼容) 支持 input 为字符串列表
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            # 按 index 排序确保顺序
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [d.embedding for d in sorted_data]
        except Exception:
            # 批量调用失败时回退到逐条调用（兼容较长的文本或 API 限制）
            embeddings = []
            for text in texts:
                try:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=text,
                    )
                    embeddings.append(response.data[0].embedding)
                except Exception:
                    # 单条也失败时返回零向量作为占位
                    embeddings.append([0.0] * 1536)
            return embeddings

    def embed_query(self, text: str) -> List[float]:
        """向量化单条查询文本。"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding


# ---------------------------------------------------------------------------
#  QwenVisionLLM —— 图片分析（百炼 qwen-vl-max）
# ---------------------------------------------------------------------------

class QwenVisionLLM:
    """
    图片分析模型封装。

    基于阿里云百炼 qwen-vl-max 模型，支持多模态视觉分析。
    """

    DEFAULT_ANALYSIS_PROMPT = (
        "你是一个教育辅助工具。请仔细分析这张图片的内容，包括：\n"
        "1. 如果图片中有文字，请完整识别所有文字内容\n"
        "2. 如果图片中有数学公式或表达式，请用 Markdown LaTeX 格式写出\n"
        "3. 如果图片中有代码，请识别代码并简要说明其功能\n"
        "4. 如果图片中有图表或数据可视化，请描述图表内容和关键数据\n"
        "5. 最后用一两句话总结这张图片的核心内容\n\n"
        "请用中文回答，结构清晰。"
    )

    def __init__(self, model: str = VISION_MODEL):
        self.model = model
        self.client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
        )

    @staticmethod
    def _get_mime_type(image_path: str) -> str:
        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/png")

    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_image(self, image_path: str, prompt: Optional[str] = None) -> str:
        """分析图片内容（通过 qwen-vl-max 多模态模型）。"""
        if prompt is None:
            prompt = self.DEFAULT_ANALYSIS_PROMPT

        mime_type = self._get_mime_type(image_path)
        image_b64 = self._image_to_base64(image_path)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=4096,
        )

        return response.choices[0].message.content or ""
