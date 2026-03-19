"""소비력 분석 모듈 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd

from src.simulation.spending_power import (
    HOUSING_PROFILES,
    SpendingPowerCalculator,
)


SAMPLE_DATA = {
    "테스트동A": {"아파트": 1000, "빌라": 500, "오피스텔": 300, "단독주택": 200},
    "테스트동B": {"아파트": 500, "빌라": 1000, "오피스텔": 200, "단독주택": 100},
}


@pytest.fixture
def calc():
    return SpendingPowerCalculator(housing_data=SAMPLE_DATA)


@pytest.fixture
def default_calc():
    return SpendingPowerCalculator()


# ── calculate() 테스트 ──

def test_calculate_returns_dataframe(calc):
    df = calc.calculate()
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"동", "유형", "세대수", "세대원수", "월소비력"}


def test_calculate_row_count(calc):
    df = calc.calculate()
    # 2동 × 4유형 = 8행
    assert len(df) == 8


def test_calculate_spending_formula(calc):
    df = calc.calculate()
    # 테스트동A 아파트: 1000세대 × 4,500,000 = 4,500,000,000
    row = df[(df["동"] == "테스트동A") & (df["유형"] == "아파트")].iloc[0]
    assert row["세대수"] == 1000
    assert row["월소비력"] == 1000 * HOUSING_PROFILES["아파트"].monthly_spend


def test_calculate_members_formula(calc):
    df = calc.calculate()
    row = df[(df["동"] == "테스트동B") & (df["빌라" == df["유형"]])] if False else \
        df[(df["동"] == "테스트동B") & (df["유형"] == "빌라")].iloc[0]
    assert row["세대원수"] == round(1000 * HOUSING_PROFILES["빌라"].avg_members)


# ── get_summary() 테스트 ──

def test_summary_columns(calc):
    summary = calc.get_summary()
    expected = {"동", "총세대수", "총인구", "총소비력", "주요주거유형", "1인당소비"}
    assert set(summary.columns) == expected


def test_summary_sorted_descending(calc):
    summary = calc.get_summary()
    spending_vals = summary["총소비력"].tolist()
    assert spending_vals == sorted(spending_vals, reverse=True)


def test_summary_main_housing_type(calc):
    summary = calc.get_summary()
    # 테스트동A: 아파트 1000이 최대 → 주요주거유형 = "아파트"
    row_a = summary[summary["동"] == "테스트동A"].iloc[0]
    assert row_a["주요주거유형"] == "아파트"
    # 테스트동B: 빌라 1000이 최대 → 주요주거유형 = "빌라"
    row_b = summary[summary["동"] == "테스트동B"].iloc[0]
    assert row_b["주요주거유형"] == "빌라"


def test_summary_total_units(calc):
    summary = calc.get_summary()
    row = summary[summary["동"] == "테스트동A"].iloc[0]
    assert row["총세대수"] == 1000 + 500 + 300 + 200


# ── simulate_change() 테스트 ──

def test_simulate_increase(calc):
    result = calc.simulate_change("테스트동A", "아파트", 500)
    assert result["변화량"]["세대수"] == 500
    assert result["변화량"]["월소비력"] == 500 * HOUSING_PROFILES["아파트"].monthly_spend
    assert result["after"]["세대수"] == 1500


def test_simulate_decrease(calc):
    result = calc.simulate_change("테스트동A", "오피스텔", -100)
    assert result["변화량"]["세대수"] == -100
    assert result["after"]["세대수"] == 200


def test_simulate_decrease_floor_zero(calc):
    """세대수가 음수가 되지 않도록 0에서 멈추는지 확인."""
    result = calc.simulate_change("테스트동A", "단독주택", -9999)
    assert result["after"]["세대수"] == 0
    assert result["변화량"]["세대수"] == -200  # 원래 200에서 0으로


def test_simulate_invalid_type(calc):
    result = calc.simulate_change("테스트동A", "존재않는유형", 100)
    assert "error" in result


def test_simulate_dong_total_changes(calc):
    result = calc.simulate_change("테스트동A", "아파트", 100)
    assert result["after"]["동_총소비력"] > result["before"]["동_총소비력"]
    diff = result["after"]["동_총소비력"] - result["before"]["동_총소비력"]
    assert diff == 100 * HOUSING_PROFILES["아파트"].monthly_spend


# ── get_dong_detail() 테스트 ──

def test_dong_detail_structure(calc):
    detail = calc.get_dong_detail("테스트동A")
    assert detail["dong"] == "테스트동A"
    assert isinstance(detail["detail"], pd.DataFrame)
    assert "총세대수" in detail["total"]
    assert "총소비력" in detail["total"]


def test_dong_detail_ratio_sums_100(calc):
    detail = calc.get_dong_detail("테스트동A")
    ratio_sum = detail["detail"]["비율"].sum()
    assert abs(ratio_sum - 100.0) < 0.5  # 반올림 오차 허용


def test_dong_detail_missing_dong(calc):
    detail = calc.get_dong_detail("존재않는동")
    assert detail["total"]["총세대수"] == 0


# ── 커스텀 데이터 주입 테스트 ──

def test_custom_data_injection():
    custom = {"커스텀동": {"아파트": 100, "빌라": 50}}
    calc = SpendingPowerCalculator(housing_data=custom)
    summary = calc.get_summary()
    assert len(summary) == 1
    assert summary.iloc[0]["동"] == "커스텀동"


# ── 기본 데이터(41개 동) 테스트 ──

def test_default_data_covers_all_dongs(default_calc):
    summary = default_calc.get_summary()
    assert len(summary) == 41
