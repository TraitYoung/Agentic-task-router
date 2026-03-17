import sqlite3

import numpy as np

from memory.database import PersonaMemory
from tools.ai_client import get_embedding


def cold_start_q2_migration(db_path: str = "./data/axiodrasil_core.db") -> None:
    """
    冷启动：将 Q2 象限历史记忆全部向量化，写入 memory_embeddings。

    流程：
    1. 找出所有 quadrant='Q2' 且尚未写入向量表的记录
    2. 调用 embedding 模型生成 1536 维向量
    3. 写入 memory_embeddings(memory_id, embedding)
    """
    print("开始 Q2 记忆语义化迁移...")

    # 确保目标数据库已经按最新 schema 初始化（含 memory_embeddings / memory_fts 等）
    # 这行会在指定 db_path 上跑一次 _init_db()，但不会破坏已有数据。
    PersonaMemory(db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT m.id, m.content
            FROM memory_matrix AS m
            LEFT JOIN memory_embeddings AS e ON m.id = e.memory_id
            WHERE m.quadrant = 'Q2' AND e.memory_id IS NULL
            """
        )
        rows = cursor.fetchall()

        if not rows:
            print("没有发现待迁移的 Q2 记录。")
            return

        for m_id, content in rows:
            # 2. 调用 embedding 模型 (text-embedding-3-small 或同维度模型)
            vector = get_embedding(content)

            if not isinstance(vector, np.ndarray):
                raise TypeError("get_embedding 必须返回 numpy.ndarray")

            # 强制为 float32，形状 (1536,)
            vector = np.asarray(vector, dtype=np.float32).reshape(-1)

            conn.execute(
                "INSERT INTO memory_embeddings (memory_id, embedding) VALUES (?, ?)",
                (m_id, vector.tobytes()),
            )
            print(f"已处理 ID: {m_id}")

        conn.commit()

    print("Q2 迁移闭环完成。")


if __name__ == "__main__":
    cold_start_q2_migration()

