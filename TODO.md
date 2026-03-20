# 프로젝트 다음 단계 (TODO)

> 최종 업데이트: 2026-03-20
> 현재 상태: master 브랜치, 대치동+영등포역 이중 지역 시뮬레이션

---

## 2026-03-21 할 일

### 시뮬레이션 정확도 개선 (영등포역)

현재 시뮬레이션 vs 실제 매출 괴리 (상세: `docs/yeongdeungpo_simulation.md`):
- 상점 66.9% vs 실제 45.9% (+21.1%) — 소매 세분류 필요
- 병원/약국 0.8% vs 실제 11.9% (-11.0%) — 방문 확률 과소

- [ ] **건물 분류 세분화**: 소매(1,773개)를 의류/식료품/편의점/생활용품 등으로 분리
  - 상가 API `indsSclsNm`(소분류명) 활용하여 재분류
- [ ] **병원/약국 방문 확률 상향**: 모든 프로파일에 약국 방문 추가 (현재 주민 12%만)
  - 실제 의약품 매출 403억(6.4%) + 일반의원 160억(2.5%) + 치과 84억(1.3%) = 10.2%
- [ ] **기타 업종 목적지 추가**: 숙박(여관 126억), 노래방(48억) 등
- [ ] **업종별 객단가 재설정**: 실제 매출/건수 데이터 기반으로 업데이트
- [ ] **보정 가중치 적용**: 시뮬레이션 방문 비율을 실제 매출 비중으로 보정

### 대치동 동일 검증
- [ ] 대치동 시뮬레이션도 실제 spending 데이터와 비교 검증
- [ ] 대치/은마/도곡 상권 실제 업종별 매출 추출

---

## 2026-03-20 작업 내역 (오후) — 영등포역 상권 시뮬레이션

### 영등포역 데이터 수집
- [x] 도보 네트워크 22,800건 수집 (`walk_network_yeongdeungpo.json`) — TbTraficWlkNet/영등포구
- [x] 횡단보도 31,080건 수집 (`crosswalk_yeongdeungpo.json`) — tbTraficCrsng/영등포구
- [x] 상가 5,868건 수집 (`stores_yeongdeungpo_1km.json`) — 반경 1km
- [x] 건물 분류 1,736개 (`buildings_classified_yeongdeungpo.json`)
- [x] 수집 스크립트: `scripts/collect_yeongdeungpo.py`

### sidewalk.py 파라미터화
- [x] `AreaConfig` dataclass 도입 — 지역별 설정 분리
- [x] `build_network(config)` 범용 함수 + `build_daechi_network()` 하위호환 wrapper
- [x] 다중 출발점 노드 지원 (`origin_` prefix)

### 다중 출발점 에이전트 시스템
- [x] `_AreaData` 클래스 — lazy loading (네트워크, 건물, Dijkstra 캐시)
- [x] 영등포 프로파일 5종: 환승객(20%)/쇼핑객(25%)/직장인점심(20%)/주민(20%)/시장방문객(15%)
- [x] 출발점 5개: 영등포역(45%)/영등포시장역(15%)/신길역(10%)/주거지(20%)/업무지구(10%)
- [x] `simulate(area="yeongdeungpo")` 시그니처 확장
- [x] `estimate_revenue(area=)` — 영등포: 6,288억원 전체 (apt_share 없음)

### 대시보드
- [x] `dashboard/pages/09_yeongdeungpo_sim.py` 신규 — 다중 출발점 마커, 출발점별 통계
- [x] `dashboard/pages/08_local_sim.py` 수정 — 새 API import 적용

### 검증 (실제 매출 비교)
- [x] 실제 매출 데이터 확인: `spending_2024Q1~Q4.parquet` → `영등포역(영등포)` 6,288억원, 47업종
- [x] 시뮬레이션 1000명 실행 → 대분류 비교표 작성
- [x] 괴리 원인 분석 → 상점 과다(+21.1%), 병원 과소(-11.0%)
- [x] `docs/yeongdeungpo_simulation.md` 문서화

---

## 2026-03-20 작업 내역 (오전)

