"""좌표 변환 및 거리 계산 유틸리티."""

import math

import numpy as np


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이의 거리를 km 단위로 계산 (Haversine 공식)."""
    R = 6371.0  # 지구 반지름 (km)
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_vectorized(
    lat1: np.ndarray, lon1: np.ndarray,
    lat2: np.ndarray, lon2: np.ndarray,
) -> np.ndarray:
    """벡터화된 Haversine 거리 계산 (km)."""
    R = 6371.0
    lat1_r, lat2_r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def epsg4326_to_5179(lon: float, lat: float) -> tuple[float, float]:
    """WGS84(EPSG:4326) → Korea TM(EPSG:5179) 근사 변환.

    정밀한 변환이 필요하면 pyproj를 사용하세요.
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
        return transformer.transform(lon, lat)
    except ImportError:
        # 서울 중심 근사 변환 (오차 ~수십m)
        x = (lon - 127.0) * 88804.0 + 953898.0
        y = (lat - 37.5) * 111320.0 + 1952050.0
        return x, y
