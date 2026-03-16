"""지역 클러스터링 - 유사한 특성의 행정동 그룹화."""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class DongClusterer:
    """행정동을 여러 지표로 클러스터링."""

    def __init__(self, n_clusters: int = 5):
        self.n_clusters = n_clusters
        self.scaler = StandardScaler()
        self.model: KMeans | None = None

    def fit_predict(
        self, df: pd.DataFrame, feature_cols: list[str] | None = None
    ) -> pd.DataFrame:
        """클러스터링 수행.

        Args:
            df: 행정동코드를 인덱스/컬럼으로 가진 DataFrame
            feature_cols: 클러스터링에 사용할 컬럼 (None이면 숫자 컬럼 전부)
        """
        if feature_cols is None:
            feature_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        valid_df = df.dropna(subset=feature_cols)
        if len(valid_df) < self.n_clusters:
            logger.warning("데이터 부족: %d행 < %d클러스터", len(valid_df), self.n_clusters)
            valid_df["클러스터"] = 0
            return valid_df

        X = self.scaler.fit_transform(valid_df[feature_cols])
        self.model = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        valid_df = valid_df.copy()
        valid_df["클러스터"] = self.model.fit_predict(X)

        return valid_df

    def cluster_summary(self, df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        """클러스터별 평균 특성."""
        if "클러스터" not in df.columns:
            return pd.DataFrame()

        summary = df.groupby("클러스터")[feature_cols].mean().round(2)
        summary["행정동수"] = df.groupby("클러스터").size()
        return summary

    def find_similar_dongs(
        self, df: pd.DataFrame, dong_code: str, top_n: int = 5
    ) -> pd.DataFrame:
        """특정 행정동과 가장 유사한 행정동 찾기."""
        if "클러스터" not in df.columns:
            return pd.DataFrame()

        target = df[df["행정동코드"] == dong_code]
        if target.empty:
            return pd.DataFrame()

        cluster = target.iloc[0]["클러스터"]
        same_cluster = df[
            (df["클러스터"] == cluster) & (df["행정동코드"] != dong_code)
        ]

        if same_cluster.empty:
            return pd.DataFrame()

        # 유클리드 거리로 정렬
        feature_cols = df.select_dtypes(include=[np.number]).columns.difference(["클러스터"])
        target_vals = target[feature_cols].values[0]
        distances = np.linalg.norm(
            self.scaler.transform(same_cluster[feature_cols]) - self.scaler.transform([target_vals]),
            axis=1,
        )
        same_cluster = same_cluster.copy()
        same_cluster["유사도거리"] = distances
        return same_cluster.nsmallest(top_n, "유사도거리")
