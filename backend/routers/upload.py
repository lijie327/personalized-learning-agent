"""图片上传接口（作业截图 / 题目照片）。"""

import asyncio
import uuid
from pathlib import Path
from typing import IO

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from backend.config import UPLOAD_DIR
from backend.llm import QwenVisionLLM

router = APIRouter(tags=["upload"])


def _is_valid_image_signature(content: bytes) -> bool:
    """基于魔数校验真实图片类型（不依赖扩展名 / content_type）。"""
    if len(content) < 12:
        return False
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if content[:3] == b"\xff\xd8\xff":
        return True
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    if content[:2] == b"BM":
        return True
    return False


def _verify_image(content: bytes) -> None:
    """解码校验图片合法性；环境具备 Pillow 时用其做强校验，否则退化到魔数校验。"""
    import io

    try:
        from PIL import Image
        Image.open(io.BytesIO(content)).verify()
    except ImportError:
        if not _is_valid_image_signature(content):
            raise ValueError("不是合法的图片文件")
    except Exception as e:
        raise ValueError(f"图片解码失败: {e}")


def _enforce_upload_quota(upload_dir: Path, max_files: int = 300) -> None:
    """控制 uploads 目录规模：超出上限时删除最旧的文件。"""
    try:
        files = [f for f in upload_dir.iterdir() if f.is_file()]
        if len(files) <= max_files:
            return
        files.sort(key=lambda f: f.stat().st_mtime)  # 最旧在前
        for old in files[: len(files) - max_files]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), student_id: str = Form("unknown")):
    """
    上传图片（作业截图、题目照片等），做安全校验后保存到 uploads 目录。

    安全措施：
    - 大小上限（5MB）；
    - 魔数 + 解码校验，确认真实图片（不只看扩展名 / content_type）；
    - student_id 仅保留安全字符，防路径穿越；
    - 唯一文件名，并定期清理旧文件。
    """
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024

    # 1. 读取内容并校验大小
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(content) // 1024}KB），上限 {MAX_UPLOAD_BYTES // 1024}KB",
        )

    # 2. 解码 / 魔数校验，确认真实图片
    try:
        _verify_image(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. 仅保留安全字符，防路径穿越
    safe_id = (
        "".join(c for c in (student_id or "unknown") if c.isalnum() or c in "-_")[:32]
        or "unknown"
    )

    # 4. 唯一文件名（保留扩展名）
    ext = Path(file.filename).suffix if file.filename else ".png"
    if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        ext = ".png"
    unique_name = f"{safe_id}_{uuid.uuid4().hex[:12]}{ext}"

    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    file_path = upload_path / unique_name
    with open(file_path, "wb") as f:
        f.write(content)

    # 5. 清理旧文件，控制目录规模
    _enforce_upload_quota(upload_path, max_files=300)

    # 构建访问 URL
    file_url = f"/uploads/{unique_name}"

    # 调用视觉模型分析图片内容
    analyzed_content = None
    content_error = None
    try:
        vision_llm = QwenVisionLLM()
        # 视觉模型为同步网络调用，放到线程池避免阻塞事件循环
        analyzed_content = await asyncio.to_thread(vision_llm.analyze_image, str(file_path))
        print(f"   🖼️ 图片分析完成: {unique_name} ({len(analyzed_content)} 字符)")
    except Exception as e:
        content_error = str(e)
        print(f"   ⚠️ 图片分析失败 ({unique_name}): {e}")

    return {
        "success": True,
        "file_name": file.filename,
        "saved_name": unique_name,
        "url": file_url,
        "size": len(content),
        "content_type": file.content_type,
        "analyzed_content": analyzed_content,
        "content_error": content_error,
    }
