"""공통 데이터 수집기 - 재시도, rate-limit, 캐싱을 통합."""

import logging
from abc import ABC, abstractmethod

import pandas as pd

from src.utils.api_client import ApiClient
from src.utils.cache import ApiCache

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """모든 collector의 베이스 클래스."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        cache_ttl_hours: int = 24,
        rate_limit_delay: float = 0.3,
    ):
        self.api_key = api_key
        self.client = ApiClient(
            base_url=base_url,
            rate_limit_delay=rate_limit_delay,
        )
        self.cache = ApiCache(ttl_hours=cache_ttl_hours)

    def fetch_with_cache(
        self,
        endpoint: str,
        params: dict,
        use_cache: bool = True,
    ) -> dict | list:
        """캐시를 확인하고, 없으면 API 호출 후 캐시에 저장."""
        if use_cache:
            cached = self.cache.get(endpoint, params)
            if cached is not None:
                logger.debug("Cache hit: %s", endpoint)
                return cached

        logger.info("API 호출: %s", endpoint)
        response = self.client.get_json(endpoint, params=params)
        if use_cache:
            self.cache.set(endpoint, params, response)
        return response

    def fetch_xml_with_cache(
        self,
        endpoint: str,
        params: dict,
        use_cache: bool = True,
    ) -> str:
        """XML 응답용 캐시 래퍼."""
        import json
        if use_cache:
            cached = self.cache.get(endpoint, params)
            if cached is not None:
                logger.debug("Cache hit: %s", endpoint)
                return cached if isinstance(cached, str) else json.dumps(cached)

        logger.info("API 호출 (XML): %s", endpoint)
        response = self.client.get_xml(endpoint, params=params)
        if use_cache:
            self.cache.set(endpoint, params, response)
        return response

    @abstractmethod
    def collect(self, **kwargs) -> pd.DataFrame:
        """데이터를 수집하여 DataFrame으로 반환."""

    def collect_range(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        **kwargs,
    ) -> pd.DataFrame:
        """지정 기간 동안의 데이터를 월 단위로 수집."""
        frames = []
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            try:
                df = self.collect(year=year, month=month, **kwargs)
                if not df.empty:
                    frames.append(df)
                    logger.info("%d-%02d: %d건 수집", year, month, len(df))
            except Exception:
                logger.exception("%d-%02d 수집 실패", year, month)
            month += 1
            if month > 12:
                month = 1
                year += 1
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
