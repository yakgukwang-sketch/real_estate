"""서울시 실시간 인구 데이터 수집."""

import logging
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from config.settings import settings
from src.collectors.live_commercial_collector import AREA_LIST

logger = logging.getLogger(__name__)


class LivePopulationCollector:
    """서울시 실시간 도시데이터 - 인구 (citydata_ppltn)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.seoul_open_api_key
        self.base_url = settings.seoul_api_base

    def collect_area(self, area_name: str) -> dict | None:
        """특정 장소의 실시간 인구 데이터 수집."""
        url = f"{self.base_url}/{self.api_key}/xml/citydata_ppltn/1/5/{area_name}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            result_code = root.findtext(".//resultCode", "")
            if result_code != "INFO-000":
                logger.warning("%s: %s", area_name, root.findtext(".//resultMsg", ""))
                return None

            record = {
                "장소명": root.findtext("AREA_NM", area_name),
                "장소코드": root.findtext("AREA_CD", ""),
                "혼잡도": root.findtext(".//AREA_CONGEST_LVL", ""),
                "혼잡도메시지": root.findtext(".//AREA_CONGEST_MSG", ""),
                "인구_최소": self._to_int(root.findtext(".//AREA_PPLTN_MIN")),
                "인구_최대": self._to_int(root.findtext(".//AREA_PPLTN_MAX")),
                "남성비율": self._to_float(root.findtext(".//MALE_PPLTN_RATE")),
                "여성비율": self._to_float(root.findtext(".//FEMALE_PPLTN_RATE")),
                "10대비율": self._to_float(root.findtext(".//PPLTN_RATE_10")),
                "20대비율": self._to_float(root.findtext(".//PPLTN_RATE_20")),
                "30대비율": self._to_float(root.findtext(".//PPLTN_RATE_30")),
                "40대비율": self._to_float(root.findtext(".//PPLTN_RATE_40")),
                "50대비율": self._to_float(root.findtext(".//PPLTN_RATE_50")),
                "60대이상비율": self._to_float(root.findtext(".//PPLTN_RATE_60")),
                "상주인구비율": self._to_float(root.findtext(".//RESNT_PPLTN_RATE")),
                "비상주인구비율": self._to_float(root.findtext(".//NON_RESNT_PPLTN_RATE")),
                "업데이트시간": root.findtext(".//PPLTN_TIME", ""),
            }

            # 시간대별 예측
            forecasts = []
            for fcst in root.findall(".//FCST_PPLTN/FCST_PPLTN"):
                forecasts.append({
                    "시간": fcst.findtext("FCST_TIME", ""),
                    "혼잡도": fcst.findtext("FCST_CONGEST_LVL", ""),
                    "인구_최소": self._to_int(fcst.findtext("FCST_PPLTN_MIN")),
                    "인구_최대": self._to_int(fcst.findtext("FCST_PPLTN_MAX")),
                })
            record["시간대예측"] = forecasts

            return record
        except Exception:
            logger.exception("실시간 인구 수집 실패: %s", area_name)
            return None

    def collect_all(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """전체 장소 수집. (현재 인구, 시간대 예측) 두 DataFrame 반환."""
        summaries = []
        forecasts = []

        for area in AREA_LIST:
            data = self.collect_area(area)
            if data is None:
                continue

            fcst_list = data.pop("시간대예측", [])
            summaries.append(data)

            for fcst in fcst_list:
                fcst["장소명"] = data["장소명"]
                fcst["장소코드"] = data.get("장소코드", "")
                forecasts.append(fcst)

            logger.info("%s: %s (인구 %s~%s)",
                        area, data.get("혼잡도", ""),
                        data.get("인구_최소", ""), data.get("인구_최대", ""))

        summary_df = pd.DataFrame(summaries) if summaries else pd.DataFrame()
        forecast_df = pd.DataFrame(forecasts) if forecasts else pd.DataFrame()
        return summary_df, forecast_df

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
