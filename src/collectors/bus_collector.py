"""서울시 버스노선별 정류장별 승하차 인원 수집."""

import logging

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)

BUS_ENDPOINT = "CardBusStatisticsServiceNew"


class BusCollector(BaseCollector):
    """서울 열린데이터 광장 - 버스 승하차 인원."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.seoul_open_api_key,
            base_url=settings.seoul_api_base,
            cache_ttl_hours=72,
        )

    def collect(
        self,
        date: str | None = None,
        year: int = 2024,
        month: int = 1,
        day: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        """버스 승하차 데이터 수집.

        Args:
            date: 날짜 문자열 (YYYYMMDD). 없으면 year/month/day로 생성.
            year: 연도
            month: 월
            day: 일

        Returns:
            columns: [날짜, 노선번호, 노선명, 정류장ID, 정류장번호, 정류장명, 승차인원, 하차인원]
        """
        if date is None:
            date = f"{year}{month:02d}{day:02d}"

        return self._fetch_all_pages(date)

    def collect_month(self, year: int, month: int) -> pd.DataFrame:
        """한 달 전체 수집."""
        frames = []
        for d in range(1, 32):
            date_str = f"{year}{month:02d}{d:02d}"
            try:
                df = self._fetch_all_pages(date_str)
                if not df.empty:
                    frames.append(df)
                    logger.info("%s: %d건", date_str, len(df))
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _fetch_all_pages(self, date_str: str) -> pd.DataFrame:
        """특정 날짜의 전체 페이지 수집 (최대 1000건씩)."""
        all_rows = []
        start = 1
        page_size = 1000

        while True:
            end = start + page_size - 1
            url = (
                f"{settings.seoul_api_base}/{self.api_key}/json/"
                f"{BUS_ENDPOINT}/{start}/{end}/{date_str}"
            )

            data = self.fetch_with_cache(url, {})
            if not isinstance(data, dict):
                break

            api_data = data.get(BUS_ENDPOINT)
            if not api_data:
                break

            result = api_data.get("RESULT", {})
            if result.get("CODE") != "INFO-000":
                break

            rows = api_data.get("row", [])
            if not rows:
                break

            all_rows.extend(rows)
            total = int(api_data.get("list_total_count", 0))
            if end >= total:
                break
            start = end + 1

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        return self._standardize(df)

    def _standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 표준화."""
        rename_map = {
            "USE_YMD": "날짜",
            "USE_DT": "날짜",
            "RTE_NO": "노선번호",
            "BUS_ROUTE_NO": "노선번호",
            "RTE_NM": "노선명",
            "BUS_ROUTE_NM": "노선명",
            "STOPS_ID": "정류장ID",
            "STND_BSSTOP_ID": "정류장ID",
            "STOPS_ARS_NO": "정류장번호",
            "BSSTOP_ARS_NO": "정류장번호",
            "SBWY_STNS_NM": "정류장명",
            "BSSTOP_NM": "정류장명",
            "GTON_TNOPE": "승차인원",
            "RIDE_PASGR_NUM": "승차인원",
            "GTOFF_TNOPE": "하차인원",
            "ALIGHT_PASGR_NUM": "하차인원",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        for col in ["승차인원", "하차인원"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        if "날짜" in df.columns:
            df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d", errors="coerce")

        return df

    def collect_station_summary(self, year: int, month: int) -> pd.DataFrame:
        """월별 정류장별 승하차 합계 (노선 무관)."""
        df = self.collect_month(year, month)
        if df.empty:
            return df
        return (
            df.groupby(["정류장ID", "정류장명"])
            .agg(승차인원=("승차인원", "sum"), 하차인원=("하차인원", "sum"))
            .reset_index()
            .sort_values("하차인원", ascending=False)
            .assign(연월=f"{year}-{month:02d}")
        )
