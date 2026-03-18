"""전체 데이터 수집 스크립트."""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def collect_subway(year: int, month: int):
    """지하철 승하차 데이터 수집."""
    from src.collectors.subway_collector import SubwayCollector

    collector = SubwayCollector()
    df = collector.collect(year=year, month=month)
    if not df.empty:
        output = RAW_DIR / f"subway_{year}{month:02d}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output, index=False)
        logger.info("지하철: %d건 → %s", len(df), output)
    return df


def collect_realestate(year: int, month: int):
    """부동산 실거래가 수집."""
    from src.collectors.realestate_collector import RealEstateCollector

    collector = RealEstateCollector()
    for ptype in ["apt", "villa", "officetel"]:
        df = collector.collect(year=year, month=month, property_type=ptype)
        if not df.empty:
            output = RAW_DIR / f"realestate_{ptype}_{year}{month:02d}.parquet"
            output.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(output, index=False)
            logger.info("%s: %d건 → %s", ptype, len(df), output)


def collect_commercial():
    """상가업소 수집."""
    from src.collectors.commercial_collector import CommercialCollector

    collector = CommercialCollector()
    df = collector.collect_all_seoul()
    if not df.empty:
        # 빈 문자열이 포함된 object 컬럼을 string 타입으로 변환
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].replace("", pd.NA).astype("string")
        output = RAW_DIR / "commercial.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output, index=False)
        logger.info("상가: %d건 → %s", len(df), output)


def collect_population(year: int, month: int):
    """생활인구 수집."""
    from src.collectors.population_collector import PopulationCollector

    collector = PopulationCollector()
    df = collector.collect(year=year, month=month)
    if not df.empty:
        output = RAW_DIR / f"population_{year}{month:02d}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output, index=False)
        logger.info("생활인구: %d건 → %s", len(df), output)


def collect_spending(year: int, quarter: int):
    """추정매출 수집."""
    from src.collectors.spending_collector import SpendingCollector

    collector = SpendingCollector()
    df = collector.collect(year=year, quarter=quarter)
    if not df.empty:
        output = RAW_DIR / f"spending_{year}Q{quarter}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output, index=False)
        logger.info("추정매출: %d건 → %s", len(df), output)


def collect_bus(year: int, month: int):
    """버스 승하차 데이터 수집."""
    from src.collectors.bus_collector import BusCollector

    collector = BusCollector()
    df = collector.collect_station_summary(year, month)
    if not df.empty:
        output = RAW_DIR / f"bus_{year}{month:02d}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output, index=False)
        logger.info("버스: %d건 → %s", len(df), output)
    return df


def collect_live():
    """실시간 인구/상권 데이터 수집."""
    from src.collectors.live_population_collector import LivePopulationCollector
    from src.collectors.live_commercial_collector import LiveCommercialCollector

    pop_collector = LivePopulationCollector()
    pop_df, pop_fcst_df = pop_collector.collect_all()
    if not pop_df.empty:
        output = RAW_DIR / "live_population.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        pop_df.to_parquet(output, index=False)
        logger.info("실시간 인구: %d건 → %s", len(pop_df), output)

    comm_collector = LiveCommercialCollector()
    comm_df, comm_detail_df = comm_collector.collect_all()
    if not comm_df.empty:
        output = RAW_DIR / "live_commercial.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        comm_df.to_parquet(output, index=False)
        logger.info("실시간 상권: %d건 → %s", len(comm_df), output)


def collect_live_snapshot():
    """실시간 인구 스냅샷 1회 누적 수집.

    1시간마다 실행하면 하루 24개 스냅샷이 축적됩니다.
    축적된 데이터로 시간대별 유동 패턴을 분석할 수 있습니다.
    """
    from src.collectors.live_snapshot_collector import LiveSnapshotCollector

    collector = LiveSnapshotCollector()
    df = collector.collect_and_save()
    if not df.empty:
        logger.info("스냅샷 누적: %d개 장소 (총 %d회 누적)", len(df), collector.get_snapshot_count())


def main():
    parser = argparse.ArgumentParser(description="데이터 수집")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--target", type=str, default="all",
                        choices=["all", "subway", "realestate", "commercial",
                                 "population", "spending", "bus", "live", "live-snapshot"])
    args = parser.parse_args()

    if not settings.seoul_open_api_key and not settings.data_go_kr_api_key:
        logger.error("API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    targets = {
        "subway": lambda: collect_subway(args.year, args.month),
        "realestate": lambda: collect_realestate(args.year, args.month),
        "commercial": collect_commercial,
        "population": lambda: collect_population(args.year, args.month),
        "spending": lambda: collect_spending(args.year, (args.month - 1) // 3 + 1),
        "bus": lambda: collect_bus(args.year, args.month),
        "live": collect_live,
        "live-snapshot": collect_live_snapshot,
    }

    if args.target == "all":
        for name, func in targets.items():
            logger.info("=== %s 수집 시작 ===", name)
            try:
                func()
            except Exception:
                logger.exception("%s 수집 실패", name)
    else:
        targets[args.target]()

    logger.info("데이터 수집 완료!")


if __name__ == "__main__":
    main()
