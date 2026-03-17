# 서울 상권 & 부동산 시뮬레이션

서울시의 **사람 이동 패턴**과 **소비 패턴**을 분석하는 데이터 기반 시뮬레이션 플랫폼.
7개 공공 API에서 수집한 지하철 승하차, 부동산 실거래가, 상가/상권, 생활/직장인구, 추정매출 데이터를 **행정동코드 + 기준연월** 기준으로 통합하여 상권-부동산 상관관계를 분석하고, What-if 시나리오와 에이전트 기반 시뮬레이션을 웹 대시보드로 시각화합니다.

---

## 아키텍처

```
┌─────────────────────────────────────────────────┐
│           7개 공공 API (data.go.kr / Seoul Open) │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Data Collection Layer (src/collectors/)         │
│  - SQLite 캐시 (TTL 24~72h)                     │
│  - Rate limiting (0.3s/req)                      │
│  - Retry logic (3회, exponential backoff)        │
└────────────────────┬────────────────────────────┘
                     │  RAW Parquet
┌────────────────────▼────────────────────────────┐
│  Data Processing Layer (src/processors/)         │
│  - GeoJSON spatial join (좌표→행정동)            │
│  - 법정동↔행정동 매핑                            │
│  - 500m 그리드 셀 할당                           │
│  - 월별 집계 파이프라인                          │
└────────────────────┬────────────────────────────┘
                     │  PROCESSED Parquet
       ┌─────────────┼─────────────┐
       │             │             │
┌──────▼──┐   ┌─────▼────┐  ┌────▼──────┐
│ Analysis │   │Simulation│  │ Dashboard │
│ -상관분석│   │-시나리오 │  │ Streamlit │
│ -클러스터│   │-에이전트 │  │ 7 pages   │
│ -스코어링│   │-OD 유동  │  │ Folium    │
│ -추세분석│   │-시계열   │  │ Plotly    │
└─────────┘   └──────────┘  └───────────┘
```

---

## 주요 기능

### 데이터 수집 & 처리
- **7개 공공 API** 자동 수집 (지하철, 아파트/빌라, 상가, 생활인구, 직장인구, 추정매출)
- **SQLite 캐시** 기반 중복 요청 방지 (TTL 24~72시간)
- **GeoJSON spatial join**으로 모든 데이터를 행정동코드 + 기준연월로 통합
- **법정동(BJD)↔행정동(HJD) 매핑** 지원
- **500m 격자 그리드** 기반 공간 분석

### 분석 엔진

| 모듈 | 기능 | 세부 사항 |
|------|------|-----------|
| **상관분석** | 교차 상관행렬, 유의성 검정, 시차 상관 | Pearson r, p < 0.05, 시차 ±N개월 |
| **클러스터링** | K-Means 유사 행정동 그룹화 | StandardScaler, 5개 클러스터, 유클리드 거리 |
| **상권 스코어링** | 6개 지표 가중합 활성도 등급 | A~E등급, 5개 상권유형별 가중치 차등 적용 |
| **추세 분석** | 선형회귀, 이동평균, 전년비, 이상치 탐지 | MA(3,6,12), YoY%, Z-score (threshold=2.0) |

### 상권 스코어링 상세

**6개 지표 (기본 가중치)**

| 지표 | 가중치 | 설명 |
|------|--------|------|
| 유동인구 | 0.25 | 지하철 승하차 기반 유동인구 |
| 매출 | 0.25 | 추정매출액 |
| 업소밀도 | 0.15 | 단위면적당 업소 수 |
| 생활인구 | 0.15 | 행정동 거주인구 |
| 부동산가격 | 0.10 | 평균 거래금액 |
| 업종다양성 | 0.10 | 업종 분포 다양성 |

**5개 상권 유형별 차등 가중치**

