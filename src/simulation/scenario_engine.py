"""What-if 시나리오 엔진."""

import logging
from copy import deepcopy

import pandas as pd

from src.simulation.flow_model import FlowModel

logger = logging.getLogger(__name__)


class ScenarioEngine:
    """What-if 시나리오 시뮬레이션.

    - 신규 지하철역 개통
    - 임대료 변동
    - 인구 변화
    """

    def __init__(self, baseline_data: dict[str, pd.DataFrame]):
        """
        Args:
            baseline_data: 기준 데이터 딕셔너리
                - "subway": 지하철 승하차
                - "realestate": 부동산 실거래
                - "population": 생활인구
                - "spending": 추정매출
                - "commercial": 상가업소
        """
        self.baseline = baseline_data
        self.flow_model = FlowModel()

    def new_station_scenario(
        self,
        station_name: str,
        dong_code: str,
        estimated_daily_passengers: int = 30000,
    ) -> dict:
        """신규 지하철역 개통 시나리오.

        Args:
            station_name: 신규역 이름
            dong_code: 해당 행정동코드
            estimated_daily_passengers: 예상 일일 승하차 인원

        Returns:
            before/after 비교 데이터
        """
        result = {
            "scenario": "new_station",
            "station_name": station_name,
            "dong_code": dong_code,
            "before": {},
            "after": {},
            "changes": {},
        }

        # Before 상태
        subway_df = self.baseline.get("subway", pd.DataFrame())
        if not subway_df.empty and "행정동코드" in subway_df.columns:
            dong_before = subway_df[subway_df["행정동코드"] == dong_code]
            result["before"]["일평균_하차"] = (
                dong_before["하차총승객수"].sum() / max(dong_before["날짜"].nunique(), 1)
                if not dong_before.empty else 0
            )
        else:
            result["before"]["일평균_하차"] = 0

        # After: 유동인구 증가
        new_daily = estimated_daily_passengers
        result["after"]["일평균_하차"] = result["before"]["일평균_하차"] + new_daily

        # 영향 추정 (경험적 계수)
        population_increase_pct = min(new_daily / 10000 * 5, 30)  # 최대 30%
        spending_increase_pct = population_increase_pct * 0.8  # 매출은 인구의 80%
        realestate_increase_pct = population_increase_pct * 0.3  # 부동산은 더 느림

        result["changes"] = {
            "유동인구_변화율": round(population_increase_pct, 1),
            "추정매출_변화율": round(spending_increase_pct, 1),
            "부동산가격_변화율": round(realestate_increase_pct, 1),
            "신규업소_예상": int(new_daily / 1000 * 5),
        }

        # 주변 동 영향
        result["ripple_effects"] = self._estimate_ripple(
            dong_code, population_increase_pct
        )

        return result

    def rent_change_scenario(
        self,
        dong_code: str,
        rent_change_pct: float,
    ) -> dict:
        """임대료 변동 시나리오.

        rent_change_pct > 0: 임대료 상승
        rent_change_pct < 0: 임대료 하락
        """
        result = {
            "scenario": "rent_change",
            "dong_code": dong_code,
            "rent_change_pct": rent_change_pct,
            "changes": {},
        }

        # 임대료 상승 시 업소 이탈, 소비 감소
        if rent_change_pct > 0:
            business_exit_rate = min(rent_change_pct * 0.3, 20)  # 최대 20% 이탈
            spending_change = -rent_change_pct * 0.2
            population_change = -rent_change_pct * 0.1
        else:
            business_exit_rate = rent_change_pct * 0.2  # 음수 = 신규 진입
            spending_change = -rent_change_pct * 0.15
            population_change = -rent_change_pct * 0.05

        result["changes"] = {
            "업소_변화율": round(-business_exit_rate, 1),
            "매출_변화율": round(spending_change, 1),
            "인구_변화율": round(population_change, 1),
        }

        return result

    def population_change_scenario(
        self,
        dong_code: str,
        population_change_pct: float,
    ) -> dict:
        """인구 변화 시나리오 (재개발, 대규모 아파트 입주 등)."""
        result = {
            "scenario": "population_change",
            "dong_code": dong_code,
            "population_change_pct": population_change_pct,
            "changes": {},
        }

        spending_change = population_change_pct * 0.7
        realestate_change = population_change_pct * 0.2
        commercial_change = population_change_pct * 0.4

        result["changes"] = {
            "매출_변화율": round(spending_change, 1),
            "부동산가격_변화율": round(realestate_change, 1),
            "업소수_변화율": round(commercial_change, 1),
        }

        return result

    def _estimate_ripple(
        self, center_dong: str, change_pct: float
    ) -> list[dict]:
        """인접 동 파급효과 추정 (거리 감쇠)."""
        # 실제 구현에서는 행정동 인접성 그래프를 사용
        return [
            {"동": "인접동1", "변화율": round(change_pct * 0.5, 1)},
            {"동": "인접동2", "변화율": round(change_pct * 0.3, 1)},
            {"동": "인접동3", "변화율": round(change_pct * 0.1, 1)},
        ]

    def compare_scenarios(self, scenarios: list[dict]) -> pd.DataFrame:
        """여러 시나리오 결과 비교."""
        rows = []
        for s in scenarios:
            row = {
                "시나리오": s.get("scenario", ""),
                "대상": s.get("dong_code", s.get("station_name", "")),
            }
            row.update(s.get("changes", {}))
            rows.append(row)
        return pd.DataFrame(rows)
