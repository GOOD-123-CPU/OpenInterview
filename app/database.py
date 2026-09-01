"""
OpenInterview - 数据库连接与初始化

统一封装 SQLite 连接与建表逻辑，供 API 与后台任务共同使用。
v2 加固：WAL 模式（并发读写）、外键约束、常用索引、settings 键值表、轻量迁移。
"""
import os
import sqlite3

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    requirements TEXT,
    responsibilities TEXT,
    quantity INTEGER,
    status INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    recruiter TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    resume_content BLOB
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    interviewer TEXT,
    start_time INTEGER,
    end_time INTEGER,
    status INTEGER DEFAULT 0,
    question_count INTEGER,
    is_passed INTEGER,
    voice_reading INTEGER DEFAULT 0,
    report_content BLOB,
    token TEXT
);

CREATE TABLE IF NOT EXISTS interview_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    question_type TEXT DEFAULT 'technical',
    difficulty TEXT DEFAULT 'medium',
    dimension TEXT DEFAULT '综合',
    score_standard TEXT,
    answer_audio BLOB,
    answer_text TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    answered_at INTEGER
);

-- 键值配置表（管理员凭据、系统设置等）
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_interviews_token ON interviews(token);
CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status);
CREATE INDEX IF NOT EXISTS idx_interviews_candidate ON interviews(candidate_id);
CREATE INDEX IF NOT EXISTS idx_questions_interview ON interview_questions(interview_id);
CREATE INDEX IF NOT EXISTS idx_candidates_position ON candidates(position_id);
"""

# v1 → v2 轻量迁移：为旧库补充新列（SQLite 无 ADD COLUMN IF NOT EXISTS）
_MIGRATIONS = [
    ("interview_questions", "question_type", "ALTER TABLE interview_questions ADD COLUMN question_type TEXT DEFAULT 'technical'"),
    ("interview_questions", "difficulty", "ALTER TABLE interview_questions ADD COLUMN difficulty TEXT DEFAULT 'medium'"),
    ("interview_questions", "dimension", "ALTER TABLE interview_questions ADD COLUMN dimension TEXT DEFAULT '综合'"),
]


def get_db(row_factory: bool = False) -> sqlite3.Connection:
    """获取数据库连接。row_factory=True 时返回 sqlite3.Row（按列名访问）"""
    conn = sqlite3.connect(config.DB_PATH)
    if row_factory:
        conn.row_factory = sqlite3.Row
    # WAL 模式：读写并发更友好；外键约束按连接开启
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """建表 + 迁移 + 管理员初始化（幂等）。数据库文件不存在时自动创建。"""
    if not os.path.exists(config.DB_PATH):
        print(f"[db] 数据库文件不存在，正在创建: {config.DB_PATH}")
    conn = get_db()
    conn.executescript(SCHEMA)

    # 轻量列迁移：逐条尝试，列已存在则忽略
    for table, column, ddl in _MIGRATIONS:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            try:
                conn.execute(ddl)
                print(f"[db] 迁移: {table} 增加 {column} 列")
            except sqlite3.OperationalError as e:
                print(f"[db] 迁移跳过 {table}.{column}: {e}")
    conn.commit()

    # 初始化管理员账户（凭据存 settings 表）
    try:
        from security import ensure_admin_account

        ensure_admin_account(conn)
    except Exception as e:
        print(f"[db] 管理员初始化跳过: {e}")

    conn.close()
    print(f"[db] 数据库就绪: {config.DB_PATH}")


if __name__ == "__main__":
    init_db()
