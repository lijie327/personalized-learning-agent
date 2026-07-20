"""
教育知识库 RAG 模块
预设课程内容，支持向量化检索和混合检索。
"""

from typing import Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.llm import QwenEmbeddings

# ---------------------------------------------------------------------------
#  课程知识库（已外置化）
#  课程内容不再硬编码在代码中，而是从 data/courses/*.md 加载；
#  每个 .md 文件对应一个科目，文件内用 `#TOPIC: <知识点>` 作为主题分隔哨兵行。
# ---------------------------------------------------------------------------

import re
from pathlib import Path

# 课程数据默认目录（项目根 / data / courses）
DEFAULT_COURSE_DIR = Path(__file__).resolve().parent.parent / "data" / "courses"


def load_course_data(data_dir: Path = DEFAULT_COURSE_DIR) -> Dict[str, Dict[str, str]]:
    """
    从 data/courses/<subject>.md 加载课程知识。

    文件格式：
        #TOPIC: <知识点标题>
        <该知识点的教学内容 markdown>

    返回与旧 COURSE_DATA 完全一致的 {subject: {topic: content}} 结构。
    """
    data_dir = Path(data_dir)
    result: Dict[str, Dict[str, str]] = {}
    if not data_dir.exists():
        print(f"   [WARN] 课程数据目录不存在: {data_dir}，知识库将为空。")
        return result

    for md in sorted(data_dir.glob("*.md")):
        subject = md.stem
        text = md.read_text(encoding="utf-8")
        topics: Dict[str, str] = {}
        current: Optional[str] = None
        buf: List[str] = []
        for line in text.split("\n"):
            m = re.match(r"^#TOPIC:\s*(.+?)\s*$", line)
            if m:
                if current is not None:
                    topics[current] = "".join(buf).rstrip("\n")
                current = m.group(1)
                buf = []
            elif current is not None:
                buf.append(line + "\n")
        if current is not None:
            topics[current] = "".join(buf).rstrip("\n")
        result[subject] = topics

    return result



