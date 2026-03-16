"""서울시 행정동 GeoJSON 다운로드 및 초기 설정."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from config.settings import GEO_DIR


def download_seoul_dong_geojson():
    """서울시 행정동 경계 GeoJSON 다운로드."""
    GEO_DIR.mkdir(parents=True, exist_ok=True)

    output_path = GEO_DIR / "seoul_dong.geojson"
    if output_path.exists():
        print(f"이미 존재: {output_path}")
        return

    # 서울시 행정동 경계 GeoJSON (GitHub 공개 데이터)
    urls = [
        "https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json",
        "https://raw.githubusercontent.com/vuski/admdongkor/master/ver20230701/HangJeongDong_ver20230701.geojson",
    ]

    for url in urls:
        try:
            print(f"다운로드 시도: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # 서울만 필터링 (필요 시)
            if "features" in data:
                seoul_features = []
                for feat in data["features"]:
                    props = feat.get("properties", {})
                    # 다양한 키 이름 대응
                    code = str(
                        props.get("adm_cd", "")
                        or props.get("ADM_CD", "")
                        or props.get("code", "")
                        or props.get("SIG_CD", "")
                        or ""
                    )
                    name = str(
                        props.get("adm_nm", "")
                        or props.get("name", "")
                        or props.get("ADM_NM", "")
                        or props.get("SIG_KOR_NM", "")
                        or ""
                    )
                    # 서울 코드는 11로 시작
                    if code.startswith("11") or "서울" in name:
                        # 속성 표준화
                        feat["properties"]["adm_cd"] = code
                        feat["properties"]["adm_nm"] = name
                        seoul_features.append(feat)

                if seoul_features:
                    data["features"] = seoul_features
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"저장 완료: {output_path} ({len(seoul_features)}개 행정동)")
                    return
                else:
                    print("서울 데이터를 찾지 못했습니다. 전체 저장...")
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"저장 완료: {output_path}")
                    return

        except Exception as e:
            print(f"실패: {e}")
            continue

    print("모든 다운로드 소스가 실패했습니다.")
    print("수동으로 GeoJSON을 data/geo/seoul_dong.geojson에 배치하세요.")


def create_bjd_hjd_mapping():
    """법정동-행정동 매핑 파일 생성 (기본 매핑)."""
    mapping_path = GEO_DIR / "bjd_hjd_mapping.json"
    if mapping_path.exists():
        print(f"이미 존재: {mapping_path}")
        return

    # 서울시 주요 법정동-행정동 매핑 (샘플)
    # 실제 운영 시 행정안전부 공개 데이터 사용 권장
    mapping = {
        "1168010100": "1168053000",  # 역삼동 (법정) → 역삼1동 (행정)
        "1168010300": "1168054000",  # 개포동 → 개포1동
        "1165010100": "1165051000",  # 서초동 → 서초1동
        "1165010200": "1165052000",  # 잠원동 → 잠원동
        "1171010100": "1171051000",  # 잠실동 → 잠실1동
        "1156010100": "1156051000",  # 영등포동 → 영등포동
        "1144010100": "1144051000",  # 마포동 → 마포동
    }

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"기본 매핑 저장: {mapping_path}")
    print("참고: 전체 매핑은 행정안전부 데이터를 활용하세요.")


if __name__ == "__main__":
    print("=== 서울시 지리 데이터 초기화 ===")
    download_seoul_dong_geojson()
    create_bjd_hjd_mapping()
    print("완료!")