| 유형 | 분류 기준 | 특징 |
|------|-----------|------|
| 관광형 | 유동인구 비율 > 0.7 | 업종다양성 가중치 ↑ (0.25) |
| 오피스형 | 0.5 < 비율 ≤ 0.7 | 매출 가중치 ↑ (0.30), 임대료부담 ↑ |
| 주거형 | 비율 < 0.3 | 생활인구 가중치 ↑ (0.30), 임대료부담 ↑↑ |
| 유흥형 | 야간 비율 높음 | 유동인구+매출 균등 가중 |
| 혼합형 | 기타 | 균등 가중치 |

### 시뮬레이션 엔진

#### What-if 시나리오 (4종)

| 시나리오 | 주요 파라미터 | 영향 모델 |
|----------|---------------|-----------|
| **신규 지하철역** | 역명, 동코드, 일 승객수 (기본 3만명) | 인구 +min(승객/10000×5, 30%), 매출 ×0.8, 부동산 ×0.3 |
| **임대료 변동** | 변동률 (%) | 업소 이탈 min(변동×0.3, 20%), 매출 -변동×0.2 |
| **인구 변화** | 변동률 (%) | 매출 ×0.7, 부동산 ×0.2, 상업 ×0.4 |
| **복합 시나리오** | 다중 시나리오 조합 | 개별 효과 합산 |

#### 파급효과 전파 모델

```
[직접 영향 동]
    │
    ├── 지리적 인접 (GeoJSON 기반)
    │   ├── 1차 인접: 변화량 × 50%
    │   └── 2차 인접: 변화량 × 20%
    │
    └── 지하철 네트워크 (BFS 기반)
        ├── 환승 0회: decay = 1.0 × 0.9^(역 수)
        ├── 환승 1회: decay = 0.4 × 0.9^(역 수)
        └── 환승 2회+: decay = 0.15 × 0.9^(역 수)
```

#### 에이전트 기반 시뮬레이션 (Mesa)

**에이전트: 주민 (Resident)**
- 속성: 거주동, 직장동, 소득수준 (1~5), 현재위치, 일일소비

**소득 수준별 기본 소비 (원/일)**

| 수준 | 기본소비 | 분포비율 |
|------|----------|----------|
| 1 | 20,000 | 15% |
| 2 | 35,000 | 25% |
| 3 | 55,000 | 30% |
| 4 | 80,000 | 20% |
| 5 | 120,000 | 10% |

**일일 4단계 사이클**
1. **오전** → 직장동으로 이동
2. **주간** → 기본소비 × 40% × random(0.5~1.5) 지출
3. **저녁** → 거주동으로 이동
4. **야간** → 기본소비 × 60% × random(0.3~1.5) 지출

#### OD 유동 모델 (중력 모델)

```
Flow(i→j) = k × Population(i) × Employment(j) / Distance(i,j)^β
```
- β = 2.0 (거리 감쇠 계수), k = 1.0

**동 유형 분류:**
- 직장지역: 유입비율 > 0.15
- 주거지역: 유입비율 < -0.15
- 혼합: 그 외

#### 시계열 예측

| 모델 | 설정 | 용도 |
|------|------|------|
| **Prophet** (기본) | 연간 계절성 ON, 주간/일간 OFF | 부동산 가격, 매출 예측 |
| **ARIMA** (대체) | order=(1,1,1), freq=MS | Prophet 미설치 시 대체 |

- 기본 예측 기간: 12개월
- 출력: 예측값(yhat), 상한(yhat_upper), 하한(yhat_lower)

---

## 프로젝트 구조

