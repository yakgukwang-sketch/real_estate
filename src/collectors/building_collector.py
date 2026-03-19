"""건축물대장 표제부 수집기 — 국토교통부 건축HUB API."""

import logging
import xml.etree.ElementTree as ET

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)

# 서울시 주요 법정동코드 (강남구)
GANGNAM_DONG_CODES: dict[str, str] = {
    "10300": "대치동",
    "10100": "역삼동",
    "10200": "개포동",
    "10400": "도곡동",
    "10500": "논현동",
    "10600": "삼성동",
    "10700": "청담동",
    "10800": "신사동",
    "10900": "압구정동",
    "11000": "세곡동",
    "11100": "일원동",
    "11200": "수서동",
    "11500": "자곡동",
    "11600": "율현동",
}


class BuildingCollector(BaseCollector):
    """건축물대장 표제부 API 수집기.

    API: 국토교통부_건축HUB_건축물대장정보 서비스
    엔드포인트: /getBrTitleInfo (표제부)
    일일 트래픽: 10,000건
    """

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.data_go_kr_api_key,
            cache_ttl_hours=168,  # 7일
            rate_limit_delay=0.3,
        )
        self.base_endpoint = settings.building_registry_url

    def collect(
        self,
        sigungu_cd: str = "11680",
        bjdong_cd: str = "10300",
        num_of_rows: int = 100,
        **kwargs,
    ) -> pd.DataFrame:
        """특정 시군구+법정동의 건축물대장 표제부를 전량 수집.

        Args:
            sigungu_cd: 시군구코드 (기본값: 11680 강남구)
            bjdong_cd: 법정동코드 (기본값: 10300 대치동)
            num_of_rows: 페이지당 건수 (최대 100)
        """
        url = f"{self.base_endpoint}/getBrTitleInfo"
        all_items: list[dict] = []
        page = 1
        total = None

        while True:
            params = {
                "serviceKey": self.api_key,
                "sigunguCd": sigungu_cd,
                "bjdongCd": bjdong_cd,
                "numOfRows": str(num_of_rows),
                "pageNo": str(page),
            }

            xml_text = self.client.get_xml(url, params=params)
            root = ET.fromstring(xml_text)

            # 에러 체크
            result_code = root.findtext(".//resultCode")
            if result_code != "00":
                msg = root.findtext(".//resultMsg", "UNKNOWN")
                logger.error("API 오류: %s (%s)", msg, result_code)
                break

            if total is None:
                total = int(root.findtext(".//totalCount", "0"))
                if total == 0:
                    break
                logger.info(
                    "%s %s: 총 %d건",
                    sigungu_cd,
                    GANGNAM_DONG_CODES.get(bjdong_cd, bjdong_cd),
                    total,
                )

            items = root.findall(".//item")
            if not items:
                break

            for item in items:
                row = {child.tag: child.text for child in item}
                all_items.append(row)

            if len(all_items) >= total:
                break
            page += 1

        if not all_items:
            return pd.DataFrame()

        df = pd.DataFrame(all_items)
        return self._standardize(df)

    def _standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 표준화 및 타입 변환."""
        column_map = {
            "platPlc": "지번주소",
            "newPlatPlc": "도로명주소",
            "bldNm": "건물명",
            "mainPurpsCdNm": "주용도",
            "etcPurps": "기타용도",
            "strctCdNm": "구조",
            "grndFlrCnt": "지상층수",
            "ugrndFlrCnt": "지하층수",
            "totArea": "연면적",
            "archArea": "건축면적",
            "platArea": "대지면적",
            "bcRat": "건폐율",
            "vlRat": "용적률",
            "hhldCnt": "세대수",
            "useAprDay": "사용승인일",
            "sigunguCd": "시군구코드",
            "bjdongCd": "법정동코드",
            "mgmBldrgstPk": "건축물대장PK",
            "bun": "번",
            "ji": "지",
            "dongNm": "동명칭",
            "mainAtchGbCdNm": "주부속구분",
            "regstrKindCdNm": "대장종류",
        }

        rename = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        numeric_cols = ["지상층수", "지하층수", "연면적", "건축면적", "대지면적", "건폐율", "용적률", "세대수"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.replace("", None)

        code_cols = ["시군구코드", "법정동코드", "건축물대장PK"]
        for col in code_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")

        return df

    def collect_dong(
        self,
        sigungu_cd: str = "11680",
        dong_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """여러 법정동의 건축물대장을 수집.

        Args:
            sigungu_cd: 시군구코드
            dong_codes: 법정동코드 목록 (None이면 강남구 전체)
        """
        codes = dong_codes or list(GANGNAM_DONG_CODES.keys())
        frames = []
        for code in codes:
            try:
                df = self.collect(sigungu_cd=sigungu_cd, bjdong_cd=code)
                if not df.empty:
                    frames.append(df)
                    logger.info(
                        "%s: %d건",
                        GANGNAM_DONG_CODES.get(code, code),
                        len(df),
                    )
            except Exception:
                logger.exception("수집 실패: %s", code)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
