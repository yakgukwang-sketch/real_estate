"""교차 상관분석 - 지하철/부동산/상권/인구 데이터 간 상관관계."""

import logging

import pandas as pd
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """행정동 단위로 통합된 데이터의 교차 상관분석."""

    def compute_correlation_matrix(self, integrated_df: pd.DataFrame) -> pd.DataFrame:
        """통합 데이터의 상관행렬 계산.

        Args:
            integrated_df: 행정동코드 + 연월 + 각 지표 컬럼이 있는 통합 DataFrame
        """
        numeric_cols = integrated_df.select_dtypes(include=[np.number]).columns.tolist()
        # 행정동코드 등 식별자 제외
        exclude = {"행정동코드"}
        numeric_cols = [c for c in numeric_cols if c not in exclude]

        return integrated_df[numeric_cols].corr()

    def pairwise_significance(
        self, integrated_df: pd.DataFrame, col_a: str, col_b: str
    ) -> dict:
        """두 변수 간 상관관계 통계적 유의성 검정."""
        valid = integrated_df[[col_a, col_b]].dropna()
        if len(valid) < 3:
            return {"r": None, "p_value": None, "n": len(valid), "significant": False}

        r, p = stats.pearsonr(valid[col_a], valid[col_b])
        return {
            "r": round(r, 4),
            "p_value": round(p, 6),
            "n": len(valid),
            "significant": p < 0.05,
        }

    def top_correlations(
        self, integrated_df: pd.DataFrame, target_col: str, top_n: int = 10
    ) -> pd.DataFrame:
        """특정 변수와 가장 높은 상관관계를 가진 변수 목록."""
        corr_matrix = self.compute_correlation_matrix(integrated_df)
        if target_col not in corr_matrix.columns:
            return pd.DataFrame()

        correlations = corr_matrix[target_col].drop(target_col, errors="ignore")
        top = correlations.abs().nlargest(top_n)
        result = pd.DataFrame({
            "변수": top.index,
            "상관계수": correlations[top.index].values,
            "절대값": top.values,
        })
        return result

    def lagged_correlation(
        self,
        df: pd.DataFrame,
        col_a: str,
        col_b: str,
        dong_code: str,
        max_lag: int = 6,
    ) -> pd.DataFrame:
        """시차 상관분석 - A가 B에 선행하는지 확인.

        예: 지하철 유동인구가 N개월 후 부동산 가격에 영향을 미치는지
        """
        dong_df = df[df["행정동코드"] == dong_code].sort_values("연월")
        results = []

        for lag in range(-max_lag, max_lag + 1):
            shifted_b = dong_df[col_b].shift(-lag)
            valid = pd.DataFrame({col_a: dong_df[col_a], f"{col_b}_lag": shifted_b}).dropna()
            if len(valid) < 3:
                continue
            r, p = stats.pearsonr(valid[col_a], valid[f"{col_b}_lag"])
            results.append({"lag": lag, "r": r, "p_value": p})

        return pd.DataFrame(results)
