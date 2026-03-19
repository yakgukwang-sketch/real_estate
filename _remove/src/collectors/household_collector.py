"""지역별 세대수 수집기.

2개 API 활용:
1. 국토교통부 공동주택 기본정보 — 아파트 단지별 세대수, 동수, 전용면적
2. 행정안전부 도로명별 주민등록 인구 및 세대현황 — 도로명별 총 세대수, 인구수
"""

import logging
import time

import pandas as pd
import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class HouseholdCollector:
    """서울시 지역별 세대수 수집."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.data_go_kr_api_key
        self.rate_limit_delay = 0.3
        self._last_request = 0.0

    def _wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

    def _get(self, url: str, params: dict) -> dict | None:
        self._wait()
        params["serviceKey"] = self.api_key
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("API 호출 실패: %s", url)
            return None

    # ─── 서울 25개 구의 대표 도로명코드 (12자리) ───
    # roadNmCd = 시군구코드(5) + 도로명코드(7)
    # 각 구에서 대표 도로 1개씩 (전체 도로를 조회하려면 도로명코드 목록이 필요)
    SEOUL_GU_ROAD_CODES: dict[str, list[str]] = {
        "11680": ["116804169259"],  # 강남구 - 테헤란로
        "11650": ["116504163259"],  # 서초구 - 서초대로
        "11710": ["117104525451"],  # 송파구 - 올림픽로
        "11440": ["114404107013"],  # 마포구 - 월드컵북로
        "11560": ["115604526329"],  # 영등포구 - 여의대방로
        "11170": ["111704100164"],  # 용산구 - 이태원로
        "11140": ["111404100029"],  # 중구 - 을지로
        "11110": ["111104100009"],  # 종로구 - 종로
        "11200": ["112004107029"],  # 성동구 - 왕십리로
        "11215": ["112154107141"],  # 광진구 - 능동로
        "11350": ["113504169007"],  # 노원구 - 동일로
        "11500": ["115004100137"],  # 강서구 - 공항대로
        "11530": ["115304158003"],  # 구로구 - 디지털로
        "11740": ["117404107031"],  # 강동구 - 천호대로
        "11305": ["113054100253"],  # 강북구 - 도봉로
        "11320": ["113204169003"],  # 도봉구 - 마들로
        "11380": ["113804169009"],  # 은평구 - 진흥로
        "11410": ["114104100043"],  # 서대문구 - 연세로
        "11470": ["114704158025"],  # 양천구 - 목동동로
        "11545": ["115454158071"],  # 금천구 - 시흥대로
        "11590": ["115904100175"],  # 동작구 - 상도로
        "11620": ["116204100201"],  # 관악구 - 관악로
        "11230": ["112304107227"],  # 동대문구 - 천호대로
        "11260": ["112604526175"],  # 중랑구 - 망우로
        "11290": ["112904100239"],  # 성북구 - 보문로
    }

    # ─── 1. 행정안전부: 도로명별 주민등록 인구 및 세대현황 ───

    def collect_registered_households(
        self,
        road_nm_cd: str,
        from_ym: str = "202501",
        to_ym: str = "202503",
    ) -> pd.DataFrame:
        """특정 도로명코드의 세대현황 수집.

        Args:
            road_nm_cd: 12자리 도로명코드
            from_ym: 조회 시작 연월 (YYYYMM)
            to_ym: 조회 종료 연월 (YYYYMM, 시작과 3개월 이내)

        Returns:
            columns: [시도명, 시군구명, 도로명, 총인구수, 세대수, 세대당인구, ...]
        """
        url = "https://apis.data.go.kr/1741000/rnPpltnHhStus/selectRnPpltnHhStus"
        all_rows = []
        page = 1
        page_size = 100

        while True:
            params = {
                "type": "json",
                "numOfRows": page_size,
                "pageNo": page,
                "roadNmCd": road_nm_cd,
                "srchFrYm": from_ym,
                "srchToYm": to_ym,
            }

            data = self._get(url, params)
            if data is None:
                break

            # 응답 파싱 — Response.head / Response.items
            resp = data.get("Response", data.get("response", data))
            head = resp.get("head", {})
            result_msg = head.get("resultMsg", "")
            if result_msg not in ("NORMAL_SERVICE",):
                if result_msg != "NO_DATA":
                    logger.warning("API 에러: %s (code=%s)", result_msg, road_nm_cd)
                break

            items_wrap = resp.get("items", resp.get("body", {}).get("items", {}))
            items = items_wrap.get("item", []) if isinstance(items_wrap, dict) else items_wrap
            if isinstance(items, dict):
                items = [items]

            if not items:
                break

            all_rows.extend(items)
            total = int(head.get("totalCount", 0))
            if page * page_size >= total:
                break
            page += 1

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        return self._standardize_household(df)

    def collect_all_seoul_households(
        self,
        from_ym: str = "202501",
        to_ym: str = "202503",
    ) -> pd.DataFrame:
        """서울 주요 구의 도로명 세대현황 수집.

        Args:
            from_ym: 조회 시작 연월
            to_ym: 조회 종료 연월
        """
        frames = []
        for gu_code, road_codes in self.SEOUL_GU_ROAD_CODES.items():
            gu_name = settings.seoul_gu_names.get(gu_code, gu_code)
            for road_cd in road_codes:
                logger.info("=== %s (도로코드: %s) 세대현황 수집 ===", gu_name, road_cd)
                df = self.collect_registered_households(road_cd, from_ym, to_ym)
                if not df.empty:
                    frames.append(df)
                    logger.info("%s: %d건", gu_name, len(df))

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _standardize_household(self, df: pd.DataFrame) -> pd.DataFrame:
        """세대현황 데이터 컬럼 표준화."""
        rename_map = {
            "ctpvNm": "시도명",
            "sggNm": "시군구명",
            "roadNm": "도로명",
            "roadNmCd": "도로명코드",
            "totNmprCnt": "총인구수",
            "hhCnt": "세대수",
            "hhNmpr": "세대당인구",
            "maleNmprCnt": "남자인구수",
            "femlNmprCnt": "여자인구수",
            "maleFemlRate": "남녀비율",
            "statsYm": "기준연월",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        for col in ["총인구수", "세대수", "남자인구수", "여자인구수"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        for col in ["세대당인구", "남녀비율"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ─── 2. 국토교통부: 공동주택 기본정보 ───

    def collect_apt_complex_info(self, kapt_code: str) -> dict | None:
        """단지코드로 공동주택 기본정보 조회.

        Returns:
            단지명, 법정동주소, 세대수, 동수, 분양형태, 사용승인일, 법정동코드 등
        """
        url = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4"
        params = {"kaptCode": kapt_code, "type": "json"}
        data = self._get(url, params)
        if data is None:
            return None

        body = data.get("response", data)
        if isinstance(body, dict):
            body = body.get("body", body)
        items = body.get("items", body.get("item", {}))
        if isinstance(items, dict):
            items = items.get("item", items)
        if isinstance(items, list):
            return items[0] if items else None
        return items if items else None

    def collect_apt_list_for_gu(self, gu_code: str) -> pd.DataFrame:
        """자치구의 공동주택 단지 목록 조회.

        Note: 단지목록 API(AptListServiceV4)가 별도로 필요.
              승인 대기 중이면 빈 DataFrame 반환.
        """
        url = "https://apis.data.go.kr/1613000/AptListServiceV4/getLegaldongAptListV4"
        all_rows = []
        page = 1

        while True:
            params = {
                "type": "json",
                "numOfRows": 100,
                "pageNo": page,
                "bjdCode": gu_code,
            }
            data = self._get(url, params)
            if data is None:
                break

            body = data.get("response", data)
            if isinstance(body, dict):
                body = body.get("body", body)

            items = body.get("items", [])
            if isinstance(items, dict):
                items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]

            if not items:
                break

            all_rows.extend(items)
            total = int(body.get("totalCount", 0))
            if page * 100 >= total:
                break
            page += 1

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        rename_map = {
            "kaptCode": "단지코드",
            "kaptName": "단지명",
            "as1": "시도",
            "as2": "시군구",
            "as3": "읍면동",
            "as4": "리",
            "bjdCode": "법정동코드",
            "kaptAddr": "도로명주소",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        return df.rename(columns=rename)

    def collect_seoul_apt_households(self) -> pd.DataFrame:
        """서울 전체 아파트 단지별 세대수 수집 (2단계: 목록 → 상세).

        1) 구별 단지 목록 조회
        2) 각 단지의 기본정보(세대수) 조회
        """
        all_complexes = []

        for gu_code in settings.seoul_gu_codes:
            gu_name = settings.seoul_gu_names.get(gu_code, gu_code)
            logger.info("=== %s 단지 목록 조회 ===", gu_name)

            apt_list = self.collect_apt_list_for_gu(gu_code)
            if apt_list.empty:
                logger.warning("%s: 단지 목록 없음 (API 미승인 가능)", gu_name)
                continue

            code_col = "단지코드" if "단지코드" in apt_list.columns else "kaptCode"
            if code_col not in apt_list.columns:
                continue

            for _, row in apt_list.iterrows():
                code = row[code_col]
                info = self.collect_apt_complex_info(code)
                if info:
                    info["자치구"] = gu_name
                    all_complexes.append(info)

            logger.info("%s: %d개 단지 조회 완료", gu_name, len(apt_list))

        if not all_complexes:
            return pd.DataFrame()

        df = pd.DataFrame(all_complexes)
        return self._standardize_apt_info(df)

    def _standardize_apt_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """공동주택 기본정보 컬럼 표준화."""
        rename_map = {
            "kaptCode": "단지코드",
            "kaptName": "단지명",
            "codeHeatNm": "난방방식",
            "codeSalesNm": "분양형태",
            "kaptAddr": "도로명주소",
            "kaptDongCnt": "동수",
            "kaptdaCnt": "세대수",
            "kaptBcompany": "시공사",
            "kaptAcompany": "시행사",
            "kaptTel": "관리사무소연락처",
            "kaptUsedate": "사용승인일",
            "kaptMparea": "관리비부과면적",
            "kaptTarea": "건축물대장연면적",
            "bjdCode": "법정동코드",
            "kaptMarea": "전용면적합",
            "kaptHoCnt": "호수",
        }
        rename = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename)

        for col in ["세대수", "동수", "호수"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        for col in ["관리비부과면적", "건축물대장연면적", "전용면적합"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ─── 행정동별 세대수 집계 ───

    def summarize_by_dong(self, household_df: pd.DataFrame) -> pd.DataFrame:
        """도로명 세대현황을 시군구 단위로 집계.

        Returns:
            columns: [시군구명, 총세대수, 총인구수, 세대당평균인구]
        """
        if household_df.empty or "시군구명" not in household_df.columns:
            return pd.DataFrame()

        summary = (
            household_df.groupby("시군구명")
            .agg(총세대수=("세대수", "sum"), 총인구수=("총인구수", "sum"))
            .reset_index()
        )
        summary["세대당평균인구"] = (
            summary["총인구수"] / summary["총세대수"].replace(0, 1)
        ).round(2)

        return summary.sort_values("총세대수", ascending=False)
