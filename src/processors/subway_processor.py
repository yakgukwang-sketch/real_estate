"""지하철 승하차 데이터 정제 및 행정동 매핑."""

import logging

import pandas as pd

from src.processors.geo_processor import GeoProcessor

logger = logging.getLogger(__name__)


class SubwayProcessor:
    """지하철 데이터를 행정동 기준으로 변환."""

    def __init__(self, geo: GeoProcessor | None = None):
        self.geo = geo or GeoProcessor()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """지하철 데이터 정제 및 행정동 매핑."""
        if df.empty:
            return df

        df = df.copy()

        # 역명-행정동 매핑
        station_dong = self.geo.subway_stations_to_dong_df()
        df = df.merge(
            station_dong[["역명", "행정동코드", "행정동명", "위도", "경도"]],
            on="역명",
            how="left",
        )

        return df

    def aggregate_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """월별 행정동별 승하차 집계."""
        if df.empty:
            return df

        df = df.copy()
        df["연월"] = df["날짜"].dt.to_period("M").astype(str)

        agg = (
            df.groupby(["연월", "행정동코드", "행정동명"])
            .agg(
                승차총승객수=("승차총승객수", "sum"),
                하차총승객수=("하차총승객수", "sum"),
                역수=("역명", "nunique"),
            )
            .reset_index()
        )
        agg["순유입"] = agg["하차총승객수"] - agg["승차총승객수"]
        return agg

    def analyze_commute_pattern(self, df: pd.DataFrame) -> pd.DataFrame:
        """출퇴근 패턴 분석 - 시간대별 데이터가 있는 경우."""
        if "시간대" not in df.columns:
            logger.warning("시간대 컬럼 없음 - 출퇴근 패턴 분석 불가")
            return pd.DataFrame()

        df = df.copy()
        df["시간"] = pd.to_numeric(df["시간대"], errors="coerce")

        # 아침 7~9시: 하차 >> 승차 = 직장지역
        morning = df[df["시간"].between(7, 9)]
        morning_agg = (
            morning.groupby(["행정동코드", "행정동명"])
            .agg(아침하차=("하차총승객수", "sum"), 아침승차=("승차총승객수", "sum"))
            .reset_index()
        )
        morning_agg["아침순유입"] = morning_agg["아침하차"] - morning_agg["아침승차"]

        # 저녁 18~20시: 승차 >> 하차 = 직장지역 (퇴근)
        evening = df[df["시간"].between(18, 20)]
        evening_agg = (
            evening.groupby(["행정동코드", "행정동명"])
            .agg(저녁하차=("하차총승객수", "sum"), 저녁승차=("승차총승객수", "sum"))
            .reset_index()
        )
        evening_agg["저녁순유출"] = evening_agg["저녁승차"] - evening_agg["저녁하차"]

        result = morning_agg.merge(evening_agg, on=["행정동코드", "행정동명"], how="outer")
        result["지역유형"] = "혼합"
        result.loc[
            (result["아침순유입"] > 0) & (result["저녁순유출"] > 0), "지역유형"
        ] = "직장지역"
        result.loc[
            (result["아침순유입"] < 0) & (result["저녁순유출"] < 0), "지역유형"
        ] = "주거지역"

        return result
