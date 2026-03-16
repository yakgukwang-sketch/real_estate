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
