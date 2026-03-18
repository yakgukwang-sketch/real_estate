"""프로젝트 설정 - API 키, 엔드포인트, 지역코드 관리."""

from pathlib import Path

from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"
CACHE_DIR = DATA_DIR / "cache"


class Settings(BaseSettings):
    """환경변수에서 API 키를 로드."""

    data_go_kr_api_key: str = ""
    seoul_open_api_key: str = ""

    # data.go.kr 엔드포인트
    apt_trade_url: str = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    villa_trade_url: str = "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"
    officetel_trade_url: str = "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"
    commercial_url: str = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"

    # data.seoul.go.kr 엔드포인트 (서울 열린데이터 광장)
    seoul_api_base: str = "http://openapi.seoul.go.kr:8088"
    subway_endpoint: str = "CardSubwayStatsNew"
    population_endpoint: str = "SPOP_LOCAL_RESD_DONG"
    spending_endpoint: str = "VwsmTrdarSelngQq"

    # 서울시 자치구 법정동코드 (앞 5자리)
    seoul_gu_codes: list[str] = [
        "11110",  # 종로구
        "11140",  # 중구
        "11170",  # 용산구
        "11200",  # 성동구
        "11215",  # 광진구
        "11230",  # 동대문구
        "11260",  # 중랑구
        "11290",  # 성북구
        "11305",  # 강북구
        "11320",  # 도봉구
        "11350",  # 노원구
        "11380",  # 은평구
        "11410",  # 서대문구
        "11440",  # 마포구
        "11470",  # 양천구
        "11500",  # 강서구
        "11530",  # 구로구
        "11545",  # 금천구
        "11560",  # 영등포구
        "11590",  # 동작구
        "11620",  # 관악구
        "11650",  # 서초구
        "11680",  # 강남구
        "11710",  # 송파구
        "11740",  # 강동구
    ]

    # 서울시 자치구 이름 매핑
    seoul_gu_names: dict[str, str] = {
        "11110": "종로구", "11140": "중구", "11170": "용산구",
        "11200": "성동구", "11215": "광진구", "11230": "동대문구",
        "11260": "중랑구", "11290": "성북구", "11305": "강북구",
        "11320": "도봉구", "11350": "노원구", "11380": "은평구",
        "11410": "서대문구", "11440": "마포구", "11470": "양천구",
        "11500": "강서구", "11530": "구로구", "11545": "금천구",
        "11560": "영등포구", "11590": "동작구", "11620": "관악구",
        "11650": "서초구", "11680": "강남구", "11710": "송파구",
        "11740": "강동구",
    }

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "extra": "ignore"}


settings = Settings()
