# 서울 상권 & 부동산 시뮬레이션

서울시의 **사람 이동 패턴**과 **소비 패턴**을 분석하는 시뮬레이션 프로젝트.
지하철 승하차 인구, 아파트/빌라 부동산, 직장인구, 소비수요 데이터를 결합하여 상권과 부동산의 상관관계를 분석하고 웹 대시보드로 시각화합니다.

## 주요 기능

- **데이터 수집**: 7개 공공 API에서 지하철, 부동산, 상권, 인구, 매출 데이터 자동 수집
- **행정동 매핑**: 좌표 기반 spatial join으로 모든 데이터를 행정동코드 + 기준연월로 통합
- **상관분석**: 유동인구-부동산-매출 간 교차 상관분석, 시차 상관분석
- **클러스터링**: K-Means 기반 유사 행정동 그룹화
- **상권 스코어링**: 6개 지표 가중합 상권 활성도 등급 (A~E)
- **시뮬레이션**: 에이전트 기반 출퇴근/소비 모델, OD 유동 모델
- **What-if 시나리오**: 신규 지하철역, 임대료 변동, 인구 변화 시 영향 예측
- **시계열 예측**: Prophet/ARIMA 기반 부동산 가격, 매출 예측
- **대시보드**: Streamlit + Folium 지도 + Plotly 차트 7페이지

## 프로젝트 구조

```
real_estate/
├── config/settings.py              # API 키, 엔드포인트, 지역코드
├── src/
│   ├── collectors/                  # 7개 공공 API 수집기
│   ├── processors/                  # 데이터 정제 + 행정동 매핑
│   ├── analysis/                    # 상관분석, 클러스터링, 스코어링
│   ├── simulation/                  # OD 유동, 에이전트, 시나리오, 예측
│   ├── models/                      # Pydantic 데이터 모델
│   └── utils/                       # HTTP 클라이언트, SQLite 캐시, 좌표 계산
├── dashboard/
│   ├── app.py                       # Streamlit 메인
│   ├── pages/                       # 7개 분석 페이지
│   └── components/                  # 지도, 차트, 필터 공통 컴포넌트
├── data/                            # raw / processed / geo / cache
├── scripts/                         # 수집, 처리, GeoJSON 초기화
└── tests/                           # 14개 테스트
```

## 데이터 소스

| 데이터 | API | 소스 |
|--------|-----|------|
| 지하철 승하차 | 서울시 지하철 호선별 역별 승하차 인원 | data.seoul.go.kr |
| 아파트 실거래가 | 국토교통부 아파트매매 실거래자료 | data.go.kr |
| 빌라 실거래가 | 국토교통부 연립다세대 매매 실거래자료 | data.go.kr |
| 상권/상가 | 소상공인 상가(상권)정보 | data.go.kr |
| 추정매출 | 서울시 상권분석서비스 추정매출 | data.seoul.go.kr |
| 생활인구 | 행정동 단위 서울 생활인구 | data.seoul.go.kr |
| 직장인구 | 서울시 사업체/종사자수 | data.seoul.go.kr |

## 기술 스택

| 용도 | 패키지 |
|------|--------|
| 데이터 | pandas, numpy, pyarrow |
| 지리 | geopandas, shapely, folium |
| 시각화 | streamlit, streamlit-folium, plotly |
| 분석 | scikit-learn, scipy |
| 시뮬레이션 | mesa |
| 예측 | prophet, statsmodels |
| 설정 | python-dotenv, pydantic-settings |

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
- **data.seoul.go.kr**: 회원가입 후 API 키 발급
- **data.go.kr**: 회원가입 후 API 키 발급 + 사용할 API 활용신청

### 3. GeoJSON 다운로드

```bash
python scripts/seed_geodata.py
```

### 4. 데이터 수집

```bash
# 전체 수집
python scripts/collect_all.py --year 2024 --month 1

# 개별 수집
python scripts/collect_all.py --target subway --year 2024 --month 1
```

### 5. 데이터 처리

```bash
python scripts/process_all.py
```

### 6. 대시보드 실행

```bash
streamlit run dashboard/app.py
```

## 대시보드 페이지

1. **서울 전체 현황** - 주요 KPI 및 행정동 지도
2. **지하철 승하차 분석** - 역별 순위, 시계열, 히트맵
3. **부동산 실거래가** - 가격 추이, 구별 비교, 면적별 분석
4. **상권 분석** - 업종 분포, 상권 지도, 추정매출
5. **생활/직장 인구** - 인구 분포, 코로플레스 지도
6. **상관관계 종합** - 변수 간 상관행렬, 유의성 검정
7. **시뮬레이션** - What-if 시나리오, 시계열 예측, 에이전트 모델

## 테스트

```bash
python -m pytest tests/ -v
```
