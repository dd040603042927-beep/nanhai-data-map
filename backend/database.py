"""数据库配置模块。

集中管理 SQLAlchemy 的数据库连接、会话工厂和基础模型类。
"""

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


def get_db():
    """为 FastAPI 依赖注入提供数据库会话，并在请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
