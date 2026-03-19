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
        """상가업소 데이터 수집.

        Args:
            dong_code: 행정동코드 (8자리)
            gu_code: 자치구코드 (5자리). dong_code가 없으면 구 단위로 수집.
        """
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
            # 구 단위로 수집하려면 해당 구의 동코드 목록 필요
            # 여기서는 간단히 구코드를 사용
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
            "lnoCd": "지번코드",
            "plotSctNm": "대지구분명",
            "lnoMnno": "지번본번",
            "lnoSlno": "지번부번",
            "rdNmAdr": "도로명주소",
            "bldMnno": "건물본번",
            "bldSlno": "건물부번",
            "bldMngNo": "건물관리번호",
            "bldNm": "건물명",
            "rdNm": "도로명",
            "rdNmCd": "도로명코드",
            "lon": "경도",
            "lat": "위도",
        }

        rename = {k: v for k, v in column_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        numeric_cols = ["경도", "위도", "지번본번", "지번부번", "건물본번", "건물부번"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 빈 문자열을 None으로 변환하여 parquet 저장 오류 방지
        df = df.replace("", None)

        # 코드 컬럼은 문자열 타입 유지
        code_cols = ["행정동코드", "법정동코드", "지번코드", "도로명코드", "건물관리번호"]
        for col in code_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")

        return df

    def collect_all_seoul(self) -> pd.DataFrame:
        """서울 전체 자치구 상가 데이터 수집."""
        frames = []
        for gu_code in settings.seoul_gu_codes:
            try:
                df = self.collect(gu_code=gu_code)
                if not df.empty:
                    frames.append(df)
                    logger.info("%s: %d건", settings.seoul_gu_names.get(gu_code, gu_code), len(df))
            except Exception:
                logger.exception("상가 수집 실패: %s", gu_code)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
