"""대전 유성구 건축물대장 전체 수집 + 특정 건물 검색."""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collectors.building_collector import BuildingCollector
from config.settings import RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# 대전 유성구 법정동코드 목록
YUSEONG_DONG_CODES: dict[str, str] = {
    "10100": "원내동",
    "10200": "교촌동",
    "10300": "대정동",
    "10400": "용계동",
    "10500": "학하동",
    "10600": "갑동",
    "10700": "덕명동",
    "10800": "덕진동",
    "10900": "하기동",
    "11000": "추목동",
    "11100": "자운동",
    "11200": "금고동",
    "11300": "대동",
    "11400": "원촌동",
    "11500": "봉명동",
    "11600": "구암동",
    "11700": "어은동",
    "11800": "궁동",
    "11900": "도룡동",
    "12000": "장동",
    "12100": "방동",
    "12200": "방현동",
    "12300": "노은동",
    "12400": "지족동",
    "12500": "죽동",
    "12600": "관평동",
    "12700": "송강동",
    "12800": "반석동",
    "12900": "온천동",
    "13000": "문지동",
    "13100": "전민동",
    "13200": "원성동",
    "13300": "화암동",
    "13400": "복용동",
    "13500": "둔곡동",
    "13600": "탑립동",
    "13700": "백운동",
    "13800": "신봉동",
    "13900": "신성동",
    "14000": "안산동",
    "14100": "외삼동",
    "14200": "수남동",
    "14300": "세동",
    "14400": "송정동",
    "14500": "가정동",
}

SIGUNGU_CD = "30200"  # 대전 유성구


def main():
    collector = BuildingCollector()

    all_frames = []
    for dong_cd, dong_nm in YUSEONG_DONG_CODES.items():
        try:
            logger.info("수집 시작: %s (%s)", dong_nm, dong_cd)
            df = collector.collect(sigungu_cd=SIGUNGU_CD, bjdong_cd=dong_cd)
            if not df.empty:
                df["법정동명"] = dong_nm
                all_frames.append(df)
                logger.info("%s: %d건", dong_nm, len(df))
            else:
                logger.info("%s: 데이터 없음", dong_nm)
        except Exception:
            logger.exception("수집 실패: %s", dong_nm)

    if not all_frames:
        logger.error("수집된 데이터 없음")
        return

    import pandas as pd
    combined = pd.concat(all_frames, ignore_index=True)
    logger.info("=== 총 %d건 수집 완료 ===", len(combined))

    # 저장
    out_path = RAW_DIR / "building_registry_yuseong.json"
    combined.to_json(out_path, orient="records", force_ascii=False, indent=2)
    logger.info("저장: %s", out_path)

    # 사용승인일 2000-12-26 건물 검색
    if "사용승인일" in combined.columns:
        match = combined[combined["사용승인일"] == "20001226"]
        if not match.empty:
            logger.info("\n=== 사용승인일 2000-12-26 건물 ===")
            cols = ["건물명", "지번주소", "도로명주소", "주용도", "연면적",
                    "지상층수", "세대수", "사용승인일", "법정동명"]
            display_cols = [c for c in cols if c in match.columns]
            print(match[display_cols].to_string(index=False))
        else:
            logger.info("사용승인일 20001226 매칭 건물 없음")

    # CSV도 저장
    csv_path = RAW_DIR / "building_registry_yuseong.csv"
    combined.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("CSV 저장: %s", csv_path)


if __name__ == "__main__":
    main()
