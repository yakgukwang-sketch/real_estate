# 영등포역 상권 보행자 시뮬레이션

## 개요

대치동 시뮬레이션의 한계(학원 매출 60% 편중, 시뮬레이션-실제 매출 비율 괴리)를 해결하기 위해
영등포역 상권으로 전환한 프로젝트.

| 항목 | 대치동 | 영등포역 |
|------|--------|----------|
| 상권 규모 | 1조 2,028억원 | 6,288억원 |
| 업종 수 | 학원 편중 | 47업종 |
| 상위3 집중도 | ~60% (학원) | 35.8% |
| 모델 | 아파트 → 상권 (단일 출발점) | 여러 곳 → 상권 (다중 출발점) |

---

## 아키텍처

```
scripts/collect_yeongdeungpo.py    # Phase 1: 데이터 수집
        │
        v
src/simulation/sidewalk.py         # Phase 2: AreaConfig 기반 네트워크 구축
        │
        v
src/simulation/local_agent.py      # Phase 3: 다중 출발점 에이전트 시뮬레이션
        │
        v
dashboard/pages/09_yeongdeungpo_sim.py  # Phase 4: Streamlit 대시보드
```

---

## Phase 1: 데이터 수집

### 파일: `scripts/collect_yeongdeungpo.py`

서울시 공공데이터 API로 영등포구 데이터 수집.

| 데이터 | API | 건수 | 출력 파일 |
|--------|-----|------|-----------|
| 도보 네트워크 | `TbTraficWlkNet/영등포구` | 22,800건 | `data/raw/walk_network_yeongdeungpo.json` |
| 횡단보도 | `tbTraficCrsng/영등포구` | 31,080건 | `data/raw/crosswalk_yeongdeungpo.json` |
| 상가 건물 | 소상공인 반경검색 (37.5158, 126.9074, 1km) | 5,868건 → 1,736건물 | `data/raw/buildings_classified_yeongdeungpo.json` |

```bash
python scripts/collect_yeongdeungpo.py
```

- 이미 파일이 존재하면 스킵
- 상가 데이터는 건물 단위로 그룹핑 후 업종 분류까지 자동 수행
- API 파라미터: 구 코드(11560)가 아니라 구 이름(`영등포구`)으로 필터링

---

## Phase 2: sidewalk.py 파라미터화

### 파일: `src/simulation/sidewalk.py`

#### 핵심 변경: `AreaConfig` dataclass 도입

```python
@dataclass
class AreaConfig:
    name: str                                    # "daechi" / "yeongdeungpo"
    center: tuple[float, float]                  # (lat, lon)
    radius: float                                # 필터링 반경 (도 단위, 0.008 ≈ 800m)
    walk_network_file: str                       # 도보 네트워크 JSON
    crosswalk_file: str                          # 횡단보도 JSON
    buildings_file: str                          # 건물 분류 JSON
    subway_stations: dict[str, tuple]            # 지하철역 좌표
    origin_points: dict[str, tuple]              # 다중 출발점 (영등포용)
    apt_node: tuple[float, float] | None         # 아파트 노드 (대치동용)
    apt_label: str                               # 아파트 라벨
```

#### 사전 정의된 설정

| 설정 | center | 지하철역 | 출발점 |
|------|--------|----------|--------|
| `DAECHI_CONFIG` | (37.4945, 127.0625) | 대치/한티/학여울/도곡/매봉/선릉 (6개) | apt 노드 1개 |
| `YEONGDEUNGPO_CONFIG` | (37.5158, 126.9074) | 영등포/영등포시장/신길 (3개) | 5개 출발점 |

#### 함수 변경

| 기존 | 변경 후 | 비고 |
|------|---------|------|
| `build_daechi_network()` | `build_network(config: AreaConfig)` | 범용화 |
| — | `build_daechi_network()` | 하위호환 wrapper |

#### 네트워크 구축 과정 (8단계)

1. 도보 네트워크 노드 파싱
2. 링크 → 엣지 등록
3. 노드 등록
4. 횡단보도 데이터 합치기 (신호대기 +30초)
5. 단절 컴포넌트 자동 연결 (30m 이내)
6. 지하철역 노드 추가 + 도로 연결
7. 아파트 노드 추가 (대치동만)
8. **다중 출발점 노드 추가 (영등포용, 신규)**

---

## Phase 3: 다중 출발점 에이전트 시스템

### 파일: `src/simulation/local_agent.py`

#### 3-1. `_AreaData` 클래스 (lazy loading)

```python
class _AreaData:
    config: AreaConfig
    profiles: dict
    network     # lazy: build_network() 호출 시점에 생성
    buildings   # lazy: JSON 로드 시점에 생성
    destinations  # lazy: Dijkstra 실행 후 생성
```

- `_dijkstra_from(start_id)`: 각 출발점에서 1회 Dijkstra → 캐시
- `_reconstruct_path(origin_id, end_id)`: 경로 역추적
- 5개 출발점 × ~11K 노드 = <1초

#### 3-2. 영등포역 출발점 분배

