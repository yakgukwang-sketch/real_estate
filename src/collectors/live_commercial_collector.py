"""서울시 실시간 상권현황 데이터 수집."""

import logging
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

# 서울시 주요 82장소 목록
AREA_LIST = [
    "강남 MICE 관광특구", "동대문 관광특구", "명동 관광특구", "이태원 관광특구",
    "잠실 관광특구", "종로·청계 관광특구", "홍대 관광특구",
    "경복궁·서촌마을", "광화문·덕수궁", "창덕궁·종묘",
    "가산디지털단지역", "강남역", "건대입구역", "고속터미널역",
    "교대역", "구로디지털단지역", "서울역", "선릉역", "신도림역",
    "신림역", "신촌·이대역", "역삼역", "연신내역", "왕십리역",
    "용산역", "이수역", "잠실역", "천호역", "합정역", "혜화역",
    "가로수길", "광장시장", "낙산공원·이화마을", "노량진",
    "덕수궁길·정동길", "북촌한옥마을", "서촌", "성수카페거리",
    "수유리 먹자골목", "쌍문동 먹자골목", "압구정로데오거리",
    "여의도", "영등포 타임스퀘어", "외대앞", "인사동·익선동",
    "창동 신경제 중심지", "청담동 명품거리", "청량리역",
    "해방촌·경리단길", "DMC(디지털미디어시티)", "DDP(동대문디자인플라자)",
    "강남구청역", "남산공원", "망원동", "뚝섬한강공원", "반포한강공원",
    "북서울꿈의숲", "서울대공원", "서울숲공원", "신촌역",
    "아차산", "양재역", "연남동", "월드컵공원", "이촌한강공원",
    "장지역", "마곡나루역", "국립중앙박물관·용산가족공원",
    "남대문시장", "방이동 먹자골목", "북한산우이역", "서울식물원·마곡나루",
    "성수동 핫플레이스", "신사역", "안국역", "영등포역",
    "올림픽공원", "을지로입구역", "이화여대역", "종각역",
    "중곡역", "한양대역",
]


class LiveCommercialCollector:
    """서울시 실시간 상권현황 API 수집기."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.seoul_open_api_key
        self.base_url = settings.seoul_api_base

    def collect_area(self, area_name: str) -> dict | None:
        """특정 장소의 실시간 상권 데이터 수집 (XML 파싱)."""
        url = f"{self.base_url}/{self.api_key}/xml/citydata_cmrcl/1/1000/{area_name}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            # 에러 체크
            result_code = root.findtext(".//resultCode", "")
            if result_code != "INFO-000":
                logger.warning("%s: %s", area_name, root.findtext(".//resultMsg", ""))
                return None

            record = {
                "장소명": root.findtext("AREA_NM", area_name),
                "장소코드": root.findtext("AREA_CD", ""),
                "상권활성도": root.findtext(".//AREA_CMRCL_LVL", ""),
                "결제건수": self._to_int(root.findtext(".//AREA_SH_PAYMENT_CNT")),
                "결제금액_최소": self._to_int(root.findtext(".//AREA_SH_PAYMENT_AMT_MIN")),
                "결제금액_최대": self._to_int(root.findtext(".//AREA_SH_PAYMENT_AMT_MAX")),
                "남성비율": self._to_float(root.findtext(".//CMRCL_MALE_RATE")),
                "여성비율": self._to_float(root.findtext(".//CMRCL_FEMALE_RATE")),
                "10대비율": self._to_float(root.findtext(".//CMRCL_10_RATE")),
                "20대비율": self._to_float(root.findtext(".//CMRCL_20_RATE")),
                "30대비율": self._to_float(root.findtext(".//CMRCL_30_RATE")),
                "40대비율": self._to_float(root.findtext(".//CMRCL_40_RATE")),
                "50대비율": self._to_float(root.findtext(".//CMRCL_50_RATE")),
                "60대이상비율": self._to_float(root.findtext(".//CMRCL_60_RATE")),
                "개인비율": self._to_float(root.findtext(".//CMRCL_PERSONAL_RATE")),
                "법인비율": self._to_float(root.findtext(".//CMRCL_CORPORATION_RATE")),
                "업데이트시간": root.findtext(".//CMRCL_TIME", ""),
            }

            # 업종별 데이터
            industries = []
            for rsb in root.findall(".//CMRCL_RSB/CMRCL_RSB"):
                industries.append({
                    "대분류": rsb.findtext("RSB_LRG_CTGR", ""),
                    "중분류": rsb.findtext("RSB_MID_CTGR", ""),
                    "업종상권현황": rsb.findtext("RSB_PAYMENT_LVL", ""),
                    "업종결제건수": self._to_int(rsb.findtext("RSB_SH_PAYMENT_CNT")),
                    "업종결제금액_최소": self._to_int(rsb.findtext("RSB_SH_PAYMENT_AMT_MIN")),
                    "업종결제금액_최대": self._to_int(rsb.findtext("RSB_SH_PAYMENT_AMT_MAX")),
                    "가맹점수": self._to_int(rsb.findtext("RSB_MCT_CNT")),
                })
            record["업종별"] = industries

            return record
        except Exception:
            logger.exception("실시간 상권 수집 실패: %s", area_name)
            return None

    def collect_all(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """82개 장소 전체 수집. (장소별 요약, 업종별 상세) 두 DataFrame 반환."""
        summaries = []
        details = []

        for area in AREA_LIST:
            data = self.collect_area(area)
            if data is None:
                continue

            industries = data.pop("업종별", [])
            summaries.append(data)

            for ind in industries:
                ind["장소명"] = data["장소명"]
                ind["장소코드"] = data.get("장소코드", "")
                details.append(ind)

            logger.info("%s: 결제 %s건", area, data.get("결제건수", 0))

        summary_df = pd.DataFrame(summaries) if summaries else pd.DataFrame()
        detail_df = pd.DataFrame(details) if details else pd.DataFrame()
        return summary_df, detail_df

    @staticmethod
    def _to_int(val: str | None) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    @staticmethod
    def _to_float(val: str | None) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except ValueError:
            return None
