from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)
DATABASE_URL = "sqlite:///./data/cloaktoast.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_add_columns(eng=None) -> None:
    """为已有数据库补充 profiles 表的新列，幂等，遇到异常不阻断启动。"""
    _engine = eng or engine
    new_cols = [
        # 第一批：省流字段（4363f4a）
        ("block_video",       "INTEGER DEFAULT 0"),
        ("block_image_max_kb","INTEGER"),
        # 第二批：WebRTC 模式 / GeoIP / 中继代理（本次会话）
        ("fp_webrtc_mode",   "TEXT    DEFAULT ''"),
        ("geoip",            "INTEGER DEFAULT 0"),
        ("relay_proxy_type", "TEXT    DEFAULT 'none'"),
        ("relay_proxy_host", "TEXT    DEFAULT ''"),
        ("relay_proxy_port", "INTEGER"),
        ("relay_proxy_user", "TEXT    DEFAULT ''"),
        ("relay_proxy_pass", "TEXT    DEFAULT ''"),
    ]
    try:
        with _engine.connect() as conn:
            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(profiles)"))
            }
            for col_name, col_def in new_cols:
                if col_name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_def}")
                    )
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME
                )
            """))
            conn.commit()
    except Exception as exc:
        import logging
        logging.getLogger("cloaktoast").warning("DB migration warning: %s", exc)
