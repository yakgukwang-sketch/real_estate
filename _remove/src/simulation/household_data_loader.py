"""세대수 데이터 → 시뮬레이션 입력 변환 모듈.

수집된 세대수(행안부/국토부) + 청약 데이터를 시뮬레이션에서 사용할
행정동별 인구/고용/주거유형 분포로 변환합니다.
"""

import logging
import math
from pathlib import Path

import pandas as pd

from config.settings import RAW_DIR
from src.processors.geo_processor import SUBWAY_STATION_COORDS, DONG_CENTROIDS

logger = logging.getLogger(__name__)

# ── 주거유형별 프로파일 ──
HOUSING_TYPE_PROFILES = {
    "apt": {
        "label": "아파트",
        "avg_household_size": 2.8,
        "income_weights": {1: 0.08, 2: 0.18, 3: 0.32, 4: 0.27, 5: 0.15},
        "spending_mult": 1.0,
        "evening_out_mult": 1.0,
    },
    "officetel": {
        "label": "오피스텔",
        "avg_household_size": 1.3,
        "income_weights": {1: 0.15, 2: 0.30, 3: 0.30, 4: 0.18, 5: 0.07},
        "spending_mult": 0.75,
        "evening_out_mult": 1.3,  # 1인가구 외식 많음
    },
    "villa": {
        "label": "빌라/다세대",
        "avg_household_size": 2.2,
        "income_weights": {1: 0.25, 2: 0.35, 3: 0.25, 4: 0.12, 5: 0.03},
        "spending_mult": 0.65,
        "evening_out_mult": 0.8,
    },
}

# ── 동 이름 별칭 매핑 (시뮬레이션용 이름 ↔ API 시군구명) ──
# 시뮬레이션에서는 "강남동" 등 약칭을 사용하고,
# API에서는 "강남구" 단위로 데이터가 들어옴
GU_TO_DONG_MAP: dict[str, list[str]] = {
    "강남구": ["강남동", "역삼동", "삼성동", "논현동", "압구정동", "청담동", "대치동", "선릉동"],
    "서초구": ["서초동", "방배동", "사당동", "교대동"],
    "송파구": ["잠실동", "송파동"],
    "강동구": ["천호동", "길동"],
    "마포구": ["마포동", "홍대동", "신촌동", "연남동", "합정동", "상암동", "망원동", "공덕동"],
    "영등포구": ["영등포동", "여의도동", "문래동"],
    "구로구": ["구로동", "가산동"],
    "용산구": ["이태원동", "용산동"],
    "중구": ["명동", "을지로", "충무로", "남산동", "중구동"],
    "종로구": ["종로동", "광화문"],
    "성동구": ["성수동", "왕십리동", "뚝섬"],
    "광진구": ["건대동", "자양동"],
    "노원구": ["노원동", "상계동"],
    "강북구": ["수유동", "미아동"],
    "성북구": ["길음동"],
    "동대문구": ["회기동", "청량리", "동대문동"],
    "중랑구": ["면목동"],
    "관악구": ["신림동", "봉천동"],
    "동작구": ["사당동", "신대방동"],
    "양천구": ["목동"],
    "강서구": ["화곡동", "발산동", "등촌동"],
    "은평구": ["불광동", "연신내동"],
}

