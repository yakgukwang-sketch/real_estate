"""출퇴근 유동 분석 - 사람들이 어디로 가는지 추정.

핵심 아이디어:
- 아침(7~9시) 인구 유입 = 직장/학교 목적지
- 저녁(18~20시) 인구 유출 = 직장/학교에서 귀가
- 상가 업종(학원, 사무실 등) + 사업체수 = 목적지 유형 추정
- 지하철/버스 승하차 패턴 = OD flow 방향 확인
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 상가 대분류 → 목적지 유형 매핑
DESTINATION_TYPE_MAP = {
    # 직장 계열
    "부동산": "직장",
    "시설관리·임대": "직장",
    "전문·과학·기술": "직장",
    "금융·보험": "직장",
    "정보통신": "직장",
    "제조": "직장",
    "운수·창고": "직장",
    "건설": "직장",
    "도매·소매": "직장",
    "공공·행정": "직장",
    # 교육 계열
    "교육": "학교·학원",
    "학원": "학교·학원",
    # 소비/여가 계열
    "음식": "소비·여가",
    "숙박": "소비·여가",
    "예술·스포츠·여가": "소비·여가",
    "소매": "소비·여가",
    # 의료
    "보건·의료": "의료",
}


class CommuteAnalyzer:
    """시간대별 인구 유동 + 업종 데이터로 출퇴근 목적지 추정."""

    def analyze_hourly_flow(self, population_df: pd.DataFrame) -> pd.DataFrame:
        """시간대별 생활인구로 행정동별 유입/유출 패턴 분석.

        Args:
            population_df: 시간대, 행정동코드, 총생활인구 컬럼 필요

        Returns:
            행정동별 시간대 패턴 + 지역유형 분류
        """
        required = {"시간대", "행정동코드", "총생활인구"}
        if not required.issubset(population_df.columns):
            missing = required - set(population_df.columns)
            logger.warning("필요한 컬럼 없음: %s", missing)
            return pd.DataFrame()

        df = population_df.copy()
        df["시간대"] = pd.to_numeric(df["시간대"], errors="coerce")
        df["총생활인구"] = pd.to_numeric(df["총생활인구"], errors="coerce")
        df = df.dropna(subset=["시간대", "총생활인구"])

        # 시간대별 행정동 인구 평균
        hourly = (
            df.groupby(["행정동코드", "시간대"])["총생활인구"]
            .mean()
            .reset_index()
        )

        # 행정동별 시간대 피벗
        pivot = hourly.pivot_table(
            index="행정동코드", columns="시간대", values="총생활인구"
        ).fillna(0)

        # 야간(0~6시) 평균 = 상주인구 추정
        night_cols = [c for c in pivot.columns if c <= 6]
        # 출근시간(7~9시) 평균
        morning_cols = [c for c in pivot.columns if 7 <= c <= 9]
        # 주간(10~17시) 평균
        daytime_cols = [c for c in pivot.columns if 10 <= c <= 17]
        # 퇴근시간(18~20시) 평균
        evening_cols = [c for c in pivot.columns if 18 <= c <= 20]

        result = pd.DataFrame({"행정동코드": pivot.index})
        result["야간인구"] = pivot[night_cols].mean(axis=1).values if night_cols else 0
        result["출근시간인구"] = pivot[morning_cols].mean(axis=1).values if morning_cols else 0
        result["주간인구"] = pivot[daytime_cols].mean(axis=1).values if daytime_cols else 0
        result["퇴근시간인구"] = pivot[evening_cols].mean(axis=1).values if evening_cols else 0

        # 주간유입률: (주간인구 - 야간인구) / 야간인구
        result["주간유입률"] = (
            (result["주간인구"] - result["야간인구"])
            / result["야간인구"].replace(0, np.nan)
            * 100
        ).round(1)

        # 지역유형 분류
        result["지역유형"] = "혼합"
        result.loc[result["주간유입률"] > 30, "지역유형"] = "직장밀집"
        result.loc[result["주간유입률"] > 100, "지역유형"] = "강력직장밀집"
        result.loc[result["주간유입률"] < -10, "지역유형"] = "주거밀집"
        result.loc[result["주간유입률"] < -30, "지역유형"] = "강력주거밀집"

        return result.sort_values("주간유입률", ascending=False)

    def classify_destination_types(
        self, commercial_df: pd.DataFrame
    ) -> pd.DataFrame:
        """상가 업종 데이터로 행정동별 목적지 유형 분포 추정.

        Args:
            commercial_df: 행정동코드, 대분류명 컬럼 필요

        Returns:
            행정동별 목적지 유형(직장/학교/소비/의료) 비율
        """
        if "행정동코드" not in commercial_df.columns:
            return pd.DataFrame()

        df = commercial_df.copy()

        # 대분류명 → 목적지 유형
        cat_col = "대분류명" if "대분류명" in df.columns else None
        if cat_col is None:
            return pd.DataFrame()

        df["목적지유형"] = df[cat_col].map(DESTINATION_TYPE_MAP).fillna("기타")

        # 행정동별 목적지유형 비율
        counts = (
            df.groupby(["행정동코드", "목적지유형"])
            .size()
            .unstack(fill_value=0)
        )
        total = counts.sum(axis=1)
        ratios = (counts.div(total, axis=0) * 100).round(1)
        ratios.columns = [f"{c}_비율" for c in ratios.columns]
        ratios["총업소수"] = total

        # 주요 목적지 유형
        type_cols = [c for c in counts.columns]
        ratios["주요목적지"] = counts[type_cols].idxmax(axis=1)

        return ratios.reset_index()

    def estimate_commute_od(
        self,
        population_df: pd.DataFrame,
        subway_df: pd.DataFrame | None = None,
        bus_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """출퇴근 OD(출발-도착) 추정.

        아침 시간대:
        - 인구 감소 행정동 = 출발지 (주거지)
        - 인구 증가 행정동 = 도착지 (직장/학교)

        지하철/버스 승하차 보조:
        - 아침 승차 많은 곳 = 출발지
        - 아침 하차 많은 곳 = 도착지
        """
        # Step 1: 시간대 인구 분석
        flow = self.analyze_hourly_flow(population_df)
        if flow.empty:
            return pd.DataFrame()

        # 출발지 (아침에 인구 감소) / 도착지 (아침에 인구 증가)
        origins = flow[flow["주간유입률"] < 0].copy()
        origins["역할"] = "출발지(주거)"
        origins["유출규모"] = (origins["야간인구"] - origins["주간인구"]).abs()

        destinations = flow[flow["주간유입률"] > 0].copy()
        destinations["역할"] = "도착지(직장·학교)"
        destinations["유입규모"] = destinations["주간인구"] - destinations["야간인구"]

        # Step 2: 지하철 데이터 보조
        if subway_df is not None and not subway_df.empty:
            subway_cols = {"행정동코드", "승차총승객수", "하차총승객수"}
            if subway_cols.issubset(subway_df.columns):
                sub_agg = (
                    subway_df.groupby("행정동코드")
                    .agg(총승차=("승차총승객수", "sum"), 총하차=("하차총승객수", "sum"))
                    .reset_index()
                )
                sub_agg["지하철순유입"] = sub_agg["총하차"] - sub_agg["총승차"]
                flow = flow.merge(sub_agg, on="행정동코드", how="left")

        # Step 3: 버스 데이터 보조
        if bus_df is not None and not bus_df.empty:
            bus_cols = {"행정동코드", "승차인원", "하차인원"}
            if bus_cols.issubset(bus_df.columns):
                bus_agg = (
                    bus_df.groupby("행정동코드")
                    .agg(버스총승차=("승차인원", "sum"), 버스총하차=("하차인원", "sum"))
                    .reset_index()
                )
                bus_agg["버스순유입"] = bus_agg["버스총하차"] - bus_agg["버스총승차"]
                flow = flow.merge(bus_agg, on="행정동코드", how="left")

        # 종합 교통 순유입
        transport_cols = []
        if "지하철순유입" in flow.columns:
            transport_cols.append("지하철순유입")
        if "버스순유입" in flow.columns:
            transport_cols.append("버스순유입")

        if transport_cols:
            flow["교통순유입"] = flow[transport_cols].sum(axis=1)
        else:
            flow["교통순유입"] = 0

        return flow

    def build_commute_matrix(
        self,
        population_df: pd.DataFrame,
        commercial_df: pd.DataFrame | None = None,
        subway_df: pd.DataFrame | None = None,
    ) -> dict:
        """종합 출퇴근 분석 결과.

        Returns:
            {
                "flow": 행정동별 시간대 유동 DataFrame,
                "destinations": 목적지 유형 분포 DataFrame,
                "origins": 출발지(주거) 행정동 목록,
                "dest_rankings": 도착지 순위,
                "summary": 요약 통계,
            }
        """
        result = {}

        # 시간대 유동 분석
        flow = self.estimate_commute_od(population_df, subway_df)
        result["flow"] = flow

        # 출발지/도착지 분류
        if not flow.empty and "주간유입률" in flow.columns:
            result["origins"] = (
                flow[flow["주간유입률"] < -5]
                .sort_values("주간유입률")
                .head(20)
            )
            result["dest_rankings"] = (
                flow[flow["주간유입률"] > 5]
                .sort_values("주간유입률", ascending=False)
                .head(20)
            )

            # 요약
            result["summary"] = {
                "직장밀집_동수": int((flow["지역유형"].str.contains("직장")).sum()),
                "주거밀집_동수": int((flow["지역유형"].str.contains("주거")).sum()),
                "혼합_동수": int((flow["지역유형"] == "혼합").sum()),
                "최대유입동": flow.iloc[0]["행정동코드"] if len(flow) > 0 else None,
                "최대유입률": flow["주간유입률"].max() if len(flow) > 0 else 0,
            }

        # 목적지 유형 분석
        if commercial_df is not None and not commercial_df.empty:
            result["destinations"] = self.classify_destination_types(commercial_df)

        return result
