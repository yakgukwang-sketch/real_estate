"""시계열 트렌드 분석."""

import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """시계열 데이터의 트렌드 분석."""

    def compute_trend(self, df: pd.DataFrame, value_col: str, time_col: str = "연월") -> dict:
        """선형 추세 분석.

        Returns:
            slope, intercept, r_squared, p_value, direction
        """
        sorted_df = df.sort_values(time_col).dropna(subset=[value_col])
        if len(sorted_df) < 3:
            return {"slope": 0, "direction": "insufficient_data"}

        x = np.arange(len(sorted_df))
        y = sorted_df[value_col].values
        slope, intercept, r, p, se = stats.linregress(x, y)

        direction = "상승" if slope > 0 else "하락" if slope < 0 else "보합"
        return {
            "slope": round(slope, 4),
            "intercept": round(intercept, 4),
            "r_squared": round(r ** 2, 4),
            "p_value": round(p, 6),
            "direction": direction,
            "monthly_change_pct": round(slope / max(abs(intercept), 1) * 100, 2),
        }

    def moving_average(
        self, df: pd.DataFrame, value_col: str, windows: list[int] | None = None
    ) -> pd.DataFrame:
        """이동평균 계산."""
        windows = windows or [3, 6, 12]
        result = df.copy()
        for w in windows:
            result[f"{value_col}_MA{w}"] = result[value_col].rolling(window=w, min_periods=1).mean()
        return result

    def yoy_change(self, df: pd.DataFrame, value_col: str, time_col: str = "연월") -> pd.DataFrame:
        """전년 동월 대비 변화율."""
        result = df.sort_values(time_col).copy()
        result[f"{value_col}_전년동월"] = result[value_col].shift(12)
        result[f"{value_col}_YoY"] = (
            (result[value_col] - result[f"{value_col}_전년동월"])
            / result[f"{value_col}_전년동월"]
            * 100
        ).round(2)
        return result

    def detect_anomalies(
        self, df: pd.DataFrame, value_col: str, threshold: float = 2.0
    ) -> pd.DataFrame:
        """이상치 탐지 (Z-score 기반)."""
        result = df.copy()
        values = result[value_col].dropna()
        if len(values) < 5:
            result["이상치"] = False
            return result

        mean, std = values.mean(), values.std()
        if std == 0:
            result["이상치"] = False
            return result

        result["z_score"] = ((result[value_col] - mean) / std).abs()
        result["이상치"] = result["z_score"] > threshold
        return result
