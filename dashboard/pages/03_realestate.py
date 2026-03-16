"""부동산 실거래가 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR, settings
from dashboard.components.chart_builder import bar_chart, line_chart, scatter_chart
from dashboard.components.filters import gu_filter

st.header("부동산 실거래가 분석")


@st.cache_data
def load_realestate():
    path = PROCESSED_DIR / "realestate.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


df = load_realestate()
if df.empty:
    st.warning("부동산 데이터가 없습니다.")
    st.stop()

# 필터
with st.sidebar:
    st.subheader("필터")
    gu_code = gu_filter(key="re_gu")
    property_type = st.selectbox("유형", ["전체", "apt", "villa"])

if gu_code:
    df = df[df["자치구코드"] == gu_code]
if property_type != "전체":
    df = df[df["유형"] == property_type]

# KPI
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("총 거래건수", f"{len(df):,}")
with col2:
    if "거래금액" in df.columns:
        st.metric("평균 거래금액 (만원)", f"{df['거래금액'].mean():,.0f}")
with col3:
    if "평당가격" in df.columns:
        st.metric("평균 평당가격 (만원)", f"{df['평당가격'].mean():,.0f}")

# 탭
tab1, tab2, tab3 = st.tabs(["가격 추이", "구별 비교", "면적별 분석"])

with tab1:
    st.subheader("월별 평균 거래금액 추이")
    if "연월" in df.columns:
        monthly = df.groupby("연월").agg(
            평균거래금액=("거래금액", "mean"),
            중위거래금액=("거래금액", "median"),
            거래건수=("거래금액", "count"),
        ).reset_index()
        st.plotly_chart(
            line_chart(monthly, "연월", ["평균거래금액", "중위거래금액"], title="월별 거래금액 추이"),
            use_container_width=True,
        )
        st.plotly_chart(
            bar_chart(monthly, "연월", "거래건수", title="월별 거래건수"),
            use_container_width=True,
        )

with tab2:
    st.subheader("자치구별 평균 거래금액")
    if "자치구코드" in df.columns:
        gu_agg = df.groupby("자치구코드").agg(
            평균거래금액=("거래금액", "mean"),
            거래건수=("거래금액", "count"),
        ).reset_index()
        gu_agg["자치구명"] = gu_agg["자치구코드"].map(settings.seoul_gu_names)
        gu_agg = gu_agg.sort_values("평균거래금액", ascending=False)
        st.plotly_chart(
            bar_chart(gu_agg, "자치구명", "평균거래금액", title="자치구별 평균 거래금액 (만원)"),
            use_container_width=True,
        )

with tab3:
    st.subheader("전용면적별 거래금액 분포")
    if "전용면적" in df.columns and "거래금액" in df.columns:
        st.plotly_chart(
            scatter_chart(
                df.sample(min(5000, len(df))),
                "전용면적", "거래금액",
                title="전용면적 vs 거래금액",
                color="유형" if "유형" in df.columns else None,
            ),
            use_container_width=True,
        )
