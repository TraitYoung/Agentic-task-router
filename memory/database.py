import sqlite3
from pathlib import Path


class PersonaMemory:
    def __init__(self, db_path: str = "./data/axiodrasil_core.db"):
        # 确保数据库所在目录存在（首次运行不报错）
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化豪威尔记忆矩阵表 + FTS5 视图 + 向量表"""
        with sqlite3.connect(self.db_path) as conn:
            # 1) 原始记忆矩阵
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_matrix (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT,
                    quadrant TEXT,
                    content TEXT,
                    status TEXT DEFAULT 'active', -- active / archived
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # 为高频查询字段添加联合索引
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_thread_quadrant_status
                ON memory_matrix (thread_id, quadrant, status)
                """
            )

            # 2) 向量表：存放 text-embedding-3-small 1536 维向量
            # 冷启动与增量更新交由 migration/上层逻辑负责
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    memory_id INTEGER PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES memory_matrix(id) ON DELETE CASCADE
                )
                """
            )

            # 3) FTS5 虚拟表：映射 memory_matrix
            # 采用 external content 模式，仅索引必要字段
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(
                    content,
                    quadrant,
                    thread_id,
                    content='memory_matrix',
                    content_rowid='id'
                )
                """
            )

            # 4) 触发器：保持 memory_matrix 与 memory_fts 同步
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS memory_matrix_ai
                AFTER INSERT ON memory_matrix
                BEGIN
                    INSERT INTO memory_fts(rowid, content, quadrant, thread_id)
                    VALUES (new.id, new.content, new.quadrant, new.thread_id);
                END;

                CREATE TRIGGER IF NOT EXISTS memory_matrix_ad
                AFTER DELETE ON memory_matrix
                BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, quadrant, thread_id)
                    VALUES('delete', old.id, old.content, old.quadrant, old.thread_id);
                END;

                CREATE TRIGGER IF NOT EXISTS memory_matrix_au
                AFTER UPDATE ON memory_matrix
                BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, quadrant, thread_id)
                    VALUES('delete', old.id, old.content, old.quadrant, old.thread_id);
                    INSERT INTO memory_fts(rowid, content, quadrant, thread_id)
                    VALUES (new.id, new.content, new.quadrant, new.thread_id);
                END;
                """
            )

            conn.commit()

    def save_memory(self, thread_id: str, content: str, quadrant: str) -> None:
        """存入记忆（文本部分）。向量部分由上层在生成 embedding 后写入 memory_embeddings。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memory_matrix (thread_id, content, quadrant) VALUES (?, ?, ?)",
                (thread_id, content, quadrant),
            )
            conn.commit()

    def get_active_q1(self, thread_id: str):
        """获取指定对话下所有未完成的 Q1 (重要且紧急) 指令，用于注入上下文"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT content
                FROM memory_matrix
                WHERE thread_id = ? AND quadrant = 'Q1' AND status = 'active'
                """,
                (thread_id,),
            )
            return [row[0] for row in cursor.fetchall()]