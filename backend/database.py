"""数据库配置模块。

集中管理 SQLAlchemy 的数据库连接、会话工厂和基础模型类。
"""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 使用项目根目录下的 SQLite 数据库文件。
DATABASE_URL = "sqlite:///./enterprise.db"

engine = create_engine(
    DATABASE_URL,
    # SQLite 默认限制同一连接只能在单线程中使用。
    # FastAPI 本地开发时通常需要关闭这个限制。
    connect_args={"check_same_thread": False}
)

# SessionLocal 是每次请求使用的数据库会话工厂。
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 所有 ORM 模型都继承这个 Base。
Base = declarative_base()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = PROJECT_ROOT / "enterprise.db"

EXTRA_ENTERPRISE_COLUMNS = {
    "data_sources": "TEXT",
    "evidence_summary": "TEXT",
    "source_count": "INTEGER DEFAULT 0",
    "company_size": "VARCHAR(50)",
    "profile_tags": "TEXT",
    "confidence_level": "VARCHAR(50)",
    "chain_position": "VARCHAR(50)",
    "upstream_enterprises": "TEXT",
    "downstream_enterprises": "TEXT",
    "related_enterprises": "TEXT",
    "llm_summary": "TEXT",
    "llm_label_suggestion": "VARCHAR(100)",
    "llm_provider": "VARCHAR(100)",
    "crawler_status": "VARCHAR(50)",
}


def get_db():
    """为 FastAPI 依赖注入提供数据库会话，并在请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_enterprise_schema():
    """兼容旧 SQLite 数据库，自动补齐新增字段。"""
    if not SQLITE_PATH.exists():
        return

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(enterprises)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in EXTRA_ENTERPRISE_COLUMNS.items():
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE enterprises ADD COLUMN {column_name} {column_type}"
            )

    conn.commit()
    conn.close()
