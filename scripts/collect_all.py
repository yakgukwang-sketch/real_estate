"""전체 데이터 수집 스크립트."""

import argparse
import logging
import sys
from pathlib import Path

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
    for ptype in ["apt", "villa"]:
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


def main():
    parser = argparse.ArgumentParser(description="데이터 수집")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--target", type=str, default="all",
                        choices=["all", "subway", "realestate", "commercial", "population", "spending"])
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
