"""에이전트 기반 시뮬레이션 모델 (mesa 프레임워크)."""

import logging
import random
from collections import defaultdict

import mesa
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Resident(mesa.Agent):
    """거주자 에이전트 - 현실적 하루 행동 패턴 시뮬레이션.

    하루 7단계:
    1. 출근 (9시) → 직장동 이동
    2. 점심 (12시) → 직장 주변 소비
    3. 오후업무 (13시) → 직장동 복귀
    4. 퇴근 (18시) → 거주동 이동
    5. 저녁외출 (20시) → 거주동 주변 상점 소비 (확률적)
    6. 귀가 (22시) → 집
    7. 수면 → 다음날
    """

    PHASES = [
        "commute_to_work",    # 09시: 출근
        "lunch",              # 12시: 점심 소비
        "afternoon_work",     # 13시: 오후 업무
        "commute_home",       # 18시: 퇴근
        "evening_errands",    # 20시: 저녁 외출 (쇼핑, 마트 등)
        "return_home",        # 22시: 귀가
        "sleep",              # 수면 → 리셋
    ]

    def __init__(
        self,
        model,
        home_dong: str,
        work_dong: str,
        income_level: int,
        housing_type: str = "apt",
        spending_mult: float = 1.0,
        evening_out_mult: float = 1.0,
    ):
        super().__init__(model)
        self.home_dong = home_dong
        self.work_dong = work_dong
        self.income_level = income_level  # 1~5 (저소득~고소득)
        self.housing_type = housing_type  # apt, officetel, villa
        self.current_dong = home_dong
        self.daily_spending = 0.0
        self.phase_idx = 0

        # 소득 수준별 기본 일일 소비 예산
        self._base_spending = {1: 20000, 2: 35000, 3: 55000, 4: 80000, 5: 120000}
        # 저녁 외출 확률 (소득 높을수록 높음)
        base_evening = {1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6}
        self._evening_out_prob = {
            k: min(v * evening_out_mult, 0.9) for k, v in base_evening.items()
        }
        self._spending_mult = spending_mult

    @property
    def time_of_day(self):
        """현재 시간대 (레거시 호환)."""
        phase = self.PHASES[self.phase_idx % len(self.PHASES)]
        legacy_map = {
            "commute_to_work": "morning",
            "lunch": "daytime",
            "afternoon_work": "daytime",
            "commute_home": "evening",
            "evening_errands": "night",
            "return_home": "night",
            "sleep": "morning",
        }
        return legacy_map.get(phase, "morning")

    @time_of_day.setter
    def time_of_day(self, value):
        """레거시 호환: 외부에서 phase를 문자열로 설정."""
        phase_map = {
            "morning": 0,
            "daytime": 1,
            "evening": 3,
            "night": 4,
        }
        self.phase_idx = phase_map.get(value, 0)

    def step(self):
        """한 단계 행동."""
        phase = self.PHASES[self.phase_idx % len(self.PHASES)]
        getattr(self, f"_do_{phase}")()
        self.phase_idx += 1

    def _do_commute_to_work(self):
        """09시 출근 → 직장동 이동."""
        origin = self.current_dong
        self.current_dong = self.work_dong
        self.model.record_flow("morning", origin, self.work_dong)
        self.model.record_movement(self.home_dong, self.work_dong, "출근")

    def _do_lunch(self):
        """12시 점심 → 직장 주변 소비."""
        base = self._base_spending.get(self.income_level, 50000) * self._spending_mult
        lunch_cost = base * 0.15 * random.uniform(0.7, 1.3)  # 일 예산의 ~15%
        self.daily_spending += lunch_cost
        self.model.record_spending(self.work_dong, lunch_cost)

    def _do_afternoon_work(self):
        """13시 오후 업무 → 직장동 (추가 소비: 카페 등)."""
        base = self._base_spending.get(self.income_level, 50000) * self._spending_mult
        if random.random() < 0.3:  # 30% 확률로 카페/간식
            snack = base * 0.05 * random.uniform(0.5, 1.5)
            self.daily_spending += snack
            self.model.record_spending(self.work_dong, snack)

    def _do_commute_home(self):
        """18시 퇴근 → 거주동 이동."""
        origin = self.current_dong
        self.current_dong = self.home_dong
        self.model.record_flow("evening", origin, self.home_dong)
        self.model.record_movement(self.work_dong, self.home_dong, "퇴근")

    def _do_evening_errands(self):
        """20시 저녁 외출 → 마트/상점 소비 (확률적)."""
        prob = self._evening_out_prob.get(self.income_level, 0.3)
        if random.random() < prob:
            base = self._base_spending.get(self.income_level, 50000) * self._spending_mult
            errand_cost = base * 0.3 * random.uniform(0.5, 2.0)  # 일 예산의 ~30%
            self.daily_spending += errand_cost
            self.model.record_spending(self.home_dong, errand_cost)

    def _do_return_home(self):
        """22시 귀가."""
        self.current_dong = self.home_dong

    def _do_sleep(self):
        """수면 → 일일 리셋."""
        self.phase_idx = -1  # step()에서 +1 되어 0으로 복귀
        self.daily_spending = 0.0