class EducationKnowledgeBase:
    """
    教育知识库：管理课程内容的向量化存储与检索。

    使用 RecursiveCharacterTextSplitter 对课程文本进行分块，
    通过 QwenEmbeddings 向量化后存入 ChromaDB。
    """

    def __init__(self, persist_directory: str = "./chroma_db",
                 course_data: Optional[Dict[str, Dict[str, str]]] = None):
        import os

        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)

        self.embeddings = QwenEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            separators=["\n## ", "\n### ", "\n```", "\n\n", "\n", " ", ""],
        )

        # 存储已初始化的科目集合
        self._initialized_subjects: set = set()

        # 原始课程数据：默认从 data/courses/*.md 加载（已外置化，不再硬编码）
        if course_data is None:
            course_data = load_course_data()
        self._raw_data = course_data

        # 持久化 ChromaDB 客户端（在 _get_or_create_collection 中懒加载）
        self._client = None
        self._collections: Dict[str, object] = {}

    # ------------------------------------------------------------------
    #  初始化 & 建库
    # ------------------------------------------------------------------

    def _get_or_create_collection(self, subject: str):
        """获取或创建指定科目的 ChromaDB 集合（持久化存储）。"""
        import chromadb

        if subject not in self._collections:
            # 懒加载：首次使用时创建持久化客户端
            if self._client is None:
                self._client = chromadb.PersistentClient(path=self.persist_directory)

            collection = self._client.get_or_create_collection(
                name=f"edu_{subject}",
                metadata={"subject": subject},
            )
            self._collections[subject] = collection

            # 如果该科目尚未入库，执行向量化写入
            if subject not in self._initialized_subjects:
                self._ingest_subject(subject, collection)
                self._initialized_subjects.add(subject)

        return self._collections[subject]

    def _ingest_subject(self, subject: str, collection):
        """将指定科目的所有课程文本分块、向量化后写入 ChromaDB。"""
        topics = self._raw_data.get(subject, {})
        if not topics:
            return

        all_chunks = []
        all_ids = []
        all_metadatas = []

        for topic, content in topics.items():
            chunks = self.text_splitter.split_text(content)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                chunk_id = f"{subject}_{topic}_chunk_{i}"
                all_ids.append(chunk_id)
                all_metadatas.append({
                    "subject": subject,
                    "topic": topic,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })

        if not all_chunks:
            return

        # 向量化
        vectors = self.embeddings.embed_documents(all_chunks)

        # 写入 ChromaDB
        collection.add(
            documents=all_chunks,
            embeddings=vectors,
            metadatas=all_metadatas,
            ids=all_ids,
        )

    # ------------------------------------------------------------------
    #  检索方法
    # ------------------------------------------------------------------

    def search(self, query: str, subject: str, k: int = 3) -> List[dict]:
        """
        按科目进行向量检索。

        Args:
            query: 检索查询文本。
            subject: 科目名称（如 'python' / 'data_structures'）。
            k: 返回结果数量。

        Returns:
            列表，每项包含 content / topic / score 等字段。
        """
        collection = self._get_or_create_collection(subject)

        # 检查集合是否有文档
        if collection.count() == 0:
            return []

        query_embedding = self.embeddings.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, collection.count()),
            where={"subject": subject},
        )

        # 整理返回结果
        items = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append({
                    "content": doc,
                    "topic": meta.get("topic", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": 1.0 - dist,  # ChromaDB 返回 L2 距离，转为相似度
                })

        return items

    def hybrid_search(self, query: str, subject: str, k: int = 5) -> List[dict]:
        """
        混合检索：向量检索 + 关键词重排序。

        先通过向量检索召回候选结果，再使用关键词匹配对结果进行重排序，
        提升与查询关键词直接相关的文档排名。

        Args:
            query: 检索查询文本。
            subject: 科目名称。
            k: 最终返回结果数量。

        Returns:
            重排序后的结果列表。
        """
        # 第一步：向量检索召回更多候选
        candidates = self.search(query, subject, k=k * 3)

        if not candidates:
            return []

        # 第二步：关键词提取与重排序
        query_keywords = self._extract_keywords(query)

        for item in candidates:
            content_lower = item["content"].lower()
            keyword_score = sum(
                1 for kw in query_keywords if kw.lower() in content_lower
            )
            # 混合分数 = 0.7 * 向量相似度 + 0.3 * 关键词命中率
            keyword_norm = keyword_score / max(len(query_keywords), 1)
            item["hybrid_score"] = 0.7 * item["score"] + 0.3 * keyword_norm

        # 按混合分数降序排序
        candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return candidates[:k]

    def get_learning_materials(
        self, subject: str, topic: str
    ) -> List[dict]:
        """
        获取指定科目和主题的完整学习材料。

        Args:
            subject: 科目名称（如 'python'）。
            topic: 主题名称（如 '变量'）。

        Returns:
            该主题所有分块的列表，按顺序排列。
        """
        subject_data = self._raw_data.get(subject, {})
        content = subject_data.get(topic, "")

        if not content:
            return []

        chunks = self.text_splitter.split_text(content)
        return [
            {
                "content": chunk,
                "subject": subject,
                "topic": topic,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i, chunk in enumerate(chunks)
        ]

    def list_subjects(self) -> List[str]:
        """列出所有可用科目。"""
        return list(self._raw_data.keys())

    def list_topics(self, subject: str) -> List[str]:
        """列出指定科目的所有主题。"""
        return list(self._raw_data.get(subject, {}).keys())

    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """
        简易关键词提取：按空格和标点分词，过滤短词。

        实际生产环境可替换为 jieba 分词或 BGE Reranker。
        """
        import re
        # 中文按连续字符切分，英文按单词切分
        tokens = re.findall(r"[一-鿿]+|[a-zA-Z_]\w*", text)
        # 过滤长度小于 2 的词
        return [t for t in tokens if len(t) >= 2]
