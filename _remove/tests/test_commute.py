"""출퇴근 유동 분석 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.analysis.commute_analyzer import CommuteAnalyzer


@pytest.fixture
def population_hourly():
    """시간대별 생활인구 샘플."""
    rows = []
    # 직장밀집 동: 주간 인구 >> 야간 인구
    for hour in range(24):
        if 0 <= hour <= 6:
            pop = 5000
        elif 7 <= hour <= 9:
            pop = 15000  # 출근 유입
        elif 10 <= hour <= 17:
            pop = 25000  # 주간 활동
        elif 18 <= hour <= 20:
            pop = 12000  # 퇴근 유출
        else:
            pop = 6000
        rows.append({"행정동코드": "WORK_DONG", "시간대": hour, "총생활인구": pop})

    # 주거밀집 동: 야간 인구 >> 주간 인구
    for hour in range(24):
        if 0 <= hour <= 6:
            pop = 30000
        elif 7 <= hour <= 9:
            pop = 20000  # 출근 유출
        elif 10 <= hour <= 17:
            pop = 12000  # 주간 감소
        elif 18 <= hour <= 20:
            pop = 22000  # 퇴근 유입
        else:
            pop = 28000
        rows.append({"행정동코드": "HOME_DONG", "시간대": hour, "총생활인구": pop})

    return pd.DataFrame(rows)


@pytest.fixture
def commercial_df():
    """상가 업종 샘플."""
    return pd.DataFrame({
        "행정동코드": ["A"] * 5 + ["B"] * 5,
        "대분류명": [
            "정보통신", "금융·보험", "음식", "교육", "제조",
            "음식", "음식", "교육", "교육", "예술·스포츠·여가",
        ],
    })


def test_analyze_hourly_flow(population_hourly):
    analyzer = CommuteAnalyzer()
    result = analyzer.analyze_hourly_flow(population_hourly)

    assert not result.empty
    assert "주간유입률" in result.columns
    assert "지역유형" in result.columns

    work = result[result["행정동코드"] == "WORK_DONG"].iloc[0]
    home = result[result["행정동코드"] == "HOME_DONG"].iloc[0]

    assert work["주간유입률"] > 0  # 직장밀집
    assert home["주간유입률"] < 0  # 주거밀집
    assert "직장" in work["지역유형"]
    assert "주거" in home["지역유형"]


def test_analyze_hourly_flow_missing_columns():
    analyzer = CommuteAnalyzer()
    result = analyzer.analyze_hourly_flow(pd.DataFrame({"x": [1]}))
    assert result.empty


def test_classify_destination_types(commercial_df):
    analyzer = CommuteAnalyzer()
    result = analyzer.classify_destination_types(commercial_df)

    assert not result.empty
    assert "주요목적지" in result.columns
    assert "총업소수" in result.columns

    a_row = result[result["행정동코드"] == "A"].iloc[0]
    b_row = result[result["행정동코드"] == "B"].iloc[0]
    assert a_row["주요목적지"] == "직장"
    assert b_row["주요목적지"] in ("소비·여가", "학교·학원")


def test_classify_empty():
    analyzer = CommuteAnalyzer()
    result = analyzer.classify_destination_types(pd.DataFrame({"x": [1]}))
    assert result.empty


def test_estimate_commute_od(population_hourly):
    analyzer = CommuteAnalyzer()
    subway_df = pd.DataFrame({
        "행정동코드": ["WORK_DONG", "HOME_DONG"],
        "승차총승객수": [5000, 20000],
        "하차총승객수": [20000, 5000],
    })
    result = analyzer.estimate_commute_od(population_hourly, subway_df)

    assert not result.empty
    assert "교통순유입" in result.columns

    work = result[result["행정동코드"] == "WORK_DONG"].iloc[0]
    assert work["교통순유입"] > 0  # 지하철 하차 > 승차


def test_build_commute_matrix(population_hourly, commercial_df):
    analyzer = CommuteAnalyzer()
    result = analyzer.build_commute_matrix(population_hourly, commercial_df)

    assert "flow" in result
    assert "summary" in result
    assert result["summary"]["직장밀집_동수"] >= 1
    assert result["summary"]["주거밀집_동수"] >= 1
