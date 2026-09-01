"""
OpenInterview - 数据库连接与初始化

统一封装 SQLite 连接与建表逻辑，供 API 与后台任务共同使用。
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
    score_standard TEXT,
    answer_audio BLOB,
    answer_text TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    answered_at INTEGER
);
"""


def get_db(row_factory: bool = False) -> sqlite3.Connection:
    """获取数据库连接。row_factory=True 时返回 sqlite3.Row（按列名访问）"""
    conn = sqlite3.connect(config.DB_PATH)
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）。数据库文件不存在时自动创建。"""
    if not os.path.exists(config.DB_PATH):
        print(f"[db] 数据库文件不存在，正在创建: {config.DB_PATH}")
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"[db] 数据库就绪: {config.DB_PATH}")
