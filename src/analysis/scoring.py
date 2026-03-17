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

    WEIGHTS_BY_TYPE = {
        "관광형": {
            "유동인구": 0.30, "매출": 0.15, "업소밀도": 0.10,
            "생활인구": 0.10, "업종다양성": 0.25, "임대료부담": -0.10,
        },
        "오피스형": {
            "유동인구": 0.20, "매출": 0.30, "업소밀도": 0.15,
            "생활인구": 0.10, "업종다양성": 0.10, "임대료부담": -0.15,
        },
        "주거형": {
            "유동인구": 0.10, "매출": 0.15, "업소밀도": 0.15,
            "생활인구": 0.30, "업종다양성": 0.10, "임대료부담": -0.20,
        },
        "유흥형": {
            "유동인구": 0.25, "매출": 0.25, "업소밀도": 0.15,
            "생활인구": 0.05, "업종다양성": 0.15, "임대료부담": -0.15,
        },
        "혼합형": {
            "유동인구": 0.20, "매출": 0.20, "업소밀도": 0.15,
            "생활인구": 0.15, "업종다양성": 0.15, "임대료부담": -0.15,
        },
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.scaler = MinMaxScaler()

    def classify_commercial_type(
        self,
        df: pd.DataFrame,
        column_mapping: dict[str, str] | None = None,
    ) -> pd.Series:
        """상권 유형 분류 (유동인구 비율 기반).

        Returns:
            "관광형"/"오피스형"/"주거형"/"유흥형"/"혼합형" Series
        """
        if column_mapping is None:
            column_mapping = {
                "유동인구": "하차총승객수",
                "생활인구": "평균생활인구",
                "매출": "추정매출",
            }

        float_col = column_mapping.get("유동인구", "하차총승객수")
        resident_col = column_mapping.get("생활인구", "평균생활인구")

        result = pd.Series("혼합형", index=df.index)

        if float_col in df.columns and resident_col in df.columns:
            total = df[float_col].fillna(0) + df[resident_col].fillna(0)
            ratio = df[float_col].fillna(0) / total.replace(0, np.nan)

            result = result.where(ratio.isna(), result)  # keep 혼합형 for NaN
            result = result.where(~(ratio > 0.7), "관광형")
            result = result.where(~((ratio > 0.5) & (ratio <= 0.7)), "오피스형")
            result = result.where(~(ratio < 0.3), "주거형")

        return result

    def compute_scores(
        self,
        integrated_df: pd.DataFrame,
        column_mapping: dict[str, str] | None = None,
        type_aware: bool = False,
    ) -> pd.DataFrame:
        """종합 상권 활성도 점수 산출.

        Args:
            integrated_df: 행정동별 통합 데이터
            column_mapping: 가중치 키 → 실제 컬럼명 매핑
            type_aware: True이면 상권 유형별 가중치 + 임대료부담지수 적용
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
        score_col_to_key = {}
        for weight_key, col_name in available.items():
            score_col = f"{weight_key}_점수"
            score_col_to_key[score_col] = weight_key
            values = df[[col_name]].fillna(0)
            if values[col_name].std() > 0:
                df[score_col] = MinMaxScaler().fit_transform(values)
            else:
                df[score_col] = 0
            score_cols.append((score_col, self.weights.get(weight_key, 0.1)))

        if type_aware:
            # 임대료부담지수 계산
            sales_col = column_mapping.get("매출", "추정매출")
            price_col = column_mapping.get("부동산가격", "평균거래금액")
            if sales_col in df.columns and price_col in df.columns:
                rent_burden = df[price_col].fillna(0) / df[sales_col].replace(0, np.nan).fillna(1)
                rb_scaled = MinMaxScaler().fit_transform(rent_burden.values.reshape(-1, 1)).flatten()
                df["임대료부담_점수"] = 1 - rb_scaled
                score_cols.append(("임대료부담_점수", 0))  # placeholder weight
                score_col_to_key["임대료부담_점수"] = "임대료부담"

            # 유형 분류
            types = self.classify_commercial_type(df, column_mapping)

            # 유형별 가중합
            df["상권활성도"] = 0.0
            for idx in df.index:
                t = types.loc[idx]
                tw = self.WEIGHTS_BY_TYPE.get(t, self.WEIGHTS_BY_TYPE["혼합형"])
                total_w = 0.0
                s = 0.0
                for col, _ in score_cols:
                    wkey = score_col_to_key.get(col, "")
                    w = abs(tw.get(wkey, 0.1))
                    s += df.loc[idx, col] * w
                    total_w += w
                if total_w > 0:
                    df.loc[idx, "상권활성도"] = s / total_w
            df["상권활성도"] = (df["상권활성도"] * 100).round(1)
        else:
            # 기존 가중합
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
