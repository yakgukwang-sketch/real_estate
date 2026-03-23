"""영등포역 상권 데이터 수집 스크립트.

수집 항목:
1. 도보 네트워크 (서울시 TbTraficWlkNet — 영등포구)
2. 횡단보도 (서울시 tbTraficCrsng — 영등포구)
3. 상가 건물 (소상공인 반경 검색 — 영등포역 1km)
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings, RAW_DIR
from src.collectors.commercial_collector import CommercialCollector
from src.utils.api_client import ApiClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 영등포구 코드
YEONGDEUNGPO_GU_CODE = "11560"

# 영등포역 중심 좌표
CENTER_LAT, CENTER_LON = 37.5158, 126.9074


def collect_walk_network():
    """서울시 도보 네트워크 수집 (영등포구)."""
    output = RAW_DIR / "walk_network_yeongdeungpo.json"
    if output.exists():
        logger.info("도보 네트워크 이미 존재: %s", output)
        return

    client = ApiClient()
    api_key = settings.seoul_open_api_key
    endpoint = settings.walk_network_endpoint
    base = settings.seoul_api_base

    all_rows = []
    start = 1
    batch = 1000

    while True:
        end = start + batch - 1
        url = f"{base}/{api_key}/json/{endpoint}/{start}/{end}/영등포구"
        logger.info("도보 네트워크 수집: %d~%d", start, end)

        try:
            data = client.get_json(url)
        except Exception as e:
            logger.error("API 오류: %s", e)
            break

        result_key = endpoint
        if result_key not in data:
            # 응답 키 확인
            for k in data:
                if k not in ("RESULT",):
                    result_key = k
                    break
            else:
                logger.info("더 이상 데이터 없음")
                break

        section = data[result_key]
        total = int(section.get("list_total_count", 0))
        rows = section.get("row", [])

        if not rows:
            break

        all_rows.extend(rows)
        logger.info("  %d건 수집 (누적 %d/%d)", len(rows), len(all_rows), total)

        if len(all_rows) >= total:
            break
        start = end + 1

    if all_rows:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=2)
        logger.info("도보 네트워크 저장: %d건 → %s", len(all_rows), output)
    else:
        logger.warning("도보 네트워크 수집 실패: 0건")


def collect_crosswalk():
    """서울시 횡단보도 수집 (영등포구)."""
    output = RAW_DIR / "crosswalk_yeongdeungpo.json"
    if output.exists():
        logger.info("횡단보도 이미 존재: %s", output)
        return

    client = ApiClient()
    api_key = settings.seoul_open_api_key
    endpoint = settings.crosswalk_endpoint
    base = settings.seoul_api_base

    all_rows = []
    start = 1
    batch = 1000

    while True:
        end = start + batch - 1
        url = f"{base}/{api_key}/json/{endpoint}/{start}/{end}/영등포구"
        logger.info("횡단보도 수집: %d~%d", start, end)

        try:
            data = client.get_json(url)
        except Exception as e:
            logger.error("API 오류: %s", e)
            break

        result_key = endpoint
        if result_key not in data:
            for k in data:
                if k not in ("RESULT",):
                    result_key = k
                    break
            else:
                break

        section = data[result_key]
        total = int(section.get("list_total_count", 0))
        rows = section.get("row", [])

        if not rows:
            break

        all_rows.extend(rows)
        logger.info("  %d건 수집 (누적 %d/%d)", len(rows), len(all_rows), total)

        if len(all_rows) >= total:
            break
        start = end + 1

    if all_rows:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=2)
        logger.info("횡단보도 저장: %d건 → %s", len(all_rows), output)
    else:
        logger.warning("횡단보도 수집 실패: 0건")


def collect_stores():
    """영등포역 반경 1km 상가 수집 및 건물 분류."""
    stores_output = RAW_DIR / "stores_yeongdeungpo_1km.json"
    buildings_output = RAW_DIR / "buildings_classified_yeongdeungpo.json"

    if buildings_output.exists():
        logger.info("건물 분류 이미 존재: %s", buildings_output)
        return

    # 1) 상가 수집
    if stores_output.exists():
        logger.info("상가 데이터 이미 존재, 로드 중: %s", stores_output)
        with open(stores_output, encoding="utf-8") as f:
            stores_data = json.load(f)
    else:
        collector = CommercialCollector()
        df = collector.collect_radius(cx=CENTER_LON, cy=CENTER_LAT, radius=1000)
        if df.empty:
            logger.warning("상가 수집 실패: 0건")
            return

        stores_data = df.to_dict("records")
        stores_output.parent.mkdir(parents=True, exist_ok=True)
        with open(stores_output, "w", encoding="utf-8") as f:
            json.dump(stores_data, f, ensure_ascii=False, indent=2)
        logger.info("상가 저장: %d건 → %s", len(stores_data), stores_output)

    # 2) 건물별 분류
    import pandas as pd
    df = pd.DataFrame(stores_data)

    lat_col = "위도" if "위도" in df.columns else "lat"
    lon_col = "경도" if "경도" in df.columns else "lon"
    name_col = "건물명" if "건물명" in df.columns else "bldNm"
    addr_col = "도로명주소" if "도로명주소" in df.columns else "rdNmAdr"
    cat_col = "대분류명" if "대분류명" in df.columns else "indsLclsNm"

    if lat_col not in df.columns:
        logger.warning("위도 컬럼 없음, 분류 건너뜀")
        return

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    # 건물 그룹핑 (소수점 4자리 기준으로 같은 건물 판단)
    df["_lat_r"] = df[lat_col].round(4)
    df["_lon_r"] = df[lon_col].round(4)

    buildings = []
    for (lat_r, lon_r), group in df.groupby(["_lat_r", "_lon_r"]):
        bld_nm = ""
        rdnm_adr = ""
        if name_col in group.columns:
            names = group[name_col].dropna()
            if not names.empty:
                bld_nm = names.mode().iloc[0] if len(names.mode()) > 0 else names.iloc[0]
        if addr_col in group.columns:
            addrs = group[addr_col].dropna()
            if not addrs.empty:
                rdnm_adr = addrs.iloc[0]

        categories = {}
        if cat_col in group.columns:
            for cat_val in group[cat_col].dropna():
                categories[cat_val] = categories.get(cat_val, 0) + 1

        buildings.append({
            "bld_nm": bld_nm or rdnm_adr,
            "rdnm_adr": rdnm_adr,
            "lat": float(group[lat_col].mean()),
            "lon": float(group[lon_col].mean()),
            "store_count": len(group),
            "categories": categories,
        })

    buildings_output.parent.mkdir(parents=True, exist_ok=True)
    with open(buildings_output, "w", encoding="utf-8") as f:
        json.dump(buildings, f, ensure_ascii=False, indent=2)
    logger.info("건물 분류 저장: %d개 → %s", len(buildings), buildings_output)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("영등포역 상권 데이터 수집 시작")
    logger.info("=" * 60)

    collect_walk_network()
    collect_crosswalk()
    collect_stores()

    logger.info("=" * 60)
    logger.info("수집 완료")
    logger.info("=" * 60)
