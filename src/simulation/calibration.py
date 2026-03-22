"""시뮬레이션 보정 모듈.

실제 상권매출 데이터와 생활인구 데이터를 활용하여
시뮬레이션의 객단가, 방문 비중, 시간대 패턴을 현실에 맞게 보정.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

# 상권명 필터 키워드 (대치동 근처)
AREA_KEYWORDS = ["대치", "도곡", "한티", "학여울", "개포"]

# 서비스업종명 → 시뮬레이션 dest_type 매핑
SERVICE_TO_DEST: dict[str, str] = {
    # 음식점 계열
    "한식음식점": "음식점",
    "중식음식점": "음식점",
    "일식음식점": "음식점",
    "양식음식점": "음식점",
    "제과점": "음식점",
    "패스트푸드점": "음식점",
    "치킨전문점": "음식점",
    "분식전문점": "음식점",
    "호프-간이주점": "음식점",
    "커피-Loss/전문점": "음식점",
    "커피-음료": "음식점",
    "피자-햄버거-샌드위치": "음식점",
    # 상점 계열
    "슈퍼마켓": "상점",
    "편의점": "상점",
    "화장품소매점": "상점",
    "의복의류소매점": "상점",
    "의약품소매점": "상점",
    "가전제품소매점": "상점",
    "서적문구소매점": "상점",
    "섬유-직물소매점": "상점",
    "스포츠용품소매점": "상점",
    "신발소매점": "상점",
    "가방소매점": "상점",
    "안경점": "상점",
    "시계-귀금속소매점": "상점",
    "유아용품소매점": "상점",
    "컴퓨터-주변기기": "상점",
    "핸드폰-통신기기": "상점",
    # 대형상가
    "백화점": "대형상가",
    "대형마트": "대형상가",
    "쇼핑몰": "대형상가",
    # 병원/약국
    "일반의원": "병원/약국",
    "치과의원": "병원/약국",
    "한의원": "병원/약국",
    "약국": "병원/약국",
    "안과의원": "병원/약국",
    "피부과의원": "병원/약국",
    "정형외과의원": "병원/약국",
    "이비인후과의원": "병원/약국",
    "산부인과의원": "병원/약국",
    "소아과의원": "병원/약국",
    # 생활서비스
    "세탁소": "생활서비스",
    "미용실": "생활서비스",
    "네일-피부관리": "생활서비스",
    "부동산중개업": "생활서비스",
    "자동차수리": "생활서비스",
    "사진관": "생활서비스",
    "인쇄-복사": "생활서비스",
}

# 시뮬레이션 기본 행동 확률 (각 dest_type의 총 방문 비중)
_SIM_DEFAULT_VISIT_SHARE: dict[str, float] = {
    "음식점": 0.40,
    "상점": 0.15,
    "대형상가": 0.08,
    "병원/약국": 0.06,
    "생활서비스": 0.05,
    "학원": 0.10,
    "학교": 0.06,
    "운동시설": 0.04,
    "공원": 0.03,
    "기타": 0.03,
}


def _load_spending_parquets() -> pd.DataFrame | None:
    """data/raw/spending_*.parquet 로드 (4분기 통합)."""
    files = sorted(DATA_RAW.glob("spending_*.parquet"))
    if not files:
        return None
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    logger.info("매출 데이터 로드: %d건 (%d파일)", len(df), len(files))
    return df


def _load_population_parquets() -> pd.DataFrame | None:
    """data/raw/population_*.parquet 로드."""
    files = sorted(DATA_RAW.glob("population_*.parquet"))
    if not files:
        return None
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    logger.info("생활인구 데이터 로드: %d건 (%d파일)", len(df), len(files))
    return df


def _filter_daechi_area(df: pd.DataFrame) -> pd.DataFrame:
    """대치동 근처 상권만 필터링."""
    if "상권명" not in df.columns:
        return df
    mask = df["상권명"].str.contains("|".join(AREA_KEYWORDS), na=False)
    filtered = df[mask].copy()
    logger.info("대치 근처 필터: %d / %d건", len(filtered), len(df))
    return filtered


def _map_service_to_dest(df: pd.DataFrame) -> pd.DataFrame:
    """서비스업종명 → dest_type 매핑."""
    if "서비스업종명" not in df.columns:
        return df
    df = df.copy()
    df["dest_type"] = df["서비스업종명"].map(SERVICE_TO_DEST).fillna("기타")
    return df


def compute_unit_prices(spending_df: pd.DataFrame) -> dict[str, int]:
    """실제 객단가 산출: 당월매출금액 / 당월매출건수 → dest_type별 평균."""
    df = _filter_daechi_area(spending_df)
    df = _map_service_to_dest(df)

    if "당월매출금액" not in df.columns or "당월매출건수" not in df.columns:
        logger.warning("매출 컬럼 없음")
        return {}

    # 건수가 0인 행 제외
    df = df[df["당월매출건수"] > 0].copy()
    df["객단가"] = df["당월매출금액"] / df["당월매출건수"]

    result = {}
    for dest_type, group in df.groupby("dest_type"):
        avg = group["객단가"].mean()
        if pd.notna(avg) and avg > 0:
            result[dest_type] = int(round(avg))

    logger.info("객단가 산출: %s", result)
    return result


def compute_visit_multipliers(spending_df: pd.DataFrame) -> dict[str, float]:
    """방문 비중 보정계수 산출: 실제비중 / 시뮬비중."""
    df = _filter_daechi_area(spending_df)
    df = _map_service_to_dest(df)

    if "당월매출건수" not in df.columns:
        return {}

    # dest_type별 매출건수 비중
    type_counts = df.groupby("dest_type")["당월매출건수"].sum()
    total = type_counts.sum()
    if total == 0:
        return {}

    real_share = (type_counts / total).to_dict()

    multipliers = {}
    for dest_type, real_s in real_share.items():
        sim_s = _SIM_DEFAULT_VISIT_SHARE.get(dest_type, 0.03)
        mult = real_s / sim_s
        multipliers[dest_type] = round(max(0.1, min(mult, 3.0)), 3)

    logger.info("방문 보정계수: %s", multipliers)
    return multipliers


def compute_hourly_pattern(pop_df: pd.DataFrame) -> pd.Series | None:
    """시간대별 생활인구 정규화 곡선 (대치동)."""
    if pop_df is None or pop_df.empty:
        return None

    # 대치동 행정동코드 필터 (1168060*)
    if "행정동코드" in pop_df.columns:
        pop_df = pop_df.copy()
        pop_df["행정동코드"] = pop_df["행정동코드"].astype(str)
        mask = pop_df["행정동코드"].str.startswith("1168060")
        pop_df = pop_df[mask]

    if pop_df.empty or "시간대" not in pop_df.columns:
        return None

    if "총생활인구" not in pop_df.columns:
        return None

    pop_df = pop_df.copy()
    pop_df["시간대"] = pd.to_numeric(pop_df["시간대"], errors="coerce")
    hourly = pop_df.groupby("시간대")["총생활인구"].mean()

    # 0~1 정규화
    max_val = hourly.max()
    if max_val > 0:
        hourly = hourly / max_val

    return hourly.sort_index()


def load_calibration() -> dict | None:
    """보정 데이터 로드. parquet 없으면 None (기존 하드코딩으로 폴백).

    Returns:
        {"unit_prices": {...}, "visit_multipliers": {...}, "hourly_pattern": Series}
        또는 None
    """
    spending_df = _load_spending_parquets()
    if spending_df is None or spending_df.empty:
        logger.info("매출 parquet 없음 — 기본값 사용")
        return None

    pop_df = _load_population_parquets()

    unit_prices = compute_unit_prices(spending_df)
    visit_multipliers = compute_visit_multipliers(spending_df)
    hourly_pattern = compute_hourly_pattern(pop_df) if pop_df is not None else None

    if not unit_prices and not visit_multipliers:
        return None

    return {
        "unit_prices": unit_prices,
        "visit_multipliers": visit_multipliers,
        "hourly_pattern": hourly_pattern,
        "spending_df": spending_df,
        "population_df": pop_df,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)

    cal = load_calibration()
    if cal:
        print("\n=== 보정 결과 ===")
        print("\n객단가:")
        for k, v in cal["unit_prices"].items():
            print(f"  {k}: {v:,}원")
        print("\n방문 보정계수:")
        for k, v in cal["visit_multipliers"].items():
            print(f"  {k}: {v:.3f}")
        if cal["hourly_pattern"] is not None:
            print("\n시간대 패턴:")
            print(cal["hourly_pattern"])
    else:
        print("보정 데이터 없음 (parquet 파일 필요)")