```
real_estate/
├── config/
│   └── settings.py                 # API 키, 25개 구 코드, 엔드포인트, 경로 설정
├── src/
│   ├── collectors/                 # 7개 공공 API 수집기
│   │   ├── base_collector.py       #   추상 베이스 (캐시, 재시도, Rate Limit)
│   │   ├── subway_collector.py     #   서울 지하철 승하차 인원
│   │   ├── realestate_collector.py #   국토부 아파트/빌라 실거래
│   │   ├── commercial_collector.py #   소상공인 상가 정보
│   │   ├── population_collector.py #   생활인구 + 직장인구
│   │   └── spending_collector.py   #   서울시 추정매출
│   ├── processors/                 # 데이터 정제 + 행정동 매핑
│   │   ├── geo_processor.py        #   핵심: 좌표→행정동, 그리드, BJD↔HJD
│   │   ├── subway_processor.py     #   역→동 매핑, 월별 집계
│   │   ├── realestate_processor.py #   거래일 파싱, 평당가 계산
│   │   ├── commercial_processor.py #   업소 집계, 업종 분포
│   │   └── population_processor.py #   인구 집계, 피크시간 분석
│   ├── analysis/                   # 통계 분석
│   │   ├── correlation.py          #   교차상관, 유의성 검정, 시차 상관
│   │   ├── clustering.py           #   K-Means 유사 행정동 클러스터링
│   │   ├── scoring.py              #   상권 활성도 스코어링 (6지표, 5유형)
│   │   └── trend_analysis.py       #   선형추세, 이동평균, YoY, 이상치
│   ├── simulation/                 # 시뮬레이션 엔진
│   │   ├── scenario_engine.py      #   What-if 시나리오 (4종 + 파급효과)
│   │   ├── agent_model.py          #   Mesa 에이전트 (주민 출퇴근/소비)
│   │   ├── flow_model.py           #   중력 모델 OD 행렬, 동 유형 분류
│   │   └── forecast.py             #   Prophet/ARIMA 시계열 예측
│   ├── models/                     # Pydantic 데이터 모델
│   │   └── __init__.py             #   DongSummary, SubwayStation, ScenarioInput
│   └── utils/                      # 유틸리티
│       ├── api_client.py           #   HTTP 클라이언트 (재시도, Rate Limit)
│       ├── cache.py                #   SQLite TTL 캐시
│       └── geo_utils.py            #   Haversine, 좌표 변환 (EPSG4326↔5179)
├── dashboard/
│   ├── app.py                      # Streamlit 메인 (데이터 상태 체크)
│   ├── pages/                      # 7개 분석 페이지
│   │   ├── 01_overview.py          #   서울 전체 현황 KPI + 행정동 지도
│   │   ├── 02_subway.py            #   지하철 승하차 분석 (역별, 시계열)
│   │   ├── 03_realestate.py        #   부동산 실거래가 (추이, 면적별)
│   │   ├── 04_commercial.py        #   상권 분석 (업종 분포, 상권 지도)
│   │   ├── 05_population.py        #   생활/직장 인구 (코로플레스 지도)
│   │   ├── 06_correlation.py       #   상관관계 종합 (행렬, 유의성)
│   │   └── 07_simulation.py        #   시뮬레이션 (시나리오, 예측, ABM)
│   └── components/                 # 공통 컴포넌트
│       ├── chart_builder.py        #   Plotly 차트 (bar, line, heatmap)
│       ├── filters.py              #   UI 필터 (날짜, 구, 카테고리)
│       └── map_viewer.py           #   Folium 지도 시각화
├── scripts/
│   ├── collect_all.py              # 데이터 수집 오케스트레이터
│   ├── process_all.py              # 데이터 처리 파이프라인
│   └── seed_geodata.py             # GeoJSON 다운로드 + BJD↔HJD 초기화
├── tests/                          # 61개 유닛 테스트
│   ├── test_analysis.py            #   상관분석, 클러스터링, 스코어링 (20개)
│   ├── test_simulation.py          #   시나리오, 에이전트, 유동, 예측 (31개)
│   └── test_utils.py               #   Haversine, 캐시 (6개)
├── data/
│   ├── raw/                        # API 원본 Parquet
│   ├── processed/                  # 처리 완료 Parquet
│   ├── geo/                        # GeoJSON, BJD↔HJD 매핑
│   └── cache/                      # SQLite API 캐시
├── pyproject.toml                  # 프로젝트 메타데이터 & 의존성
├── .env.example                    # API 키 템플릿
└── .env                            # API 키 (git-ignored)
```

---

## 데이터 소스

