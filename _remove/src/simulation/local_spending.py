"""단일 아파트 로컬 소비 시뮬레이션.

래미안 대치팰리스 1개 단지 기준.
주민 1명이 정문 나서서 어디로 가는지 = 도보시간 + 횡단보도 수로 결정.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Apartment:
    name: str
    units: int
    avg_members: float = 3.1

    @property
    def population(self) -> int:
        return round(self.units * self.avg_members)


@dataclass
class Zone:
    """아파트에서 갈 수 있는 상권 구역."""
    name: str
    walk_min: int          # 도보 시간 (분)
    crossings: int         # 횡단보도 수
    stores: list[str] = field(default_factory=list)  # 있는 업종들


# 업종별: 하루 방문확률 (인구 대비), 객단가
CATEGORY_PARAMS = {
    "편의점":    {"visit_rate": 0.10, "avg_spend": 4_000},
    "카페":      {"visit_rate": 0.20, "avg_spend": 5_500},
    "음식점":    {"visit_rate": 0.25, "avg_spend": 9_000},
    "마트/슈퍼": {"visit_rate": 0.06, "avg_spend": 25_000},
    "기타":      {"visit_rate": 0.12, "avg_spend": 7_000},
}


# === 래미안 대치팰리스 설정 ===

DAECHI_APT = Apartment(
    name="래미안대치팰리스",
    units=1600,
    avg_members=3.1,
)

DAECHI_ZONES = [
    Zone("단지 앞 도곡로 (같은쪽)", walk_min=2, crossings=0,
         stores=["편의점", "카페", "음식점", "기타"]),
    Zone("도곡로 건너편", walk_min=3, crossings=1,
         stores=["음식점", "카페", "편의점"]),
    Zone("대치역 상권", walk_min=8, crossings=0,
         stores=["음식점", "카페", "편의점", "기타"]),
    Zone("한티역 상권", walk_min=12, crossings=1,
         stores=["음식점", "카페", "마트/슈퍼"]),
    Zone("학원가 뒷길", walk_min=10, crossings=1,
         stores=["카페", "편의점", "음식점"]),
]


def _accessibility_score(zone: Zone) -> float:
    """도보시간 + 횡단보도로 접근성 점수 계산.

    - 도보시간: exp(-walk_min / 5) → 가까울수록 높음
    - 횡단보도: 1개당 0.3배 → 건널수록 급감
    """
    walk_decay = math.exp(-zone.walk_min / 5.0)
    crossing_penalty = 0.3 ** zone.crossings
    return walk_decay * crossing_penalty


def calculate_zone_visits(
    apt: Apartment,
    zones: list[Zone],
) -> pd.DataFrame:
    """업종별로 어느 구역에 몇 명이 가고, 얼마를 쓰는지 계산.

    Returns:
        DataFrame[업종, 구역, 접근성, 방문확률, 방문자수, 매출]
    """
    pop = apt.population
    rows = []

    for category, params in CATEGORY_PARAMS.items():
        # 이 업종이 있는 구역만 필터
        available = [z for z in zones if category in z.stores]
        if not available:
            continue

        # 접근성 점수 계산
        scores = {z.name: _accessibility_score(z) for z in available}
        total_score = sum(scores.values())
        if total_score <= 0:
            continue

        # 정규화 → 방문 확률 분배
        total_visitors = pop * params["visit_rate"]

        for z in available:
            ratio = scores[z.name] / total_score
            visitors = total_visitors * ratio
            revenue = visitors * params["avg_spend"]

            rows.append({
                "업종": category,
                "구역": z.name,
                "도보(분)": z.walk_min,
                "횡단보도": z.crossings,
                "접근성": round(scores[z.name], 4),
                "방문비율": round(ratio, 3),
                "방문자수": round(visitors),
                "매출": round(revenue),
            })

    return pd.DataFrame(rows)


def get_summary(df: pd.DataFrame) -> dict:
    """구역별, 업종별 요약."""
    by_zone = df.groupby("구역").agg(
        총방문자수=("방문자수", "sum"),
        총매출=("매출", "sum"),
    ).sort_values("총매출", ascending=False).reset_index()

    by_category = df.groupby("업종").agg(
        총방문자수=("방문자수", "sum"),
        총매출=("매출", "sum"),
    ).sort_values("총매출", ascending=False).reset_index()

    return {
        "아파트": DAECHI_APT.name,
        "세대수": DAECHI_APT.units,
        "인구": DAECHI_APT.population,
        "일일총매출": int(df["매출"].sum()),
        "by_zone": by_zone,
        "by_category": by_category,
    }


if __name__ == "__main__":
    df = calculate_zone_visits(DAECHI_APT, DAECHI_ZONES)

    print(f"=== {DAECHI_APT.name} ({DAECHI_APT.units}세대, {DAECHI_APT.population}명) ===\n")

    summary = get_summary(df)
    print(f"일일 총매출: {summary['일일총매출']:,}원\n")

    print("[ 구역별 ]")
    for _, r in summary["by_zone"].iterrows():
        print(f"  {r['구역']}: {r['총방문자수']:,}명, {r['총매출']:,}원")

    print("\n[ 업종별 ]")
    for _, r in summary["by_category"].iterrows():
        print(f"  {r['업종']}: {r['총방문자수']:,}명, {r['총매출']:,}원")

    print("\n[ 상세 ]")
    print(df.to_string(index=False))
