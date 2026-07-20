"""SSE 流式响应工具函数。"""

import json
from typing import Any, Dict


def sse_format(data: Dict[str, Any]) -> str:
    """
    格式化 SSE 消息。

    SSE 格式要求：``data: {json}\\n\\n``
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
