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


def inflow_outflow_chart(
    flow_df: pd.DataFrame,
    title: str = "유입/유출 순이동",
    height: int = 400,
) -> go.Figure:
    """동별 순유입/유출 수평 바 차트.

    Args:
        flow_df: columns=[origin, destination, count, phase]
    """
    if flow_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title, height=height)
        return fig

    # 유입 합산
    inflow = flow_df.groupby("destination")["count"].sum().rename("inflow")
    # 유출 합산
    outflow = flow_df.groupby("origin")["count"].sum().rename("outflow")
    net = pd.DataFrame({"inflow": inflow, "outflow": outflow}).fillna(0)
    net["net"] = net["inflow"] - net["outflow"]
    net = net.sort_values("net")

    # 상위/하위 15개
    top_out = net.head(10)
    top_in = net.tail(10)
    display = pd.concat([top_out, top_in]).drop_duplicates()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=display.index,
        x=display["net"].clip(upper=0),
        orientation="h",
        name="순유출",
        marker_color="#ef4444",
    ))
    fig.add_trace(go.Bar(
        y=display.index,
        x=display["net"].clip(lower=0),
        orientation="h",
        name="순유입",
        marker_color="#3b82f6",
    ))
    fig.update_layout(
        title=title, height=height, barmode="relative",
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="순이동 인원",
        yaxis_title="",
    )
    return fig


def phase_spending_chart(
    spending_df: pd.DataFrame,
    title: str = "시간대별 소비 분석",
    height: int = 400,
) -> go.Figure:
    """시간대별 동별 소비 그룹 바 차트.

    Args:
        spending_df: columns=[dong, phase, spending]
    """
    if spending_df.empty:
        fig = go.Figure()
        fig.update_layout(title=title, height=height)
        return fig

    phase_labels = {
        "morning": "출근시간(오전)",
        "daytime": "주간",
        "evening": "퇴근시간(저녁)",
        "night": "야간",
    }
    phase_colors = {
        "morning": "#f59e0b",
        "daytime": "#3b82f6",
        "evening": "#ef4444",
        "night": "#8b5cf6",
    }

    # 총소비 상위 10개 동만
    dong_totals = spending_df.groupby("dong")["spending"].sum().nlargest(10)
    top_dongs = dong_totals.index.tolist()
    filtered = spending_df[spending_df["dong"].isin(top_dongs)]

    fig = go.Figure()
    for phase in ["morning", "daytime", "evening", "night"]:
        phase_data = filtered[filtered["phase"] == phase]
        if phase_data.empty:
            continue
        # 동 순서를 총소비 기준으로 정렬
        phase_data = phase_data.set_index("dong").reindex(top_dongs).reset_index()
        fig.add_trace(go.Bar(
            x=phase_data["dong"],
            y=phase_data["spending"],
            name=phase_labels.get(phase, phase),
            marker_color=phase_colors.get(phase, "#999"),
        ))

    fig.update_layout(
        title=title, height=height, barmode="group",
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="행정동",
        yaxis_title="소비액 (원)",
    )
    return fig


def dong_ranking_chart(
    population_df: pd.DataFrame,
    spending_df: pd.DataFrame,
    title: str = "동별 인구 & 소비 순위",
    height: int = 400,
) -> go.Figure:
    """동별 인구와 소비를 보여주는 결합 차트.

    Args:
        population_df: columns=[dong, phase, population]
        spending_df: columns=[dong, phase, spending]
    """
    fig = go.Figure()

    if population_df.empty and spending_df.empty:
        fig.update_layout(title=title, height=height)
        return fig

    pop_total = population_df.groupby("dong")["population"].sum() if not population_df.empty else pd.Series(dtype=float)
    spend_total = spending_df.groupby("dong")["spending"].sum() if not spending_df.empty else pd.Series(dtype=float)

    combined = pd.DataFrame({"population": pop_total, "spending": spend_total}).fillna(0)
    combined = combined.sort_values("spending", ascending=False).head(15)

    fig.add_trace(go.Bar(
        x=combined.index,
        y=combined["spending"],
        name="소비액",
        marker_color="#3b82f6",
        yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=combined.index,
        y=combined["population"],
        name="인구수",
        mode="lines+markers",
        marker_color="#ef4444",
        yaxis="y2",
    ))

    fig.update_layout(
        title=title, height=height,
        margin=dict(l=20, r=60, t=40, b=20),
        yaxis=dict(title="소비액 (원)", side="left"),
        yaxis2=dict(title="인구수", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99),
    )
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
