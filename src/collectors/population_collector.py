"""서울시 생활인구 및 직장인구 수집."""

import logging

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class PopulationCollector(BaseCollector):
    """서울 열린데이터 광장 - 생활인구 API."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.seoul_open_api_key,
            base_url=settings.seoul_api_base,
            cache_ttl_hours=72,
        )

    def collect(
        self,
        year: int = 2024,
        month: int = 1,
        dong_code: str | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """행정동 단위 서울 생활인구 수집.

        Args:
            year: 연도
            month: 월
            dong_code: 특정 행정동코드 (None이면 전체)
        """
        date_str = f"{year}-{month:02d}"
        start_idx = 1
        batch_size = 1000
        all_rows = []

        while True:
            end_idx = start_idx + batch_size - 1
            url = (
                f"{settings.seoul_api_base}/{self.api_key}/json/"
                f"{settings.population_endpoint}/{start_idx}/{end_idx}/{date_str}"
            )
            if dong_code:
                url += f"/{dong_code}"

            params = {}
            try:
                data = self.fetch_with_cache(url, params)
            except Exception:
                logger.exception("생활인구 API 호출 실패: %s", url)
                break

            if not isinstance(data, dict):
                break

            api_data = data.get(settings.population_endpoint)
            if not api_data:
                break

            result = api_data.get("RESULT", {})
            if result.get("CODE") != "INFO-000":
                logger.warning("API 에러: %s", result.get("MESSAGE"))
                break

            rows = api_data.get("row", [])
            if not rows:
                break

            all_rows.extend(rows)

            total = int(api_data.get("list_total_count", 0))
            if end_idx >= total:
                break
            start_idx = end_idx + 1

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        return self._standardize(df)

    def _standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼 표준화."""
        rename_map = {
            "STDR_DE_ID": "기준일",
            "TMZON_PD_SE": "시간대",
            "ADSTRD_CODE_SE": "행정동코드",
            "TOT_LVPOP_CO": "총생활인구",
            "ML_LVPOP_CO": "남성생활인구",
            "FML_LVPOP_CO": "여성생활인구",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        num_cols = ["총생활인구", "남성생활인구", "여성생활인구"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "기준일" in df.columns:
            df["기준일"] = pd.to_datetime(df["기준일"], format="%Y%m%d", errors="coerce")

        return df


class WorkerPopulationCollector(BaseCollector):
    """서울시 사업체/종사자수 수집."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.seoul_open_api_key,
            base_url=settings.seoul_api_base,
            cache_ttl_hours=168,
        )

    def collect(
        self,
        year: int = 2024,
        **kwargs,
    ) -> pd.DataFrame:
        """사업체/종사자수 데이터 수집."""
        start_idx = 1
        batch_size = 1000
        all_rows = []

        while True:
            end_idx = start_idx + batch_size - 1
            url = (
                f"{settings.seoul_api_base}/{self.api_key}/json/"
                f"SgisEstmBzCnt/{start_idx}/{end_idx}/{year}"
            )
            params = {}
            try:
                data = self.fetch_with_cache(url, params)
            except Exception:
                break

            if not isinstance(data, dict):
                break

            api_data = data.get("SgisEstmBzCnt")
            if not api_data:
                break

            rows = api_data.get("row", [])
            if not rows:
                break

            all_rows.extend(rows)
            total = int(api_data.get("list_total_count", 0))
            if end_idx >= total:
                break
            start_idx = end_idx + 1

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        return df
