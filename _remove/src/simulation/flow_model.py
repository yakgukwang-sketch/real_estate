"""OD(출발-도착) 유동 모델 - 중력 모델 기반."""

import logging

import numpy as np
import pandas as pd

from src.utils.geo_utils import haversine

logger = logging.getLogger(__name__)


class FlowModel:
    """지하철 승하차 데이터 기반 OD 유동 모델.

    중력 모델: Flow(i,j) = k × Pop(i) × Employment(j) / Distance(i,j)^β
    """

    def __init__(self, beta: float = 2.0, k: float = 1.0):
        self.beta = beta
        self.k = k

    def build_od_matrix(
        self,
        subway_df: pd.DataFrame,
        dong_centroids: pd.DataFrame,
    ) -> pd.DataFrame:
        """승하차 데이터로 OD 행렬 근사.

        아침 시간대:
        - 하차 >> 승차인 역 = 목적지(직장)
        - 승차 >> 하차인 역 = 출발지(주거)

        Args:
            subway_df: 역별 승하차 데이터 (행정동코드 포함)
            dong_centroids: 행정동별 중심좌표 (행정동코드, 위도, 경도)
        """
        if subway_df.empty or dong_centroids.empty:
            return pd.DataFrame()

        # 행정동별 승하차 합계
        dong_subway = (
            subway_df.groupby("행정동코드")
            .agg(총승차=("승차총승객수", "sum"), 총하차=("하차총승객수", "sum"))
            .reset_index()
        )
        dong_subway["순유입"] = dong_subway["총하차"] - dong_subway["총승차"]

        # OD 행렬 구축 (중력 모델)
        dongs = dong_subway["행정동코드"].unique()
        n = len(dongs)

        # 중심좌표 매핑
        centroid_map = {}
        for _, row in dong_centroids.iterrows():
            code = str(row["행정동코드"])
            centroid_map[code] = (row["위도"], row["경도"])

        od_matrix = np.zeros((n, n))

        for i, origin in enumerate(dongs):
            for j, dest in enumerate(dongs):
                if i == j or origin not in centroid_map or dest not in centroid_map:
                    continue

                lat1, lon1 = centroid_map[origin]
                lat2, lon2 = centroid_map[dest]
                dist = haversine(lat1, lon1, lat2, lon2)
                if dist < 0.1:
                    dist = 0.1

                pop_i = dong_subway.loc[dong_subway["행정동코드"] == origin, "총승차"].iloc[0]
                emp_j = dong_subway.loc[dong_subway["행정동코드"] == dest, "총하차"].iloc[0]

                od_matrix[i, j] = self.k * pop_i * emp_j / (dist ** self.beta)

        od_df = pd.DataFrame(od_matrix, index=dongs, columns=dongs)
        return od_df

    def classify_dong_type(self, subway_df: pd.DataFrame) -> pd.DataFrame:
        """행정동을 직장지역/주거지역/혼합지역으로 분류."""
        dong_agg = (
            subway_df.groupby("행정동코드")
            .agg(총승차=("승차총승객수", "sum"), 총하차=("하차총승객수", "sum"))
            .reset_index()
        )
        dong_agg["순유입"] = dong_agg["총하차"] - dong_agg["총승차"]
        dong_agg["유입비율"] = dong_agg["순유입"] / dong_agg[["총승차", "총하차"]].max(axis=1)

        dong_agg["지역유형"] = "혼합"
        dong_agg.loc[dong_agg["유입비율"] > 0.15, "지역유형"] = "직장지역"
        dong_agg.loc[dong_agg["유입비율"] < -0.15, "지역유형"] = "주거지역"

        return dong_agg

    def build_od_matrix_with_bus(
        self,
        subway_df: pd.DataFrame,
        bus_df: pd.DataFrame,
        dong_centroids: pd.DataFrame,
        bus_weight: float = 0.3,
    ) -> pd.DataFrame:
        """지하철 + 버스 통합 OD 행렬 구축.

        Args:
            subway_df: 지하철 승하차 (행정동코드, 승차총승객수, 하차총승객수)
            bus_df: 버스 승하차 (행정동코드, 승차인원, 하차인원)
            dong_centroids: 행정동별 중심좌표
            bus_weight: 버스 데이터 가중치 (0~1)
        """
        # 지하철 OD
        subway_od = self.build_od_matrix(subway_df, dong_centroids)
        if subway_od.empty:
            return subway_od

        # 버스 데이터를 지하철 형식으로 변환
        if bus_df.empty or "행정동코드" not in bus_df.columns:
            return subway_od

        bus_renamed = bus_df.rename(columns={
            "승차인원": "승차총승객수",
            "하차인원": "하차총승객수",
        })
        bus_od = self.build_od_matrix(bus_renamed, dong_centroids)
        if bus_od.empty:
            return subway_od

        # 공통 행정동 인덱스로 맞추기
        common = subway_od.index.intersection(bus_od.index)
        if common.empty:
            return subway_od

        combined = (
            subway_od.loc[common, common] * (1 - bus_weight)
            + bus_od.loc[common, common] * bus_weight
        )
        return combined

    def estimate_impact(
        self,
        od_matrix: pd.DataFrame,
        target_dong: str,
        change_pct: float,
    ) -> pd.DataFrame:
        """특정 동의 유동인구 변화가 연관 동에 미치는 영향 추정."""
        if target_dong not in od_matrix.index:
            return pd.DataFrame()

        # target_dong으로의 유입 변화
        inflow_change = od_matrix[target_dong] * (change_pct / 100)

        # target_dong에서의 유출 변화
        outflow_change = od_matrix.loc[target_dong] * (change_pct / 100)

        impact = pd.DataFrame({
            "행정동코드": od_matrix.index,
            "유입변화": inflow_change.values,
            "유출변화": outflow_change.values,
        })
        impact["총영향"] = impact["유입변화"] + impact["유출변화"]
        return impact.sort_values("총영향", key=abs, ascending=False)

    def compute_flow_summary(self, od_matrix: pd.DataFrame) -> pd.DataFrame:
        """OD 행렬에서 행정동별 유입/유출 요약."""
        if od_matrix.empty:
            return pd.DataFrame()

        return pd.DataFrame({
            "행정동코드": od_matrix.index,
            "총유입": od_matrix.sum(axis=0).values,
            "총유출": od_matrix.sum(axis=1).values,
            "순유입": (od_matrix.sum(axis=0) - od_matrix.sum(axis=1)).values,
        }).sort_values("순유입", ascending=False)
