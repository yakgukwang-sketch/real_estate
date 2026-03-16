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
