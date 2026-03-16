"""Pydantic 데이터 모델."""

from pydantic import BaseModel


class DongSummary(BaseModel):
    """행정동 요약 데이터."""
    행정동코드: str
    행정동명: str
    자치구명: str = ""
    연월: str = ""
    승차인원: int = 0
    하차인원: int = 0
    순유입: int = 0
    평균거래금액: float = 0
    거래건수: int = 0
    업소수: int = 0
    생활인구: float = 0
    추정매출: float = 0
    상권활성도: float = 0


class SubwayStation(BaseModel):
    """지하철역 정보."""
    역명: str
    호선: str = ""
    위도: float
    경도: float
    행정동코드: str = ""
    행정동명: str = ""


class ScenarioInput(BaseModel):
    """시뮬레이션 시나리오 입력."""
    scenario_type: str  # "new_station", "rent_change", "population_change"
    target_dong: str = ""
    target_station: str = ""
    parameter_value: float = 0
    description: str = ""
