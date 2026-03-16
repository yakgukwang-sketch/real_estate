"""공통 차트 빌더 - Plotly 기반."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str | None = None,
    orientation: str = "v",
    height: int = 400,
) -> go.Figure:
    """바 차트."""
    fig = px.bar(
        df, x=x, y=y, title=title, color=color,
        orientation=orientation, height=height,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str = "",
    height: int = 400,
) -> go.Figure:
    """라인 차트."""
    if isinstance(y, list):
        fig = go.Figure()
        for col in y:
            fig.add_trace(go.Scatter(x=df[x], y=df[col], mode="lines+markers", name=col))
        fig.update_layout(title=title, height=height, margin=dict(l=20, r=20, t=40, b=20))
    else:
        fig = px.line(df, x=x, y=y, title=title, height=height)
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str | None = None,
    size: str | None = None,
    hover_data: list[str] | None = None,
    height: int = 400,
) -> go.Figure:
    """산점도."""
    fig = px.scatter(
        df, x=x, y=y, title=title, color=color, size=size,
        hover_data=hover_data, height=height,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def heatmap_chart(
    df: pd.DataFrame,
    title: str = "",
    height: int = 500,
) -> go.Figure:
    """히트맵 (상관행렬 등)."""
    fig = px.imshow(
        df, text_auto=".2f", title=title, height=height,
        color_continuous_scale="RdBu_r", aspect="auto",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def pie_chart(
    df: pd.DataFrame,
    values: str,
    names: str,
    title: str = "",
    height: int = 400,
) -> go.Figure:
    """파이 차트."""
    fig = px.pie(df, values=values, names=names, title=title, height=height)
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def forecast_chart(
    forecast_df: pd.DataFrame,
    title: str = "시계열 예측",
    height: int = 400,
) -> go.Figure:
    """예측 결과 시각화 (실제값 + 예측값 + 신뢰구간)."""
    fig = go.Figure()

    # 실제값
    actual = forecast_df.dropna(subset=["실제값"])
    if not actual.empty:
        fig.add_trace(go.Scatter(
            x=actual["날짜"], y=actual["실제값"],
            mode="lines+markers", name="실제값", line=dict(color="blue"),
        ))

    # 예측값
    predicted = forecast_df.dropna(subset=["예측값"])
    if not predicted.empty:
        fig.add_trace(go.Scatter(
            x=predicted["날짜"], y=predicted["예측값"],
            mode="lines", name="예측값", line=dict(color="red", dash="dash"),
        ))

    # 신뢰구간
    if "상한" in forecast_df.columns and "하한" in forecast_df.columns:
        conf = forecast_df.dropna(subset=["상한", "하한"])
        if not conf.empty:
            fig.add_trace(go.Scatter(
                x=list(conf["날짜"]) + list(conf["날짜"][::-1]),
                y=list(conf["상한"]) + list(conf["하한"][::-1]),
                fill="toself", fillcolor="rgba(255,0,0,0.1)",
                line=dict(color="rgba(255,0,0,0)"),
                name="95% 신뢰구간",
            ))

    fig.update_layout(title=title, height=height, margin=dict(l=20, r=20, t=40, b=20))
    return fig
