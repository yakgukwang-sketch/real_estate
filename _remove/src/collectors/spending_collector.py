"""서울시 상권분석서비스 추정매출 수집."""

import logging

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class SpendingCollector(BaseCollector):
    """서울 열린데이터 광장 - 상권 추정매출 API."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.seoul_open_api_key,
            base_url=settings.seoul_api_base,
            cache_ttl_hours=72,
        )

    def collect(
        self,
        year: int = 2024,
        quarter: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        """분기별 상권 추정매출 수집.

        Args:
            year: 연도
            quarter: 분기 (1~4)
        """
        start_idx = 1
        batch_size = 1000
        all_rows = []
        stdr_qu_cd = f"{year}{quarter}"

        while True:
            end_idx = start_idx + batch_size - 1
            url = (
                f"{settings.seoul_api_base}/{self.api_key}/json/"
                f"{settings.spending_endpoint}/{start_idx}/{end_idx}/{stdr_qu_cd}"
            )
            params = {}

            try:
                data = self.fetch_with_cache(url, params)
            except Exception:
                logger.exception("추정매출 API 호출 실패")
                break

            if not isinstance(data, dict):
                break

            api_data = data.get(settings.spending_endpoint)
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
            "STDR_QU_CD": "기준분기코드",
            "TRDAR_SE_CD": "상권구분코드",
            "TRDAR_SE_NM": "상권구분명",
            "TRDAR_CD": "상권코드",
            "TRDAR_CD_NM": "상권명",
            "SVC_INDUTY_CD": "서비스업종코드",
            "SVC_INDUTY_CD_NM": "서비스업종명",
            "THSMON_SELNG_AMT": "당월매출금액",
            "THSMON_SELNG_CO": "당월매출건수",
            "ML_SELNG_AMT": "남성매출금액",
            "FML_SELNG_AMT": "여성매출금액",
            "AGRDE_10_SELNG_AMT": "10대매출금액",
            "AGRDE_20_SELNG_AMT": "20대매출금액",
            "AGRDE_30_SELNG_AMT": "30대매출금액",
            "AGRDE_40_SELNG_AMT": "40대매출금액",
            "AGRDE_50_SELNG_AMT": "50대매출금액",
            "AGRDE_60_ABOVE_SELNG_AMT": "60대이상매출금액",
            "MON_SELNG_AMT": "월요일매출금액",
            "TUES_SELNG_AMT": "화요일매출금액",
            "WED_SELNG_AMT": "수요일매출금액",
            "THUR_SELNG_AMT": "목요일매출금액",
            "FRI_SELNG_AMT": "금요일매출금액",
            "SAT_SELNG_AMT": "토요일매출금액",
            "SUN_SELNG_AMT": "일요일매출금액",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        # 금액 컬럼 숫자 변환
        amt_cols = [c for c in df.columns if "매출금액" in c or "매출건수" in c]
        for col in amt_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
