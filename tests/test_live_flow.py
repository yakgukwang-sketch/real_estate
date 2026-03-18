"""실시간 스냅샷 유동 분석 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import pytest

from src.analysis.live_flow_analyzer import LiveFlowAnalyzer
from src.collectors.live_snapshot_collector import LiveSnapshotCollector


@pytest.fixture
def snapshots_df():
    """82개 장소 중 3곳의 시간대별 스냅샷 샘플."""
    rows = []
    for hour in range(24):
        # 강남역: 오피스 패턴 (주간 >> 야간)
        if 0 <= hour <= 6:
            pop = 5000
        elif 10 <= hour <= 17:
            pop = 80000
        else:
            pop = 30000
        rows.append({
            "장소명": "강남역", "수집시간": hour, "추정인구": pop,
            "수집날짜": "2024-03-11", "수집시각": f"2024-03-11T{hour:02d}:00:00",
            "혼잡도": "보통" if pop < 50000 else "붐빔",
        })

        # 잠실: 주거 패턴 (야간 >> 주간)
        if 0 <= hour <= 6:
            pop = 60000
        elif 10 <= hour <= 17:
            pop = 25000
        else:
            pop = 45000
        rows.append({
            "장소명": "잠실 관광특구", "수집시간": hour, "추정인구": pop,
            "수집날짜": "2024-03-11", "수집시각": f"2024-03-11T{hour:02d}:00:00",
            "혼잡도": "보통",
        })

        # 홍대: 상권 패턴 (저녁 피크)
        if 0 <= hour <= 6:
            pop = 10000
        elif 10 <= hour <= 14:
            pop = 40000
        elif 15 <= hour <= 21:
            pop = 70000
        else:
            pop = 35000
        rows.append({
            "장소명": "홍대 관광특구", "수집시간": hour, "추정인구": pop,
            "수집날짜": "2024-03-11", "수집시각": f"2024-03-11T{hour:02d}:00:00",
            "혼잡도": "약간 붐빔" if pop > 50000 else "보통",
        })

    return pd.DataFrame(rows)


def test_build_hourly_profile(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    profile = analyzer.build_hourly_profile(snapshots_df)
    assert not profile.empty
    assert "추정인구" in profile.columns
    assert len(profile["장소명"].unique()) == 3


def test_build_hourly_pivot(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    pivot = analyzer.build_hourly_pivot(snapshots_df)
    assert not pivot.empty
    assert pivot.shape[0] == 3  # 3개 장소
    assert pivot.shape[1] == 24  # 24시간


def test_classify_area_function(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    result = analyzer.classify_area_function(snapshots_df)
    assert not result.empty
    assert "장소기능" in result.columns
    assert "주야비율" in result.columns

    gangnam = result[result["장소명"] == "강남역"].iloc[0]
    assert gangnam["주야비율"] > 2.0  # 주간 >> 야간 → 오피스


def test_classify_empty():
    analyzer = LiveFlowAnalyzer()
    result = analyzer.classify_area_function(pd.DataFrame())
    assert result.empty


def test_detect_flow_direction(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    result = analyzer.detect_flow_direction(snapshots_df)
    assert not result.empty
    assert "최대유입시간" in result.columns
    assert "오전유입량" in result.columns
    assert "출퇴근패턴" in result.columns

    gangnam = result[result["장소명"] == "강남역"].iloc[0]
    assert gangnam["오전유입량"] > 0  # 오전에 유입


def test_compare_weekday_weekend(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    # 모든 데이터가 월요일(평일)이므로 주말 데이터가 없어 비교 제한적
    result = analyzer.compare_weekday_weekend(snapshots_df)
    assert not result.empty


def test_get_area_detail(snapshots_df):
    analyzer = LiveFlowAnalyzer()
    detail = analyzer.get_area_detail(snapshots_df, "강남역")
    assert detail["장소명"] == "강남역"
    assert not detail["시간대별"].empty
    assert detail["총스냅샷수"] == 24
    assert "혼잡도분포" in detail


def test_get_area_detail_missing():
    analyzer = LiveFlowAnalyzer()
    detail = analyzer.get_area_detail(pd.DataFrame(), "없는장소")
    assert detail == {}


def test_snapshot_collector_init(tmp_path):
    collector = LiveSnapshotCollector(snapshot_dir=tmp_path / "test_snapshots")
    assert collector.get_snapshot_count() == 0
    assert collector.load_all_snapshots().empty
    assert collector.get_snapshot_dates() == []
