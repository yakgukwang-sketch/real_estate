# 래미안 대치팰리스 상권 시뮬레이션

래미안 대치팰리스(1,600세대) 주민의 **이동 패턴**과 **소비 행태**를 에이전트 기반으로 시뮬레이션합니다.

실제 보행 네트워크(서울시 공공데이터) 위에서 에이전트가 실제 건물(상가정보 + 건축물대장)로 이동하며, 시간대별 스케줄과 소비를 시뮬레이션합니다.

## 주요 기능

- **보행 네트워크**: 서울시 도보 네트워크 11,366노드 + 횡단보도 1,121개
- **건물 데이터**: 상가정보 3,987건 + 건축물대장 1,736건 → 599개 건물 (487개 도달 가능)
- **에이전트 시뮬레이션**: 5개 유형 (직장인/맞벌이/주부/학생/은퇴자)
- **시간대 스케줄**: 이른아침~밤 6개 시간대별 행동 패턴
- **연쇄 이동**: 학원→카페, 운동→음식점 등 trip chain
- **소비 시뮬레이션**: 업종별 객단가, 프로파일/시간대별 소비 집계
- **대시보드**: Streamlit + Leaflet 실시간 애니메이션 지도

## 프로젝트 구조

```
real_estate/
├── config/
│   └── settings.py                 # API 키, 엔드포인트, 서울 25개 구 코드
├── src/
│   ├── collectors/                 # 데이터 수집기
│   │   ├── base_collector.py       #   공통 베이스 (캐싱, Rate-limit)
│   │   ├── building_collector.py   #   건축물대장 표제부
│   │   └── commercial_collector.py #   상가(상권) 정보 + 반경 검색
│   ├── simulation/                 # 시뮬레이션 엔진
│   │   ├── sidewalk.py             #   보행 네트워크 (도보+횡단보도)
│   │   └── local_agent.py          #   에이전트 시뮬레이션 (v2)
│   └── utils/                      # 공통 유틸리티
│       ├── api_client.py           #   HTTP 클라이언트
│       └── cache.py                #   SQLite 캐시
├── dashboard/
│   ├── app.py                      # Streamlit 메인
│   └── pages/
│       └── 08_local_sim.py         # 주민 이동 시뮬레이션 시각화
├── data/
│   ├── raw/                        # 수집 데이터 (gitignored)
│   ├── geo/                        # GeoJSON, 행정동 매핑
│   └── collection_dates.json       # 수집 이력
├── _remove/                        # 이전 버전 코드 (보존)
├── SIMULATION.md                   # 시뮬레이션 상세 문서
└── TODO.md                         # 작업 이력 및 다음 단계
```

## 데이터 소스

| 데이터 | API | 건수 |
|--------|-----|------|
| 도보 네트워크 | `TbTraficWlkNet` (서울 열린데이터) | 29,134 |
| 횡단보도 | `tbTraficCrsng` (서울 열린데이터) | 2,062 |
| 상가정보 | `storeListInRadius` (data.go.kr) | 3,987 |
| 건축물대장 | `getBrTitleInfo` (data.go.kr) | 1,736 |

## 시뮬레이션 모델

### 에이전트 유형 (5종)

| 유형 | 비율 | 특징 |
|------|------|------|
| 직장인 | 35% | 출퇴근, 점심/저녁 외식, 소비 최다 |
| 맞벌이 | 20% | 등원+출근, 학원 픽업, 장보기 |
| 주부 | 15% | 장보기, 학원 픽업, 점심 외식 |
| 학생 | 15% | 등교, 학원, 저녁 외식 적음 |
| 은퇴자 | 15% | 새벽 산책, 병원, 종교 활동 |

### 시간대 (6구간)

이른아침(06~08) → 오전(08~10) → 점심(11~13) → 오후(13~17) → 저녁(17~19) → 밤(19~22)

### 목적지 유형 (10종)

음식점, 학원, 학교, 상점, 병원/약국, 생활서비스, 어린이집/복지, 종교시설, 운동시설, 대형상가

## 시작하기

### 1. 설치

```bash
pip install -e .
```

### 2. API 키 설정

`.env` 파일 생성:

```
DATA_GO_KR_API_KEY=your_key_here
SEOUL_OPEN_API_KEY=your_key_here
SAFEMAP_API_KEY=your_key_here
```

| 키 | 발급처 | 용도 |
|----|--------|------|
| `DATA_GO_KR_API_KEY` | [data.go.kr](https://www.data.go.kr) | 상가정보, 건축물대장 |
| `SEOUL_OPEN_API_KEY` | [data.seoul.go.kr](https://data.seoul.go.kr) | 도보 네트워크, 횡단보도 |
| `SAFEMAP_API_KEY` | [safemap.go.kr](https://www.safemap.go.kr) | 생활안전지도 (미사용) |

### 3. 대시보드 실행

```bash
streamlit run dashboard/app.py
```

## 기술 스택

| 용도 | 패키지 |
|------|--------|
| 데이터 | pandas, numpy |
| 네트워크 | osmnx, networkx |
| 시각화 | streamlit, leaflet.js |
| 설정 | pydantic-settings, python-dotenv |
| HTTP | requests, urllib3 |
| 캐싱 | sqlite3 |

## 라이선스

학습 및 연구 목적. 공공 API 데이터 사용은 각 제공기관 이용약관을 따릅니다.