| 데이터 | API | 소스 | 수집 주기 |
|--------|-----|------|-----------|
| 지하철 승하차 | 서울시 지하철 호선별 역별 승하차 인원 | data.seoul.go.kr | 일별 |
| 아파트 실거래가 | 국토교통부 아파트매매 실거래자료 | data.go.kr | 월별 |
| 빌라 실거래가 | 국토교통부 연립다세대 매매 실거래자료 | data.go.kr | 월별 |
| 상권/상가 | 소상공인 상가(상권)정보 | data.go.kr | 분기별 |
| 추정매출 | 서울시 상권분석서비스 추정매출 | data.seoul.go.kr | 분기별 |
| 생활인구 | 행정동 단위 서울 생활인구 | data.seoul.go.kr | 월별 |
| 직장인구 | 서울시 사업체/종사자수 | data.seoul.go.kr | 월별 |

---

## 기술 스택

| 용도 | 패키지 | 버전 |
|------|--------|------|
| 데이터 처리 | pandas, numpy, pyarrow | ≥2.0, ≥1.24, ≥14.0 |
| 지리 공간 | geopandas, shapely, folium | ≥0.14, ≥2.0, ≥0.15 |
| 시각화 | streamlit, streamlit-folium, plotly | ≥1.30, ≥0.17, ≥5.18 |
| 통계 분석 | scikit-learn, scipy | ≥1.3, ≥1.11 |
| 시뮬레이션 | mesa | ≥2.1 |
| 시계열 예측 | prophet, statsmodels | ≥1.1, latest |
| 설정 관리 | python-dotenv, pydantic, pydantic-settings | ≥1.0, ≥2.5, ≥2.1 |
| Python | | ≥ 3.10 |

---

## 시작하기

### 1. 설치

```bash
pip install -e ".[dev]"
```

### 2. API 키 설정

```bash
cp .env.example .env
```

`.env` 파일에 API 키 입력:

