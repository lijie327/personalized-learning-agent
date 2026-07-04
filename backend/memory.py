"""
学习记忆模块
管理学生数据的三级存储架构：
- 短期：当前会话上下文（Redis）
- 中期：跨学科薄弱点追踪（Redis）
- 长期：知识图谱向量存储（ChromaDB）
"""

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

import redis

from backend.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


# ===================================================================
#  短期记忆 —— 当前会话上下文（Redis）
# ===================================================================

class SessionMemory:
    """
    短期记忆：存储当前会话的对话上下文。

    基于 Redis List 实现，支持 TTL 自动过期和消息数量限制。
    """

    # Redis key 前缀
    _KEY_PREFIX = "session"

    def __init__(self, max_history: int = 50, ttl: int = 3600, file_path: str = ""):
        """
        Args:
            max_history: 每个会话最大保留的消息数量。
            ttl: 会话过期时间（秒），默认 1 小时。
            file_path: （已废弃，Redis 替代 JSON 文件持久化）。
        """
        self._max_history = max_history
        self._ttl = ttl
        self._redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,
        )
        # 测试连接
        try:
            self._redis.ping()
            print(f"   [REDIS] Connected to {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
        except redis.ConnectionError as e:
            print(f"   [REDIS] Connection failed: {e}, falling back to in-memory dict")
            self._redis = None
            self._store: Dict[str, List[Dict[str, Any]]] = {}
            self._timestamps: Dict[str, float] = {}

    def _messages_key(self, session_id: str) -> str:
        return f"{self._KEY_PREFIX}:{session_id}:messages"

    def add_message(self, session_id: str, message: Dict[str, Any]):
        """
        向指定会话添加一条消息。

        Args:
            session_id: 会话 ID。
            message: 消息字典，如 {"role": "user", "content": "..."}。
        """
        message["timestamp"] = datetime.now().isoformat()

        if self._redis is None:
            # 降级：使用 in-memory dict
            if session_id not in self._store:
                self._store[session_id] = []
            self._store[session_id].append(message)
            if len(self._store[session_id]) > self._max_history:
                self._store[session_id] = self._store[session_id][-self._max_history:]
            return

        key = self._messages_key(session_id)
        pipe = self._redis.pipeline()
        pipe.rpush(key, json.dumps(message, ensure_ascii=False))
        pipe.ltrim(key, -self._max_history, -1)  # 保留最近 N 条
        pipe.expire(key, self._ttl)
        pipe.execute()

    def get_history(self, session_id: str, last_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取会话历史。

        Args:
            session_id: 会话 ID。
            last_n: 获取最近 N 条消息。

        Returns:
            消息列表。
        """
        if self._redis is None:
            # 降级：使用 in-memory dict
            if session_id not in self._store:
                return []
            return self._store[session_id][-last_n:]

        key = self._messages_key(session_id)
        if not self._redis.exists(key):
            return []

        # 获取最后 last_n 条消息
        raw_msgs = self._redis.lrange(key, -last_n, -1)
        messages = []
        for raw in raw_msgs:
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return messages

    def get_context(self, session_id: str, last_n: int = 10) -> Optional[str]:
        """
        获取会话上下文文本（用于传给 LLM）。

        Args:
            session_id: 会话 ID。
            last_n: 获取最近 N 条消息。

        Returns:
            格式化的上下文文本。
        """
        history = self.get_history(session_id, last_n)
        if not history:
            return None

        parts = []
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"[{role}]: {content}")

        return "\n".join(parts)

    def clear_session(self, session_id: str):
        """清除指定会话的所有消息。"""
        if self._redis is None:
            self._store.pop(session_id, None)
            return
        self._redis.delete(self._messages_key(session_id))

    def cleanup(self):
        """Redis 通过 TTL 自动过期，无需手动清理。"""
        pass  # Redis EXPIRE 自动处理


# ===================================================================
#  中期记忆 —— 跨学科薄弱点追踪
# ===================================================================

class WeakPointTracker:
    """
    中期记忆：追踪学生跨学科的薄弱知识点。

    使用 Python dict 模拟 Redis 存储，生产环境应替换为真实 Redis。
    每个学生的薄弱点按学科分类，附带正确率、最近测试时间等元数据。
    """

    def __init__(self, file_path: str = "./data/weak_points.json"):
        # 结构: {student_id: {subject: {topic: {"score": float, "attempts": int, "last_tested": str}}}}
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._file_path = file_path
        self._load()

    def update_weak_point(
        self,
        student_id: str,
        topic: str,
        score: float,
        subject: str = "general",
    ):
        """
        更新学生某个知识点的得分。

        Args:
            student_id: 学生 ID。
            topic: 知识点名称。
            score: 得分（0-1），越高表示掌握越好。
            subject: 科目名称。
        """
        if student_id not in self._store:
            self._store[student_id] = {}
        if subject not in self._store[student_id]:
            self._store[student_id][subject] = {}

        existing = self._store[student_id][subject].get(topic, {})
        old_score = existing.get("score", score)
        old_attempts = existing.get("attempts", 0)

        # 移动平均：新分数权重更高
        new_score = old_score * 0.3 + score * 0.7

        self._store[student_id][subject][topic] = {
            "score": round(new_score, 2),
            "attempts": old_attempts + 1,
            "last_tested": datetime.now().isoformat(),
        }
        self._save()

    def get_weak_points(
        self,
        student_id: str,
        subject: Optional[str] = None,
        threshold: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        获取学生的薄弱知识点（得分低于阈值的知识点）。

        Args:
            student_id: 学生 ID。
            subject: 指定科目（None 表示所有科目）。
            threshold: 薄弱判定阈值，低于此值视为薄弱。

        Returns:
            薄弱知识点列表，每项含 topic / score / subject / attempts。
        """
        if student_id not in self._store:
            return []

        weak_points = []
        subjects = [subject] if subject else self._store[student_id].keys()

        for subj in subjects:
            if subj not in self._store[student_id] or subj == "_metadata":
                continue
            for topic, data in self._store[student_id][subj].items():
                if data["score"] < threshold:
                    weak_points.append({
                        "topic": topic,
                        "subject": subj,
                        "score": data["score"],
                        "attempts": data["attempts"],
                        "last_tested": data["last_tested"],
                    })

        # 按分数升序排列（最薄弱的排在前面）
        weak_points.sort(key=lambda x: x["score"])
        return weak_points

    def get_strong_points(
        self,
        student_id: str,
        subject: Optional[str] = None,
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        获取学生已掌握的知识点（得分高于阈值的知识点）。

        Args:
            student_id: 学生 ID。
            subject: 指定科目（None 表示所有科目）。
            threshold: 强项判定阈值。

        Returns:
            已掌握知识点列表。
        """
        if student_id not in self._store:
            return []

        strong_points = []
        subjects = [subject] if subject else self._store[student_id].keys()

        for subj in subjects:
            if subj not in self._store[student_id] or subj == "_metadata":
                continue
            for topic, data in self._store[student_id][subj].items():
                if data["score"] >= threshold:
                    strong_points.append({
                        "topic": topic,
                        "subject": subj,
                        "score": data["score"],
                        "attempts": data["attempts"],
                        "last_tested": data["last_tested"],
                    })

        return strong_points

    def get_all_topics(self, student_id: str) -> Dict[str, Any]:
        """
        获取学生所有知识点的完整数据。

        Args:
            student_id: 学生 ID。

        Returns:
            按科目分组的知识点数据（不包含 _metadata）。
        """
        data = self._store.get(student_id, {})
        return {k: v for k, v in data.items() if k != "_metadata"}

    def set_metadata(self, student_id: str, key: str, value: Any):
        """
        设置学生的元数据（如姓名、偏好等）。

        Args:
            student_id: 学生 ID。
            key: 元数据键名（如 'name'）。
            value: 元数据值。
        """
        if student_id not in self._store:
            self._store[student_id] = {}
        if "_metadata" not in self._store[student_id]:
            self._store[student_id]["_metadata"] = {}
        self._store[student_id]["_metadata"][key] = value
        self._save()

    def get_metadata(self, student_id: str, key: Optional[str] = None) -> Any:
        """
        获取学生的元数据。

        Args:
            student_id: 学生 ID。
            key: 元数据键名（None 返回全部元数据）。

        Returns:
            元数据值或全部元数据字典。
        """
        metadata = self._store.get(student_id, {}).get("_metadata", {})
        if key is None:
            return metadata
        return metadata.get(key)

    def clear_student(self, student_id: str):
        """清除学生的所有薄弱点记录。"""
        self._store.pop(student_id, None)
        self._save()

    # ------------------------------------------------------------------
    #  持久化
    # ------------------------------------------------------------------

    def _save(self):
        """原子写入：持久化当前状态到 JSON 文件。"""
        import os
        import logging
        _logger = logging.getLogger(__name__)
        try:
            os.makedirs(os.path.dirname(self._file_path) or ".", exist_ok=True)
            tmp_path = self._file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._file_path)
        except PermissionError as e:
            _logger.error(f"[WeakPointTracker] 权限不足，无法保存到 {self._file_path}: {e}")
        except OSError as e:
            _logger.error(f"[WeakPointTracker] 磁盘错误，无法保存到 {self._file_path}: {e}")
        except Exception as e:
            _logger.error(f"[WeakPointTracker] 未知错误保存失败: {e}")

    def _load(self):
        """从 JSON 文件加载状态。"""
        import os
        try:
            if not os.path.exists(self._file_path):
                return
            with open(self._file_path, "r", encoding="utf-8") as f:
                self._store = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass


# ===================================================================
#  长期记忆 —— 知识图谱向量存储（ChromaDB）
# ===================================================================

class KnowledgeGraphStore:
    """
    长期记忆：存储学生知识图谱的向量表示。

    使用 ChromaDB 持久化存储，支持相似度检索和图谱更新。
    每个知识点存储为向量，附带掌握程度、错误模式等元数据。
    """

    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Args:
            persist_directory: ChromaDB 持久化存储路径。
        """
        self._persist_directory = persist_directory
        self._client = None
        self._collection = None
        self._initialized = False

    def _get_collection(self):
        """懒加载 ChromaDB 集合。"""
        if self._collection is not None:
            return self._collection

        import chromadb

        self._client = chromadb.PersistentClient(path=self._persist_directory)
        self._collection = self._client.get_or_create_collection(
            name="student_knowledge_graph",
            metadata={"description": "学生知识图谱向量存储"},
        )
        self._initialized = True
        return self._collection

    def store_knowledge(
        self,
        student_id: str,
        topic: str,
        content: str,
        mastery: float,
        subject: str = "general",
    ):
        """
        存储知识点到知识图谱。

        Args:
            student_id: 学生 ID。
            topic: 知识点名称。
            content: 知识点内容文本（用于向量化）。
            mastery: 掌握程度（0-1）。
            subject: 科目名称。
        """
        from backend.llm import QwenEmbeddings

        collection = self._get_collection()
        embeddings = QwenEmbeddings()

        # 向量化内容
        vector = embeddings.embed_documents([content])[0]

        doc_id = f"{student_id}_{topic}_{subject}"
        metadata = {
            "student_id": student_id,
            "topic": topic,
            "subject": subject,
            "mastery": mastery,
            "stored_at": datetime.now().isoformat(),
        }

        # 如果已存在则更新
        try:
            existing = collection.get(ids=[doc_id])
            if existing and existing["ids"]:
                collection.update(
                    ids=[doc_id],
                    embeddings=[vector],
                    metadatas=[metadata],
                    documents=[content],
                )
                return
        except Exception:
            pass

        # 新增
        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[metadata],
            documents=[content],
        )

    def query_knowledge(
        self,
        student_id: str,
        query: str,
        k: int = 5,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询学生的知识图谱。

        Args:
            student_id: 学生 ID。
            query: 查询文本。
            k: 返回结果数量。
            subject: 过滤科目（可选）。

        Returns:
            匹配的知识节点列表。
        """
        from backend.llm import QwenEmbeddings

        collection = self._get_collection()
        if collection.count() == 0:
            return []

        embeddings = QwenEmbeddings()
        query_vector = embeddings.embed_query(query)

        where_filter = {"student_id": student_id}
        if subject:
            where_filter["subject"] = subject

        # 如果集合有文档，检查是否有匹配条件的
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(k, collection.count()),
            where=where_filter,
        )

        if not results or not results["documents"]:
            return []

        items = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            items.append({
                "topic": meta.get("topic", ""),
                "subject": meta.get("subject", ""),
                "mastery": meta.get("mastery", 0),
                "content": doc,
                "score": 1.0 - dist,
                "stored_at": meta.get("stored_at", ""),
            })

        return items

    def get_student_graph(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """
        获取学生完整的知识图谱概览。

        Args:
            student_id: 学生 ID。

        Returns:
            {
                "nodes": List[dict],  # 所有知识点节点
                "statistics": dict,   # 统计数据
            }
        """
        collection = self._get_collection()
        if collection.count() == 0:
            return {"nodes": [], "statistics": {}}

        # 获取该学生的所有节点
        results = collection.get(
            where={"student_id": student_id},
        )

        if not results or not results["documents"]:
            return {"nodes": [], "statistics": {}}

        nodes = []
        mastery_scores = []

        for doc, meta in zip(results["documents"], results["metadatas"]):
            mastery = meta.get("mastery", 0)
            nodes.append({
                "topic": meta.get("topic", ""),
                "subject": meta.get("subject", ""),
                "mastery": mastery,
                "stored_at": meta.get("stored_at", ""),
            })
            mastery_scores.append(mastery)

        # 统计
        statistics = {
            "total_nodes": len(nodes),
            "avg_mastery": round(sum(mastery_scores) / len(mastery_scores), 2) if mastery_scores else 0,
            "subjects": list(set(n["subject"] for n in nodes if n.get("subject"))),
            "mastered": len([s for s in mastery_scores if s >= 0.8]),
            "needs_work": len([s for s in mastery_scores if s < 0.6]),
        }

        return {"nodes": nodes, "statistics": statistics}

    def delete_student_graph(self, student_id: str):
        """删除学生的所有知识图谱数据。"""
        collection = self._get_collection()
        try:
            results = collection.get(where={"student_id": student_id})
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
        except Exception:
            pass


# ===================================================================
#  统一记忆管理 —— LearningMemory
# ===================================================================

class LearningMemory:
    """
    学习记忆统一管理类。

    整合短期、中期、长期三层存储：
    - 短期：SessionMemory —— 当前会话上下文
    - 中期：WeakPointTracker —— 跨学科薄弱点追踪
    - 长期：KnowledgeGraphStore —— ChromaDB 知识图谱

    提供统一的学生画像获取和更新接口。
    """

    def __init__(
        self,
        session_max_history: int = 50,
        session_ttl: int = 3600,
        persist_directory: str = "./chroma_db",
        data_dir: str = "./data",
    ):
        """
        Args:
            session_max_history: 每个会话最大保留消息数。
            session_ttl: 会话过期时间（秒）。
            persist_directory: ChromaDB 持久化路径。
            data_dir: JSON 数据文件目录。
        """
        import os
        os.makedirs(data_dir, exist_ok=True)

        self.short_term = SessionMemory(
            max_history=session_max_history,
            ttl=session_ttl,
        )
        self.mid_term = WeakPointTracker(
            file_path=os.path.join(data_dir, "weak_points.json"),
        )
        self.long_term = KnowledgeGraphStore(
            persist_directory=persist_directory,
        )
        self._synced_students: set = set()

    # ------------------------------------------------------------------
    #  学生画像获取
    # ------------------------------------------------------------------

    def sync_long_to_mid(self, student_id: str):
        """
        从长期记忆 (ChromaDB) 恢复数据到中期记忆 (WeakPointTracker)。

        用于服务重启后自动恢复中期数据。
        """
        graph = self.long_term.get_student_graph(student_id)
        for node in graph.get("nodes", []):
            topic = node.get("topic")
            subject = node.get("subject", "general")
            mastery = node.get("mastery", 0)
            if topic:
                all_topics = self.mid_term.get_all_topics(student_id)
                if subject not in all_topics or topic not in all_topics.get(subject, {}):
                    self.mid_term.update_weak_point(student_id, topic, mastery, subject)

    def get_student_profile(self, student_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取学生完整画像，整合三层存储。

        Args:
            student_id: 学生 ID。
            session_id: 会话 ID（可选，用于附加当前会话上下文）。

        Returns:
            {
                "student_id": str,
                "weak_points": List[dict],      # 薄弱知识点
                "strengths": List[dict],        # 已掌握知识点
                "knowledge_graph": dict,        # 知识图谱概览
                "session_context": str | None,  # 当前会话上下文
                "all_topics": dict,             # 所有知识点数据
            }
        """
        # 首次访问：从长期记忆恢复中期数据（服务重启后自愈）
        if student_id not in self._synced_students:
            self.sync_long_to_mid(student_id)
            self._synced_students.add(student_id)

        # 短期记忆：会话上下文
        session_context = None
        if session_id:
            session_context = self.short_term.get_context(session_id, last_n=10)

        # 中期记忆：薄弱点和强项
        weak_points = self.mid_term.get_weak_points(student_id)
        strengths = self.mid_term.get_strong_points(student_id)
        all_topics = self.mid_term.get_all_topics(student_id)

        # 长期记忆：知识图谱
        knowledge_graph = self.long_term.get_student_graph(student_id)

        # 学生元数据（姓名等）
        metadata = self.mid_term.get_metadata(student_id)

        # 汇总薄弱点名称（扁平列表，兼容现有接口）
        weak_point_names = [wp["topic"] for wp in weak_points]

        return {
            "student_id": student_id,
            "name": metadata.get("name", ""),
            "weak_points": weak_point_names,
            "weak_points_detail": weak_points,
            "strengths": [s["topic"] for s in strengths],
            "strengths_detail": strengths,
            "knowledge_graph": knowledge_graph,
            "session_context": session_context,
            "all_topics": all_topics,
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    #  学生画像更新
    # ------------------------------------------------------------------

    def update_weak_point(
        self,
        student_id: str,
        topic: str,
        score: float,
        subject: str = "general",
    ):
        """
        更新学生某个知识点的得分（同时更新中期和长期记忆）。

        Args:
            student_id: 学生 ID。
            topic: 知识点名称。
            score: 得分（0-1），越高表示掌握越好。
            subject: 科目名称。
        """
        self.mid_term.update_weak_point(
            student_id=student_id,
            topic=topic,
            score=score,
            subject=subject,
        )
        # 自动同步到长期记忆
        self.long_term.store_knowledge(
            student_id=student_id,
            topic=topic,
            content=f"知识点: {topic} (科目: {subject}) - 掌握程度: {score:.0%}",
            mastery=score,
            subject=subject,
        )

    def store_knowledge(
        self,
        student_id: str,
        topic: str,
        content: str,
        mastery: float,
        subject: str = "general",
    ):
        """
        存储知识点到知识图谱（长期记忆）。

        Args:
            student_id: 学生 ID。
            topic: 知识点名称。
            content: 知识点内容文本。
            mastery: 掌握程度（0-1）。
            subject: 科目名称。
        """
        self.long_term.store_knowledge(
            student_id=student_id,
            topic=topic,
            content=content,
            mastery=mastery,
            subject=subject,
        )

    def add_session_message(self, session_id: str, message: Dict[str, Any]):
        """
        添加会话消息（短期记忆）。

        Args:
            session_id: 会话 ID。
            message: 消息字典。
        """
        self.short_term.add_message(session_id, message)

    def set_metadata(self, student_id: str, key: str, value: Any):
        """
        设置学生元数据（如姓名）。

        Args:
            student_id: 学生 ID。
            key: 元数据键名。
            value: 元数据值。
        """
        self.mid_term.set_metadata(student_id, key, value)

    def get_metadata(self, student_id: str, key: Optional[str] = None) -> Any:
        """
        获取学生元数据。

        Args:
            student_id: 学生 ID。
            key: 元数据键名（None 返回全部）。

        Returns:
            元数据值。
        """
        return self.mid_term.get_metadata(student_id, key)

    # ------------------------------------------------------------------
    #  清理
    # ------------------------------------------------------------------

    def cleanup_session(self, session_id: str):
        """清理指定会话的短期记忆。"""
        self.short_term.clear_session(session_id)

    def cleanup_expired_sessions(self):
        """清理所有过期的短期会话。"""
        self.short_term.cleanup()

    def clear_student(self, student_id: str):
        """清除学生的所有记忆数据。"""
        self.mid_term.clear_student(student_id)
        self.long_term.delete_student_graph(student_id)

    def __repr__(self) -> str:
        return "<LearningMemory>"
