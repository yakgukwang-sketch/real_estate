"""세대수 데이터 기반 시뮬레이션 테스트."""

import pytest

from src.simulation.household_data_loader import (
    HOUSING_TYPE_PROFILES,
    GU_TO_DONG_MAP,
    HouseholdDataLoader,
    compute_subway_distance_matrix,
    compute_work_weights_by_distance,
)
from src.simulation.agent_model import CityModel, Resident


class TestHouseholdDataLoader:
    """HouseholdDataLoader 테스트."""

    def test_distance_matrix_completeness(self):
        dm = compute_subway_distance_matrix()
        assert len(dm) > 30
        # 자기 자신까지의 거리는 0
        for dong in dm:
            assert dm[dong][dong] == 0.0

    def test_distance_matrix_symmetry(self):
        dm = compute_subway_distance_matrix()
        dongs = list(dm.keys())[:10]
        for d1 in dongs:
            for d2 in dongs:
                assert abs(dm[d1][d2] - dm[d2][d1]) < 0.01

    def test_distance_realistic_range(self):
        dm = compute_subway_distance_matrix()
        # 서울 내 최대 거리 ~40km 이내
        for d1 in dm:
            for d2 in dm[d1]:
                assert dm[d1][d2] < 50.0

    def test_work_weights_distance_decay(self):
        dm = compute_subway_distance_matrix()
        emp = {"강남동": 10000, "노원동": 10000, "여의도동": 10000}
        weights = compute_work_weights_by_distance("강남동", emp, dm)
        # 강남동에서 강남동이 가장 높은 가중치
        assert weights["강남동"] > weights["노원동"]

    def test_work_weights_sum_to_one(self):
        dm = compute_subway_distance_matrix()
        emp = {"강남동": 10000, "역삼동": 8000, "서초동": 7000}
        weights = compute_work_weights_by_distance("강남동", emp, dm)
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_housing_profiles_valid(self):
        for ht, profile in HOUSING_TYPE_PROFILES.items():
            assert "income_weights" in profile
            assert abs(sum(profile["income_weights"].values()) - 1.0) < 0.01
            assert profile["spending_mult"] > 0
            assert profile["avg_household_size"] > 0

    def test_gu_to_dong_map_covers_major_dongs(self):
        all_dongs = set()
        for dongs in GU_TO_DONG_MAP.values():
            all_dongs.update(dongs)
        assert "강남동" in all_dongs
        assert "여의도동" in all_dongs
        assert "잠실동" in all_dongs
        assert "노원동" in all_dongs

    def test_loader_data_status(self):
        loader = HouseholdDataLoader()
        status = loader.get_data_status()
        assert isinstance(status, dict)
        assert "household_summary" in status

    def test_loader_fallback_population(self):
        loader = HouseholdDataLoader()
        fallback = {"강남동": 50000, "역삼동": 40000}
        result = loader.build_dong_population(fallback_population=fallback)
        # 실제 데이터 없으면 fallback 반환
        assert len(result) >= 2

    def test_build_simulation_input(self):
        loader = HouseholdDataLoader()
        fallback_pop = {"강남동": 5000, "역삼동": 3000}
        fallback_emp = {"강남동": 12000, "역삼동": 9000}
        result = loader.build_simulation_input(fallback_pop, fallback_emp)
        assert "dong_population" in result
        assert "dong_employment" in result
        assert "housing_distribution" in result
        assert "distance_matrix" in result


class TestCityModelHousing:
    """주거유형 통합 CityModel 테스트."""

    @pytest.fixture
    def small_model(self):
        pop = {"강남동": 3000, "역삼동": 2000, "노원동": 4000}
        emp = {"강남동": 10000, "역삼동": 8000, "노원동": 2000}
        housing = {
            "강남동": {"apt": 0.4, "officetel": 0.3, "villa": 0.3},
            "역삼동": {"apt": 0.5, "officetel": 0.3, "villa": 0.2},
            "노원동": {"apt": 0.7, "officetel": 0.1, "villa": 0.2},
        }
        dm = compute_subway_distance_matrix()
        model = CityModel(pop, emp, housing_distribution=housing, distance_matrix=dm)
        return model

    def test_agents_have_housing_type(self, small_model):
        agents = list(small_model.agents)
        assert len(agents) > 0
        types = {a.housing_type for a in agents}
        assert types.issubset({"apt", "officetel", "villa"})

    def test_housing_type_distribution(self, small_model):
        from collections import Counter
        agents = list(small_model.agents)
        types = Counter(a.housing_type for a in agents)
        # apt가 가장 많아야 함 (평균 비율이 가장 높음)
        assert types["apt"] > types.get("villa", 0) or len(agents) < 20

    def test_spending_multiplier_applied(self, small_model):
        agents = list(small_model.agents)
        villa_agents = [a for a in agents if a.housing_type == "villa"]
        apt_agents = [a for a in agents if a.housing_type == "apt"]
        if villa_agents and apt_agents:
            # villa spending_mult (0.65) < apt (1.0)
            assert villa_agents[0]._spending_mult < apt_agents[0]._spending_mult

    def test_simulation_runs(self, small_model):
        small_model.run(days=3)
        summary = small_model.get_summary()
        assert len(summary) > 0
        assert all(v > 0 for v in summary.values())

    def test_housing_type_summary(self, small_model):
        small_model.run(days=1)
        ht_summary = small_model.get_housing_type_summary()
        assert not ht_summary.empty
        assert "주거유형" in ht_summary.columns

    def test_commute_distance_summary(self, small_model):
        small_model.run(days=1)
        cd = small_model.get_commute_distance_summary()
        assert not cd.empty
        assert "평균거리" in cd.columns

    def test_from_household_data_factory(self):
        pop = {"강남동": 2000, "잠실동": 3000}
        emp = {"강남동": 8000, "잠실동": 3000}
        model = CityModel.from_household_data(
            fallback_population=pop,
            fallback_employment=emp,
        )
        agents = list(model.agents)
        assert len(agents) > 0
        model.run(days=2)
        assert len(model.daily_records) == 2

    def test_distance_based_work_preference(self):
        """가까운 직장동이 더 많이 선택되는지 검증."""
        pop = {"강남동": 10000}
        emp = {"강남동": 5000, "역삼동": 5000, "노원동": 5000}
        dm = compute_subway_distance_matrix()
        model = CityModel(pop, emp, distance_matrix=dm)
        agents = list(model.agents)
        work_counts = {}
        for a in agents:
            work_counts[a.work_dong] = work_counts.get(a.work_dong, 0) + 1
        # 강남동/역삼동 (가까움) > 노원동 (멀음)
        nearby = work_counts.get("강남동", 0) + work_counts.get("역삼동", 0)
        far = work_counts.get("노원동", 0)
        assert nearby > far
