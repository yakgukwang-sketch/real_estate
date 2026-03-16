"""에이전트 기반 시뮬레이션 모델 (mesa 프레임워크)."""

import logging
import random

import mesa
import numpy as np

logger = logging.getLogger(__name__)


class Resident(mesa.Agent):
    """거주자 에이전트 - 거주동, 직장동, 소득수준, 소비패턴 보유."""

    def __init__(self, model, home_dong: str, work_dong: str, income_level: int):
        super().__init__(model)
        self.home_dong = home_dong
        self.work_dong = work_dong
        self.income_level = income_level  # 1~5 (저소득~고소득)
        self.current_dong = home_dong
        self.daily_spending = 0.0
        self.time_of_day = "morning"

        # 소득 수준별 기본 소비 성향
        self._base_spending = {1: 20000, 2: 35000, 3: 55000, 4: 80000, 5: 120000}

    def step(self):
        """하루 행동 시뮬레이션."""
        if self.time_of_day == "morning":
            self._commute_to_work()
        elif self.time_of_day == "daytime":
            self._daytime_spending()
        elif self.time_of_day == "evening":
            self._commute_home()
        elif self.time_of_day == "night":
            self._nighttime_spending()

    def _commute_to_work(self):
        """출근."""
        self.current_dong = self.work_dong
        self.time_of_day = "daytime"

    def _daytime_spending(self):
        """주간 소비 (직장 주변)."""
        base = self._base_spending.get(self.income_level, 50000)
        self.daily_spending += base * 0.4 * random.uniform(0.5, 1.5)
        self.model.record_spending(self.work_dong, self.daily_spending)
        self.time_of_day = "evening"

    def _commute_home(self):
        """퇴근."""
        self.current_dong = self.home_dong
        self.time_of_day = "night"

    def _nighttime_spending(self):
        """야간 소비 (거주지 주변)."""
        base = self._base_spending.get(self.income_level, 50000)
        night_spend = base * 0.6 * random.uniform(0.3, 1.5)
        self.daily_spending += night_spend
        self.model.record_spending(self.home_dong, night_spend)
        self.time_of_day = "morning"
        self.daily_spending = 0.0  # 일일 리셋


class CityModel(mesa.Model):
    """서울시 도시 시뮬레이션 모델."""

    def __init__(
        self,
        dong_population: dict[str, int],
        dong_employment: dict[str, int],
        income_distribution: dict[int, float] | None = None,
    ):
        """
        Args:
            dong_population: 행정동별 거주 인구수
            dong_employment: 행정동별 직장 인구수 (= 유입 가중치)
            income_distribution: 소득수준별 비율 {1: 0.2, 2: 0.3, ...}
        """
        super().__init__()
        self.dong_population = dong_population
        self.dong_employment = dong_employment
        self.income_dist = income_distribution or {
            1: 0.15, 2: 0.25, 3: 0.30, 4: 0.20, 5: 0.10
        }
        self.spending_ledger: dict[str, float] = {}
        self.daily_records: list[dict] = []

        self._create_agents()

    def _create_agents(self):
        """에이전트 생성."""
        # 직장동 가중치 (총 고용 인구 기반)
        total_emp = sum(self.dong_employment.values()) or 1
        work_weights = {k: v / total_emp for k, v in self.dong_employment.items()}
        work_dongs = list(work_weights.keys())
        work_probs = list(work_weights.values())

        # 소득 분포
        income_levels = list(self.income_dist.keys())
        income_probs = list(self.income_dist.values())

        for dong, pop in self.dong_population.items():
            # 인구를 1/100로 스케일링 (시뮬레이션 속도)
            n_agents = max(1, pop // 100)
            for _ in range(n_agents):
                work = random.choices(work_dongs, weights=work_probs, k=1)[0]
                income = random.choices(income_levels, weights=income_probs, k=1)[0]
                agent = Resident(self, home_dong=dong, work_dong=work, income_level=income)
                # mesa 3.x에서는 agents 자동 관리

    def record_spending(self, dong: str, amount: float):
        """소비 기록."""
        self.spending_ledger[dong] = self.spending_ledger.get(dong, 0) + amount

    def step(self):
        """하루 4단계 시뮬레이션."""
        self.spending_ledger = {}
        for phase in ["morning", "daytime", "evening", "night"]:
            for agent in self.agents:
                agent.time_of_day = phase
                agent.step()

        self.daily_records.append(dict(self.spending_ledger))

    def run(self, days: int = 30) -> list[dict]:
        """N일 시뮬레이션 실행."""
        self.daily_records = []
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
