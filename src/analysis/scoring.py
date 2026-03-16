"""상권 활성도 스코어링."""

import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)


class CommercialScorer:
    """행정동별 상권 활성도 종합 점수 산출."""

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        "유동인구": 0.25,
        "매출": 0.25,
        "업소밀도": 0.15,
        "부동산가격": 0.10,
        "생활인구": 0.15,
        "업종다양성": 0.10,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.scaler = MinMaxScaler()

    def compute_scores(
        self,
        integrated_df: pd.DataFrame,
        column_mapping: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """종합 상권 활성도 점수 산출.

        Args:
            integrated_df: 행정동별 통합 데이터
            column_mapping: 가중치 키 → 실제 컬럼명 매핑
        """
        if column_mapping is None:
            column_mapping = {
                "유동인구": "하차총승객수",
                "매출": "추정매출",
                "업소밀도": "업소수",
                "부동산가격": "평균거래금액",
                "생활인구": "평균생활인구",
                "업종다양성": "대분류수",
            }

        df = integrated_df.copy()
        available = {k: v for k, v in column_mapping.items() if v in df.columns}

        if not available:
            logger.warning("스코어링에 사용할 컬럼 없음")
            df["상권활성도"] = 0
            return df

        # 각 지표 정규화 (0~1)
        score_cols = []
        for weight_key, col_name in available.items():
            score_col = f"{weight_key}_점수"
            values = df[[col_name]].fillna(0)
            if values[col_name].std() > 0:
                df[score_col] = MinMaxScaler().fit_transform(values)
            else:
                df[score_col] = 0
            score_cols.append((score_col, self.weights.get(weight_key, 0.1)))

        # 가중합
        total_weight = sum(w for _, w in score_cols)
        df["상권활성도"] = sum(
            df[col] * (w / total_weight) for col, w in score_cols
        )
        df["상권활성도"] = (df["상권활성도"] * 100).round(1)

        # 등급
        df["상권등급"] = pd.cut(
            df["상권활성도"],
            bins=[0, 20, 40, 60, 80, 100],
            labels=["E", "D", "C", "B", "A"],
            include_lowest=True,
        )

        return df

    def rank_dongs(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """상권 활성도 상위 행정동."""
        if "상권활성도" not in df.columns:
            return pd.DataFrame()
        cols = ["행정동코드", "행정동명", "상권활성도", "상권등급"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].nlargest(top_n, "상권활성도").reset_index(drop=True)
