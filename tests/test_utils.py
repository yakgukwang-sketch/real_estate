"""유틸리티 모듈 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.utils.geo_utils import haversine
from src.utils.cache import ApiCache


def test_haversine_same_point():
    assert haversine(37.5, 127.0, 37.5, 127.0) == 0.0


def test_haversine_known_distance():
    # 서울역 ↔ 강남역 약 8.6km
    dist = haversine(37.5547, 126.9707, 37.4979, 127.0276)
    assert 7.0 < dist < 10.0


def test_cache_set_get(tmp_path):
    cache = ApiCache(db_path=tmp_path / "test.sqlite", ttl_hours=1)
    cache.set("test_ep", {"key": "val"}, {"result": 42})
    result = cache.get("test_ep", {"key": "val"})
    assert result == {"result": 42}


def test_cache_miss(tmp_path):
    cache = ApiCache(db_path=tmp_path / "test.sqlite", ttl_hours=1)
    assert cache.get("nonexistent", {}) is None


def test_cache_clear(tmp_path):
    cache = ApiCache(db_path=tmp_path / "test.sqlite", ttl_hours=1)
    cache.set("ep", {}, {"data": 1})
    cache.clear()
    assert cache.get("ep", {}) is None
