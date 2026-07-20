"""知识库检索接口。"""

from typing import Optional

from fastapi import APIRouter, HTTPException

import backend.runtime as runtime

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/search")
async def knowledge_search(
    query: str,
    subject: str = "python",
    k: int = 5,
):
    """
    从知识库检索学习材料。
    """
    if runtime.knowledge_base is None:
        raise HTTPException(status_code=500, detail="Knowledge Base 未初始化")

    results = runtime.knowledge_base.hybrid_search(query, subject, k)

    return {
        "query": query,
        "subject": subject,
        "results": results,
        "count": len(results),
    }


@router.get("/knowledge/topics")
async def list_topics(subject: str = "python"):
    """
    列出指定科目的所有知识点主题。
    """
    if runtime.knowledge_base is None:
        raise HTTPException(status_code=500, detail="Knowledge Base 未初始化")

    topics = runtime.knowledge_base.list_topics(subject)
    subjects = runtime.knowledge_base.list_subjects()

    return {
        "subject": subject,
        "topics": topics,
        "available_subjects": subjects,
    }
