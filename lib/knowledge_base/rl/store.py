"""Experience Store

基于 SQLite 的经验存储模块，支持向量检索。
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .experience import Experience, ExperienceBatch, ExperienceType


class ExperienceStore:
    """经验存储

    使用 SQLite 存储经验数据，支持批量查询和基本统计。
    """

    def __init__(self, db_path: str = ".young/rl_experiences.db"):
        """初始化存储

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        """确保目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 经验表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                content TEXT NOT NULL,
                reward REAL DEFAULT 0.0,
                total_reward REAL DEFAULT 0.0,
                rewards TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exp_type TEXT DEFAULT 'episode',
                steps TEXT,
                metadata TEXT,
                group_id TEXT,
                rank INTEGER,
                advantage REAL DEFAULT 0.0,
                model_name TEXT DEFAULT 'default',
                temperature REAL DEFAULT 0.7,
                generation_params TEXT
            )
        """)

        # 组信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experience_groups (
                group_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                task_id TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 训练统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                policy_loss REAL DEFAULT 0.0,
                value_loss REAL DEFAULT 0.0,
                entropy_loss REAL DEFAULT 0.0,
                total_loss REAL DEFAULT 0.0,
                mean_advantage REAL DEFAULT 0.0,
                max_advantage REAL DEFAULT 0.0,
                min_advantage REAL DEFAULT 0.0,
                mean_reward REAL DEFAULT 0.0,
                max_reward REAL DEFAULT 0.0,
                min_reward REAL DEFAULT 0.0,
                learning_rate REAL DEFAULT 0.0,
                clip_fraction REAL DEFAULT 0.0,
                explained_variance REAL DEFAULT 0.0
            )
        """)

        # 创建索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_id ON experiences(task_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_type ON experiences(task_type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_group_id ON experiences(group_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reward ON experiences(reward DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_created_at ON experiences(created_at DESC)"
        )

        conn.commit()
        conn.close()

    def save_experience(self, experience: Experience) -> str:
        """保存单条经验

        Args:
            experience: 经验数据

        Returns:
            经验 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO experiences
            (id, task_id, task_type, prompt, content, reward, total_reward,
             rewards, created_at, exp_type, steps, metadata, group_id, rank,
             advantage, model_name, temperature, generation_params)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experience.id,
                experience.task_id,
                experience.task_type,
                experience.prompt,
                experience.content,
                experience.reward,
                experience.total_reward,
                json.dumps(experience.rewards),
                experience.created_at.isoformat(),
                experience.exp_type.value,
                json.dumps([s.to_dict() for s in experience.steps]),
                json.dumps(experience.metadata),
                experience.group_id,
                experience.rank,
                experience.advantage,
                experience.model_name,
                experience.temperature,
                json.dumps(experience.generation_params),
            ),
        )

        conn.commit()
        conn.close()
        return experience.id

    def save_batch(self, batch: ExperienceBatch) -> List[str]:
        """批量保存经验

        Args:
            batch: 经验批次

        Returns:
            保存的经验 ID 列表
        """
        ids = []
        for exp in batch.experiences:
            exp.group_id = batch.group_id
            exp_id = self.save_experience(exp)
            ids.append(exp_id)

        # 保存组信息
        if batch.group_id:
            self._save_group(batch)

        return ids

    def _save_group(self, batch: ExperienceBatch) -> None:
        """保存组信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO experience_groups
            (group_id, task_type, task_id, size, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                batch.group_id,
                batch.task_type or "unknown",
                batch.experiences[0].task_id if batch.experiences else "",
                batch.size,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def get_experience(self, exp_id: str) -> Optional[Experience]:
        """获取单条经验

        Args:
            exp_id: 经验 ID

        Returns:
            经验数据或 None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM experiences WHERE id = ?", (exp_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_experience(row)
        return None

    def get_experiences(
        self,
        task_id: Optional[str] = None,
        task_type: Optional[str] = None,
        group_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Experience]:
        """查询经验列表

        Args:
            task_id: 任务 ID
            task_type: 任务类型
            group_id: 组 ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            经验列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)

        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)

        if group_id:
            conditions.append("group_id = ?")
            params.append(group_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM experiences
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_experience(row) for row in rows]

    def get_group_experiences(self, group_id: str) -> ExperienceBatch:
        """获取组内所有经验

        Args:
            group_id: 组 ID

        Returns:
            经验批次
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM experiences WHERE group_id = ? ORDER BY reward DESC",
            (group_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        experiences = [self._row_to_experience(row) for row in rows]
        return ExperienceBatch(
            experiences=experiences,
            group_id=group_id,
            task_type=experiences[0].task_type if experiences else None,
        )

    def get_latest_experiences(
        self, task_type: Optional[str] = None, limit: int = 100
    ) -> List[Experience]:
        """获取最新的经验

        Args:
            task_type: 任务类型过滤
            limit: 返回数量

        Returns:
            经验列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if task_type:
            cursor.execute(
                """
                SELECT * FROM experiences
                WHERE task_type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_type, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM experiences
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_experience(row) for row in rows]

    def _row_to_experience(self, row: sqlite3.Row) -> Experience:
        """将数据库行转换为 Experience 对象"""
        rewards = json.loads(row["rewards"]) if row["rewards"] else {}
        steps = json.loads(row["steps"]) if row["steps"] else []
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        generation_params = (
            json.loads(row["generation_params"])
            if row["generation_params"]
            else {}
        )

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        exp_type = ExperienceType(row["exp_type"])

        # 解析 steps
        from .experience import StepData

        step_data = [StepData.from_dict(s) for s in steps]

        return Experience(
            id=row["id"],
            task_id=row["task_id"],
            task_type=row["task_type"],
            prompt=row["prompt"],
            content=row["content"],
            reward=row["reward"],
            total_reward=row["total_reward"],
            rewards=rewards,
            created_at=created_at,
            exp_type=exp_type,
            steps=step_data,
            metadata=metadata,
            group_id=row["group_id"],
            rank=row["rank"],
            advantage=row["advantage"],
            model_name=row["model_name"],
            temperature=row["temperature"],
            generation_params=generation_params,
        )

    def delete_experience(self, exp_id: str) -> bool:
        """删除经验

        Args:
            exp_id: 经验 ID

        Returns:
            是否成功删除
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM experiences WHERE id = ?", (exp_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def delete_old_experiences(self, keep_count: int = 1000) -> int:
        """删除旧经验，保留最新的

        Args:
            keep_count: 保留数量

        Returns:
            删除的数量
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM experiences
            WHERE id NOT IN (
                SELECT id FROM experiences
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (keep_count,),
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总经验数
        cursor.execute("SELECT COUNT(*) FROM experiences")
        total_count = cursor.fetchone()[0]

        # 按任务类型统计
        cursor.execute(
            """
            SELECT task_type, COUNT(*) as count, AVG(reward) as avg_reward
            FROM experiences
            GROUP BY task_type
            """
        )
        task_stats = [
            {"task_type": row[0], "count": row[1], "avg_reward": row[2]}
            for row in cursor.fetchall()
        ]

        # 组数量
        cursor.execute("SELECT COUNT(DISTINCT group_id) FROM experiences WHERE group_id IS NOT NULL")
        group_count = cursor.fetchone()[0]

        # 最近奖励统计
        cursor.execute(
            """
            SELECT AVG(reward), MAX(reward), MIN(reward)
            FROM experiences
            WHERE created_at > datetime('now', '-1 day')
            """
        )
        row = cursor.fetchone()
        recent_stats = {
            "avg_reward": row[0] or 0.0,
            "max_reward": row[1] or 0.0,
            "min_reward": row[2] or 0.0,
        }

        conn.close()

        return {
            "total_experiences": total_count,
            "total_groups": group_count,
            "task_stats": task_stats,
            "recent_stats": recent_stats,
        }

    def save_training_stats(self, stats: Dict[str, Any]) -> None:
        """保存训练统计

        Args:
            stats: 统计字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO training_stats
            (step, policy_loss, value_loss, entropy_loss, total_loss,
             mean_advantage, max_advantage, min_advantage,
             mean_reward, max_reward, min_reward,
             learning_rate, clip_fraction, explained_variance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stats.get("step", 0),
                stats.get("policy_loss", 0.0),
                stats.get("value_loss", 0.0),
                stats.get("entropy_loss", 0.0),
                stats.get("total_loss", 0.0),
                stats.get("mean_advantage", 0.0),
                stats.get("max_advantage", 0.0),
                stats.get("min_advantage", 0.0),
                stats.get("mean_reward", 0.0),
                stats.get("max_reward", 0.0),
                stats.get("min_reward", 0.0),
                stats.get("learning_rate", 0.0),
                stats.get("clip_fraction", 0.0),
                stats.get("explained_variance", 0.0),
            ),
        )

        conn.commit()
        conn.close()

    def get_training_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取训练历史

        Args:
            limit: 返回数量

        Returns:
            训练历史列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM training_stats
            ORDER BY step DESC
            LIMIT ?
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


# 单例实例
_store: Optional[ExperienceStore] = None


def get_experience_store(db_path: str = ".young/rl_experiences.db") -> ExperienceStore:
    """获取经验存储单例

    Args:
        db_path: 数据库路径

    Returns:
        ExperienceStore 实例
    """
    global _store
    if _store is None:
        _store = ExperienceStore(db_path)
    return _store
