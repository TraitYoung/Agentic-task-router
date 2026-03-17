import sqlite3
from typing import List, Tuple, Optional, Dict, Any

import numpy as np


class HybridRetriever:
    """
    工业级双路召回 + RRF 融合检索引擎。

    - 路 1：SQLite FTS5 关键词检索（BM25 排序）
    - 路 2：向量语义检索（余弦相似度）
    - 融合：Reciprocal Rank Fusion (RRF)
    """

    def __init__(self, db_path: str = "./data/axiodrasil_core.db", k: int = 60):
        self.db_path = db_path
        self.k = k  # RRF 常数，防止长尾放大

    # --------- 路 1：FTS5 关键词检索 ---------
    def _get_keyword_scores(
        self,
        query: str,
        top_n: int = 10,
        thread_id: Optional[str] = None,
        quadrant: Optional[str] = None,
    ) -> List[int]:
        """
        使用 SQLite FTS5 对 memory_fts 进行 BM25 检索。

        返回：按相关度排序的 memory_matrix.id 列表（只关心 rank）。
        """
        # NOTE: 默认 FTS5 分词器对中文支持一般，建议后续通过迁移脚本
        # 对历史数据进行 jieba 预分词后再写入 FTS 表。
        conditions = ["memory_fts MATCH ?"]
        params: List[Any] = [query]

        if thread_id is not None:
            conditions.append("memory_fts.thread_id = ?")
            params.append(thread_id)

        if quadrant is not None:
            conditions.append("memory_fts.quadrant = ?")
            params.append(quadrant)

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT rowid, bm25(memory_fts) AS score
        FROM memory_fts
        WHERE {where_clause}
        ORDER BY score ASC
        LIMIT ?
        """
        params.append(top_n)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

        # rows: [(id, score), ...]，这里只需要按顺序的 id
        return [row[0] for row in rows]

    # --------- 路 2：向量语义检索 ---------
    def _get_vector_scores(
        self,
        query_embedding: np.ndarray,
        top_n: int = 10,
        thread_id: Optional[str] = None,
        quadrant: Optional[str] = None,
    ) -> List[int]:
        """
        使用 memory_embeddings 中的向量，基于余弦相似度做语义检索。

        要求：memory_embeddings.embedding 存放 text-embedding-3-small 1536 维 float32 向量（BLOB）。
        """
        if query_embedding is None:
            return []

        # 归一化查询向量
        q = query_embedding.astype(np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        base_sql = """
        SELECT e.memory_id, e.embedding
        FROM memory_embeddings AS e
        JOIN memory_matrix AS m ON m.id = e.memory_id
        WHERE m.status = 'active'
        """

        params: List[Any] = []
        if thread_id is not None:
            base_sql += " AND m.thread_id = ?"
            params.append(thread_id)
        if quadrant is not None:
            base_sql += " AND m.quadrant = ?"
            params.append(quadrant)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(base_sql, params)
            rows = cursor.fetchall()

        if not rows:
            return []

        ids: List[int] = []
        embeddings: List[np.ndarray] = []
        for memory_id, blob in rows:
            if blob is None:
                continue
            vec = np.frombuffer(blob, dtype=np.float32)
            if vec.size == 0:
                continue
            ids.append(memory_id)
            embeddings.append(vec)

        if not embeddings:
            return []

        mat = np.vstack(embeddings)  # (N, D)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms

        # 余弦相似度
        sims = np.dot(mat, q)  # (N,)

        # 根据相似度排序取前 top_n
        top_indices = np.argsort(-sims)[:top_n]
        ranked_ids = [ids[i] for i in top_indices]
        return ranked_ids

    # --------- RRF 融合 ---------
    def rrf_fusion(
        self,
        keyword_results: List[int],
        vector_results: List[int],
    ) -> List[Tuple[int, float]]:
        """
        倒数排名融合 (Reciprocal Rank Fusion, RRF)

        score(d) = sum_{list∈{K,V}} 1 / (k + rank_{list}(d))
        """
        scores: Dict[int, float] = {}

        for rank, doc_id in enumerate(keyword_results):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.k + rank + 1)

        for rank, doc_id in enumerate(vector_results):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.k + rank + 1)

        # 按 RRF 分数从高到低排序
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # --------- 对外主入口：Hybrid 检索 ---------
    def search_hybrid(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_k: int = 5,
        thread_id: Optional[str] = None,
        quadrant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        对外暴露的 Hybrid 检索接口。

        - 输入：自然语言 query + 已计算好的向量 query_embedding
        - 内部：FTS5 + 向量检索，两路召回后用 RRF 融合
        - 输出：按相关度排序的前 top_k 条 memory_matrix 记录
        """
        # 两路召回
        keyword_ids = self._get_keyword_scores(
            query=query,
            top_n=top_k * 4,  # 多召回一些，便于融合重排
            thread_id=thread_id,
            quadrant=quadrant,
        )

        vector_ids = self._get_vector_scores(
            query_embedding=query_embedding,
            top_n=top_k * 4,
            thread_id=thread_id,
            quadrant=quadrant,
        )

        # RRF 融合
        fused = self.rrf_fusion(keyword_ids, vector_ids)
        if not fused:
            return []

        top_ids = [doc_id for doc_id, _ in fused[:top_k]]
        if not top_ids:
            return []

        placeholders = ",".join("?" for _ in top_ids)
        sql = f"""
        SELECT id, thread_id, quadrant, content, status, created_at
        FROM memory_matrix
        WHERE id IN ({placeholders})
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, top_ids)
            rows = cursor.fetchall()

        # 将结果转为字典列表，方便上层直接使用
        result = [
            {
                "id": row[0],
                "thread_id": row[1],
                "quadrant": row[2],
                "content": row[3],
                "status": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

        # 为了与 RRF 排名保持一致，需要按 top_ids 的顺序重排
        id_to_item = {item["id"]: item for item in result}
        ordered = [id_to_item[i] for i in top_ids if i in id_to_item]
        return ordered


__all__ = ["HybridRetriever"]

