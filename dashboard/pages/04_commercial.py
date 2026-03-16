"""상권 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import bar_chart, pie_chart
from dashboard.components.filters import gu_filter
from dashboard.components.map_viewer import create_base_map, add_heatmap, render_map

st.header("상권 분석")


@st.cache_data
def load_commercial():
    path = PROCESSED_DIR / "commercial.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@st.cache_data
def load_spending():
    path = PROCESSED_DIR / "spending.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


commercial_df = load_commercial()
spending_df = load_spending()

if commercial_df.empty:
    st.warning("상가업소 데이터가 없습니다.")
    st.stop()

# 필터
with st.sidebar:
    gu_code = gu_filter(key="com_gu")

if gu_code and "행정동코드" in commercial_df.columns:
    commercial_df = commercial_df[commercial_df["행정동코드"].astype(str).str.startswith(gu_code)]

# KPI
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("총 상가업소", f"{len(commercial_df):,}")
with col2:
    if "대분류명" in commercial_df.columns:
        st.metric("업종 대분류수", commercial_df["대분류명"].nunique())
with col3:
    if "행정동코드" in commercial_df.columns:
        st.metric("행정동 수", commercial_df["행정동코드"].nunique())

# 탭
tab1, tab2, tab3 = st.tabs(["업종 분포", "상권 지도", "추정매출"])

with tab1:
    if "대분류명" in commercial_df.columns:
        cat_dist = (
            commercial_df.groupby("대분류명")
            .size()
            .reset_index(name="업소수")
            .sort_values("업소수", ascending=False)
        )
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                bar_chart(cat_dist.head(15), "대분류명", "업소수", title="업종 대분류별 업소수"),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                pie_chart(cat_dist.head(10), "업소수", "대분류명", title="업종 구성비"),
                use_container_width=True,
            )

    # 행정동별 업소 밀도
    if "행정동명" in commercial_df.columns:
        dong_density = (
            commercial_df.groupby("행정동명")
            .size()
            .reset_index(name="업소수")
            .sort_values("업소수", ascending=False)
        )
        st.plotly_chart(
            bar_chart(dong_density.head(20), "행정동명", "업소수", title="행정동별 업소수 TOP 20"),
            use_container_width=True,
        )

with tab2:
    if "위도" in commercial_df.columns and "경도" in commercial_df.columns:
        m = create_base_map()
        sample = commercial_df.sample(min(5000, len(commercial_df)))
        m = add_heatmap(m, sample, lat_col="위도", lon_col="경도")
        render_map(m)
    else:
        st.info("좌표 데이터가 없습니다.")

with tab3:
    if not spending_df.empty:
        st.subheader("상권 추정매출")
        if "서비스업종명" in spending_df.columns and "당월매출금액" in spending_df.columns:
            industry_spending = (
                spending_df.groupby("서비스업종명")
                .agg(총매출=("당월매출금액", "sum"))
                .nlargest(20, "총매출")
                .reset_index()
            )
            st.plotly_chart(
                bar_chart(industry_spending, "서비스업종명", "총매출", title="업종별 추정매출 TOP 20"),
                use_container_width=True,
            )
    else:
        st.info("추정매출 데이터가 없습니다.")
