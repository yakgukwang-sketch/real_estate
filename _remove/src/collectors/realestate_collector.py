"""국토교통부 아파트/빌라 실거래가 수집."""

import logging
import xml.etree.ElementTree as ET

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class RealEstateCollector(BaseCollector):
    """국토교통부 실거래가 API 수집기."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.data_go_kr_api_key,
            cache_ttl_hours=168,  # 과거 거래 데이터는 변하지 않음
        )

    def collect(
        self,
        year: int = 2024,
        month: int = 1,
        gu_code: str | None = None,
        property_type: str = "apt",
        **kwargs,
    ) -> pd.DataFrame:
        """실거래가 데이터 수집.

        Args:
            year: 연도
            month: 월
            gu_code: 자치구 법정동코드 (5자리). None이면 서울 전체.
            property_type: "apt" (아파트), "villa" (연립다세대), "officetel" (오피스텔)
        """
        gu_codes = [gu_code] if gu_code else settings.seoul_gu_codes
        url_map = {
            "apt": settings.apt_trade_url,
            "villa": settings.villa_trade_url,
            "officetel": settings.officetel_trade_url,
        }
        url = url_map.get(property_type, settings.apt_trade_url)

        frames = []
        for code in gu_codes:
            try:
                df = self._fetch_gu(url, code, year, month, property_type)
                if not df.empty:
                    frames.append(df)
            except Exception:
                logger.exception("실거래가 수집 실패: %s %d-%02d", code, year, month)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _fetch_gu(
        self, url: str, gu_code: str, year: int, month: int, property_type: str
    ) -> pd.DataFrame:
        """특정 구의 실거래가 데이터 수집."""
        deal_ymd = f"{year}{month:02d}"
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": gu_code,
            "DEAL_YMD": deal_ymd,
            "pageNo": "1",
            "numOfRows": "9999",
        }

        xml_text = self.fetch_xml_with_cache(url, params)
        return self._parse_xml(xml_text, gu_code, property_type)

    def _parse_xml(
        self, xml_text: str, gu_code: str, property_type: str
    ) -> pd.DataFrame:
        """XML 응답 파싱."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.error("XML 파싱 실패")
            return pd.DataFrame()

        items = root.findall(".//item")
        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            record = {
                "자치구코드": gu_code,
                "법정동": self._get_text(item, "법정동") or self._get_text(item, "umdNm", ""),
                "건물명": self._get_text(item, "아파트") or self._get_text(item, "aptNm", ""),
                "전용면적": self._get_float(item, "전용면적") or self._get_float(item, "excluUseAr"),
                "거래금액": self._parse_price(item),
                "건축년도": self._get_text(item, "건축년도") or self._get_text(item, "buildYear", ""),
                "층": self._get_text(item, "층") or self._get_text(item, "floor", ""),
                "거래년": self._get_text(item, "년") or self._get_text(item, "dealYear", ""),
                "거래월": self._get_text(item, "월") or self._get_text(item, "dealMonth", ""),
                "거래일": self._get_text(item, "일") or self._get_text(item, "dealDay", ""),
                "유형": property_type,
            }
            records.append(record)

        df = pd.DataFrame(records)

        # 숫자 변환
        df["전용면적"] = pd.to_numeric(df["전용면적"], errors="coerce")
        df["거래금액"] = pd.to_numeric(df["거래금액"], errors="coerce")

        # 날짜 생성
        df["거래년"] = df["거래년"].str.strip()
        df["거래월"] = df["거래월"].str.strip()
        df["거래일"] = df["거래일"].str.strip()

        return df

    @staticmethod
    def _get_text(item: ET.Element, tag: str, default: str = "") -> str:
        el = item.find(tag)
        return el.text.strip() if el is not None and el.text else default

    @staticmethod
    def _get_float(item: ET.Element, tag: str) -> float | None:
        el = item.find(tag)
        if el is not None and el.text:
            try:
                return float(el.text.strip().replace(",", ""))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_price(item: ET.Element) -> str:
        """거래금액 파싱 (만원 단위, 쉼표 제거)."""
        for tag in ["거래금액", "dealAmount"]:
            el = item.find(tag)
            if el is not None and el.text:
                return el.text.strip().replace(",", "")
        return ""
