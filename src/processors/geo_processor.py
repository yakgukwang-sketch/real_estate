"""행정동코드 매핑 및 좌표-행정동 변환 (핵심 프로세서).

모든 데이터셋을 행정동코드 + 기준연월로 통합하기 위한 지리 매핑.
"""

import json
import logging
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

from config.settings import GEO_DIR

logger = logging.getLogger(__name__)

# 서울시 지하철역 좌표 (주요 역)
SUBWAY_STATION_COORDS: dict[str, tuple[float, float]] = {
    "서울역": (37.5547, 126.9707),
    "시청": (37.5637, 126.9770),
    "종각": (37.5701, 126.9830),
    "종로3가": (37.5712, 126.9916),
    "종로5가": (37.5708, 126.9987),
    "동대문": (37.5712, 127.0095),
    "신설동": (37.5755, 127.0248),
    "강남": (37.4979, 127.0276),
    "역삼": (37.5006, 127.0369),
    "삼성": (37.5089, 127.0631),
    "선릉": (37.5045, 127.0490),
    "교대": (37.4934, 127.0145),
    "서초": (37.4916, 127.0076),
    "방배": (37.4813, 126.9976),
    "사당": (37.4764, 126.9816),
    "이수": (37.4856, 126.9822),
    "잠실": (37.5133, 127.1000),
    "신림": (37.4841, 126.9299),
    "구로디지털단지": (37.4851, 126.9015),
    "가산디지털단지": (37.4818, 126.8828),
    "홍대입구": (37.5571, 126.9241),
    "합정": (37.5497, 126.9136),
    "망원": (37.5560, 126.9102),
    "여의도": (37.5215, 126.9243),
    "여의나루": (37.5268, 126.9327),
    "영등포구청": (37.5246, 126.8961),
    "신촌": (37.5553, 126.9369),
    "이대": (37.5567, 126.9458),
    "아현": (37.5575, 126.9566),
    "충정로": (37.5600, 126.9636),
    "건대입구": (37.5406, 127.0697),
    "성수": (37.5446, 127.0558),
    "왕십리": (37.5614, 127.0382),
    "한양대": (37.5576, 127.0451),
    "뚝섬": (37.5473, 127.0471),
    "압구정": (37.5271, 127.0283),
    "신사": (37.5164, 127.0206),
    "논현": (37.5102, 127.0212),
    "학동": (37.5149, 127.0315),
    "강남구청": (37.5172, 127.0410),
    "청담": (37.5194, 127.0528),
    "삼성중앙": (37.5103, 127.0606),
    "봉은사": (37.5148, 127.0563),
    "목동": (37.5264, 126.8758),
    "오목교": (37.5243, 126.8764),
    "양천구청": (37.5170, 126.8666),
    "노원": (37.6554, 127.0613),
    "상계": (37.6602, 127.0730),
    "마들": (37.6647, 127.0585),
    "수락산": (37.6730, 127.0573),
    "당고개": (37.6781, 127.0466),
    "미아": (37.6137, 127.0300),
    "미아사거리": (37.6132, 127.0297),
    "길음": (37.6037, 127.0250),
    "혜화": (37.5821, 127.0019),
    "동대문역사문화공원": (37.5650, 127.0074),
    "을지로3가": (37.5660, 126.9924),
    "을지로4가": (37.5670, 126.9980),
    "을지로입구": (37.5660, 126.9829),
    "명동": (37.5610, 126.9859),
    "회현": (37.5575, 126.9815),
    "남산": (37.5570, 126.9866),
    "이태원": (37.5346, 126.9943),
    "녹사평": (37.5343, 126.9876),
    "삼각지": (37.5348, 126.9726),
    "숙대입구": (37.5438, 126.9723),
    "공덕": (37.5440, 126.9518),
    "마포": (37.5395, 126.9458),
    "디지털미디어시티": (37.5777, 126.8999),
    "수색": (37.5826, 126.8957),
    "연신내": (37.6189, 126.9214),
    "불광": (37.6110, 126.9298),
    "독바위": (37.6136, 126.9251),
    "구파발": (37.6370, 126.9186),
}


def assign_grid_cell(lat: float, lon: float, resolution_m: float = 500) -> str:
    """좌표를 그리드 셀 ID로 변환."""
    lat_step = resolution_m / 111320.0
    lon_step = resolution_m / (111320.0 * math.cos(math.radians(lat)))
    lat_idx = math.floor(lat / lat_step)
    lon_idx = math.floor(lon / lon_step)
    return f"grid_{lat_idx}_{lon_idx}"