| 키 | 발급처 | 용도 |
|----|--------|------|
| `SEOUL_OPEN_API_KEY` | [data.seoul.go.kr](https://data.seoul.go.kr) | 지하철, 생활인구, 추정매출 |
| `DATA_GO_KR_API_KEY` | [data.go.kr](https://www.data.go.kr) | 부동산 실거래, 상가 정보 |

### 3. GeoJSON 다운로드

```bash
python scripts/seed_geodata.py
```

서울 행정동 경계 GeoJSON 및 법정동↔행정동 매핑 데이터를 초기화합니다.

### 4. 데이터 수집

```bash
# 전체 수집 (특정 월)
python scripts/collect_all.py --year 2024 --month 1

# 개별 수집
python scripts/collect_all.py --target subway --year 2024 --month 1

# 수집 가능 대상: subway, realestate, commercial, population, spending
```

### 5. 데이터 처리

```bash
python scripts/process_all.py
```

수집된 원본 데이터를 정제하고 행정동 기준으로 통합합니다.
처리 결과는 `data/processed/integrated.parquet`에 저장됩니다.

### 6. 대시보드 실행

```bash
streamlit run dashboard/app.py
```

---

## 대시보드 페이지

| # | 페이지 | 주요 시각화 | 분석 내용 |
|---|--------|-------------|-----------|
| 1 | **서울 전체 현황** | KPI 카드, 행정동 지도 | 주요 지표 요약, 공간 분포 |
| 2 | **지하철 승하차** | 역별 순위, 시계열, 히트맵 | 유동인구 흐름, 출퇴근 패턴 |
| 3 | **부동산 실거래가** | 가격 추이, 구별 비교 | 아파트/빌라 가격 변동, 면적별 분석 |
| 4 | **상권 분석** | 업종 분포, 상권 지도 | 업종 밀도, 추정매출 분포 |
| 5 | **생활/직장 인구** | 코로플레스 지도, 분포 차트 | 주야간 인구 차이, 직주비 |
| 6 | **상관관계 종합** | 상관행렬 히트맵, 산점도 | 변수 간 유의미한 상관, 시차 분석 |
| 7 | **시뮬레이션** | 시나리오 비교, 예측 차트 | What-if, 시계열 예측, 에이전트 결과 |

---

## 데이터 파이프라인

```
1. Collection    API → BaseCollector (cache/retry) → data/raw/*.parquet
2. Processing    Raw → GeoProcessor (spatial join) → Processors → data/processed/*.parquet
3. Integration   Processed → 행정동코드+연월 기준 merge → integrated.parquet
4. Analysis      Integrated → Correlation, Clustering, Scoring, Trend
5. Simulation    Baseline → Scenarios, Agent Model, Forecasts
6. Visualization All outputs → Streamlit Dashboard (7 pages)
```

---

## 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 모듈별 실행
python -m pytest tests/test_analysis.py -v     # 상관분석, 클러스터링, 스코어링 (20개)
python -m pytest tests/test_simulation.py -v   # 시나리오, 에이전트, 유동, 예측 (31개)
python -m pytest tests/test_utils.py -v        # Haversine, 캐시 (6개)
```

총 **61개 유닛 테스트** | 모두 통과

---

## 알려진 이슈 & 트러블슈팅

### API 수집 현황

| API | 상태 | 비고 |
|-----|------|------|
| 지하철 승하차 (Seoul Open) | ✅ 정상 | `SEOUL_OPEN_API_KEY` 필요 |
| 생활인구 (Seoul Open) | ⚠️ 빈 응답 | 특정 기간 데이터 미제공 가능 |
| 추정매출 (Seoul Open) | ⚠️ 빈 응답 | 분기 단위, 데이터 지연 가능 |
| 아파트 실거래 (MOLIT) | ❌ 연결 불가 | `openapi.molit.go.kr:8081` 서버 간헐적 차단 |
| 빌라 실거래 (MOLIT) | ❌ 연결 불가 | 동일 서버 이슈 |
| 상가 정보 (data.go.kr) | ✅ 정상 | `DATA_GO_KR_API_KEY` 필요 |

### 자주 발생하는 에러

| 에러 | 원인 | 해결 |
|------|------|------|
| `401 Unauthorized` | API 키 미설정 또는 만료 | `.env` 파일의 API 키 확인 |
| `ConnectionError: 10061` | MOLIT API 서버 연결 거부 | 시간대를 바꿔 재시도 (새벽/주말 권장) |
| `ArrowInvalid: Could not convert ''` | 상가 데이터 빈 문자열 | v0.2.0에서 수정 완료 |
| `처리된 데이터가 없습니다` | `data/processed/` 비어있음 | `scripts/process_all.py` 실행 |

### MOLIT API 우회 방법

국토교통부 API(`openapi.molit.go.kr:8081`)가 연결 거부될 경우:
1. **시간대 변경**: 새벽 또는 주말에 재시도
2. **VPN 사용**: 네트워크 환경 변경 후 시도
3. **공공데이터포털**: [data.go.kr](https://www.data.go.kr)에서 CSV 직접 다운로드

---

## 서울 25개 구 코드

| 코드 | 구 | 코드 | 구 | 코드 | 구 |
|------|----|------|----|------|----|
| 11110 | 종로구 | 11380 | 은평구 | 11620 | 관악구 |
| 11140 | 중구 | 11410 | 서대문구 | 11650 | 서초구 |
| 11170 | 용산구 | 11440 | 마포구 | 11680 | 강남구 |
| 11200 | 성동구 | 11470 | 양천구 | 11710 | 송파구 |
| 11215 | 광진구 | 11500 | 강서구 | 11740 | 강동구 |
| 11230 | 동대문구 | 11530 | 구로구 | | |
| 11260 | 중랑구 | 11545 | 금천구 | | |
| 11290 | 성북구 | 11560 | 영등포구 | | |
| 11305 | 강북구 | 11590 | 동작구 | | |
| 11320 | 도봉구 | | | | |
| 11350 | 노원구 | | | | |

---

## 라이선스

MIT License
