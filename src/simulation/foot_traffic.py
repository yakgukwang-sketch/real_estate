"""유동인구 → 상권매출 시뮬레이션 엔진.

세대수(주거유형별) → 인구수 → 외출율 → 근처 상권 방문 → 업종별 매출 산출.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.processors.geo_processor import DONG_CENTROIDS
from src.simulation.spending_power import HOUSING_PROFILES, DEFAULT_DONG_HOUSING
from src.utils.geo_utils import haversine


@dataclass
class StoreProfile:
    name: str               # "음식점", "카페" 등
    avg_spend: int          # 방문당 평균 지출 (원)
    daily_visit_rate: float # 외출인구 중 해당 업종 방문 확률
    capture_radius_km: float  # 상권 영향 반경


STORE_PROFILES = {
    "음식점":    StoreProfile("음식점",    9000, 0.25, 2.0),
    "카페":      StoreProfile("카페",      5500, 0.15, 1.5),
    "편의점":    StoreProfile("편의점",    4000, 0.30, 0.8),
    "마트/슈퍼": StoreProfile("마트/슈퍼", 25000, 0.08, 1.5),
    "기타":      StoreProfile("기타",      7000, 0.12, 2.0),
}


@dataclass
class TimeSlot:
    name: str               # "morning", "lunch", "evening", "night"
    label: str              # "오전(출근)", "점심", "저녁(퇴근후)", "야간"
    outing_rate: float      # 전체 인구 중 외출 비율
    spend_multiplier: float # 소비 강도 계수


DEFAULT_TIME_SLOTS = [
    TimeSlot("morning", "오전(출근)",    0.15, 0.6),
    TimeSlot("lunch",   "점심",          0.30, 1.0),
    TimeSlot("evening", "저녁(퇴근후)",  0.35, 1.3),
    TimeSlot("night",   "야간",          0.10, 0.8),
]

# 41개 동별 업종별 점포수 (샘플 데이터)
# DONG_CENTROIDS 41개 동과 1:1 매핑
DEFAULT_DONG_STORES: dict[str, dict[str, int]] = {
    # 강남권 - 상업 중심지, 점포 많음
    "강남동":   {"음식점": 450, "카페": 320, "편의점": 180, "마트/슈퍼": 25, "기타": 200},
    "역삼동":   {"음식점": 380, "카페": 280, "편의점": 150, "마트/슈퍼": 20, "기타": 170},
    "서초동":   {"음식점": 300, "카페": 200, "편의점": 130, "마트/슈퍼": 18, "기타": 140},
    "삼성동":   {"음식점": 350, "카페": 250, "편의점": 140, "마트/슈퍼": 15, "기타": 160},
    "잠실동":   {"음식점": 280, "카페": 200, "편의점": 160, "마트/슈퍼": 22, "기타": 130},
    "선릉동":   {"음식점": 320, "카페": 260, "편의점": 120, "마트/슈퍼": 12, "기타": 150},
    "교대동":   {"음식점": 200, "카페": 150, "편의점": 100, "마트/슈퍼": 15, "기타": 90},
    "압구정동": {"음식점": 250, "카페": 220, "편의점": 90,  "마트/슈퍼": 10, "기타": 130},
    "신사동":   {"음식점": 280, "카페": 300, "편의점": 100, "마트/슈퍼": 12, "기타": 160},
    "논현동":   {"음식점": 260, "카페": 200, "편의점": 110, "마트/슈퍼": 14, "기타": 120},
    "청담동":   {"음식점": 200, "카페": 180, "편의점": 70,  "마트/슈퍼": 8,  "기타": 110},
    "학동":     {"음식점": 180, "카페": 150, "편의점": 90,  "마트/슈퍼": 10, "기타": 80},
    # 서남권
    "방배동":   {"음식점": 150, "카페": 100, "편의점": 80,  "마트/슈퍼": 15, "기타": 70},
    "사당동":   {"음식점": 180, "카페": 120, "편의점": 110, "마트/슈퍼": 18, "기타": 80},
    "신림동":   {"음식점": 220, "카페": 130, "편의점": 140, "마트/슈퍼": 20, "기타": 100},
    "구로동":   {"음식점": 200, "카페": 110, "편의점": 130, "마트/슈퍼": 16, "기타": 90},
    "가산동":   {"음식점": 180, "카페": 120, "편의점": 100, "마트/슈퍼": 10, "기타": 80},
    "목동":     {"음식점": 200, "카페": 150, "편의점": 120, "마트/슈퍼": 20, "기타": 90},
    "영등포동": {"음식점": 250, "카페": 160, "편의점": 140, "마트/슈퍼": 18, "기타": 110},
    "여의도동": {"음식점": 300, "카페": 200, "편의점": 120, "마트/슈퍼": 10, "기타": 140},
    # 마포/서대문권 - 상업 중심지
    "홍대동":   {"음식점": 400, "카페": 350, "편의점": 160, "마트/슈퍼": 12, "기타": 200},
    "합정동":   {"음식점": 200, "카페": 180, "편의점": 100, "마트/슈퍼": 12, "기타": 90},
    "망원동":   {"음식점": 150, "카페": 160, "편의점": 80,  "마트/슈퍼": 10, "기타": 70},
    "신촌동":   {"음식점": 250, "카페": 200, "편의점": 130, "마트/슈퍼": 14, "기타": 110},
    "공덕동":   {"음식점": 180, "카페": 130, "편의점": 100, "마트/슈퍼": 12, "기타": 80},
    "마포동":   {"음식점": 160, "카페": 110, "편의점": 90,  "마트/슈퍼": 14, "기타": 70},
    # 도심권 - 상업 중심지
    "종로동":   {"음식점": 300, "카페": 200, "편의점": 130, "마트/슈퍼": 10, "기타": 150},
    "명동":     {"음식점": 500, "카페": 400, "편의점": 200, "마트/슈퍼": 8,  "기타": 250},
    "중구동":   {"음식점": 250, "카페": 180, "편의점": 120, "마트/슈퍼": 12, "기타": 110},
    "용산동":   {"음식점": 180, "카페": 130, "편의점": 100, "마트/슈퍼": 15, "기타": 80},
    "이태원동": {"음식점": 250, "카페": 200, "편의점": 80,  "마트/슈퍼": 8,  "기타": 130},
    "동대문동": {"음식점": 280, "카페": 180, "편의점": 130, "마트/슈퍼": 14, "기타": 120},
    # 성동/광진권
    "성수동":   {"음식점": 250, "카페": 280, "편의점": 110, "마트/슈퍼": 12, "기타": 130},
    "건대동":   {"음식점": 280, "카페": 220, "편의점": 130, "마트/슈퍼": 14, "기타": 120},
    "왕십리동": {"음식점": 180, "카페": 120, "편의점": 100, "마트/슈퍼": 16, "기타": 80},
    # 강북권 - 주거 중심지, 점포 적음
    "노원동":   {"음식점": 150, "카페": 80,  "편의점": 120, "마트/슈퍼": 22, "기타": 60},
    "상계동":   {"음식점": 130, "카페": 60,  "편의점": 110, "마트/슈퍼": 20, "기타": 50},
    "미아동":   {"음식점": 140, "카페": 80,  "편의점": 100, "마트/슈퍼": 18, "기타": 60},
    "길음동":   {"음식점": 130, "카페": 80,  "편의점": 90,  "마트/슈퍼": 16, "기타": 55},
    "불광동":   {"음식점": 120, "카페": 70,  "편의점": 80,  "마트/슈퍼": 15, "기타": 50},
    "연신내동": {"음식점": 140, "카페": 80,  "편의점": 100, "마트/슈퍼": 18, "기타": 55},
}


class FootTrafficSimulator:
    """유동인구 → 상권매출 시뮬레이터."""

    def __init__(
        self,
        housing_data: dict[str, dict[str, int]] | None = None,
        store_data: dict[str, dict[str, int]] | None = None,
    ):
        self.housing_data = housing_data or DEFAULT_DONG_HOUSING
        self.store_data = store_data or DEFAULT_DONG_STORES

    def _get_dong_population(self, dong: str) -> int:
        """동의 총 인구수 = 세대수 × 평균세대원수 합산."""
        dong_housing = self.housing_data.get(dong, {})
        total = 0
        for htype, count in dong_housing.items():
            profile = HOUSING_PROFILES.get(htype)
            if profile:
                total += round(count * profile.avg_members)
        return total

    @staticmethod
    def _distance_decay(dist_km: float, radius_km: float) -> float:
        """가우시안 거리감쇠: exp(-d²/(2σ²)), σ = radius/2."""
        sigma = radius_km / 2.0
        if sigma <= 0:
            return 0.0
        return math.exp(-(dist_km ** 2) / (2 * sigma ** 2))

    def _compute_visit_distribution(
        self, origin: str, category: str,
    ) -> dict[str, float]:
        """출발 동에서 업종별 방문 분포 계산.

        점포수 × 거리감쇠 → 정규화하여 각 동별 비율 반환.
        """
        profile = STORE_PROFILES.get(category)
        if profile is None:
            return {}

        origin_coords = DONG_CENTROIDS.get(origin)
        if origin_coords is None:
            return {}

        scores: dict[str, float] = {}
        for dest_dong, stores in self.store_data.items():
            store_count = stores.get(category, 0)
            if store_count <= 0:
                continue

            dest_coords = DONG_CENTROIDS.get(dest_dong)
            if dest_coords is None:
                continue

            dist = haversine(
                origin_coords[0], origin_coords[1],
                dest_coords[0], dest_coords[1],
            )
            decay = self._distance_decay(dist, profile.capture_radius_km)
            score = store_count * decay
            if score > 0:
                scores[dest_dong] = score

        # 정규화
        total_score = sum(scores.values())
        if total_score <= 0:
            return {}
        return {dong: s / total_score for dong, s in scores.items()}

    def calculate_daily(self, dong: str | None = None) -> pd.DataFrame:
        """일일 유동인구-매출 시뮬레이션.

        Args:
            dong: 특정 동만 계산 (None이면 전체)

        Returns:
            DataFrame[출발동, 도착동, 시간대, 업종, 방문자수, 예상매출]
        """
        origins = [dong] if dong else list(self.housing_data.keys())
        rows = []

        for origin in origins:
            pop = self._get_dong_population(origin)
            if pop <= 0:
                continue

            for ts in DEFAULT_TIME_SLOTS:
                outing_pop = pop * ts.outing_rate

                for cat_name, store_profile in STORE_PROFILES.items():
                    visitors_total = outing_pop * store_profile.daily_visit_rate
                    distribution = self._compute_visit_distribution(origin, cat_name)

                    for dest_dong, ratio in distribution.items():
                        visitors = visitors_total * ratio
                        revenue = visitors * store_profile.avg_spend * ts.spend_multiplier

                        rows.append({
                            "출발동": origin,
                            "도착동": dest_dong,
                            "시간대": ts.label,
                            "시간대코드": ts.name,
                            "업종": cat_name,
                            "방문자수": round(visitors),
                            "예상매출": round(revenue),
                        })

        return pd.DataFrame(rows)

    def get_summary(self) -> pd.DataFrame:
        """도착동 기준 집계 요약.

        Returns:
            DataFrame[동, 총방문자수, 총매출, 음식점매출, 카페매출, 편의점매출, 마트/슈퍼매출, 기타매출]
            — 매출 내림차순
        """
        df = self.calculate_daily()
        if df.empty:
            return pd.DataFrame(columns=[
                "동", "총방문자수", "총매출",
                "음식점매출", "카페매출", "편의점매출", "마트/슈퍼매출", "기타매출",
            ])

        # 도착동 기준 총합
        summary = df.groupby("도착동").agg(
            총방문자수=("방문자수", "sum"),
            총매출=("예상매출", "sum"),
        ).reset_index().rename(columns={"도착동": "동"})

        # 업종별 매출
        cat_pivot = df.pivot_table(
            index="도착동", columns="업종", values="예상매출", aggfunc="sum", fill_value=0,
        ).reset_index().rename(columns={"도착동": "동"})

        for cat in STORE_PROFILES:
            col_name = f"{cat}매출"
            if cat in cat_pivot.columns:
                cat_pivot = cat_pivot.rename(columns={cat: col_name})
            else:
                cat_pivot[col_name] = 0

        summary = summary.merge(
            cat_pivot[["동"] + [f"{c}매출" for c in STORE_PROFILES]],
            on="동", how="left",
        ).fillna(0)

        return summary.sort_values("총매출", ascending=False).reset_index(drop=True)

    def get_dong_detail(self, dong: str) -> dict:
        """특정 동의 상세 분석 (도착동 기준).

        Returns:
            {
                "dong": str,
                "population": int,
                "by_category": DataFrame[업종, 방문자수, 매출],
                "by_time": DataFrame[시간대, 방문자수, 매출],
                "by_origin": DataFrame[출발동, 방문자수, 매출],
            }
        """
        full_df = self.calculate_daily()
        dest_df = full_df[full_df["도착동"] == dong] if not full_df.empty else full_df

        by_category = pd.DataFrame(columns=["업종", "방문자수", "매출"])
        by_time = pd.DataFrame(columns=["시간대", "방문자수", "매출"])
        by_origin = pd.DataFrame(columns=["출발동", "방문자수", "매출"])

        if not dest_df.empty:
            by_category = dest_df.groupby("업종").agg(
                방문자수=("방문자수", "sum"), 매출=("예상매출", "sum"),
            ).reset_index().sort_values("매출", ascending=False)

            by_time = dest_df.groupby("시간대").agg(
                방문자수=("방문자수", "sum"), 매출=("예상매출", "sum"),
            ).reset_index()

            by_origin = dest_df.groupby("출발동").agg(
                방문자수=("방문자수", "sum"), 매출=("예상매출", "sum"),
            ).reset_index().sort_values("매출", ascending=False)

        return {
            "dong": dong,
            "population": self._get_dong_population(dong),
            "by_category": by_category,
            "by_time": by_time,
            "by_origin": by_origin,
        }

    def simulate_change(
        self, dong: str, housing_type: str, delta: int,
    ) -> dict:
        """세대수 변경 시 매출 변화 시뮬레이션.

        Args:
            dong: 대상 동
            housing_type: 주거유형
            delta: 세대수 변화량 (+/-)

        Returns:
            {"before": {...}, "after": {...}, "변화량": {...}, "이웃영향": [...]}
        """
        # Before: 현재 상태로 계산
        before_df = self.calculate_daily(dong=dong)
        before_revenue_by_dest = {}
        if not before_df.empty:
            before_revenue_by_dest = dict(
                before_df.groupby("도착동")["예상매출"].sum()
            )
        before_total = sum(before_revenue_by_dest.values())
        before_visitors = int(before_df["방문자수"].sum()) if not before_df.empty else 0

        # After: 변경된 housing_data로 계산
        modified_housing = {
            d: dict(units) for d, units in self.housing_data.items()
        }
        if dong not in modified_housing:
            modified_housing[dong] = {}
        current = modified_housing[dong].get(housing_type, 0)
        modified_housing[dong][housing_type] = max(0, current + delta)

        after_sim = FootTrafficSimulator(
            housing_data=modified_housing,
            store_data=self.store_data,
        )
        after_df = after_sim.calculate_daily(dong=dong)
        after_revenue_by_dest = {}
        if not after_df.empty:
            after_revenue_by_dest = dict(
                after_df.groupby("도착동")["예상매출"].sum()
            )
        after_total = sum(after_revenue_by_dest.values())
        after_visitors = int(after_df["방문자수"].sum()) if not after_df.empty else 0

        before_pop = self._get_dong_population(dong)
        after_pop = after_sim._get_dong_population(dong)

        # 이웃 동 영향
        neighbor_effects = []
        all_dests = set(list(before_revenue_by_dest.keys()) + list(after_revenue_by_dest.keys()))
        for dest in sorted(all_dests):
            if dest == dong:
                continue
            b = before_revenue_by_dest.get(dest, 0)
            a = after_revenue_by_dest.get(dest, 0)
            if b != a:
                neighbor_effects.append({
                    "동": dest,
                    "변경전매출": round(b),
                    "변경후매출": round(a),
                    "매출변화": round(a - b),
                    "변화율": round((a - b) / b * 100, 1) if b > 0 else 0,
                })

        return {
            "before": {
                "인구": before_pop,
                "총방문자수": before_visitors,
                "총매출": round(before_total),
            },
            "after": {
                "인구": after_pop,
                "총방문자수": after_visitors,
                "총매출": round(after_total),
            },
            "변화량": {
                "인구": after_pop - before_pop,
                "총방문자수": after_visitors - before_visitors,
                "총매출": round(after_total - before_total),
            },
            "이웃영향": neighbor_effects,
        }