### 건물 데이터 보강
- [x] 건축물대장 API 승인 (국토교통부_건축HUB_건축물대장정보, ~2028-03-20)
- [x] 건축물대장 수집기 `src/collectors/building_collector.py` 구현
- [x] 상가정보 수집기 `src/collectors/commercial_collector.py` 구현 (반경 검색 포함)
- [x] 대치동 상가 3,987건 + 건축물대장 1,736건 수집
- [x] 비상업 시설 16개 geocoding (Nominatim) → `buildings_classified.json` 통합 (599개)
- [x] 목적지 유형 확장: 학교, 어린이집/복지, 종교시설, 운동시설, 문화시설 추가
- [x] 에이전트 동기 업데이트: "등원/등교", "산책/운동", "종교 활동" 추가

### 보행 네트워크 수집
- [x] 서울 OA-21208/21209 → ERROR-500, 대체 엔드포인트 발견
- [x] **도보 네트워크** `TbTraficWlkNet` 강남구 29,134건 수집 (12,654노드/16,480링크)
- [x] **횡단보도** `tbTraficCrsng` 강남구 2,062건 수집 (1,306노드/756링크)
- [x] 시뮬레이션 연동 확인: 11,366노드, 횡단보도 1,121개, 목적지 487개

### 인프라 정비
- [x] `src/utils/api_client.py`, `src/utils/cache.py` 복원
- [x] `src/collectors/base_collector.py` 복원
- [x] `.env`에 safemap API 키 추가
- [x] `config/settings.py`에 건축물대장, 상가 반경, safemap 엔드포인트 추가

### API 키 발급
- [x] 생활안전지도 API 키 발급 (`7M1YBFTM-...`)
  - 인도(IF_0095), 횡단보도(IF_0097) — 좌표 데이터 미포함 (속성만)

### 신규/수정 파일 목록

**코드:**
| 파일 | 상태 | 설명 |
|------|------|------|
| `src/collectors/building_collector.py` | 신규 | 건축물대장 표제부 수집기 |
| `src/collectors/commercial_collector.py` | 신규 | 상가정보 수집기 (반경 검색) |
| `src/collectors/base_collector.py` | 복원 | 공통 수집기 베이스 |
| `src/utils/api_client.py` | 복원 | HTTP 클라이언트 |
| `src/utils/cache.py` | 복원 | SQLite 캐시 |
| `src/simulation/local_agent.py` | 수정 | 비상업 시설 유형 + 동기 추가 |
| `config/settings.py` | 수정 | 건축물대장/safemap 엔드포인트 |
| `.env` | 수정 | safemap API 키 추가 |

**데이터 (`data/raw/`, gitignored):**
| 파일 | 건수 | 출처 |
|------|------|------|
| `walk_network_gangnam.json` | 29,134 | TbTraficWlkNet (강남구) |
| `crosswalk_gangnam.json` | 2,062 | tbTraficCrsng (강남구) |
| `stores_daechi_1km.json` | 3,987 | storeListInRadius |
| `buildings_classified.json` | 599 | 상가+건축물대장 통합 |
| `building_registry_daechi.json` | 1,736 | 건축물대장 표제부 (대치동) |
| `non_commercial_geocoded.json` | 59 | Nominatim geocoding |

---

## 2026-03-19 작업 내역

### 데이터 수집
- [x] 강남구 횡단보도 데이터 수집 (`crosswalk_gangnam.json`, 31,080건) — OA-21209 API
- [x] 대치동 반경 1km 상권정보 수집 (`stores_daechi_1km.json`, 3,987개 가게) — storeListInRadius API
- [x] 상권 데이터 기반 건물 분류 (`buildings_classified.json`, 585개 건물)

### 시뮬레이션 개편
- [x] **구역(zone) 개념 제거** → 실제 건물 좌표로 직접 이동하도록 변경
- [x] `sidewalk.py` — 횡단보도 31K건 통합, 지하철역 6개 노드 추가, 컴포넌트 자동 연결
- [x] `local_agent.py` — 건물 기반 목적지 선택 (436개 도달 가능 건물)
  - 다익스트라 1회 사전 계산 (apt → 모든 노드)
  - 11개 외출 동기 × 건물 유형 매칭
  - 거리 선호(near/mid/far) + 가게 수(인기도) 가중 선택
- [x] `08_local_sim.py` — 목적지 유형별 색상 매핑 (음식점=빨강, 학원=파랑 등)
- [x] `SIMULATION.md` 업데이트

