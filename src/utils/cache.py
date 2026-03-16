"""SQLite 기반 API 응답 캐시."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from config.settings import CACHE_DIR


class ApiCache:
    """endpoint + params + date 조합으로 API 응답을 캐싱."""

    def __init__(self, db_path: Path | None = None, ttl_hours: int = 24):
        self.db_path = db_path or (CACHE_DIR / "api_cache.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    @staticmethod
    def _make_key(endpoint: str, params: dict) -> str:
        raw = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, endpoint: str, params: dict) -> dict | list | None:
        key = self._make_key(endpoint, params)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT response, created_at FROM cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if time.time() - row[1] > self.ttl_seconds:
            self.delete(endpoint, params)
            return None
        return json.loads(row[0])

    def set(self, endpoint: str, params: dict, response: dict | list) -> None:
        key = self._make_key(endpoint, params)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (cache_key, response, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(response, ensure_ascii=False), time.time()),
            )

    def delete(self, endpoint: str, params: dict) -> None:
        key = self._make_key(endpoint, params)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))

    def clear(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
