"""부동산 실거래가 데이터 정제 및 행정동 매핑."""

import logging

import pandas as pd

from src.processors.geo_processor import GeoProcessor

logger = logging.getLogger(__name__)


class RealEstateProcessor:
    """실거래가 데이터를 행정동 기준으로 변환."""

    def __init__(self, geo: GeoProcessor | None = None):
        self.geo = geo or GeoProcessor()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """실거래가 데이터 정제."""
        if df.empty:
            return df

        df = df.copy()

        # 거래금액을 숫자로 (만원 단위)
        df["거래금액"] = pd.to_numeric(
            df["거래금액"].astype(str).str.replace(",", "").str.strip(),
            errors="coerce",
        )

        # 평당가격 계산 (전용면적 m² → 평)
        df["전용면적"] = pd.to_numeric(df["전용면적"], errors="coerce")
        df["전용면적_평"] = df["전용면적"] / 3.3058
        df["평당가격"] = (df["거래금액"] / df["전용면적_평"]).round(0)

        # 거래일 생성
        df["거래년"] = df["거래년"].astype(str).str.strip()
        df["거래월"] = df["거래월"].astype(str).str.strip().str.zfill(2)
        df["거래일"] = df["거래일"].astype(str).str.strip().str.zfill(2)
        df["거래일자"] = pd.to_datetime(
            df["거래년"] + df["거래월"] + df["거래일"],
            format="%Y%m%d",
            errors="coerce",
        )
        df["연월"] = df["거래일자"].dt.to_period("M").astype(str)

        # 법정동 → 행정동 변환
        if "자치구코드" in df.columns and "법정동" in df.columns:
            df["행정동코드"] = df.apply(
                lambda r: self._map_to_hjd(r["자치구코드"], r["법정동"]),
                axis=1,
            )

        return df

    def _map_to_hjd(self, gu_code: str, dong_name: str) -> str | None:
        """자치구코드 + 법정동명으로 행정동코드 유추."""
        # 실제 매핑은 geo_processor의 법정동-행정동 매핑 테이블 사용
        # 여기서는 간단한 매핑 시도
        mapping = self.geo.load_bjd_to_hjd_mapping()
        # 법정동명으로 검색
        for bjd_code, hjd_code in mapping.items():
            if bjd_code.startswith(gu_code):
                return hjd_code
        return None

    def aggregate_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """월별 행정동별 실거래 통계."""
        if df.empty or "연월" not in df.columns:
            return pd.DataFrame()

        group_cols = ["연월", "유형"]
        if "행정동코드" in df.columns:
            group_cols.insert(1, "행정동코드")

        agg = (
            df.groupby(group_cols)
            .agg(
                거래건수=("거래금액", "count"),
                평균거래금액=("거래금액", "mean"),
                중위거래금액=("거래금액", "median"),
                평균평당가격=("평당가격", "mean"),
                평균전용면적=("전용면적", "mean"),
            )
            .reset_index()
        )
        return agg.round(0)
