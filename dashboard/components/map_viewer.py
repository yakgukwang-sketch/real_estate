"""Folium 지도 컴포넌트."""

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# 서울 중심 좌표
SEOUL_CENTER = [37.5665, 126.9780]


def create_base_map(
    center: list[float] | None = None,
    zoom: int = 11,
    tiles: str = "cartodbpositron",
) -> folium.Map:
    """기본 서울 지도 생성."""
    return folium.Map(
        location=center or SEOUL_CENTER,
        zoom_start=zoom,
        tiles=tiles,
    )


def add_choropleth(
    m: folium.Map,
    gdf: gpd.GeoDataFrame,
    value_col: str,
    key_col: str = "adm_cd",
    legend_name: str = "",
    fill_color: str = "YlOrRd",
) -> folium.Map:
    """행정동 단위 코로플레스 지도."""
    geojson = gdf.to_json()

    folium.Choropleth(
        geo_data=geojson,
        data=gdf,
        columns=[key_col, value_col],
        key_on=f"feature.properties.{key_col}",
        fill_color=fill_color,
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name=legend_name or value_col,
        nan_fill_color="white",
    ).add_to(m)

    return m


def add_markers(
    m: folium.Map,
    df: pd.DataFrame,
    lat_col: str = "위도",
    lon_col: str = "경도",
    popup_col: str = "역명",
    color: str = "blue",
    icon: str = "info-sign",
) -> folium.Map:
    """마커 추가."""
    for _, row in df.iterrows():
        if pd.isna(row.get(lat_col)) or pd.isna(row.get(lon_col)):
            continue
        folium.Marker(
            location=[row[lat_col], row[lon_col]],
            popup=str(row.get(popup_col, "")),
            icon=folium.Icon(color=color, icon=icon),
        ).add_to(m)
    return m


def add_heatmap(
    m: folium.Map,
    df: pd.DataFrame,
    lat_col: str = "위도",
    lon_col: str = "경도",
    weight_col: str | None = None,
) -> folium.Map:
    """히트맵 추가."""
    from folium.plugins import HeatMap

    valid = df.dropna(subset=[lat_col, lon_col])
    if valid.empty:
        return m

    if weight_col and weight_col in valid.columns:
        data = valid[[lat_col, lon_col, weight_col]].values.tolist()
    else:
        data = valid[[lat_col, lon_col]].values.tolist()

    HeatMap(data, radius=15, blur=10).add_to(m)
    return m


def render_map(m: folium.Map, height: int = 600) -> dict:
    """Streamlit에서 Folium 지도 렌더링."""
    return st_folium(m, width=None, height=height, returned_objects=[])


def create_flow_map(
    flow_df: pd.DataFrame,
    spending_df: pd.DataFrame,
    population_df: pd.DataFrame,
    coord_map: dict[str, tuple[float, float]],
    phase: str,
    geojson_path: str | None = None,
) -> folium.Map:
    """유동인구 흐름 시각화 지도 생성.

    Args:
        flow_df: columns=[origin, destination, count, phase]
        spending_df: columns=[dong, phase, spending]
        population_df: columns=[dong, phase, population]
        coord_map: 동 이름 → (lat, lon) 매핑
        phase: 시간대 필터 ("morning", "daytime", "evening", "night")
        geojson_path: 서울 GeoJSON 파일 경로 (선택)
    """
    from folium.plugins import AntPath

    m = create_base_map(zoom=12)

    # 선택된 시간대 데이터 필터
    phase_flows = flow_df[flow_df["phase"] == phase].copy() if not flow_df.empty else pd.DataFrame()
    phase_spending = spending_df[spending_df["phase"] == phase].copy() if not spending_df.empty else pd.DataFrame()
    phase_pop = population_df[population_df["phase"] == phase].copy() if not population_df.empty else pd.DataFrame()

    # 코로플레스 (소비 기준) - gu-level GeoJSON 사용 시
    # geojson은 gu-level이므로 dong-level 소비와 직접 매핑이 어려움 → 생략

    # AntPath: 상위 20개 OD 흐름
    if not phase_flows.empty:
        top_flows = phase_flows.nlargest(20, "count")
        max_count = top_flows["count"].max() if not top_flows.empty else 1
        min_count = top_flows["count"].min() if not top_flows.empty else 1
        count_range = max_count - min_count if max_count != min_count else 1

        for _, row in top_flows.iterrows():
            origin_coords = coord_map.get(row["origin"])
            dest_coords = coord_map.get(row["destination"])
            if origin_coords is None or dest_coords is None:
                continue
            if row["origin"] == row["destination"]:
                continue

            # 선 굵기: 2~8 범위로 정규화
            normalized = (row["count"] - min_count) / count_range
            weight = 2 + normalized * 6

            # 색상: 파랑(낮음) → 빨강(높음)
            r = int(normalized * 255)
            b = int((1 - normalized) * 255)
            color = f"#{r:02x}00{b:02x}"

            popup_text = f"{row['origin']} → {row['destination']}: {row['count']:,}명"

            AntPath(
                locations=[
                    [origin_coords[0], origin_coords[1]],
                    [dest_coords[0], dest_coords[1]],
                ],
                color=color,
                weight=weight,
                opacity=0.7,
                dash_array=[10, 20],
                delay=1000,
                popup=folium.Popup(popup_text, max_width=250),
            ).add_to(m)

    # CircleMarker: 각 동의 인구 + 소비
    spending_by_dong = {}
    if not phase_spending.empty:
        spending_by_dong = dict(zip(phase_spending["dong"], phase_spending["spending"]))

    pop_by_dong = {}
    if not phase_pop.empty:
        pop_by_dong = dict(zip(phase_pop["dong"], phase_pop["population"]))

    all_dongs = set(list(spending_by_dong.keys()) + list(pop_by_dong.keys()))
    for dong in all_dongs:
        coords = coord_map.get(dong)
        if coords is None:
            continue
        pop = pop_by_dong.get(dong, 0)
        spend = spending_by_dong.get(dong, 0)
        radius = max(5, min(25, pop / max(max(pop_by_dong.values(), default=1), 1) * 25)) if pop > 0 else 5

        popup_html = (
            f"<b>{dong}</b><br>"
            f"인구: {pop:,}명<br>"
            f"소비: {spend:,.0f}원"
        )
        folium.CircleMarker(
            location=[coords[0], coords[1]],
            radius=radius,
            color="#3388ff",
            fill=True,
            fill_color="#3388ff",
            fill_opacity=0.5,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(m)

    return m


def create_comparison_maps(
    gdf: gpd.GeoDataFrame,
    before_col: str,
    after_col: str,
    key_col: str = "adm_cd",
) -> tuple[folium.Map, folium.Map]:
    """Before/After 비교 지도 쌍 생성."""
    m_before = create_base_map()
    m_after = create_base_map()

    add_choropleth(m_before, gdf, before_col, key_col, legend_name=f"Before: {before_col}")
    add_choropleth(m_after, gdf, after_col, key_col, legend_name=f"After: {after_col}")

    return m_before, m_after