class CityModel(mesa.Model):
    """서울시 도시 시뮬레이션 모델."""

    def __init__(
        self,
        dong_population: dict[str, int],
        dong_employment: dict[str, int],
        income_distribution: dict[int, float] | None = None,
        housing_distribution: dict[str, dict[str, float]] | None = None,
        distance_matrix: dict[str, dict[str, float]] | None = None,
    ):
        """
        Args:
            dong_population: 행정동별 거주 인구수
            dong_employment: 행정동별 직장 인구수 (= 유입 가중치)
            income_distribution: 소득수준별 비율 {1: 0.2, 2: 0.3, ...}
            housing_distribution: 동별 주거유형 비율 {dong: {apt: 0.6, officetel: 0.2, villa: 0.2}}
            distance_matrix: 동-동 간 거리 (km) {dong: {dong: km}}
        """
        super().__init__()
        self.dong_pop_input = dong_population
        self.dong_employment = dong_employment
        self.income_dist = income_distribution or {
            1: 0.15, 2: 0.25, 3: 0.30, 4: 0.20, 5: 0.10
        }
        self.housing_dist = housing_distribution or {}
        self.distance_matrix = distance_matrix or {}
        self.spending_ledger: dict[str, float] = {}
        self.movement_ledger: dict[tuple, int] = {}
        self.daily_records: list[dict] = []
        self.movement_records: list[dict] = []

        # 유동인구 흐름 추적
        self.flow_ledger: dict[str, dict[tuple[str, str], int]] = {
            phase: defaultdict(int) for phase in ("morning", "daytime", "evening", "night")
        }
        self.phase_spending: dict[str, dict[str, float]] = {
            phase: defaultdict(float) for phase in ("morning", "daytime", "evening", "night")
        }
        self.dong_population: dict[str, dict[str, int]] = {
            phase: defaultdict(int) for phase in ("morning", "daytime", "evening", "night")
        }

        self._create_agents()

    def _create_agents(self):
        """에이전트 생성 (주거유형별 + 거리 기반 직장 배정)."""
        from src.simulation.household_data_loader import (
            HOUSING_TYPE_PROFILES,
            compute_work_weights_by_distance,
        )

        work_dongs = list(self.dong_employment.keys())

        # 거리 기반 직장 가중치 캐시 (동별로 한 번만 계산)
        _work_weight_cache: dict[str, tuple[list[str], list[float]]] = {}

        def _get_work_choice(home_dong: str) -> str:
            if home_dong not in _work_weight_cache:
                if self.distance_matrix:
                    weights = compute_work_weights_by_distance(
                        home_dong, self.dong_employment, self.distance_matrix,
                    )
                    dongs = list(weights.keys())
                    probs = list(weights.values())
                else:
                    total_emp = sum(self.dong_employment.values()) or 1
                    dongs = work_dongs
                    probs = [v / total_emp for v in self.dong_employment.values()]
                _work_weight_cache[home_dong] = (dongs, probs)
            dongs, probs = _work_weight_cache[home_dong]
            return random.choices(dongs, weights=probs, k=1)[0]

        for dong, pop in self.dong_pop_input.items():
            # 인구를 1/100로 스케일링 (시뮬레이션 속도)
            n_agents = max(1, pop // 100)

            # 주거유형 비율
            h_dist = self.housing_dist.get(dong, {"apt": 0.5, "officetel": 0.15, "villa": 0.35})
            h_types = list(h_dist.keys())
            h_probs = list(h_dist.values())

            for _ in range(n_agents):
                # 주거유형 결정
                h_type = random.choices(h_types, weights=h_probs, k=1)[0]
                profile = HOUSING_TYPE_PROFILES.get(h_type, HOUSING_TYPE_PROFILES["apt"])

                # 소득 분포: 주거유형별 가중치 적용
                income_weights = profile["income_weights"]
                income_levels = list(income_weights.keys())
                income_probs = list(income_weights.values())
                income = random.choices(income_levels, weights=income_probs, k=1)[0]

                # 거리 기반 직장 배정
                work = _get_work_choice(dong)

                agent = Resident(
                    self,
                    home_dong=dong,
                    work_dong=work,
                    income_level=income,
                    housing_type=h_type,
                    spending_mult=profile["spending_mult"],
                    evening_out_mult=profile["evening_out_mult"],
                )
                # mesa 3.x에서는 agents 자동 관리

    def record_spending(self, dong: str, amount: float):
        """소비 기록."""
        self.spending_ledger[dong] = self.spending_ledger.get(dong, 0) + amount

    def record_flow(self, phase: str, origin: str, destination: str):
        """유동인구 흐름 기록."""
        self.flow_ledger[phase][(origin, destination)] += 1

    def record_movement(self, from_dong: str, to_dong: str, purpose: str):
        """이동 기록."""
        key = (from_dong, to_dong, purpose)
        self.movement_ledger[key] = self.movement_ledger.get(key, 0) + 1

    def _record_phase_population(self, phase: str):
        """현 단계에서 각 동의 인구수를 기록."""
        for agent in self.agents:
            self.dong_population[phase][agent.current_dong] += 1

    def step(self):
        """하루 7단계 시뮬레이션.

        출근 → 점심 → 오후업무 → 퇴근 → 저녁외출 → 귀가 → 수면
        """
        self.spending_ledger = {}
        self.movement_ledger = {}
        self._current_phase_spending: dict[str, float] = {}

        for phase in ["morning", "daytime", "evening", "night"]:
            phase_spend_before = dict(self.spending_ledger)
            for agent in self.agents:
                agent.step()
            # 이 단계에서 발생한 소비만 기록
            for dong, total in self.spending_ledger.items():
                prev = phase_spend_before.get(dong, 0.0)
                diff = total - prev
                if diff > 0:
                    self.phase_spending[phase][dong] += diff
            self._record_phase_population(phase)

        # sleep 단계 (7단계 중 나머지)
        for agent in self.agents:
            agent.step()
        for agent in self.agents:
            agent.step()
        for agent in self.agents:
            agent.step()

        self.daily_records.append(dict(self.spending_ledger))
        self.movement_records.append(dict(self.movement_ledger))

    def run(self, days: int = 30) -> list[dict]:
        """N일 시뮬레이션 실행."""
        self.daily_records = []
        self.movement_records = []
        # 누적 데이터 초기화
        self.flow_ledger = {
            phase: defaultdict(int) for phase in ("morning", "daytime", "evening", "night")
        }
        self.phase_spending = {
            phase: defaultdict(float) for phase in ("morning", "daytime", "evening", "night")
        }
        self.dong_population = {
            phase: defaultdict(int) for phase in ("morning", "daytime", "evening", "night")
        }
        for day in range(days):
            self.step()
            if (day + 1) % 10 == 0:
                logger.info("시뮬레이션 %d/%d일 완료", day + 1, days)
        return self.daily_records

    def get_summary(self) -> dict[str, float]:
        """행정동별 총 소비액 요약."""
        summary: dict[str, float] = {}
        for daily in self.daily_records:
            for dong, amount in daily.items():
                summary[dong] = summary.get(dong, 0) + amount
        return summary

    def get_flow_summary(self) -> pd.DataFrame:
        """유동인구 흐름 요약 DataFrame 반환."""
        rows = []
        for phase, flows in self.flow_ledger.items():
            for (origin, dest), count in flows.items():
                rows.append({
                    "origin": origin,
                    "destination": dest,
                    "count": count,
                    "phase": phase,
                })
        if not rows:
            return pd.DataFrame(columns=["origin", "destination", "count", "phase"])
        return pd.DataFrame(rows)

    def get_phase_spending(self) -> pd.DataFrame:
        """단계별 소비 요약 DataFrame 반환."""
        rows = []
        for phase, spending in self.phase_spending.items():
            for dong, amount in spending.items():
                rows.append({
                    "dong": dong,
                    "phase": phase,
                    "spending": amount,
                })
        if not rows:
            return pd.DataFrame(columns=["dong", "phase", "spending"])
        return pd.DataFrame(rows)

    def get_dong_population(self) -> pd.DataFrame:
        """단계별 동별 인구 요약 DataFrame 반환."""
        rows = []
        for phase, pops in self.dong_population.items():
            for dong, pop in pops.items():
                rows.append({
                    "dong": dong,
                    "phase": phase,
                    "population": pop,
                })
        if not rows:
            return pd.DataFrame(columns=["dong", "phase", "population"])
        return pd.DataFrame(rows)

    def get_movement_summary(self) -> pd.DataFrame:
        """이동 패턴 요약 - 출발지→도착지별 이동 횟수."""
        rows = []
        for daily in self.movement_records:
            for (from_dong, to_dong, purpose), count in daily.items():
                rows.append({
                    "출발지": from_dong,
                    "도착지": to_dong,
                    "목적": purpose,
                    "이동횟수": count,
                })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        return (
            df.groupby(["출발지", "도착지", "목적"])["이동횟수"]
            .sum()
            .reset_index()
            .sort_values("이동횟수", ascending=False)
        )

    def get_daily_series(self) -> pd.DataFrame:
        """일별 행정동별 소비액 시계열."""
        rows = []
        for day, daily in enumerate(self.daily_records, 1):
            for dong, amount in daily.items():
                rows.append({"일차": day, "행정동": dong, "소비액": amount})
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @classmethod
    def from_processed_data(
        cls,
        population_df: pd.DataFrame,
        subway_df: pd.DataFrame | None = None,
        income_distribution: dict[int, float] | None = None,
    ) -> "CityModel":
        """처리된 데이터에서 CityModel 자동 생성.

        Args:
            population_df: 행정동코드, 평균생활인구 컬럼 필요
            subway_df: 행정동코드, 하차총승객수 컬럼 (직장인구 프록시)
            income_distribution: 소득수준별 비율
        """
        # 거주인구
        dong_pop: dict[str, int] = {}
        if "행정동코드" in population_df.columns:
            pop_col = "평균생활인구" if "평균생활인구" in population_df.columns else None
            if pop_col:
                agg = population_df.groupby("행정동코드")[pop_col].mean()
                dong_pop = {str(k): int(v) for k, v in agg.items() if v > 0}

        # 직장인구 (지하철 하차 기반 프록시)
        dong_emp: dict[str, int] = {}
        if subway_df is not None and not subway_df.empty:
            emp_col = "하차총승객수" if "하차총승객수" in subway_df.columns else None
            if emp_col:
                agg = subway_df.groupby("행정동코드")[emp_col].sum()
                dong_emp = {str(k): int(v) for k, v in agg.items() if v > 0}

        if not dong_pop:
            raise ValueError("인구 데이터에서 유효한 행정동을 찾을 수 없습니다")

        # 직장인구가 없으면 거주인구를 기본으로 사용
        if not dong_emp:
            dong_emp = dong_pop

        return cls(dong_pop, dong_emp, income_distribution)

    @classmethod
    def from_household_data(
        cls,
        fallback_population: dict[str, int] | None = None,
        fallback_employment: dict[str, int] | None = None,
    ) -> "CityModel":
        """세대수 데이터에서 CityModel 자동 생성.

        수집된 세대수 데이터가 있으면 활용하고,
        없으면 fallback 데이터로 생성합니다.
        """
        from src.simulation.household_data_loader import HouseholdDataLoader

        loader = HouseholdDataLoader()
        sim_input = loader.build_simulation_input(
            fallback_population=fallback_population,
            fallback_employment=fallback_employment,
        )
        return cls(
            dong_population=sim_input["dong_population"],
            dong_employment=sim_input["dong_employment"],
            housing_distribution=sim_input["housing_distribution"],
            distance_matrix=sim_input["distance_matrix"],
        )

    def get_housing_type_summary(self) -> pd.DataFrame:
        """에이전트 주거유형별 통계."""
        rows = []
        type_stats: dict[str, dict] = {}
        for agent in self.agents:
            ht = agent.housing_type
            if ht not in type_stats:
                type_stats[ht] = {"count": 0, "total_spending": 0.0}
            type_stats[ht]["count"] += 1
            type_stats[ht]["total_spending"] += agent.daily_spending

        for ht, stats in type_stats.items():
            rows.append({
                "주거유형": ht,
                "에이전트수": stats["count"],
                "비율": round(stats["count"] / max(len(list(self.agents)), 1) * 100, 1),
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_commute_distance_summary(self) -> pd.DataFrame:
        """출퇴근 거리 통계."""
        from src.simulation.household_data_loader import compute_subway_distance_matrix

        dist_matrix = self.distance_matrix or compute_subway_distance_matrix()
        rows = []
        for agent in self.agents:
            home = agent.home_dong
            work = agent.work_dong
            dist = dist_matrix.get(home, {}).get(work, 0)
            rows.append({
                "거주동": home,
                "직장동": work,
                "주거유형": agent.housing_type,
                "거리_km": round(dist, 2),
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.groupby(["거주동", "직장동"]).agg(
            이동인원=("거리_km", "count"),
            평균거리=("거리_km", "mean"),
        ).reset_index().sort_values("이동인원", ascending=False)
