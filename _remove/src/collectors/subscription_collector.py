"""한국부동산원 청약홈 분양정보/경쟁률 수집기.

APT, 오피스텔/도시형, 공공지원 민간임대, 취소후재공급, 잔여세대,
임의공급의 분양정보/경쟁률 및 특별공급 신청현황 데이터를 수집합니다.
"""

import logging
import time

import pandas as pd
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1"

# 엔드포인트 목록
ENDPOINTS = {
    "apt": {
        "path": "/getAPTLttotPblancCmpet",
        "name": "APT 분양정보/경쟁률",
    },
    "officetel": {
        "path": "/getUrbtyOfctlLttotPblancCmpet",
        "name": "오피스텔/도시형/민간임대/생활숙박시설",
    },
    "public_rent": {
        "path": "/getPblPvtRentLttotPblancCmpet",
        "name": "공공지원 민간임대",
    },
    "cancel_resupply": {
        "path": "/getCancResplLttotPblancCmpet",
        "name": "취소후재공급",
    },
    "remaining": {
        "path": "/getRemndrLttotPblancCmpet",
        "name": "잔여세대",
    },
    "apt_score": {
        "path": "/getAptLttotPblancScore",
        "name": "APT 당첨가점",
    },
    "optional": {
        "path": "/getOPTLttotPblancCmpet",
        "name": "임의공급",
    },
    "apt_special": {
        "path": "/getAPTSpsplyReqstStus",
        "name": "APT 특별공급 신청현황",
    },
}


class SubscriptionCollector:
    """청약홈 분양정보/경쟁률 수집기."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.data_go_kr_api_key
        self.rate_limit_delay = 0.3
        self._last_request = 0.0

    def _wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

    def collect(
        self,
        endpoint_key: str = "apt",
        max_rows: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """특정 엔드포인트의 전체 데이터 수집.

        Args:
            endpoint_key: ENDPOINTS 딕셔너리 키 (apt, officetel, ...)
            max_rows: 최대 수집 건수 (None이면 전체)
            filters: 조건 필터 (예: {"SIDO_NM::EQ": "서울특별시"})

        Returns:
            수집된 데이터 DataFrame
        """
        if endpoint_key not in ENDPOINTS:
            logger.error("알 수 없는 엔드포인트: %s", endpoint_key)
            return pd.DataFrame()

        ep = ENDPOINTS[endpoint_key]
        url = f"{BASE_URL}{ep['path']}"
        all_rows = []
        page = 1
        per_page = 500

        while True:
            self._wait()
            params = {
                "serviceKey": self.api_key,
                "page": page,
                "perPage": per_page,
            }
            if filters:
                for k, v in filters.items():
                    params[f"cond[{k}]"] = v

            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.exception("%s 수집 실패 (page %d)", ep["name"], page)
                break

            items = data.get("data", [])
            if not items:
                break

            all_rows.extend(items)
            total = data.get("totalCount", data.get("matchCount", 0))

            if max_rows and len(all_rows) >= max_rows:
                all_rows = all_rows[:max_rows]
                break

            if page * per_page >= total:
                break
            page += 1

            if page % 10 == 0:
                logger.info("%s: %d/%d건", ep["name"], len(all_rows), total)

        if not all_rows:
            return pd.DataFrame()

        logger.info("%s: 총 %d건 수집", ep["name"], len(all_rows))
        df = pd.DataFrame(all_rows)
        return self._standardize(df, endpoint_key)

    def collect_all_types(self, max_rows_per_type: int | None = None) -> dict[str, pd.DataFrame]:
        """모든 유형의 분양정보 수집.

        Returns:
            {endpoint_key: DataFrame} 딕셔너리
        """
        results = {}
        for key in ENDPOINTS:
            logger.info("=== %s 수집 ===", ENDPOINTS[key]["name"])
            df = self.collect(key, max_rows=max_rows_per_type)
            if not df.empty:
                results[key] = df
        return results

    def collect_apt_supply(self) -> pd.DataFrame:
        """APT 분양 공급세대수 수집 (경쟁률 포함)."""
        return self.collect("apt")

    def collect_officetel_supply(self) -> pd.DataFrame:
        """오피스텔/도시형 공급세대수 수집."""
        return self.collect("officetel")

    def _standardize(self, df: pd.DataFrame, endpoint_key: str) -> pd.DataFrame:
        """컬럼명 한글화."""
        rename_map = {
            "HOUSE_MANAGE_NO": "주택관리번호",
            "PBLANC_NO": "공고번호",
            "HOUSE_TY": "주택형",
            "MODEL_NO": "모델번호",
            "SUPLY_HSHLDCO": "공급세대수",
            "REQ_CNT": "접수건수",
            "CMPET_RATE": "경쟁률",
            "RESIDE_SECD": "거주지역코드",
            "RESIDE_SENM": "거주지역명",
            "SUBSCRPT_RANK_CODE": "청약순위",
            "RESIDNT_PRIOR_AT": "거주자우선여부",
            "RESIDNT_PRIOR_SENM": "공급구분명",
            "SPSPLY_KND_NM": "공급유형",
            "SPSPLY_KND_HSHLDCO": "배정세대수",
            "SPSPLY_HSHLDCO": "특별공급세대수",
            "LWET_SCORE": "최저당첨가점",
            "TOP_SCORE": "최고당첨가점",
            "AVRG_SCORE": "평균당첨가점",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        for col in ["공급세대수", "접수건수", "배정세대수", "특별공급세대수",
                     "최저당첨가점", "최고당첨가점"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        df["유형"] = endpoint_key
        return df

    def get_supply_summary(self, apt_df: pd.DataFrame) -> pd.DataFrame:
        """주택관리번호별 총 공급세대수 집계.

        Returns:
            columns: [주택관리번호, 총공급세대수, 주택형수, 경쟁률_목록]
        """
        if apt_df.empty or "주택관리번호" not in apt_df.columns:
            return pd.DataFrame()

        summary = (
            apt_df.groupby("주택관리번호")
            .agg(
                총공급세대수=("공급세대수", "sum"),
                주택형수=("주택형", "nunique"),
            )
            .reset_index()
        )
        return summary.sort_values("총공급세대수", ascending=False)
