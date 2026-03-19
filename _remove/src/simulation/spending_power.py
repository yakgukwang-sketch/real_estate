"""소비력 분석 엔진 - 주거유형별 세대수 기반 지역 소비력 산출."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.processors.geo_processor import DONG_CENTROIDS


@dataclass
class HousingProfile:
    name: str           # "아파트", "빌라", "오피스텔", "단독주택"
    avg_members: float  # 평균 세대원수
    monthly_spend: int  # 세대당 월 소비액 (원)


HOUSING_PROFILES = {
    "아파트": HousingProfile("아파트", 3.1, 4_500_000),
    "빌라": HousingProfile("빌라", 2.3, 2_800_000),
    "오피스텔": HousingProfile("오피스텔", 1.4, 1_800_000),
    "단독주택": HousingProfile("단독주택", 2.8, 3_500_000),
}

# 41개 동별 유형별 세대수 (샘플 데이터, 추후 실데이터로 교체)
# DONG_CENTROIDS의 41개 동과 1:1 매핑, 동 특성 반영
DEFAULT_DONG_HOUSING: dict[str, dict[str, int]] = {
    # 강남권 - 아파트 위주
    "강남동": {"아파트": 12000, "빌라": 1500, "오피스텔": 3000, "단독주택": 500},
    "역삼동": {"아파트": 8000, "빌라": 2000, "오피스텔": 4000, "단독주택": 300},
    "서초동": {"아파트": 11000, "빌라": 1800, "오피스텔": 2500, "단독주택": 700},
    "삼성동": {"아파트": 9000, "빌라": 1200, "오피스텔": 3500, "단독주택": 300},
    "잠실동": {"아파트": 15000, "빌라": 1000, "오피스텔": 2000, "단독주택": 200},
    "선릉동": {"아파트": 7000, "빌라": 1500, "오피스텔": 3500, "단독주택": 200},
    "교대동": {"아파트": 6000, "빌라": 2000, "오피스텔": 2000, "단독주택": 400},
    "압구정동": {"아파트": 10000, "빌라": 800, "오피스텔": 1500, "단독주택": 700},
    "신사동": {"아파트": 5000, "빌라": 1500, "오피스텔": 2500, "단독주택": 500},
    "논현동": {"아파트": 4500, "빌라": 2000, "오피스텔": 3000, "단독주택": 300},
    "청담동": {"아파트": 6000, "빌라": 500, "오피스텔": 1500, "단독주택": 1000},
    "학동": {"아파트": 5000, "빌라": 1800, "오피스텔": 2500, "단독주택": 400},
    # 서남권 - 빌라/다세대 혼합
    "방배동": {"아파트": 7000, "빌라": 3000, "오피스텔": 1500, "단독주택": 1000},
    "사당동": {"아파트": 8000, "빌라": 4000, "오피스텔": 1000, "단독주택": 800},
    "신림동": {"아파트": 6000, "빌라": 8000, "오피스텔": 2000, "단독주택": 500},
    "구로동": {"아파트": 5000, "빌라": 5000, "오피스텔": 3000, "단독주택": 400},
    "가산동": {"아파트": 3000, "빌라": 2000, "오피스텔": 5000, "단독주택": 200},
    "목동": {"아파트": 14000, "빌라": 2000, "오피스텔": 1000, "단독주택": 500},
    "영등포동": {"아파트": 5000, "빌라": 3000, "오피스텔": 4000, "단독주택": 300},
    "여의도동": {"아파트": 9000, "빌라": 500, "오피스텔": 3000, "단독주택": 100},
    # 마포/서대문권 - 오피스텔 위주
    "홍대동": {"아파트": 3000, "빌라": 3000, "오피스텔": 6000, "단독주택": 200},
    "합정동": {"아파트": 4000, "빌라": 3000, "오피스텔": 3500, "단독주택": 300},
    "망원동": {"아파트": 3000, "빌라": 4000, "오피스텔": 2000, "단독주택": 500},
    "신촌동": {"아파트": 3000, "빌라": 3500, "오피스텔": 4000, "단독주택": 300},
    "공덕동": {"아파트": 6000, "빌라": 2000, "오피스텔": 3000, "단독주택": 400},
    "마포동": {"아파트": 5000, "빌라": 3000, "오피스텔": 2500, "단독주택": 500},
    # 도심권
    "종로동": {"아파트": 2000, "빌라": 1500, "오피스텔": 3000, "단독주택": 500},
    "명동": {"아파트": 1000, "빌라": 500, "오피스텔": 2000, "단독주택": 100},
    "중구동": {"아파트": 2000, "빌라": 1000, "오피스텔": 2500, "단독주택": 300},
    "용산동": {"아파트": 5000, "빌라": 2000, "오피스텔": 2000, "단독주택": 800},
    "이태원동": {"아파트": 3000, "빌라": 2000, "오피스텔": 1500, "단독주택": 1000},
    "동대문동": {"아파트": 4000, "빌라": 3000, "오피스텔": 2000, "단독주택": 600},
    # 성동/광진권
    "성수동": {"아파트": 5000, "빌라": 2500, "오피스텔": 4000, "단독주택": 300},
    "건대동": {"아파트": 4000, "빌라": 3000, "오피스텔": 3500, "단독주택": 300},
    "왕십리동": {"아파트": 6000, "빌라": 3500, "오피스텔": 2000, "단독주택": 500},
    # 강북권 - 빌라/다세대 비중 높음
    "노원동": {"아파트": 12000, "빌라": 5000, "오피스텔": 1500, "단독주택": 1000},
    "상계동": {"아파트": 14000, "빌라": 4000, "오피스텔": 1000, "단독주택": 800},
    "미아동": {"아파트": 6000, "빌라": 5000, "오피스텔": 1500, "단독주택": 1200},
    "길음동": {"아파트": 7000, "빌라": 4000, "오피스텔": 1500, "단독주택": 800},
    "불광동": {"아파트": 5000, "빌라": 4000, "오피스텔": 1000, "단독주택": 1500},
    "연신내동": {"아파트": 6000, "빌라": 4500, "오피스텔": 1000, "단독주택": 1200},
}


class SpendingPowerCalculator:
    """주거유형별 세대수 기반 소비력 계산기."""

    def __init__(self, housing_data: dict[str, dict[str, int]] | None = None):
        self.housing_data = housing_data or DEFAULT_DONG_HOUSING

    def calculate(self) -> pd.DataFrame:
        """동별 유형별 세대수/세대원수/월소비력 산출.

        Returns:
            DataFrame(동, 유형, 세대수, 세대원수, 월소비력)
        """
        rows = []
        for dong, units in self.housing_data.items():
            for htype, count in units.items():
                profile = HOUSING_PROFILES.get(htype)
                if profile is None:
                    continue
                rows.append({
                    "동": dong,
                    "유형": htype,
                    "세대수": count,
                    "세대원수": round(count * profile.avg_members),
                    "월소비력": count * profile.monthly_spend,
                })
        return pd.DataFrame(rows)

    def get_summary(self) -> pd.DataFrame:
        """동별 요약: 총세대수, 총소비력, 주요주거유형, 1인당소비.

        Returns:
            DataFrame(동, 총세대수, 총인구, 총소비력, 주요주거유형, 1인당소비) — 총소비력 내림차순
        """
        detail = self.calculate()
        if detail.empty:
            return pd.DataFrame(
                columns=["동", "총세대수", "총인구", "총소비력", "주요주거유형", "1인당소비"]
            )

        grouped = detail.groupby("동").agg(
            총세대수=("세대수", "sum"),
            총인구=("세대원수", "sum"),
            총소비력=("월소비력", "sum"),
        ).reset_index()

        # 주요주거유형: 세대수가 가장 많은 유형
        main_type = (
            detail.loc[detail.groupby("동")["세대수"].idxmax()]
            .set_index("동")["유형"]
        )
        grouped["주요주거유형"] = grouped["동"].map(main_type)

        # 1인당 소비
        grouped["1인당소비"] = (grouped["총소비력"] / grouped["총인구"].replace(0, 1)).round(0).astype(int)

        return grouped.sort_values("총소비력", ascending=False).reset_index(drop=True)

    def simulate_change(self, dong: str, housing_type: str, delta: int) -> dict:
        """특정 동의 주거유형 세대수 변경 시뮬레이션.

        Args:
            dong: 동 이름
            housing_type: 주거유형 ("아파트", "빌라", "오피스텔", "단독주택")
            delta: 세대수 변화량 (+/-)

        Returns:
            {"before": {...}, "after": {...}, "변화량": {...}}
        """
        profile = HOUSING_PROFILES.get(housing_type)
        if profile is None:
            return {"error": f"알 수 없는 주거유형: {housing_type}"}

        dong_data = self.housing_data.get(dong, {})
        before_count = dong_data.get(housing_type, 0)
        after_count = max(0, before_count + delta)

        before_spend = before_count * profile.monthly_spend
        after_spend = after_count * profile.monthly_spend
        before_pop = round(before_count * profile.avg_members)
        after_pop = round(after_count * profile.avg_members)

        # 동 전체 소비력 계산
        total_before = sum(
            cnt * HOUSING_PROFILES[ht].monthly_spend
            for ht, cnt in dong_data.items()
            if ht in HOUSING_PROFILES
        )
        total_after = total_before - before_spend + after_spend

        return {
            "before": {
                "세대수": before_count,
                "세대원수": before_pop,
                "월소비력": before_spend,
                "동_총소비력": total_before,
            },
            "after": {
                "세대수": after_count,
                "세대원수": after_pop,
                "월소비력": after_spend,
                "동_총소비력": total_after,
            },
            "변화량": {
                "세대수": after_count - before_count,
                "세대원수": after_pop - before_pop,
                "월소비력": after_spend - before_spend,
                "동_총소비력": total_after - total_before,
            },
        }

    def get_dong_detail(self, dong: str) -> dict:
        """특정 동의 유형별 상세 분석.

        Returns:
            {"dong": str, "detail": DataFrame, "total": dict}
        """
        dong_data = self.housing_data.get(dong, {})
        rows = []
        for htype, count in dong_data.items():
            profile = HOUSING_PROFILES.get(htype)
            if profile is None:
                continue
            rows.append({
                "유형": htype,
                "세대수": count,
                "세대원수": round(count * profile.avg_members),
                "월소비력": count * profile.monthly_spend,
                "비율": 0.0,  # 아래서 계산
            })

        detail_df = pd.DataFrame(rows)
        total_units = detail_df["세대수"].sum() if not detail_df.empty else 0
        if total_units > 0:
            detail_df["비율"] = (detail_df["세대수"] / total_units * 100).round(1)

        total_pop = detail_df["세대원수"].sum() if not detail_df.empty else 0
        total_spend = detail_df["월소비력"].sum() if not detail_df.empty else 0

        return {
            "dong": dong,
            "detail": detail_df,
            "total": {
                "총세대수": int(total_units),
                "총인구": int(total_pop),
                "총소비력": int(total_spend),
                "1인당소비": int(total_spend / total_pop) if total_pop > 0 else 0,
            },
        }
