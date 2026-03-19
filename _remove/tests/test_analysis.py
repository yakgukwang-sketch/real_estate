"""분석 모듈 테스트."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.analysis.correlation import CorrelationAnalyzer
from src.analysis.clustering import DongClusterer
from src.analysis.scoring import CommercialScorer
from src.analysis.trend_analysis import TrendAnalyzer
from src.processors.geo_processor import assign_grid_cell, GeoProcessor


@pytest.fixture
def sample_df():
    np.random.seed(42)
    n = 100
    return pd.DataFrame({
        "행정동코드": [f"116805{i:04d}" for i in range(n)],
        "하차총승객수": np.random.randint(1000, 100000, n),
        "평균거래금액": np.random.randint(30000, 200000, n),
        "업소수": np.random.randint(50, 2000, n),
        "평균생활인구": np.random.randint(5000, 50000, n),
        "추정매출": np.random.randint(1000000, 100000000, n),
    })


def test_correlation_matrix(sample_df):
    analyzer = CorrelationAnalyzer()
    corr = analyzer.compute_correlation_matrix(sample_df)
    assert not corr.empty
    assert corr.shape[0] == corr.shape[1]


def test_pairwise_significance(sample_df):
    analyzer = CorrelationAnalyzer()
    result = analyzer.pairwise_significance(sample_df, "하차총승객수", "업소수")
    assert "r" in result
    assert "p_value" in result


def test_clustering(sample_df):
    clusterer = DongClusterer(n_clusters=3)
    result = clusterer.fit_predict(sample_df)
    assert "클러스터" in result.columns
    assert result["클러스터"].nunique() == 3


def test_scoring(sample_df):
    scorer = CommercialScorer()
    result = scorer.compute_scores(sample_df)
    assert "상권활성도" in result.columns
    assert "상권등급" in result.columns
    assert result["상권활성도"].min() >= 0
    assert result["상권활성도"].max() <= 100


def test_trend_analysis():
    analyzer = TrendAnalyzer()
    df = pd.DataFrame({
        "연월": pd.date_range("2020-01", periods=24, freq="MS"),
        "값": range(100, 124),
    })
    trend = analyzer.compute_trend(df, "값", "연월")
    assert trend["direction"] == "상승"
    assert trend["slope"] > 0


# ── Grid 테스트 ──

def test_grid_cell_deterministic():
    """같은 좌표는 항상 같은 셀 ID."""
    cell1 = assign_grid_cell(37.5, 127.0)
    cell2 = assign_grid_cell(37.5, 127.0)
    assert cell1 == cell2

def test_grid_cell_different_locations():
    """멀리 떨어진 좌표는 다른 셀."""
    cell1 = assign_grid_cell(37.5, 127.0)
    cell2 = assign_grid_cell(37.6, 127.1)
    assert cell1 != cell2

def test_grid_cell_same_cell():
    """가까운 좌표는 같은 셀 (500m 해상도)."""
    cell1 = assign_grid_cell(37.5000, 127.0000)
    cell2 = assign_grid_cell(37.5001, 127.0001)
    assert cell1 == cell2

def test_grid_cell_resolution_change():
    """해상도 변경 시 다른 셀 ID."""
    cell_500 = assign_grid_cell(37.5, 127.0, resolution_m=500)
    cell_1000 = assign_grid_cell(37.5, 127.0, resolution_m=1000)
    assert cell_500 != cell_1000

def test_grid_batch_processing():
    """배치 처리로 grid_id 컬럼 추가."""
    df = pd.DataFrame({
        "위도": [37.5, 37.6, 37.7],
        "경도": [127.0, 127.1, 127.2],
    })
    geo = GeoProcessor.__new__(GeoProcessor)  # skip __init__ to avoid loading geo files
    result = GeoProcessor.assign_grid_cells_batch(geo, df)
    assert "grid_id" in result.columns
    assert len(result) == 3
    assert all(result["grid_id"].str.startswith("grid_"))


# ── Scoring type_aware 테스트 ──

def test_scoring_type_aware(sample_df):
    """type_aware=True 스코어 산출."""
    sample_df["대분류수"] = np.random.randint(1, 10, len(sample_df))
    scorer = CommercialScorer()
    result = scorer.compute_scores(sample_df, type_aware=True)
    assert "상권활성도" in result.columns
    assert result["상권활성도"].min() >= 0
    assert result["상권활성도"].max() <= 100

def test_scoring_type_aware_backward_compat(sample_df):
    """type_aware=False는 기존과 동일."""
    scorer = CommercialScorer()
    result_old = scorer.compute_scores(sample_df)
    result_new = scorer.compute_scores(sample_df, type_aware=False)
    pd.testing.assert_frame_equal(result_old, result_new)

def test_classify_commercial_type():
    """상권 유형 분류."""
    scorer = CommercialScorer()
    df = pd.DataFrame({
        "하차총승객수": [9000, 6000, 2000, 5000],
        "평균생활인구": [1000, 4000, 8000, 5000],
        "추정매출": [100, 100, 100, 100],
    })
    types = scorer.classify_commercial_type(df)
    assert types.iloc[0] == "관광형"   # 9000/(9000+1000) = 0.9
    assert types.iloc[2] == "주거형"   # 2000/(2000+8000) = 0.2
    assert types.iloc[3] == "혼합형"   # 5000/(5000+5000) = 0.5

def test_scoring_high_rent_burden_low_score():
    """높은 임대료부담 → 낮은 점수."""
    scorer = CommercialScorer()
    df = pd.DataFrame({
        "행정동코드": ["A", "B"],
        "하차총승객수": [50000, 50000],
        "추정매출": [1000, 1000000],  # A: 매출 낮음 → 부담 높음
        "업소수": [500, 500],
        "평균거래금액": [100000, 100000],  # 같은 가격
        "평균생활인구": [20000, 20000],
        "대분류수": [5, 5],
    })
    result = scorer.compute_scores(df, type_aware=True)
    # A has higher rent burden (high price / low sales) → lower score
    score_a = result[result["행정동코드"] == "A"]["상권활성도"].iloc[0]
    score_b = result[result["행정동코드"] == "B"]["상권활성도"].iloc[0]
    assert score_b > score_a