class GeoProcessor:
    """지리 데이터 처리 - 행정동 매핑의 핵심."""

    def __init__(self, geo_dir: Path | None = None):
        self.geo_dir = geo_dir or GEO_DIR
        self._dong_gdf: gpd.GeoDataFrame | None = None
        self._bjd_to_hjd: dict[str, str] | None = None

    @property
    def dong_gdf(self) -> gpd.GeoDataFrame:
        """서울시 행정동 GeoDataFrame (lazy load)."""
        if self._dong_gdf is None:
            self._dong_gdf = self._load_dong_geodata()
        return self._dong_gdf

    def _load_dong_geodata(self) -> gpd.GeoDataFrame:
        """행정동 GeoJSON 로드."""
        geojson_path = self.geo_dir / "seoul_dong.geojson"
        if not geojson_path.exists():
            raise FileNotFoundError(
                f"행정동 GeoJSON 파일이 없습니다: {geojson_path}\n"
                "scripts/seed_geodata.py를 먼저 실행하세요."
            )
        gdf = gpd.read_file(geojson_path)
        gdf = gdf.to_crs(epsg=4326)
        return gdf

    def coord_to_dong(self, lat: float, lon: float) -> dict | None:
        """좌표 → 행정동 정보 반환 (spatial join).

        Returns:
            {"행정동코드": "...", "행정동명": "...", "자치구명": "..."} or None
        """
        point = gpd.GeoDataFrame(
            [{"geometry": Point(lon, lat)}],
            crs="EPSG:4326",
        )
        result = gpd.sjoin(point, self.dong_gdf, how="left", predicate="within")
        if result.empty or pd.isna(result.iloc[0].get("adm_cd")):
            return None
        row = result.iloc[0]
        return {
            "행정동코드": str(row.get("adm_cd", "")),
            "행정동명": str(row.get("adm_nm", "")),
            "자치구명": str(row.get("sgg_nm", "")),
        }

    def coords_to_dong_batch(self, df: pd.DataFrame, lat_col: str = "위도", lon_col: str = "경도") -> pd.DataFrame:
        """DataFrame의 좌표 컬럼으로 행정동 매핑 (벡터화)."""
        valid = df[[lat_col, lon_col]].dropna()
        if valid.empty:
            df["행정동코드"] = None
            df["행정동명"] = None
            return df

        points = gpd.GeoDataFrame(
            valid,
            geometry=gpd.points_from_xy(valid[lon_col], valid[lat_col]),
            crs="EPSG:4326",
        )
        joined = gpd.sjoin(points, self.dong_gdf, how="left", predicate="within")

        df = df.copy()
        df.loc[valid.index, "행정동코드"] = joined.get("adm_cd")
        df.loc[valid.index, "행정동명"] = joined.get("adm_nm")
        return df

    def subway_station_to_dong(self, station_name: str) -> dict | None:
        """지하철역명 → 행정동 매핑."""
        coords = SUBWAY_STATION_COORDS.get(station_name)
        if coords is None:
            logger.warning("좌표 미등록 역: %s", station_name)
            return None
        return self.coord_to_dong(coords[0], coords[1])

    def subway_stations_to_dong_df(self) -> pd.DataFrame:
        """전체 지하철역-행정동 매핑 테이블 생성."""
        records = []
        for station, (lat, lon) in SUBWAY_STATION_COORDS.items():
            dong_info = self.coord_to_dong(lat, lon)
            record = {"역명": station, "위도": lat, "경도": lon}
            if dong_info:
                record.update(dong_info)
            records.append(record)
        return pd.DataFrame(records)

    def load_bjd_to_hjd_mapping(self) -> dict[str, str]:
        """법정동코드 → 행정동코드 매핑 로드."""
        if self._bjd_to_hjd is not None:
            return self._bjd_to_hjd

        mapping_path = self.geo_dir / "bjd_hjd_mapping.json"
        if mapping_path.exists():
            with open(mapping_path, encoding="utf-8") as f:
                self._bjd_to_hjd = json.load(f)
        else:
            logger.warning("법정동-행정동 매핑 파일 없음: %s", mapping_path)
            self._bjd_to_hjd = {}
        return self._bjd_to_hjd

    def bjd_to_hjd(self, bjd_code: str) -> str | None:
        """법정동코드 → 행정동코드 변환."""
        mapping = self.load_bjd_to_hjd_mapping()
        return mapping.get(bjd_code)

    def assign_grid_cells_batch(
        self,
        df: pd.DataFrame,
        lat_col: str = "위도",
        lon_col: str = "경도",
        resolution_m: float = 500,
    ) -> pd.DataFrame:
        """DataFrame에 grid_id 컬럼을 추가 (벡터화)."""
        df = df.copy()
        lat = df[lat_col].values
        lon = df[lon_col].values
        lat_step = resolution_m / 111320.0
        lon_step = resolution_m / (111320.0 * np.cos(np.radians(lat)))
        lat_idx = np.floor(lat / lat_step).astype(int)
        lon_idx = np.floor(lon / lon_step).astype(int)
        df["grid_id"] = [f"grid_{la}_{lo}" for la, lo in zip(lat_idx, lon_idx)]
        return df

    def create_seoul_grid(self, resolution_m: float = 500) -> gpd.GeoDataFrame:
        """서울시 영역을 그리드로 분할."""
        seoul_boundary = self.dong_gdf.union_all()
        minx, miny, maxx, maxy = seoul_boundary.bounds

        lat_step = resolution_m / 111320.0
        mid_lat = (miny + maxy) / 2
        lon_step = resolution_m / (111320.0 * math.cos(math.radians(mid_lat)))

        grid_cells = []
        lat = miny
        while lat < maxy:
            lon = minx
            while lon < maxx:
                cell = box(lon, lat, lon + lon_step, lat + lat_step)
                lat_idx = math.floor(lat / lat_step)
                lon_idx = math.floor(lon / lon_step)
                grid_cells.append({
                    "grid_id": f"grid_{lat_idx}_{lon_idx}",
                    "geometry": cell,
                })
                lon += lon_step
            lat += lat_step

        grid_gdf = gpd.GeoDataFrame(grid_cells, crs="EPSG:4326")
        grid_gdf = gpd.clip(grid_gdf, seoul_boundary)
        return grid_gdf[["grid_id", "geometry"]]