| 출발점 | 비중 | 노드 ID |
|--------|------|---------|
| 영등포역 (지하철) | 45% | `subway_영등포역` |
| 영등포시장역 (지하철) | 15% | `subway_영등포시장역` |
| 신길역 (지하철) | 10% | `subway_신길역` |
| 영등포동 주거지 | 20% | `origin_영등포동_주거` |
| 영등포 업무지구 | 10% | `origin_영등포_업무` |

각 프로파일이 `origins` 딕셔너리로 출발점별 확률을 갖고, 에이전트 생성 시 가중 랜덤 배정.

#### 3-3. 영등포역 에이전트 프로파일 (5종)

| 프로파일 | 비중 | 주요 출발점 | 행동 패턴 |
|---------|------|------------|-----------|
| 환승객 | 20% | 지하철 70% | 커피/간식 후 빠르게 이동, chain_prob 10% |
| 쇼핑객 | 25% | 지하철+주거 | 의류/시장 쇼핑, 연쇄이동 높음 (30%) |
| 직장인(점심) | 20% | 업무지구 60% | 점심 시간대 집중 (prob 80%) |
| 주민 | 20% | 주거지 70% | 장보기, 병원, 생활서비스 |
| 시장방문객 | 15% | 혼합 | 전통시장 식료품 구매, chain 25% |

#### 3-4. 매출 보정

```python
AREA_SALES = {
    "daechi": {
        "annual": 1_202_800_000_000,  # 1조 2,028억원
        "apt_share": 1600 / 20000,     # 래미안 8%
    },
    "yeongdeungpo": {
        "annual": 628_800_000_000,     # 6,288억원
        "apt_share": 1.0,              # 상권 전체 커버 (apt_share 불필요)
    },
}
```

#### 3-5. simulate() 시그니처

```python
def simulate(n_agents=100, seed=42, area="daechi") -> list[Agent]
def estimate_revenue(df, n_agents, area="daechi") -> pd.DataFrame
```

#### 3-6. Agent dataclass 확장

```python
@dataclass
class Agent:
    id: int
    home: tuple[float, float]  # 출발점 좌표 (다중 출발점 시 각각 다름)
    profile: str
    origin: str                # 출발점 이름 (신규)
    log: list[dict]
```

- `agents_to_df()`에 `출발점` 컬럼 추가

---

## Phase 4: 대시보드

### 파일: `dashboard/pages/09_yeongdeungpo_sim.py`

08_local_sim.py 구조 기반, 영등포 특화:

| 항목 | 대치동 (08) | 영등포 (09) |
|------|------------|------------|
| 지도 중심 | 래미안 대치팰리스 | 영등포역 |
| 출발점 마커 | 🏢 아파트 1개 | 🚇 지하철 3개 + 🏘️ 주거 + 🏢 업무 |
| 사이드바 | 인원/시드/속도 | + 출발점별 에이전트 수 |
| 매출 기준 | 1.2조 × 8% = 962억 | 6,288억원 전체 |
| 프로파일 이모지 | 💼👫🏠📚🧓 | 🚉🛍️💼🏠🧺 |
| 에이전트 선택 | #ID [프로파일] | #ID [프로파일] (출발점) |
| 프로파일 탭 | 프로파일별 이동 | + 출발점별 이동 추가 |

### 파일: `dashboard/pages/08_local_sim.py` (수정)

import 변경만 (3줄):

```python
# Before
from src.simulation.local_agent import ... NETWORK, DESTINATIONS, ...
# After
from src.simulation.local_agent import ... _get_area_data, ...
_daechi_data = _get_area_data("daechi")
NETWORK = _daechi_data.network
DESTINATIONS = _daechi_data.destinations
```

---

## Phase 5: 검증 — 실제 매출 vs 시뮬레이션 비교

### 데이터 소스

- **실제 매출**: `data/raw/spending_2024Q1~Q4.parquet` → `상권명 = '영등포역(영등포)'`
- **시뮬레이션**: `simulate(n_agents=1000, seed=42, area='yeongdeungpo')`

### 수집 데이터 현황

| 데이터 | 건수 | 상태 |
|--------|------|------|
| 도보 네트워크 | 22,800건 | 수집 완료 |
| 횡단보도 | 31,080건 | 수집 완료 |
| 상가 (반경 1km) | 5,868건 | 수집 완료 |
| 건물 분류 | 1,736건물 | 수집 완료 |
| 도달 가능 목적지 | 1,633건물 | 시뮬 생성 |

### 영등포역 실제 매출 — 2024년 연간 (47업종)

| 순위 | 업종 | 매출(억원) | 비율 |
|------|------|-----------|------|
| 1 | 한식음식점 | 1,378 | 21.9% |
| 2 | 반찬가게 | 469 | 7.5% |
| 3 | 의약품 | 403 | 6.4% |
| 4 | 일반의류 | 398 | 6.3% |
| 5 | 신발 | 320 | 5.1% |
| 6 | 호프-간이주점 | 312 | 5.0% |
| 7 | 핸드폰 | 304 | 4.8% |
| 8 | 청과상 | 266 | 4.2% |
| 9 | 시계및귀금속 | 263 | 4.2% |
| 10 | 편의점 | 225 | 3.6% |
| 11~47 | 기타 37개 업종 | 1,950 | 31.0% |
| **합계** | **47업종** | **6,288** | **100%** |

