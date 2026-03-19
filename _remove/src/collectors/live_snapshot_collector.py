"""실시간 인구 스냅샷 누적 수집기.

일반 LivePopulationCollector는 한 시점만 가져오지만,
이 모듈은 수집할 때마다 타임스탬프와 함께 누적 저장하여
시간대별 인구 변화 패턴을 축적합니다.

사용법:
    # 1시간마다 실행하면 하루 24개 스냅샷 축적
    python -c "from src.collectors.live_snapshot_collector import LiveSnapshotCollector; LiveSnapshotCollector().collect_and_save()"

    # 또는 collect_all.py에서:
    python scripts/collect_all.py --target live-snapshot
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import RAW_DIR
from src.collectors.live_population_collector import LivePopulationCollector

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = RAW_DIR / "live_snapshots"


class LiveSnapshotCollector:
    """실시간 인구 스냅샷을 타임스탬프와 함께 누적 저장."""

    def __init__(self, snapshot_dir: Path | None = None):
        self.snapshot_dir = snapshot_dir or SNAPSHOT_DIR
        self.collector = LivePopulationCollector()

    def collect_and_save(self) -> pd.DataFrame:
        """현재 시점 스냅샷을 수집하여 parquet로 저장.

        파일명: live_snapshot_YYYYMMDD_HH.parquet
        매 시간마다 호출하면 하루 24개 파일 축적.
        """
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M")

        summary_df, forecast_df = self.collector.collect_all()
        if summary_df.empty:
            logger.warning("스냅샷 수집 실패: 데이터 없음")
            return pd.DataFrame()

        # 수집 타임스탬프 추가
        summary_df["수집시각"] = now.isoformat()
        summary_df["수집시간"] = now.hour
        summary_df["수집날짜"] = now.strftime("%Y-%m-%d")

        # 인구 중간값 계산 (최소~최대의 평균)
        if "인구_최소" in summary_df.columns and "인구_최대" in summary_df.columns:
            summary_df["추정인구"] = (
                (summary_df["인구_최소"].fillna(0) + summary_df["인구_최대"].fillna(0)) / 2
            ).astype(int)

        # 저장
        output = self.snapshot_dir / f"live_snapshot_{timestamp}.parquet"
        summary_df.to_parquet(output, index=False)
        logger.info("스냅샷 저장: %d개 장소, %s", len(summary_df), output)

        # 예측 데이터도 저장
        if not forecast_df.empty:
            forecast_df["수집시각"] = now.isoformat()
            fcst_output = self.snapshot_dir / f"live_forecast_{timestamp}.parquet"
            forecast_df.to_parquet(fcst_output, index=False)

        return summary_df

    def load_all_snapshots(self) -> pd.DataFrame:
        """누적된 모든 스냅샷을 하나의 DataFrame으로 로드."""
        files = sorted(self.snapshot_dir.glob("live_snapshot_*.parquet"))
        if not files:
            return pd.DataFrame()

        frames = [pd.read_parquet(f) for f in files]
        df = pd.concat(frames, ignore_index=True)
        logger.info("총 %d개 스냅샷 로드 (%d건)", len(files), len(df))
        return df

    def load_snapshots_for_date(self, date_str: str) -> pd.DataFrame:
        """특정 날짜의 스냅샷만 로드.

        Args:
            date_str: "YYYYMMDD" 형식
        """
        pattern = f"live_snapshot_{date_str}_*.parquet"
        files = sorted(self.snapshot_dir.glob(pattern))
        if not files:
            return pd.DataFrame()
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    def get_snapshot_dates(self) -> list[str]:
        """수집된 날짜 목록."""
        files = sorted(self.snapshot_dir.glob("live_snapshot_*.parquet"))
        dates = set()
        for f in files:
            # live_snapshot_YYYYMMDD_HHMM.parquet
            parts = f.stem.split("_")
            if len(parts) >= 3:
                dates.add(parts[2])  # YYYYMMDD
        return sorted(dates)

    def get_snapshot_count(self) -> int:
        """누적 스냅샷 수."""
        return len(list(self.snapshot_dir.glob("live_snapshot_*.parquet")))
