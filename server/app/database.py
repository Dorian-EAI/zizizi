"""数据库连接与 ORM 基类"""

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

_engine_options = {
    "pool_pre_ping": True,
    "echo": settings.APP_DEBUG,
}
if settings.DB_DRIVER == "sqlite":
    _engine_options["connect_args"] = {"check_same_thread": False}
    if settings.SQLITE_PATH == ":memory:":
        # 测试环境的内存 SQLite 必须跨 Session 复用同一连接。
        _engine_options["poolclass"] = StaticPool
else:
    _engine_options.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(settings.database_url, **_engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