### API 조사
- [x] V-World 건축물 API (LT_C_SPBD) 테스트 — 키 발급 완료 (`186FEA78-...`, 만료 2026-09-19)
  - `domain=localhost` 필요, 현재 INCORRECT_KEY 에러 간헐적 발생
- [x] 서울시 API: 지하철출구(ERROR-500), 버스정류장(ERROR-500) — 서버 불안정

---

## 완료된 작업

- [x] stash 변경사항 통합 (collect_all, process_all, agent_model 등)
- [x] 버스/실시간 인구/실시간 상권/스냅샷 수집기 4개 추가
- [x] 출퇴근 유동 분석 모듈 2개 (commute_analyzer, live_flow_analyzer)
- [x] 대시보드 08_commute, 09_sim_map 페이지 추가
- [x] 테스트 15개 추가 (전체 61 passed)
- [x] 세대수 수집기 (household_collector.py) — 행안부 + 국토부 API
- [x] 청약홈 분양정보 수집기 (subscription_collector.py) — APT/오피스텔 공급세대수
- [x] **세대수 기반 시뮬레이션 연동** (household_data_loader.py)
  - 주거유형별 에이전트 프로파일 (아파트/오피스텔/빌라 소득·소비·외출 차별화)
  - 지하철역 거리 기반 직장 배정 (거리 감쇠 모델: `1/(1+d)^1.5`)
  - 42개 동-동 간 거리 행렬 (Haversine)
  - 25개 구 도로명코드 확장
  - 대시보드 실제 데이터/기본값 토글
  - 테스트 18개 추가 (전체 79 passed)
- [x] **세대수 데이터 수집 완료** (2026-03-18)
  - 행안부 세대현황: 40,647건 (서울 25개 구 전체) → `data/raw/household.parquet`
  - 구별 요약: 25개 구 세대수·인구수 집계 → `data/raw/household_summary.parquet`
  - 청약 APT 분양: 50,640건 → `data/raw/subscription_apt.parquet`
  - 청약 오피스텔: 2,485건 → `data/raw/subscription_officetel.parquet`
  - 구로구 502 에러로 1,000건만 수집 (나머지 24개 구 정상)
  - 국토부 공동주택(`apt-household`)은 단지목록 API(AptListServiceV4) 미승인으로 수집 불가
- [x] **생활인구 수집 완료** (2026-03-18)
  - 수집기 버그 수정: 날짜 포맷 `YYYY-MM` → `YYYYMMDD` (API는 일 단위만 지원)
  - 월별 4일 샘플링 (1, 8, 15, 22일) 방식으로 변경
  - 2026-01: 40,704건 → `data/raw/population_202601.parquet` (11MB)
  - 2026-02: 40,704건 → `data/raw/population_202602.parquet` (11MB)
  - 2026-03: 20,352건 → `data/raw/population_202603.parquet` (5.5MB, 1·8일만 제공)
  - 참고: API에 2024~2025년 데이터 없음, 2026년만 수집 가능
- [x] **추정매출 수집 완료** (2026-03-18)
  - 수집기 버그 수정: 엔드포인트 `tbgisg` → `VwsmTrdarSelngQq`, 분기코드 URL 경로 포함
  - 2024 Q1: 21,910건 → `data/raw/spending_2024Q1.parquet` (5.5MB)
  - 2024 Q2: 21,887건 → `data/raw/spending_2024Q2.parquet` (5.6MB)
  - 2024 Q3: 21,718건 → `data/raw/spending_2024Q3.parquet` (5.5MB)
  - 2024 Q4: 21,664건 → `data/raw/spending_2024Q4.parquet` (5.5MB)
  - 합계: 87,179건 (22MB), 2024년 전 분기 완료
- [x] **수집일자 기록 파일 생성** → `data/collection_dates.json`

---

## API 활성화 확인 완료

- [x] **행안부 도로명별 주민등록 세대현황 API** — 동작 확인 완료
  - 실행: `python scripts/collect_all.py --target household`
  - 필수 파라미터: `roadNmCd`(12자리 도로명코드), `srchFrYm`, `srchToYm` (3개월 이내)
  - 데이터: 도로명 단위 세대수, 총인구수, 세대당인구 (강남구 2,421건 확인)

