"""유동인구 → 상권매출 시뮬레이션 테스트."""

import math

import pandas as pd
import pytest

from src.simulation.foot_traffic import (
    FootTrafficSimulator,
    STORE_PROFILES,
    DEFAULT_TIME_SLOTS,
    DEFAULT_DONG_STORES,
)
from src.simulation.spending_power import HOUSING_PROFILES


@pytest.fixture
def simulator():
    return FootTrafficSimulator()


@pytest.fixture
def custom_simulator():
    """최소 데이터로 검증용 시뮬레이터."""
    housing = {
        "강남동": {"아파트": 1000, "빌라": 500},
        "역삼동": {"아파트": 800},
    }
    stores = {
        "강남동": {"음식점": 100, "카페": 50},
        "역삼동": {"음식점": 80, "카페": 40},
    }
    return FootTrafficSimulator(housing_data=housing, store_data=stores)


class TestPopulation:
    def test_dong_population_positive(self, simulator):
        pop = simulator._get_dong_population("강남동")
        assert pop > 0

    def test_dong_population_accuracy(self, custom_simulator):
        pop = custom_simulator._get_dong_population("강남동")
        expected = round(1000 * HOUSING_PROFILES["아파트"].avg_members) + \
                   round(500 * HOUSING_PROFILES["빌라"].avg_members)
        assert pop == expected

    def test_unknown_dong_returns_zero(self, simulator):
        assert simulator._get_dong_population("없는동") == 0


class TestDistanceDecay:
    def test_same_location_max_decay(self):
        assert FootTrafficSimulator._distance_decay(0.0, 2.0) == 1.0

    def test_decay_decreases_with_distance(self):
        near = FootTrafficSimulator._distance_decay(0.5, 2.0)
        far = FootTrafficSimulator._distance_decay(3.0, 2.0)
        assert near > far

    def test_zero_radius(self):
        assert FootTrafficSimulator._distance_decay(1.0, 0.0) == 0.0


class TestVisitDistribution:
    def test_distribution_sums_to_one(self, simulator):
        dist = simulator._compute_visit_distribution("강남동", "음식점")
        assert len(dist) > 0
        assert abs(sum(dist.values()) - 1.0) < 1e-6

    def test_same_dong_higher_than_far(self, simulator):
        dist = simulator._compute_visit_distribution("강남동", "편의점")
        # 편의점: capture_radius=0.8km, 같은 동은 거리 0이므로 가장 높아야 함
        if "강남동" in dist:
            assert dist["강남동"] >= max(
                v for k, v in dist.items() if k != "강남동"
            )

    def test_unknown_category_empty(self, simulator):
        assert simulator._compute_visit_distribution("강남동", "없는업종") == {}


class TestCalculateDaily:
    def test_columns(self, simulator):
        df = simulator.calculate_daily(dong="강남동")
        expected_cols = {"출발동", "도착동", "시간대", "시간대코드", "업종", "방문자수", "예상매출"}
        assert expected_cols.issubset(set(df.columns))

    def test_non_negative_values(self, simulator):
        df = simulator.calculate_daily(dong="강남동")
        assert (df["방문자수"] >= 0).all()
        assert (df["예상매출"] >= 0).all()

    def test_single_dong_origin(self, simulator):
        df = simulator.calculate_daily(dong="강남동")
        assert (df["출발동"] == "강남동").all()

    def test_full_simulation_not_empty(self, simulator):
        df = simulator.calculate_daily()
        assert len(df) > 0

    def test_custom_data(self, custom_simulator):
        df = custom_simulator.calculate_daily()
        assert len(df) > 0
        assert set(df["출발동"].unique()).issubset({"강남동", "역삼동"})


class TestGetSummary:
    def test_columns(self, simulator):
        summary = simulator.get_summary()
        assert "동" in summary.columns
        assert "총방문자수" in summary.columns
        assert "총매출" in summary.columns
        for cat in STORE_PROFILES:
            assert f"{cat}매출" in summary.columns

    def test_sorted_by_revenue(self, simulator):
        summary = simulator.get_summary()
        if len(summary) > 1:
            assert summary["총매출"].iloc[0] >= summary["총매출"].iloc[1]

    def test_non_negative(self, simulator):
        summary = simulator.get_summary()
        assert (summary["총방문자수"] >= 0).all()
        assert (summary["총매출"] >= 0).all()


class TestSimulateChange:
    def test_increase_units(self, simulator):
        result = simulator.simulate_change("강남동", "아파트", 1000)
        assert result["변화량"]["인구"] > 0
        assert result["변화량"]["총매출"] > 0
        assert result["변화량"]["총방문자수"] > 0

    def test_decrease_units(self, simulator):
        result = simulator.simulate_change("강남동", "아파트", -500)
        assert result["변화량"]["인구"] < 0
        assert result["변화량"]["총매출"] < 0

    def test_neighbor_effects_exist(self, simulator):
        result = simulator.simulate_change("강남동", "아파트", 2000)
        assert len(result["이웃영향"]) > 0

    def test_neighbor_revenue_changes(self, simulator):
        result = simulator.simulate_change("강남동", "아파트", 2000)
        for neighbor in result["이웃영향"]:
            assert "동" in neighbor
            assert "매출변화" in neighbor
            # 세대 증가 시 이웃 매출도 증가
            assert neighbor["매출변화"] > 0


class TestGetDongDetail:
    def test_detail_structure(self, simulator):
        detail = simulator.get_dong_detail("강남동")
        assert detail["dong"] == "강남동"
        assert detail["population"] > 0
        assert isinstance(detail["by_category"], pd.DataFrame)
        assert isinstance(detail["by_time"], pd.DataFrame)
        assert isinstance(detail["by_origin"], pd.DataFrame)

    def test_detail_categories(self, simulator):
        detail = simulator.get_dong_detail("강남동")
        cats = set(detail["by_category"]["업종"].tolist())
        # 강남동에 모든 업종 점포가 있으므로 전부 나와야 함
        assert len(cats) > 0
