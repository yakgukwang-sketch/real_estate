"""소상공인 상가(상권) 정보 수집."""

import logging

import pandas as pd

from config.settings import settings
from src.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class CommercialCollector(BaseCollector):
    """소상공인시장진흥공단 상가(상권) 정보 API."""

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or settings.data_go_kr_api_key,
            cache_ttl_hours=168,
        )

    def collect(
        self,
        dong_code: str | None = None,
        gu_code: str | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """행정동 또는 시군구 단위 상가업소 수집."""
        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "numOfRows": "1000",
            "type": "json",
        }
        if dong_code:
            params["divId"] = "adongCd"
            params["key"] = dong_code
        elif gu_code:
            params["divId"] = "signguCd"
            params["key"] = gu_code

        url = settings.commercial_url
        all_data = []
        page = 1

        while True:
            params["pageNo"] = str(page)
            data = self.fetch_with_cache(url, params)

            if not isinstance(data, dict):
                break

            body = data.get("body", {})
            items = body.get("items", [])
            if not items:
                break

            all_data.extend(items)
            total_count = int(body.get("totalCount", 0))
            if page * 1000 >= total_count:
                break
            page += 1

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        return self._standardize(df)

    def collect_radius(
        self,
        cx: float,
        cy: float,
        radius: int = 1000,
    ) -> pd.DataFrame:
        """반경 내 상가업소 수집.

        Args:
            cx: 중심 경도
            cy: 중심 위도
            radius: 반경 (미터)
        """
        url = settings.commercial_radius_url
        all_data = []
        page = 1

        while True:
            params = {
                "serviceKey": self.api_key,
                "radius": str(radius),
                "cx": str(cx),
                "cy": str(cy),
                "numOfRows": "1000",
                "pageNo": str(page),
                "type": "json",
            }
            data = self.fetch_with_cache(url, params)

            if not isinstance(data, dict):
                break

            body = data.get("body", {})
            items = body.get("items", [])
            if not items:
                break

            all_data.extend(items)
            total_count = int(body.get("totalCount", 0))
            logger.info("page %d: %d건 (누적 %d/%d)", page, len(items), len(all_data), total_count)
            if len(all_data) >= total_count:
                break
            page += 1

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        return self._standardize(df)

    def _standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 표준화."""
        column_map = {
            "bizesId": "사업자ID",
            "bizesNm": "상호명",
            "brchNm": "지점명",
            "indsLclsNm": "대분류명",
            "indsMclsNm": "중분류명",
            "indsSclsNm": "소분류명",
            "ksicNm": "표준산업분류명",
            "ctprvnNm": "시도명",
            "signguNm": "시군구명",
            "adongNm": "행정동명",
            "adongCd": "행정동코드",
            "ldongNm": "법정동명",
            "ldongCd": "법정동코드",
            "rdNmAdr": "도로명주소",
            "bldMngNo": "건물관리번호",
            "bldNm": "건물명",
            "rdNm": "도로명",
            "lon": "경도",
            "lat": "위도",
        }

        rename = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        numeric_cols = ["경도", "위도"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.replace("", None)

        code_cols = ["행정동코드", "법정동코드", "건물관리번호"]
        for col in code_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")

        return df
