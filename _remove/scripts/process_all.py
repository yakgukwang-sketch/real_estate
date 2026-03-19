"""전체 데이터 처리 스크립트 - raw → processed Parquet."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from config.settings import RAW_DIR, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def process_subway():
    """지하철 데이터 처리."""
    from src.processors.geo_processor import GeoProcessor
    from src.processors.subway_processor import SubwayProcessor

    files = sorted(RAW_DIR.glob("subway_*.parquet"))
    if not files:
        logger.warning("지하철 원본 파일 없음")
        return

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    logger.info("지하철 원본: %d건", len(df))

    try:
        geo = GeoProcessor()
        processor = SubwayProcessor(geo)
        df = processor.process(df)
        monthly = processor.aggregate_monthly(df)

        output = PROCESSED_DIR / "subway.parquet"
        monthly.to_parquet(output, index=False)
        logger.info("지하철 처리 완료: %d건 → %s", len(monthly), output)
    except FileNotFoundError as e:
        logger.warning("GeoJSON 없이 기본 처리: %s", e)
        output = PROCESSED_DIR / "subway.parquet"
        df.to_parquet(output, index=False)


def process_realestate():
    """부동산 데이터 처리."""
    from src.processors.realestate_processor import RealEstateProcessor

    files = sorted(RAW_DIR.glob("realestate_*.parquet"))
    if not files:
        logger.warning("부동산 원본 파일 없음")
        return

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    logger.info("부동산 원본: %d건", len(df))

    processor = RealEstateProcessor()
    df = processor.process(df)
    monthly = processor.aggregate_monthly(df)

    output = PROCESSED_DIR / "realestate.parquet"
    monthly.to_parquet(output, index=False)
    logger.info("부동산 처리 완료: %d건 → %s", len(monthly), output)


def process_commercial():
    """상가업소 데이터 처리."""
    from src.processors.commercial_processor import CommercialProcessor

    path = RAW_DIR / "commercial.parquet"
    if not path.exists():
        logger.warning("상가 원본 파일 없음")
        return

    df = pd.read_parquet(path)
    logger.info("상가 원본: %d건", len(df))

    try:
        processor = CommercialProcessor()
        df = processor.process(df)
    except FileNotFoundError:
        logger.warning("GeoJSON 없이 기본 처리")

    output = PROCESSED_DIR / "commercial.parquet"
    df.to_parquet(output, index=False)
    logger.info("상가 처리 완료: %d건 → %s", len(df), output)


def process_population():
    """인구 데이터 처리."""
    from src.processors.population_processor import PopulationProcessor

    files = sorted(RAW_DIR.glob("population_*.parquet"))
    if not files:
        logger.warning("인구 원본 파일 없음")
        return

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    logger.info("인구 원본: %d건", len(df))

    processor = PopulationProcessor()
    monthly = processor.aggregate_monthly(df)

    output = PROCESSED_DIR / "population.parquet"
    monthly.to_parquet(output, index=False)
    logger.info("인구 처리 완료: %d건 → %s", len(monthly), output)


def process_spending():
    """매출 데이터 처리."""
    files = sorted(RAW_DIR.glob("spending_*.parquet"))
    if not files:
        logger.warning("매출 원본 파일 없음")
        return

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    output = PROCESSED_DIR / "spending.parquet"
    df.to_parquet(output, index=False)
    logger.info("매출 처리 완료: %d건 → %s", len(df), output)


def process_bus():
    """버스 데이터 처리."""
    from src.processors.geo_processor import GeoProcessor

    files = sorted(RAW_DIR.glob("bus_*.parquet"))
    if not files:
        logger.warning("버스 원본 파일 없음")
        return

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    logger.info("버스 원본: %d건", len(df))

    # 정류장 좌표가 있으면 행정동 매핑
    if "위도" in df.columns and "경도" in df.columns:
        try:
            geo = GeoProcessor()
            df = geo.coords_to_dong_batch(df, lat_col="위도", lon_col="경도")
        except FileNotFoundError:
            logger.warning("GeoJSON 없이 기본 처리")

    output = PROCESSED_DIR / "bus.parquet"
    df.to_parquet(output, index=False)
    logger.info("버스 처리 완료: %d건 → %s", len(df), output)


def create_integrated():
    """통합 데이터 생성 - 행정동코드 + 연월 기준."""
    dfs = {}
    for name in ["subway", "realestate", "population", "spending", "bus"]:
        path = PROCESSED_DIR / f"{name}.parquet"
        if path.exists():
            dfs[name] = pd.read_parquet(path)

    if not dfs:
        logger.warning("통합할 데이터 없음")
        return

    base = None
    for name, df in dfs.items():
        if "행정동코드" not in df.columns or "연월" not in df.columns:
            continue
        agg = df.groupby(["행정동코드", "연월"]).first().reset_index()
        if base is None:
            base = agg
        else:
            base = base.merge(agg, on=["행정동코드", "연월"], how="outer", suffixes=("", f"_{name}"))

    if base is not None:
        output = PROCESSED_DIR / "integrated.parquet"
        base.to_parquet(output, index=False)
        logger.info("통합 데이터: %d건 → %s", len(base), output)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    processors = [
        ("지하철", process_subway),
        ("부동산", process_realestate),
        ("상가", process_commercial),
        ("인구", process_population),
        ("매출", process_spending),
        ("버스", process_bus),
    ]

    for name, func in processors:
        logger.info("=== %s 처리 시작 ===", name)
        try:
            func()
        except Exception:
            logger.exception("%s 처리 실패", name)

    logger.info("=== 통합 데이터 생성 ===")
    create_integrated()

    logger.info("전체 데이터 처리 완료!")


if __name__ == "__main__":
    main()
