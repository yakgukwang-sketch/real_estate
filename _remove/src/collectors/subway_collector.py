"""서울시 지하철 호선별 역별 승하차 인원 수집."""

import logging

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class SubwayCollector(BaseCollector):
    """서울 열린데이터 광장 - 지하철 승하차 인원."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.seoul_open_api_key,
            base_url=settings.seoul_api_base,
            cache_ttl_hours=72,  # 과거 데이터이므로 캐시 길게
        )

    def _build_url(self, start_idx: int, end_idx: int) -> str:
        """서울 열린데이터 API URL 생성."""
        return (
            f"{settings.seoul_api_base}/{self.api_key}/json/"
            f"{settings.subway_endpoint}/{start_idx}/{end_idx}"
        )

    def collect(
        self,
        year: int = 2024,
        month: int = 1,
        day: int | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """지하철 승하차 데이터 수집.

        Args:
            year: 연도
            month: 월
            day: 일 (None이면 해당 월 전체)

        Returns:
            columns: [날짜, 호선, 역명, 승차총승객수, 하차총승객수]
        """
        if day is not None:
            date_str = f"{year}{month:02d}{day:02d}"
            return self._fetch_day(date_str)

        # 월 전체 수집: 1~31일 순회
        frames = []
        for d in range(1, 32):
            date_str = f"{year}{month:02d}{d:02d}"
            try:
                df = self._fetch_day(date_str)
                if not df.empty:
                    frames.append(df)
            except Exception:
                continue  # 존재하지 않는 날짜 무시
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _fetch_day(self, date_str: str) -> pd.DataFrame:
        """특정 날짜의 승하차 데이터 수집."""
        # 서울 열린데이터 API: /{key}/json/{endpoint}/{start}/{end}/{date}
        url = (
            f"{settings.seoul_api_base}/{self.api_key}/json/"
            f"{settings.subway_endpoint}/1/1000/{date_str}"
        )

        data = self.fetch_with_cache(url, {})
        if not isinstance(data, dict):
            return pd.DataFrame()

        api_data = data.get(settings.subway_endpoint)
        if not api_data:
            return pd.DataFrame()

        # 에러 체크
        result = api_data.get("RESULT", {})
        if result.get("CODE") != "INFO-000":
            logger.warning("API 에러: %s - %s", result.get("CODE"), result.get("MESSAGE"))
            return pd.DataFrame()

        rows = api_data.get("row", [])
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "USE_YMD": "날짜",
            "SBWY_ROUT_LN_NM": "호선",
            "SBWY_STNS_NM": "역명",
            "GTON_TNOPE": "승차총승객수",
            "GTOFF_TNOPE": "하차총승객수",
        })

        # 숫자 변환
        for col in ["승차총승객수", "하차총승객수"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d")
        return df[["날짜", "호선", "역명", "승차총승객수", "하차총승객수"]]

    def collect_monthly_summary(
        self, year: int, month: int
    ) -> pd.DataFrame:
        """월별 역별 승하차 합계."""
        df = self.collect(year=year, month=month)
        if df.empty:
            return df
        return (
            df.groupby(["호선", "역명"])
            .agg(승차총승객수=("승차총승객수", "sum"), 하차총승객수=("하차총승객수", "sum"))
            .reset_index()
            .assign(연월=f"{year}-{month:02d}")
        )
