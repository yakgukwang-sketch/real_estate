"""시뮬레이션 검증 모듈.

시뮬레이션 결과와 실제 데이터를 비교하여 매치율을 산출.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _cosine_similarity(a: dict, b: dict) -> float:
    """두 dict의 코사인 유사도 (공통 키 기준)."""
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 0.0
    va = np.array([a.get(k, 0) for k in keys], dtype=float)
    vb = np.array([b.get(k, 0) for k in keys], dtype=float)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def compare_unit_prices(
    sim_df: pd.DataFrame,
    spending_df: pd.DataFrame,
) -> dict:
    """업종별 객단가 비교.

    Returns:
        {dest_type: {"sim": int, "real": int, "diff_pct": float}}
    """
    from src.simulation.calibration import (
        _filter_daechi_area,
        _map_service_to_dest,
    )

    # 시뮬레이션 객단가
    sim_spend = sim_df[sim_df["소비(원)"] > 0].copy()
    if sim_spend.empty:
        return {}
    sim_avg = sim_spend.groupby("목적지유형")["소비(원)"].mean()

    # 실제 객단가
    real_df = _filter_daechi_area(spending_df)
    real_df = _map_service_to_dest(real_df)
    real_df = real_df[real_df["당월매출건수"] > 0].copy()
    if real_df.empty:
        return {}
    real_df["객단가"] = real_df["당월매출금액"] / real_df["당월매출건수"]
    real_avg = real_df.groupby("dest_type")["객단가"].mean()

    result = {}
    all_types = set(sim_avg.index) | set(real_avg.index)
    for dt in all_types:
        s = int(sim_avg.get(dt, 0))
        r = int(real_avg.get(dt, 0))
        diff = abs(s - r) / max(r, 1) * 100 if r > 0 else 0
        result[dt] = {"sim": s, "real": r, "diff_pct": round(diff, 1)}

    return result


def compare_visit_share(
    sim_df: pd.DataFrame,
    spending_df: pd.DataFrame,
) -> dict:
    """방문 비중 비교 (코사인 유사도).

    Returns:
        {"sim_share": dict, "real_share": dict, "cosine_similarity": float}
    """
    from src.simulation.calibration import (
        _filter_daechi_area,
        _map_service_to_dest,
    )

    # 시뮬레이션 방문 비중
    sim_counts = sim_df["목적지유형"].value_counts(normalize=True).to_dict()

    # 실제 방문 비중 (매출건수 기준)
    real_df = _filter_daechi_area(spending_df)
    real_df = _map_service_to_dest(real_df)
    if "당월매출건수" not in real_df.columns or real_df.empty:
        return {"sim_share": sim_counts, "real_share": {}, "cosine_similarity": 0.0}

    type_counts = real_df.groupby("dest_type")["당월매출건수"].sum()
    total = type_counts.sum()
    real_share = (type_counts / total).to_dict() if total > 0 else {}

    cos_sim = _cosine_similarity(sim_counts, real_share)

    return {
        "sim_share": {k: round(v, 4) for k, v in sim_counts.items()},
        "real_share": {k: round(v, 4) for k, v in real_share.items()},
        "cosine_similarity": round(cos_sim, 4),
    }


def compare_hourly_pattern(
    sim_df: pd.DataFrame,
    hourly_pattern: pd.Series | None,
) -> dict:
    """시간대 패턴 비교 (피어슨 상관계수).

    Returns:
        {"sim_pattern": dict, "real_pattern": dict, "correlation": float}
    """
    if hourly_pattern is None or hourly_pattern.empty:
        return {"sim_pattern": {}, "real_pattern": {}, "correlation": 0.0}

    # 시뮬레이션 시간대 분포 (HH:00 → 시간대 정수)
    sim_df = sim_df.copy()
    sim_df["hour"] = sim_df["시간"].str.extract(r"(\d+)").astype(float)
    sim_hourly = sim_df.groupby("hour")["agent_id"].count()
    max_sim = sim_hourly.max()
    if max_sim > 0:
        sim_hourly = sim_hourly / max_sim

    # 공통 시간대로 정렬
    real_pattern = hourly_pattern.copy()
    real_pattern.index = real_pattern.index.astype(float)

    common = sorted(set(sim_hourly.index) & set(real_pattern.index))
    if len(common) < 3:
        return {
            "sim_pattern": sim_hourly.to_dict(),
            "real_pattern": real_pattern.to_dict(),
            "correlation": 0.0,
        }

    sim_vals = np.array([sim_hourly.get(h, 0) for h in common])
    real_vals = np.array([real_pattern.get(h, 0) for h in common])

    corr = float(np.corrcoef(sim_vals, real_vals)[0, 1])
    if np.isnan(corr):
        corr = 0.0

    return {
        "sim_pattern": {int(k): round(v, 4) for k, v in sim_hourly.items()},
        "real_pattern": {int(k): round(v, 4) for k, v in real_pattern.items()},
        "correlation": round(corr, 4),
    }


def compare_daily_revenue(
    sim_df: pd.DataFrame,
    spending_df: pd.DataFrame,
    n_agents: int,
    total_households: int = 1600,
) -> dict:
    """일일 총매출 비교: 시뮬 스케일업 vs 실제/90일.

    Returns:
        {"sim_daily": int, "real_daily": int, "ratio": float}
    """
    from src.simulation.calibration import (
        _filter_daechi_area,
        _map_service_to_dest,
    )

    # 시뮬레이션 일일 매출 (에이전트 수 → 세대수 스케일링)
    sim_total = sim_df["소비(원)"].sum()
    scale = total_households / max(n_agents, 1)
    sim_daily = int(sim_total * scale)

    # 실제 분기 매출 → 일 평균 (90일)
    real_df = _filter_daechi_area(spending_df)
    real_df = _map_service_to_dest(real_df)
    if "당월매출금액" not in real_df.columns:
        return {"sim_daily": sim_daily, "real_daily": 0, "ratio": 0.0}

    real_quarterly = real_df["당월매출금액"].sum()
    # 분기 수 기준 평균
    n_quarters = real_df["기준분기코드"].nunique() if "기준분기코드" in real_df.columns else 1
    real_daily = int(real_quarterly / max(n_quarters, 1) / 90)

    ratio = sim_daily / max(real_daily, 1) if real_daily > 0 else 0.0

    return {
        "sim_daily": sim_daily,
        "real_daily": real_daily,
        "ratio": round(ratio, 3),
    }


def validate(
    sim_df: pd.DataFrame,
    spending_df: pd.DataFrame,
    pop_df: pd.DataFrame | None = None,
    hourly_pattern: pd.Series | None = None,
    n_agents: int = 100,
) -> dict:
    """전체 검증 실행.

    Returns:
        {
            "unit_prices": {...},
            "visit_share": {...},
            "hourly": {...},
            "daily_revenue": {...},
            "match_score": float,  # 0~100%
        }
    """
    unit_prices = compare_unit_prices(sim_df, spending_df)
    visit_share = compare_visit_share(sim_df, spending_df)
    hourly = compare_hourly_pattern(sim_df, hourly_pattern)
    daily_rev = compare_daily_revenue(sim_df, spending_df, n_agents)

    # 매치 스코어: 3가지 지표 가중 평균
    scores = []

    # 1. 객단가 오차 (낮을수록 좋음) → 0~100 스코어
    if unit_prices:
        avg_diff = np.mean([v["diff_pct"] for v in unit_prices.values()])
        price_score = max(0, 100 - avg_diff)
        scores.append(("unit_price", price_score, 0.3))

    # 2. 방문 비중 코사인 유사도 → 0~100
    cos_sim = visit_share.get("cosine_similarity", 0)
    visit_score = cos_sim * 100
    scores.append(("visit_share", visit_score, 0.35))

    # 3. 시간대 상관계수 → 0~100
    corr = hourly.get("correlation", 0)
    hourly_score = max(0, corr * 100)
    scores.append(("hourly", hourly_score, 0.35))

    if scores:
        total_weight = sum(w for _, _, w in scores)
        match_score = sum(s * w for _, s, w in scores) / total_weight
    else:
        match_score = 0.0

    return {
        "unit_prices": unit_prices,
        "visit_share": visit_share,
        "hourly": hourly,
        "daily_revenue": daily_rev,
        "match_score": round(match_score, 1),
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)

    from src.simulation.calibration import load_calibration
    from src.simulation.local_agent import simulate, agents_to_df

    cal = load_calibration()
    agents = simulate(100, seed=42)
    sim_df = agents_to_df(agents)

    if cal and cal.get("spending_df") is not None:
        result = validate(
            sim_df,
            cal["spending_df"],
            cal.get("population_df"),
            cal.get("hourly_pattern"),
            n_agents=100,
        )
        print(f"\n매치 스코어: {result['match_score']}%")
        print(f"방문 비중 유사도: {result['visit_share']['cosine_similarity']}")
        print(f"시간대 상관계수: {result['hourly']['correlation']}")

        print("\n객단가 비교:")
        for dt, v in result["unit_prices"].items():
            print(f"  {dt}: 시뮬 {v['sim']:,}원 / 실제 {v['real']:,}원 (차이 {v['diff_pct']}%)")
    else:
        print("보정 데이터 없음 — 검증 불가")