- [x] **국토부 공동주택 기본정보 API** — 동작 확인 완료
  - 실행: `python scripts/collect_all.py --target apt-household`
  - 필수 파라미터: `kaptCode`(단지코드)
  - 데이터: 아파트 단지별 세대수, 동수, 전용면적, 시공사, 법정동코드
  - 참고: 단지코드 목록 API(AptListServiceV4) 별도 승인 필요

- [x] **청약홈 분양정보 API** — 동작 확인 완료
  - 실행: `python scripts/collect_all.py --target subscription`
  - 데이터: APT/오피스텔 공급세대수, 경쟁률 (총 50,640건)

---

## 다음 단계

### 1. 건물 데이터 보강 (우선순위: 높음) — ✅ 완료 (2026-03-20)

- [x] **건축물대장 API 승인 및 수집기 구현** — `src/collectors/building_collector.py`
  - 대치동 1,736건 수집 (`data/raw/building_registry_daechi.json`)
  - 건물 용도(주거/상업/교육/노유자/종교 등), 연면적, 층수 정밀 데이터
- [x] **상가정보 수집기 리팩토링** — `src/collectors/commercial_collector.py`
  - 반경 검색(`collect_radius`) 지원 추가
  - 대치동 반경 1km 상가 3,987건 수집 (`data/raw/stores_daechi_1km.json`)
- [x] **비상업 시설 추가** — 건축물대장 기반 geocoding으로 16개 시설 통합
  - 학교 9, 어린이집/복지 4, 종교시설 2, 문화시설 1
  - `buildings_classified.json`: 583 → 599개 건물, 목적지 유형 6 → 10종
- [x] **보행 네트워크 대체** — 서울 OA-21208/21209 API 장애로 OSM(OpenStreetMap) 활용
  - osmnx로 800m 반경 보행 네트워크 수집 (628노드, 1,752링크)
  - Overpass API로 횡단보도 82개 수집
- [ ] V-World 건축물 API — 건물 폴리곤 필요 시 재시도 (현재 불필요)

### 2. 시뮬레이션 고도화 (우선순위: 중간) — ✅ 완료 (2026-03-20)

- [x] **에이전트 유형 분화** — 직장인(35%)/맞벌이(20%)/주부(15%)/학생(15%)/은퇴자(15%)
- [x] **시간대별 스케줄** — 이른아침/오전/점심/오후/저녁/밤 6개 시간대
- [x] **연쇄 이동 (trip chain)** — "학원→음식점", "운동→카페" 등 유형별 연쇄 규칙
- [x] **소비 시뮬레이션 연동** — 이동별 소비 금액, 프로파일/시간대별 집계
- [x] **대시보드 업데이트** — 탭 구조 (동기별/프로파일/소비/에이전트), 총소비 메트릭

### 3. 프로젝트 정리 (우선순위: 중간) — ✅ 완료 (2026-03-20)

- [x] `_remove/` 폴더로 미사용 파일 이동 완료 (이전 커밋에서)
- [x] `dashboard/app.py` — 현재 상태 반영 (시뮬레이션 구성 설명)
- [x] `dashboard/pages/08_local_sim.py` — v2 대시보드 (탭 UI, 소비 표시, 프로파일)
- [x] README.md — 현재 프로젝트 구조/기능/데이터 소스 전면 재작성

### 4. 데이터 기간 확장 (우선순위: 낮음)

- [ ] 지하철 승하차 2~12월 추가 수집 (현재 2024-01만)
- [ ] 부동산 실거래가 2~12월 추가 수집 (현재 2024-01만)
- [ ] 국토부 공동주택 단지목록 API(AptListServiceV4) 승인 후 수집

---

## 수집 명령어 요약

```bash
# 기존 데이터
python scripts/collect_all.py --target subway --year 2024 --month 1
python scripts/collect_all.py --target realestate --year 2024 --month 1
python scripts/collect_all.py --target commercial
python scripts/collect_all.py --target population --year 2026 --month 1   # ※ 2026년만 가능
python scripts/collect_all.py --target spending --year 2024 --month 1     # month→분기 자동변환

# 버스/실시간
python scripts/collect_all.py --target bus --year 2024 --month 1
python scripts/collect_all.py --target live
python scripts/collect_all.py --target live-snapshot

# 세대수/청약
python scripts/collect_all.py --target household        # 행안부 세대현황
python scripts/collect_all.py --target apt-household     # 국토부 공동주택 (API 미승인)
python scripts/collect_all.py --target subscription      # 청약홈 분양정보
```
