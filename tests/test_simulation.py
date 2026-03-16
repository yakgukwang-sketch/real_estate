"""시뮬레이션 모듈 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.simulation.agent_model import CityModel
from src.simulation.scenario_engine import ScenarioEngine
from src.simulation.flow_model import FlowModel


def test_city_model_runs():
    pop = {"동A": 10000, "동B": 20000}
    emp = {"동A": 30000, "동B": 15000}
    model = CityModel(pop, emp)
    records = model.run(days=3)
    assert len(records) == 3
    summary = model.get_summary()
    assert len(summary) > 0


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


def test_flow_model_classify():
    model = FlowModel()
    df = pd.DataFrame({
        "행정동코드": ["A", "A", "B", "B"],
        "승차총승객수": [1000, 1000, 5000, 5000],
        "하차총승객수": [5000, 5000, 1000, 1000],
    })
    result = model.classify_dong_type(df)
    assert "지역유형" in result.columns
