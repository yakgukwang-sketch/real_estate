"""공통 필터 컴포넌트 - 구/동/기간 선택."""

import streamlit as st
import pandas as pd

from config.settings import settings


def gu_filter(key: str = "gu_filter") -> str | None:
    """자치구 선택 필터."""
    gu_options = ["전체"] + list(settings.seoul_gu_names.values())
    selected = st.selectbox("자치구", gu_options, key=key)
    if selected == "전체":
        return None
    # 이름 → 코드 역매핑
    for code, name in settings.seoul_gu_names.items():
        if name == selected:
            return code
    return None


def dong_filter(
    dong_list: list[dict], key: str = "dong_filter"
) -> str | None:
    """행정동 선택 필터.

    Args:
        dong_list: [{"행정동코드": "...", "행정동명": "..."}, ...]
    """
    if not dong_list:
        return None

    options = ["전체"] + [f"{d['행정동명']} ({d['행정동코드']})" for d in dong_list]
    selected = st.selectbox("행정동", options, key=key)
    if selected == "전체":
        return None
    # 코드 추출
    code = selected.split("(")[-1].rstrip(")")
    return code


def period_filter(
    key: str = "period_filter",
    min_year: int = 2020,
    max_year: int = 2025,
) -> tuple[int, int, int, int]:
    """기간 선택 필터.

    Returns:
        (start_year, start_month, end_year, end_month)
    """
    col1, col2 = st.columns(2)
    with col1:
        st.write("시작")
        start_year = st.selectbox(
            "시작 연도", range(min_year, max_year + 1),
            index=max_year - min_year - 1,
            key=f"{key}_sy",
        )
        start_month = st.selectbox(
            "시작 월", range(1, 13), index=0, key=f"{key}_sm"
        )
    with col2:
        st.write("종료")
        end_year = st.selectbox(
            "종료 연도", range(min_year, max_year + 1),
            index=max_year - min_year,
            key=f"{key}_ey",
        )
        end_month = st.selectbox(
            "종료 월", range(1, 13), index=11, key=f"{key}_em"
        )
    return start_year, start_month, end_year, end_month


def metric_filter(
    metrics: list[str], key: str = "metric_filter", default: str | None = None
) -> str:
    """지표 선택 필터."""
    idx = metrics.index(default) if default and default in metrics else 0
    return st.selectbox("지표", metrics, index=idx, key=key)


def multi_metric_filter(
    metrics: list[str], key: str = "multi_metric_filter"
) -> list[str]:
    """복수 지표 선택 필터."""
    return st.multiselect("지표 선택", metrics, default=metrics[:3], key=key)
