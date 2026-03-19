"""지하철 승하차 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import bar_chart, line_chart
from dashboard.components.filters import gu_filter, period_filter
from dashboard.components.map_viewer import create_base_map, add_markers, add_heatmap, render_map

st.header("지하철 승하차 분석")


@st.cache_data
def load_subway():
    path = PROCESSED_DIR / "subway.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


df = load_subway()
if df.empty:
    st.warning("지하철 데이터가 없습니다.")
    st.stop()

# 필터
with st.sidebar:
    st.subheader("필터")
    gu_code = gu_filter()

# 자치구 필터 적용
if gu_code and "행정동코드" in df.columns:
    df = df[df["행정동코드"].astype(str).str.startswith(gu_code)]

# 탭
tab1, tab2, tab3 = st.tabs(["역별 순위", "시계열 추이", "지도"])

with tab1:
    st.subheader("역별 하차인원 TOP 20")
    top_stations = (
        df.groupby("역명")
        .agg(하차총승객수=("하차총승객수", "sum"))
        .nlargest(20, "하차총승객수")
        .reset_index()
    )
    st.plotly_chart(
        bar_chart(top_stations, "역명", "하차총승객수", title="역별 총 하차인원"),
        use_container_width=True,
    )

with tab2:
    st.subheader("월별 승하차 추이")
    if "연월" in df.columns:
        monthly = (
            df.groupby("연월")
            .agg(승차총승객수=("승차총승객수", "sum"), 하차총승객수=("하차총승객수", "sum"))
            .reset_index()
        )
        st.plotly_chart(
            line_chart(monthly, "연월", ["승차총승객수", "하차총승객수"], title="월별 승하차 추이"),
            use_container_width=True,
        )

    # 역 선택 상세
    station = st.selectbox("역 선택", sorted(df["역명"].unique()))
    station_df = df[df["역명"] == station]
    if not station_df.empty and "연월" in station_df.columns:
        station_monthly = (
            station_df.groupby("연월")
            .agg(승차=("승차총승객수", "sum"), 하차=("하차총승객수", "sum"))
            .reset_index()
        )
        st.plotly_chart(
            line_chart(station_monthly, "연월", ["승차", "하차"], title=f"{station}역 월별 추이"),
            use_container_width=True,
        )

with tab3:
    st.subheader("역 위치 지도")
    if "위도" in df.columns and "경도" in df.columns:
        station_coords = df.drop_duplicates("역명")[["역명", "위도", "경도", "하차총승객수"]].dropna()
        m = create_base_map()
        m = add_markers(m, station_coords, popup_col="역명")
        m = add_heatmap(m, station_coords, weight_col="하차총승객수")
        render_map(m)
    else:
        st.info("좌표 데이터가 없습니다.")
