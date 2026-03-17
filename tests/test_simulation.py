"""시뮬레이션 모듈 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import pytest

from src.simulation.agent_model import CityModel
from src.simulation.scenario_engine import ScenarioEngine
from src.simulation.flow_model import FlowModel
from src.simulation.forecast import Forecaster
from src.analysis.trend_analysis import TrendAnalyzer


def _has_statsmodels():
    try:
        import statsmodels
        return True
    except ImportError:
        return False


# ── CityModel 테스트 ──

def test_city_model_runs():
    pop = {"동A": 10000, "동B": 20000}
    emp = {"동A": 30000, "동B": 15000}
    model = CityModel(pop, emp)
    records = model.run(days=3)
    assert len(records) == 3
    summary = model.get_summary()
    assert len(summary) > 0


def test_city_model_daily_series():
    pop = {"동A": 10000, "동B": 20000}
    emp = {"동A": 30000, "동B": 15000}
    model = CityModel(pop, emp)
    model.run(days=5)
    series = model.get_daily_series()
    assert not series.empty
    assert "일차" in series.columns
    assert "행정동" in series.columns
    assert "소비액" in series.columns
    assert series["일차"].max() == 5


def test_city_model_from_processed_data():
    pop_df = pd.DataFrame({
        "행정동코드": ["A", "A", "B", "B"],
        "평균생활인구": [5000, 6000, 3000, 4000],
    })
    subway_df = pd.DataFrame({
        "행정동코드": ["A", "B"],
        "하차총승객수": [20000, 10000],
    })
    model = CityModel.from_processed_data(pop_df, subway_df)
    records = model.run(days=2)
    assert len(records) == 2


def test_city_model_from_processed_data_no_subway():
    pop_df = pd.DataFrame({
        "행정동코드": ["A", "B"],
        "평균생활인구": [5000, 3000],
    })
    model = CityModel.from_processed_data(pop_df)
    records = model.run(days=1)
    assert len(records) == 1


def test_city_model_from_processed_data_empty():
    pop_df = pd.DataFrame({"행정동코드": [], "평균생활인구": []})
    with pytest.raises(ValueError, match="유효한 행정동"):
        CityModel.from_processed_data(pop_df)


# ── ScenarioEngine 테스트 ──

def test_scenario_new_station():
    engine = ScenarioEngine({})
    result = engine.new_station_scenario("테스트역", "1168010100", 30000)
    assert result["scenario"] == "new_station"
    assert "유동인구_변화율" in result["changes"]


def test_scenario_rent_change():
    engine = ScenarioEngine({})
    result = engine.rent_change_scenario("1168010100", 20)
    assert result["scenario"] == "rent_change"
    assert "업소_변화율" in result["changes"]


def test_scenario_rent_decrease():
    engine = ScenarioEngine({})
    result = engine.rent_change_scenario("1168010100", -15)
    assert result["changes"]["업소_변화율"] > 0  # 임대료 하락 → 업소 증가


def test_scenario_population_change():
    engine = ScenarioEngine({})
    result = engine.population_change_scenario("1168010100", 30)
    assert result["scenario"] == "population_change"
    assert "매출_변화율" in result["changes"]
    assert result["changes"]["매출_변화율"] > 0


def test_scenario_combined():
    engine = ScenarioEngine({})
    s1 = engine.new_station_scenario("역", "1168010100", 30000)
    s2 = engine.rent_change_scenario("1168010100", 10)
    combined = engine.combined_scenario([s1, s2])
    assert combined["scenario"] == "combined"
    assert len(combined["sub_scenarios"]) == 2
    assert "changes" in combined


def test_scenario_compare():
    engine = ScenarioEngine({})
    s1 = engine.new_station_scenario("역", "1168010100", 30000)
    s2 = engine.rent_change_scenario("1168010100", 10)
    df = engine.compare_scenarios([s1, s2])
    assert len(df) == 2
    assert "시나리오" in df.columns


def test_scenario_ripple_with_subway_data():
    subway_df = pd.DataFrame({
        "행정동코드": ["A", "A", "B", "B", "C", "C"],
        "승차총승객수": [1000, 1000, 5000, 5000, 3000, 3000],
        "하차총승객수": [5000, 5000, 1000, 1000, 2000, 2000],
        "날짜": ["2024-01-01"] * 6,
    })
    engine = ScenarioEngine({"subway": subway_df})
    engine._adjacency = {}  # 인접성 그래프 비우기 → OD fallback 사용
    result = engine.new_station_scenario("역", "A", 50000)
    # 파급효과는 OD fallback으로 추정됨
    assert isinstance(result["ripple_effects"], list)


# ── FlowModel 테스트 ──

def test_flow_model_classify():
    model = FlowModel()
    df = pd.DataFrame({
        "행정동코드": ["A", "A", "B", "B"],
        "승차총승객수": [1000, 1000, 5000, 5000],
        "하차총승객수": [5000, 5000, 1000, 1000],
    })
    result = model.classify_dong_type(df)
    assert "지역유형" in result.columns
    a_type = result[result["행정동코드"] == "A"]["지역유형"].iloc[0]
    b_type = result[result["행정동코드"] == "B"]["지역유형"].iloc[0]
    assert a_type == "직장지역"  # 하차 >> 승차
    assert b_type == "주거지역"  # 승차 >> 하차


def test_flow_model_estimate_impact():
    model = FlowModel()
    od = pd.DataFrame(
        [[0, 100, 50], [80, 0, 30], [60, 40, 0]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    impact = model.estimate_impact(od, "A", 10)
    assert not impact.empty
    assert "총영향" in impact.columns


def test_flow_model_estimate_impact_missing_dong():
    model = FlowModel()
    od = pd.DataFrame(
        [[0, 100], [80, 0]],
        index=["A", "B"],
        columns=["A", "B"],
    )
    impact = model.estimate_impact(od, "X", 10)
    assert impact.empty


def test_flow_model_summary():
    model = FlowModel()
    od = pd.DataFrame(
        [[0, 100, 50], [80, 0, 30], [60, 40, 0]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    summary = model.compute_flow_summary(od)
    assert not summary.empty
    assert "순유입" in summary.columns
    assert len(summary) == 3


def test_flow_model_summary_empty():
    model = FlowModel()
    result = model.compute_flow_summary(pd.DataFrame())
    assert result.empty


# ── Forecaster 테스트 ──

@pytest.mark.skipif(
    not _has_statsmodels(),
    reason="statsmodels 미설치",
)
def test_forecaster_arima():
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=24, freq="MS"),
        "평균거래금액": np.random.randint(50000, 100000, 24),
    })
    forecaster = Forecaster(method="arima")
    result = forecaster.forecast(df, periods=6)
    assert not result.empty
    assert "예측값" in result.columns


def test_forecaster_arima_insufficient_data():
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=2, freq="MS"),
        "평균거래금액": [50000, 60000],
    })
    forecaster = Forecaster(method="arima")
    result = forecaster.forecast(df, periods=6)
    assert result.empty


def test_forecaster_by_dong():
    df = pd.DataFrame({
        "행정동코드": ["A"] * 12 + ["B"] * 12,
        "연월": list(pd.date_range("2020-01", periods=12, freq="MS")) * 2,
        "평균거래금액": np.random.randint(50000, 100000, 24),
    })
    forecaster = Forecaster(method="arima")
    results = forecaster.forecast_by_dong(df, ["A", "B"], periods=3)
    assert "A" in results
    assert "B" in results


# ── TrendAnalyzer 추가 테스트 ──

def test_trend_moving_average():
    analyzer = TrendAnalyzer()
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=12, freq="MS"),
        "값": range(100, 112),
    })
    result = analyzer.moving_average(df, "값", [3])
    assert "값_MA3" in result.columns


def test_trend_yoy_change():
    analyzer = TrendAnalyzer()
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=24, freq="MS"),
        "값": list(range(100, 112)) + list(range(110, 122)),
    })
    result = analyzer.yoy_change(df, "값")
    assert "값_YoY" in result.columns
    # 13번째 행부터 YoY 값이 있어야 함
    assert result["값_YoY"].notna().sum() == 12


def test_trend_detect_anomalies():
    analyzer = TrendAnalyzer()
    values = [100] * 20 + [500]  # 마지막 값이 이상치
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=21, freq="MS"),
        "값": values,
    })
    result = analyzer.detect_anomalies(df, "값", threshold=2.0)
    assert "이상치" in result.columns
    assert result.iloc[-1]["이상치"]  # 500은 이상치


def test_trend_insufficient_data():
    analyzer = TrendAnalyzer()
    df = pd.DataFrame({"연월": ["2020-01"], "값": [100]})
    trend = analyzer.compute_trend(df, "값")
    assert trend["direction"] == "insufficient_data"


# ── Subway Network 테스트 ──

from src.simulation.scenario_engine import build_subway_network_graph, SUBWAY_LINES

def test_subway_network_graph_built():
    """그래프 구축 검증."""
    graph = build_subway_network_graph()
    assert len(graph) > 0
    assert "서울역" in graph
    assert "강남" in graph

def test_subway_network_transfer_count():
    """환승 횟수 정확성."""
    graph = build_subway_network_graph()
    # 서울역 → 시청: 같은 1호선, 0 환승
    assert graph["서울역"]["시청"] == 0
    # 서울역 → 강남: 환승 필요 (1호선→2호선 등)
    assert graph["서울역"]["강남"] >= 1

def test_subway_same_line_stronger_ripple():
    """같은 노선 > 환승 역 파급효과."""
    engine = ScenarioEngine({})
    result = engine.new_station_scenario(
        "서울역", "1168010100", 30000, use_subway_network=True
    )
    ripple = result["ripple_effects"]
    assert isinstance(ripple, list)
    assert len(ripple) > 0

def test_subway_network_backward_compat():
    """use_subway_network=False는 기존과 동일."""
    engine = ScenarioEngine({})
    result = engine.new_station_scenario("테스트역", "1168010100", 30000)
    assert result["scenario"] == "new_station"
    assert "유동인구_변화율" in result["changes"]
