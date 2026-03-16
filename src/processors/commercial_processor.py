"""상권/상가 데이터 정제."""

import logging

import pandas as pd

from src.processors.geo_processor import GeoProcessor

logger = logging.getLogger(__name__)


class CommercialProcessor:
    """상가업소 데이터를 행정동 기준으로 집계."""

    def __init__(self, geo: GeoProcessor | None = None):
        self.geo = geo or GeoProcessor()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """상가업소 데이터 정제 및 좌표-행정동 매핑."""
        if df.empty:
            return df

        df = df.copy()

        # 좌표가 있으면 행정동 매핑
        if "위도" in df.columns and "경도" in df.columns:
            has_coords = df["위도"].notna() & df["경도"].notna()
            if has_coords.any() and "행정동코드" not in df.columns:
                df = self.geo.coords_to_dong_batch(df, lat_col="위도", lon_col="경도")

        return df

    def aggregate_by_dong(self, df: pd.DataFrame) -> pd.DataFrame:
        """행정동별 업종 분포 집계."""
        if df.empty:
            return df

        group_cols = ["행정동코드"]
        if "행정동명" in df.columns:
            group_cols.append("행정동명")

        agg = (
            df.groupby(group_cols)
            .agg(
                총업소수=("상호명", "count"),
                대분류수=("대분류명", "nunique") if "대분류명" in df.columns else ("상호명", "count"),
            )
            .reset_index()
        )
        return agg

    def category_distribution(self, df: pd.DataFrame, dong_code: str | None = None) -> pd.DataFrame:
        """업종 대분류별 분포."""
        if df.empty or "대분류명" not in df.columns:
            return pd.DataFrame()

        if dong_code:
            df = df[df["행정동코드"] == dong_code]

        return (
            df.groupby("대분류명")
            .size()
            .reset_index(name="업소수")
            .sort_values("업소수", ascending=False)
        )
