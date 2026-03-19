"""생활인구/직장인구 데이터 정제."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class PopulationProcessor:
    """생활인구 데이터 정제 및 집계."""

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """기본 정제."""
        if df.empty:
            return df
        df = df.copy()
        if "기준일" in df.columns:
            df["기준일"] = pd.to_datetime(df["기준일"], errors="coerce")
            df["연월"] = df["기준일"].dt.to_period("M").astype(str)
        return df

    def aggregate_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """월별 행정동별 생활인구 집계."""
        if df.empty or "행정동코드" not in df.columns:
            return pd.DataFrame()

        df = self.process(df)
        return (
            df.groupby(["연월", "행정동코드"])
            .agg(
                평균생활인구=("총생활인구", "mean"),
                최대생활인구=("총생활인구", "max"),
                평균남성=("남성생활인구", "mean"),
                평균여성=("여성생활인구", "mean"),
            )
            .reset_index()
            .round(0)
        )

    def peak_hours(self, df: pd.DataFrame, dong_code: str) -> pd.DataFrame:
        """특정 행정동의 시간대별 생활인구 피크."""
        if df.empty or "시간대" not in df.columns:
            return pd.DataFrame()

        dong_df = df[df["행정동코드"] == dong_code]
        return (
            dong_df.groupby("시간대")
            .agg(평균생활인구=("총생활인구", "mean"))
            .reset_index()
            .sort_values("시간대")
        )