### 대분류 매핑 후 비교 (1000명 시뮬레이션)

| 업종 | 실제 매출 | 실제 비율 | 시뮬 매출 | 시뮬 비율 | 차이 |
|------|----------|----------|----------|----------|------|
| 상점 | 2,883억 | 45.9% | 4,208억 | 66.9% | **+21.1%** |
| 음식점 | 2,404억 | 38.2% | 2,000억 | 31.8% | -6.4% |
| 병원/약국 | 746억 | 11.9% | 52억 | 0.8% | **-11.0%** |
| 기타 | 185억 | 2.9% | 16억 | 0.3% | -2.7% |
| 생활서비스 | 70억 | 1.1% | 12억 | 0.2% | -0.9% |

### 시뮬레이션 상세 (1000명, seed=42)

| 항목 | 값 |
|------|-----|
| 외출자 | 870명 |
| 총 이동 | 1,575건 |
| 연쇄이동 | 65건 |
| 총 소비 | 23,297,500원 |

**출발점별 에이전트 분포:**

| 출발점 | 에이전트 수 |
|--------|-----------|
| 영등포역 | 322명 |
| 영등포동_주거 | 198명 |
| 영등포시장역 | 181명 |
| 영등포_업무 | 103명 |
| 신길역 | 66명 |

### 괴리 원인 분석

| 문제 | 원인 | 개선 방향 |
|------|------|----------|
| **상점 +21.1%** | 소매 1,773개가 모두 "상점"으로 뭉침. 에이전트가 상점을 너무 자주 방문 | 소매 세분류(의류/식료품/편의점 등) 분리, 방문 확률 조정 |
| **병원/약국 -11.0%** | 의약품 403억(6.4%)인데 에이전트 병원 방문 확률이 너무 낮음 (주민 12%, 은퇴자 15%) | 모든 프로파일에 약국 방문 추가, 확률 상향 |
| **음식점 -6.4%** | 비교적 근접. 한식 21.9%가 최대 업종이므로 시뮬 음식점 비중도 합리적 | 미세 조정 가능 |
| **기타/생활서비스 과소** | 여관(126억), 노래방(48억) 등이 시뮬에서 거의 안 잡힘 | 기타 업종 목적지 유형 추가 |

### 건물 분류 원본 데이터 (상가 API 대분류)

| 대분류 | 가게 수 |
|--------|--------|
| 소매 | 1,773 |
| 음식 | 1,561 |
| 과학·기술 | 708 |
| 수리·개인 | 461 |
| 시설관리·임대 | 323 |
| 교육 | 258 |
| 예술·스포츠 | 233 |
| 부동산 | 206 |
| 보건의료 | 178 |
| 숙박 | 167 |

---

## 실행 방법

```bash
# 1. 데이터 수집 (최초 1회, 이미 완료)
python scripts/collect_yeongdeungpo.py

# 2. 시뮬레이션 CLI 테스트
python -m src.simulation.local_agent yeongdeungpo

# 3. 대시보드 실행
streamlit run dashboard/app.py
# → 사이드바에서 "09_yeongdeungpo_sim" 페이지 선택
```

---

## 파일 목록

| 파일 | 상태 | 설명 |
|------|------|------|
| `scripts/collect_yeongdeungpo.py` | 신규 | 영등포구 데이터 수집 |
| `src/simulation/sidewalk.py` | 수정 | AreaConfig 파라미터화 |
| `src/simulation/local_agent.py` | 수정 | 다중 출발점, 영등포 프로파일, lazy loading |
| `dashboard/pages/08_local_sim.py` | 수정 | 새 API import 적용 |
| `dashboard/pages/09_yeongdeungpo_sim.py` | 신규 | 영등포 대시보드 |
| `data/raw/walk_network_yeongdeungpo.json` | 수집 완료 | 도보 네트워크 22,800건 |
| `data/raw/crosswalk_yeongdeungpo.json` | 수집 완료 | 횡단보도 31,080건 |
| `data/raw/stores_yeongdeungpo_1km.json` | 수집 완료 | 상가 원본 5,868건 |
| `data/raw/buildings_classified_yeongdeungpo.json` | 수집 완료 | 건물 분류 1,736개 |

---

## 다음 단계 (TODO)

- [ ] 건물 분류 세분화: 소매 → 의류/식료품/편의점/생활용품 분리
- [ ] 병원/약국 방문 확률 상향 (모든 프로파일에 약국 방문 추가)
- [ ] 기타 업종(숙박, 노래방 등) 목적지 유형 추가
- [ ] 업종별 실제 매출 비중으로 보정 가중치 적용
- [ ] 대치동 시뮬레이션 동일 방식으로 검증
