"""상관관계 종합 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import numpy as np

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import heatmap_chart, scatter_chart, line_chart
from src.analysis.correlation import CorrelationAnalyzer

st.header("상관관계 종합 분석")


@st.cache_data
def load_integrated():
    """통합 데이터 로드."""
    path = PROCESSED_DIR / "integrated.parquet"
    if path.exists():
        return pd.read_parquet(path)
    # 개별 파일에서 병합 시도
    dfs = {}
    for name in ["subway", "realestate", "population", "spending"]:
        p = PROCESSED_DIR / f"{name}.parquet"
        if p.exists():
            dfs[name] = pd.read_parquet(p)
    if not dfs:
        return pd.DataFrame()
    # 간단 병합
    base = None
    for name, df in dfs.items():
        if "행정동코드" in df.columns and "연월" in df.columns:
            agg = df.groupby(["행정동코드", "연월"]).first().reset_index()
            if base is None:
                base = agg
            else:
                base = base.merge(agg, on=["행정동코드", "연월"], how="outer", suffixes=("", f"_{name}"))
    return base if base is not None else pd.DataFrame()


df = load_integrated()
if df.empty:
    st.warning("통합 데이터가 없습니다. 데이터를 먼저 수집/처리하세요.")
    st.stop()

analyzer = CorrelationAnalyzer()

# 상관행렬
st.subheader("변수 간 상관행렬")
corr_matrix = analyzer.compute_correlation_matrix(df)
if not corr_matrix.empty:
    st.plotly_chart(
        heatmap_chart(corr_matrix, title="상관행렬"),
        use_container_width=True,
    )

# 변수 쌍 상세 분석
st.subheader("변수 쌍 상세 분석")
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) >= 2:
    col1, col2 = st.columns(2)
    with col1:
        var_a = st.selectbox("변수 A", numeric_cols, index=0)
    with col2:
        var_b = st.selectbox("변수 B", numeric_cols, index=min(1, len(numeric_cols) - 1))

    if var_a != var_b:
        result = analyzer.pairwise_significance(df, var_a, var_b)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("상관계수 (r)", f"{result['r']:.4f}" if result['r'] else "N/A")
        with col2:
            st.metric("p-value", f"{result['p_value']:.6f}" if result['p_value'] else "N/A")
        with col3:
            sig = "유의함" if result.get("significant") else "유의하지 않음"
            st.metric("유의성 (p<0.05)", sig)

        st.plotly_chart(
            scatter_chart(df, var_a, var_b, title=f"{var_a} vs {var_b}"),
            use_container_width=True,
        )

# 타겟 변수 기준 상위 상관
st.subheader("특정 변수 기준 상위 상관관계")
if numeric_cols:
    target = st.selectbox("타겟 변수", numeric_cols, key="target_var")
    top_corr = analyzer.top_correlations(df, target)
    if not top_corr.empty:
        st.dataframe(top_corr, use_container_width=True)
