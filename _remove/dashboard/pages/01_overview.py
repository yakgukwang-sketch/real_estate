"""서울 전체 현황 대시보드."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR, GEO_DIR
from dashboard.components.map_viewer import create_base_map, add_choropleth, render_map
from dashboard.components.chart_builder import bar_chart

st.header("서울 전체 현황")


@st.cache_data
def load_data():
    """처리된 데이터 로드."""
    data = {}
    for name in ["subway", "realestate", "commercial", "population", "spending"]:
        path = PROCESSED_DIR / f"{name}.parquet"
        if path.exists():
            data[name] = pd.read_parquet(path)
    return data


data = load_data()

if not data:
    st.warning("처리된 데이터가 없습니다. `scripts/process_all.py`를 먼저 실행하세요.")
    st.stop()

# KPI 메트릭
col1, col2, col3, col4 = st.columns(4)

with col1:
    if "subway" in data:
        total_passengers = data["subway"]["하차총승객수"].sum()
        st.metric("총 하차 인원", f"{total_passengers:,.0f}")

with col2:
    if "realestate" in data:
        avg_price = data["realestate"]["평균거래금액"].mean()
        st.metric("평균 거래금액 (만원)", f"{avg_price:,.0f}")

with col3:
    if "commercial" in data:
        total_stores = len(data["commercial"])
        st.metric("총 상가업소", f"{total_stores:,}")

with col4:
    if "population" in data:
        avg_pop = data["population"]["평균생활인구"].mean()
        st.metric("평균 생활인구", f"{avg_pop:,.0f}")

# 지도
st.subheader("서울시 행정동 지도")
geojson_path = GEO_DIR / "seoul_dong.geojson"
if geojson_path.exists():
    import geopandas as gpd
    gdf = gpd.read_file(geojson_path)
    m = create_base_map()
    if "subway" in data and "행정동코드" in data["subway"].columns:
        subway_agg = data["subway"].groupby("행정동코드").agg(하차총승객수=("하차총승객수", "sum")).reset_index()
        gdf = gdf.merge(subway_agg, left_on="adm_cd", right_on="행정동코드", how="left")
        m = add_choropleth(gdf, gdf, "하차총승객수", legend_name="총 하차인원")
    render_map(m)
else:
    st.info("GeoJSON 파일이 필요합니다. `scripts/seed_geodata.py`를 실행하세요.")

# 자치구별 요약
st.subheader("자치구별 요약")
if "subway" in data and "행정동코드" in data["subway"].columns:
    subway_gu = data["subway"].copy()
    subway_gu["자치구코드"] = subway_gu["행정동코드"].astype(str).str[:5]
    from config.settings import settings
    subway_gu["자치구명"] = subway_gu["자치구코드"].map(settings.seoul_gu_names)
    gu_summary = subway_gu.groupby("자치구명").agg(
        총하차=("하차총승객수", "sum"),
        총승차=("승차총승객수", "sum"),
    ).reset_index().sort_values("총하차", ascending=False)
    st.plotly_chart(bar_chart(gu_summary, "자치구명", "총하차", title="자치구별 지하철 하차인원"), use_container_width=True)
