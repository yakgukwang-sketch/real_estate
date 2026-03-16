"""생활/직장 인구 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR, GEO_DIR
from dashboard.components.chart_builder import bar_chart, line_chart
from dashboard.components.filters import gu_filter
from dashboard.components.map_viewer import create_base_map, add_choropleth, render_map

st.header("생활/직장 인구 분석")


@st.cache_data
def load_population():
    path = PROCESSED_DIR / "population.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


df = load_population()
if df.empty:
    st.warning("인구 데이터가 없습니다.")
    st.stop()

with st.sidebar:
    gu_code = gu_filter(key="pop_gu")

if gu_code and "행정동코드" in df.columns:
    df = df[df["행정동코드"].astype(str).str.startswith(gu_code)]

# KPI
col1, col2, col3 = st.columns(3)
with col1:
    if "평균생활인구" in df.columns:
        st.metric("평균 생활인구", f"{df['평균생활인구'].mean():,.0f}")
with col2:
    if "평균남성" in df.columns:
        st.metric("평균 남성 인구", f"{df['평균남성'].mean():,.0f}")
with col3:
    if "평균여성" in df.columns:
        st.metric("평균 여성 인구", f"{df['평균여성'].mean():,.0f}")

# 탭
tab1, tab2 = st.tabs(["행정동별 인구", "인구 추이"])

with tab1:
    if "행정동코드" in df.columns and "평균생활인구" in df.columns:
        dong_pop = (
            df.groupby("행정동코드")
            .agg(평균생활인구=("평균생활인구", "mean"))
            .nlargest(30, "평균생활인구")
            .reset_index()
        )
        st.plotly_chart(
            bar_chart(dong_pop, "행정동코드", "평균생활인구", title="행정동별 평균 생활인구 TOP 30"),
            use_container_width=True,
        )

    # 지도
    geojson_path = GEO_DIR / "seoul_dong.geojson"
    if geojson_path.exists() and "행정동코드" in df.columns:
        import geopandas as gpd
        gdf = gpd.read_file(geojson_path)
        pop_agg = df.groupby("행정동코드").agg(평균생활인구=("평균생활인구", "mean")).reset_index()
        gdf = gdf.merge(pop_agg, left_on="adm_cd", right_on="행정동코드", how="left")
        m = create_base_map()
        m = add_choropleth(m, gdf, "평균생활인구", legend_name="평균 생활인구", fill_color="YlGnBu")
        render_map(m)

with tab2:
    if "연월" in df.columns:
        monthly = df.groupby("연월").agg(평균생활인구=("평균생활인구", "mean")).reset_index()
        st.plotly_chart(
            line_chart(monthly, "연월", "평균생활인구", title="월별 평균 생활인구 추이"),
            use_container_width=True,
        )
