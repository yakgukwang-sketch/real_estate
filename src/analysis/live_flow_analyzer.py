"""실시간 스냅샷 기반 시간대별 유동 분석.

누적된 실시간 인구 스냅샷에서:
1. 장소별 시간대별 인구 곡선 생성
2. 유입/유출 피크 시간 식별
3. 장소별 "기능" 추정 (출근지/주거지/상권/관광지)
4. 평일 vs 주말 패턴 비교
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LiveFlowAnalyzer:
    """실시간 스냅샷에서 시간대별 유동 패턴 분석."""

    def build_hourly_profile(self, snapshots_df: pd.DataFrame) -> pd.DataFrame:
        """장소별 시간대별 평균 인구 프로파일 생성.

        Args:
            snapshots_df: 장소명, 수집시간, 추정인구 컬럼 필요

        Returns:
            장소별 0~23시 평균 인구
        """
        required = {"장소명", "수집시간", "추정인구"}
        if not required.issubset(snapshots_df.columns):
            return pd.DataFrame()

        profile = (
            snapshots_df.groupby(["장소명", "수집시간"])["추정인구"]
            .mean()
            .round(0)
            .astype(int)
            .reset_index()
        )
        return profile

    def build_hourly_pivot(self, snapshots_df: pd.DataFrame) -> pd.DataFrame:
        """장소 × 시간대 피벗 테이블.

        Returns:
            index=장소명, columns=0~23, values=평균 추정인구
        """
        profile = self.build_hourly_profile(snapshots_df)
        if profile.empty:
            return pd.DataFrame()

        return profile.pivot_table(
            index="장소명", columns="수집시간", values="추정인구"
        ).fillna(0)

    def classify_area_function(self, snapshots_df: pd.DataFrame) -> pd.DataFrame:
        """장소별 기능 분류 — 시간대 패턴으로 추정.

        분류 기준:
        - 출근지(오피스): 주간(10~17시) >> 야간(0~6시), 주간 피크
        - 주거지: 야간(0~6시) >> 주간(10~17시), 야간/저녁 피크
        - 상권(쇼핑/음식): 오후~저녁(14~21시) 피크
        - 관광지: 낮(10~18시) 피크, 주말 > 평일
        - 유흥지역: 심야(22~2시) 피크
        """
        pivot = self.build_hourly_pivot(snapshots_df)
        if pivot.empty:
            return pd.DataFrame()

        result = pd.DataFrame({"장소명": pivot.index})

        # 시간대별 평균
        night_cols = [c for c in pivot.columns if c <= 6]
        morning_cols = [c for c in pivot.columns if 7 <= c <= 9]
        daytime_cols = [c for c in pivot.columns if 10 <= c <= 17]
        evening_cols = [c for c in pivot.columns if 18 <= c <= 21]
        late_night_cols = [c for c in pivot.columns if c >= 22 or c <= 2]

        result["야간인구"] = pivot[night_cols].mean(axis=1).values if night_cols else 0
        result["출근시간인구"] = pivot[morning_cols].mean(axis=1).values if morning_cols else 0
        result["주간인구"] = pivot[daytime_cols].mean(axis=1).values if daytime_cols else 0
        result["저녁인구"] = pivot[evening_cols].mean(axis=1).values if evening_cols else 0

        # 피크 시간
        result["피크시간"] = pivot.idxmax(axis=1).values
        result["피크인구"] = pivot.max(axis=1).values
        result["최저시간"] = pivot.idxmin(axis=1).values
        result["최저인구"] = pivot.min(axis=1).values

        # 주간/야간 비율
        result["주야비율"] = (
            result["주간인구"] / result["야간인구"].replace(0, np.nan)
        ).round(2)

        # 저녁/주간 비율 (상권 특성)
        result["저녁주간비율"] = (
            result["저녁인구"] / result["주간인구"].replace(0, np.nan)
        ).round(2)

        # 기능 분류
        result["장소기능"] = "혼합"

        # 출근지: 주간 >> 야간 (주야비율 > 2)
        result.loc[result["주야비율"] > 2.0, "장소기능"] = "오피스"
        result.loc[result["주야비율"] > 5.0, "장소기능"] = "강력오피스"

        # 상권: 저녁 피크 (저녁/주간 비율 > 1.2, 피크 14~21시)
        result.loc[
            (result["저녁주간비율"] > 1.2) & (result["피크시간"].between(14, 21)),
            "장소기능",
        ] = "상권"

        # 주거지: 야간 >> 주간 (주야비율 < 0.7)
        result.loc[result["주야비율"] < 0.7, "장소기능"] = "주거지"

        # 유흥: 피크 22시 이후
        result.loc[
            (result["피크시간"] >= 22) | (result["피크시간"] <= 2),
            "장소기능",
        ] = "유흥"

        return result.sort_values("주야비율", ascending=False)

    def compare_weekday_weekend(self, snapshots_df: pd.DataFrame) -> pd.DataFrame:
        """평일 vs 주말 패턴 비교.

        Args:
            snapshots_df: 수집날짜, 장소명, 수집시간, 추정인구 필요

        Returns:
            장소별 평일/주말 주간인구 비율
        """
        if "수집날짜" not in snapshots_df.columns:
            return pd.DataFrame()

        df = snapshots_df.copy()
        df["수집날짜"] = pd.to_datetime(df["수집날짜"])
        df["요일"] = df["수집날짜"].dt.dayofweek  # 0=월 ~ 6=일
        df["평일주말"] = df["요일"].apply(lambda x: "주말" if x >= 5 else "평일")

        # 평일/주말별 주간(10~17시) 평균
        daytime = df[df["수집시간"].between(10, 17)]
        comparison = (
            daytime.groupby(["장소명", "평일주말"])["추정인구"]
            .mean()
            .round(0)
            .unstack(fill_value=0)
        )

        if "평일" in comparison.columns and "주말" in comparison.columns:
            comparison["주말평일비율"] = (
                comparison["주말"] / comparison["평일"].replace(0, np.nan)
            ).round(2)

            # 주말 > 평일이면 관광/쇼핑, 평일 > 주말이면 오피스
            comparison["패턴유형"] = "유사"
            comparison.loc[comparison["주말평일비율"] > 1.3, "패턴유형"] = "주말형(관광·쇼핑)"
            comparison.loc[comparison["주말평일비율"] < 0.7, "패턴유형"] = "평일형(오피스)"

        return comparison.reset_index()

    def detect_flow_direction(self, snapshots_df: pd.DataFrame) -> pd.DataFrame:
        """시간대별 인구 변화량으로 유입/유출 방향 추정.

        각 장소의 시간대별 인구 변화(delta)를 계산하여
        양수 = 유입, 음수 = 유출로 유동 방향을 파악.
        """
        pivot = self.build_hourly_pivot(snapshots_df)
        if pivot.empty:
            return pd.DataFrame()

        # 시간대별 변화량 (현재시간 - 이전시간)
        delta = pivot.diff(axis=1)
        delta = delta.drop(columns=[delta.columns[0]], errors="ignore")  # 첫 컬럼 NaN 제거

        # 최대 유입 시간, 최대 유출 시간
        result = pd.DataFrame({"장소명": pivot.index})
        result["최대유입시간"] = delta.idxmax(axis=1).values
        result["최대유입량"] = delta.max(axis=1).round(0).astype(int).values
        result["최대유출시간"] = delta.idxmin(axis=1).values
        result["최대유출량"] = delta.min(axis=1).round(0).astype(int).values

        # 오전유입 (7~10시 총 변화)
        morning_cols = [c for c in delta.columns if 7 <= c <= 10]
        if morning_cols:
            result["오전유입량"] = delta[morning_cols].sum(axis=1).round(0).astype(int).values

        # 저녁유출 (18~21시 총 변화)
        evening_cols = [c for c in delta.columns if 18 <= c <= 21]
        if evening_cols:
            result["저녁유출량"] = delta[evening_cols].sum(axis=1).round(0).astype(int).values

        # 출퇴근 패턴 판별
        if "오전유입량" in result.columns and "저녁유출량" in result.columns:
            result["출퇴근패턴"] = "비출퇴근"
            result.loc[
                (result["오전유입량"] > 0) & (result["저녁유출량"] < 0),
                "출퇴근패턴",
            ] = "출근유입→퇴근유출 (직장)"
            result.loc[
                (result["오전유입량"] < 0) & (result["저녁유출량"] > 0),
                "출퇴근패턴",
            ] = "출근유출→퇴근유입 (주거)"

        return result.sort_values("오전유입량", ascending=False)

    def get_area_detail(
        self, snapshots_df: pd.DataFrame, area_name: str
    ) -> dict:
        """특정 장소의 상세 시간대 프로파일."""
        if snapshots_df.empty or "장소명" not in snapshots_df.columns:
            return {}
        area_data = snapshots_df[snapshots_df["장소명"] == area_name]
        if area_data.empty:
            return {}

        hourly = (
            area_data.groupby("수집시간")["추정인구"]
            .agg(["mean", "min", "max", "std", "count"])
            .round(0)
            .reset_index()
        )
        hourly.columns = ["시간", "평균인구", "최소인구", "최대인구", "표준편차", "스냅샷수"]

        # 혼잡도 분포
        congestion = {}
        if "혼잡도" in area_data.columns:
            congestion = area_data["혼잡도"].value_counts().to_dict()

        # 연령대 평균
        age_cols = [c for c in area_data.columns if "대비율" in c]
        age_avg = {}
        for col in age_cols:
            val = pd.to_numeric(area_data[col], errors="coerce").mean()
            if pd.notna(val):
                age_avg[col] = round(val, 1)

        return {
            "장소명": area_name,
            "시간대별": hourly,
            "혼잡도분포": congestion,
            "연령대비율": age_avg,
            "총스냅샷수": len(area_data),
            "수집기간": {
                "시작": str(area_data["수집시각"].min()) if "수집시각" in area_data.columns else "",
                "종료": str(area_data["수집시각"].max()) if "수집시각" in area_data.columns else "",
            },
        }