# 역 매핑: 동 이름 → 가장 가까운 지하철역
DONG_NEAREST_STATION: dict[str, str] = {
    "강남동": "강남", "역삼동": "역삼", "서초동": "서초",
    "삼성동": "삼성", "잠실동": "잠실", "선릉동": "선릉",
    "교대동": "교대", "방배동": "방배", "사당동": "사당",
    "신림동": "신림", "구로동": "구로디지털단지", "가산동": "가산디지털단지",
    "홍대동": "홍대입구", "합정동": "합정", "망원동": "망원",
    "여의도동": "여의도", "영등포동": "영등포구청",
    "신촌동": "신촌", "종로동": "종각", "명동": "명동",
    "이태원동": "이태원", "성수동": "성수", "건대동": "건대입구",
    "왕십리동": "왕십리", "압구정동": "압구정", "논현동": "논현",
    "청담동": "청담", "목동": "목동", "노원동": "노원",
    "상계동": "상계", "미아동": "미아", "길음동": "길음",
    "공덕동": "공덕", "마포동": "마포", "용산동": "서울역",
    "중구동": "시청", "동대문동": "동대문", "불광동": "불광",
    "연신내동": "연신내", "뚝섬": "뚝섬",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리 (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_subway_distance_matrix() -> dict[str, dict[str, float]]:
    """동-동 간 지하철역 기반 거리 행렬.

    각 동의 최근접 지하철역 좌표를 기준으로 거리를 계산.
    Returns:
        {home_dong: {work_dong: distance_km}}
    """
    dong_station_coords: dict[str, tuple[float, float]] = {}

    for dong, station in DONG_NEAREST_STATION.items():
        if station in SUBWAY_STATION_COORDS:
            dong_station_coords[dong] = SUBWAY_STATION_COORDS[station]
        elif dong in DONG_CENTROIDS:
            dong_station_coords[dong] = DONG_CENTROIDS[dong]

    # 좌표만 있는 동도 포함
    for dong, coords in DONG_CENTROIDS.items():
        if dong not in dong_station_coords:
            dong_station_coords[dong] = coords

    dongs = list(dong_station_coords.keys())
    matrix: dict[str, dict[str, float]] = {}
    for d1 in dongs:
        lat1, lon1 = dong_station_coords[d1]
        row: dict[str, float] = {}
        for d2 in dongs:
            lat2, lon2 = dong_station_coords[d2]
            row[d2] = _haversine_km(lat1, lon1, lat2, lon2)
        matrix[d1] = row

    return matrix


def compute_work_weights_by_distance(
    home_dong: str,
    dong_employment: dict[str, int],
    distance_matrix: dict[str, dict[str, float]],
    decay_power: float = 1.5,
) -> dict[str, float]:
    """거리 감쇠 기반 직장동 가중치 계산.

    weight(j) = employment(j) / (1 + distance_km)^decay_power
    """
    if home_dong not in distance_matrix:
        # fallback: 균등 분배
        total = sum(dong_employment.values()) or 1
        return {d: v / total for d, v in dong_employment.items()}

    distances = distance_matrix[home_dong]
    weights: dict[str, float] = {}

    for dong, emp in dong_employment.items():
        dist = distances.get(dong, 15.0)  # 매핑 없으면 15km 가정
        w = emp / (1 + dist) ** decay_power
        weights[dong] = w

    total_w = sum(weights.values()) or 1.0
    return {d: w / total_w for d, w in weights.items()}


class HouseholdDataLoader:
    """수집된 세대수 데이터를 시뮬레이션 입력으로 변환."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or RAW_DIR

    def load_household_summary(self) -> pd.DataFrame:
        """행안부 세대현황 요약 데이터 로드."""
        path = self.data_dir / "household_summary.parquet"
        if path.exists():
            return pd.read_parquet(path)
        logger.warning("세대현황 요약 데이터 없음: %s", path)
        return pd.DataFrame()

    def load_apt_household(self) -> pd.DataFrame:
        """국토부 공동주택 세대수 데이터 로드."""
        path = self.data_dir / "apt_household.parquet"
        if path.exists():
            return pd.read_parquet(path)
        logger.warning("공동주택 세대수 데이터 없음: %s", path)
        return pd.DataFrame()

    def load_household_detail(self) -> pd.DataFrame:
        """행안부 세대현황 상세 데이터 로드."""
        path = self.data_dir / "household.parquet"
        if path.exists():
            return pd.read_parquet(path)
        logger.warning("세대현황 상세 데이터 없음: %s", path)
        return pd.DataFrame()

    def build_dong_population(
        self,
        fallback_population: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """행정동별 거주인구 생성.

        세대수 데이터가 있으면 세대수 × 평균가구원수로 계산,
        없으면 fallback_population 사용.
        """
        summary = self.load_household_summary()

        if summary.empty:
            logger.info("세대수 데이터 없음 → fallback 인구 사용")
            return fallback_population or {}

        dong_pop: dict[str, int] = {}

        for _, row in summary.iterrows():
            gu_name = row.get("시군구명", "")
            total_pop = int(row.get("총인구수", 0))
            total_hh = int(row.get("총세대수", 0))

            if not gu_name or total_pop == 0:
                continue

            # 구 이름에서 "서울특별시 " 제거
            gu_short = gu_name.replace("서울특별시 ", "").strip()

            # 해당 구의 시뮬레이션 동 목록
            sim_dongs = GU_TO_DONG_MAP.get(gu_short, [])
            if not sim_dongs:
                continue

            # 인구를 동 개수로 균등 분배 (추후 상세 데이터로 개선 가능)
            per_dong = total_pop // len(sim_dongs)
            for dong in sim_dongs:
                dong_pop[dong] = per_dong

        if dong_pop:
            logger.info("세대수 데이터 기반 인구 생성: %d개 동", len(dong_pop))

        # fallback으로 빠진 동 보완
        if fallback_population:
            for dong, pop in fallback_population.items():
                if dong not in dong_pop:
                    dong_pop[dong] = pop

        return dong_pop

    def build_housing_type_distribution(self) -> dict[str, dict[str, float]]:
        """행정동별 주거유형 비율 추정.

        아파트 세대수 데이터가 있으면 아파트 비율 계산,
        없으면 구 특성 기반 기본값 사용.

        Returns:
            {dong_name: {"apt": 0.6, "officetel": 0.2, "villa": 0.2}}
        """
        apt_df = self.load_apt_household()
        summary = self.load_household_summary()

        # 구별 아파트 세대수 집계
        gu_apt_count: dict[str, int] = {}
        if not apt_df.empty and "자치구" in apt_df.columns and "세대수" in apt_df.columns:
            agg = apt_df.groupby("자치구")["세대수"].sum()
            gu_apt_count = {str(k): int(v) for k, v in agg.items()}

        # 구별 총 세대수
        gu_total_hh: dict[str, int] = {}
        if not summary.empty and "시군구명" in summary.columns:
            for _, row in summary.iterrows():
                gu = row["시군구명"].replace("서울특별시 ", "").strip()
                gu_total_hh[gu] = int(row.get("총세대수", 0))

        result: dict[str, dict[str, float]] = {}

        for gu, dongs in GU_TO_DONG_MAP.items():
            apt_hh = gu_apt_count.get(gu, 0)
            total_hh = gu_total_hh.get(gu, 0)

            if total_hh > 0 and apt_hh > 0:
                apt_ratio = min(apt_hh / total_hh, 0.85)
                remaining = 1.0 - apt_ratio
                # 남은 비율을 오피스텔:빌라 = 3:7로 분배
                ofc_ratio = remaining * 0.3
                villa_ratio = remaining * 0.7
            else:
                # 구 특성 기반 기본값
                apt_ratio, ofc_ratio, villa_ratio = self._default_housing_ratio(gu)

            for dong in dongs:
                result[dong] = {
                    "apt": round(apt_ratio, 3),
                    "officetel": round(ofc_ratio, 3),
                    "villa": round(villa_ratio, 3),
                }

        return result

    @staticmethod
    def _default_housing_ratio(gu_name: str) -> tuple[float, float, float]:
        """구 특성 기반 주거유형 기본 비율."""
        # 아파트 비중 높은 구
        high_apt = {"송파구", "노원구", "강동구", "양천구", "강서구", "도봉구"}
        # 오피스텔 비중 높은 구
        high_ofc = {"강남구", "서초구", "마포구", "영등포구", "중구"}
        # 빌라/다세대 비중 높은 구
        high_villa = {"관악구", "동작구", "성북구", "강북구", "중랑구", "금천구"}

        if gu_name in high_apt:
            return 0.65, 0.10, 0.25
        elif gu_name in high_ofc:
            return 0.45, 0.25, 0.30
        elif gu_name in high_villa:
            return 0.30, 0.10, 0.60
        else:
            return 0.50, 0.15, 0.35

    def build_simulation_input(
        self,
        fallback_population: dict[str, int] | None = None,
        fallback_employment: dict[str, int] | None = None,
    ) -> dict:
        """시뮬레이션에 필요한 모든 입력 데이터를 한번에 구성.

        Returns:
            {
                "dong_population": {dong: pop},
                "dong_employment": {dong: emp},
                "housing_distribution": {dong: {type: ratio}},
                "distance_matrix": {dong: {dong: km}},
            }
        """
        dong_pop = self.build_dong_population(fallback_population)
        housing_dist = self.build_housing_type_distribution()
        distance_matrix = compute_subway_distance_matrix()

        # 고용인구는 현재 실데이터 없으므로 fallback 사용
        dong_emp = fallback_employment or {}
        # fallback에도 없는 동은 인구의 0.8배로 추정
        for dong in dong_pop:
            if dong not in dong_emp:
                dong_emp[dong] = int(dong_pop[dong] * 0.8)

        return {
            "dong_population": dong_pop,
            "dong_employment": dong_emp,
            "housing_distribution": housing_dist,
            "distance_matrix": distance_matrix,
        }

    def get_data_status(self) -> dict[str, bool]:
        """각 데이터 소스의 존재 여부 확인."""
        return {
            "household_summary": (self.data_dir / "household_summary.parquet").exists(),
            "household_detail": (self.data_dir / "household.parquet").exists(),
            "apt_household": (self.data_dir / "apt_household.parquet").exists(),
            "subscription_apt": (self.data_dir / "subscription_apt.parquet").exists(),
            "subscription_officetel": (self.data_dir / "subscription_officetel.parquet").exists(),
        }
