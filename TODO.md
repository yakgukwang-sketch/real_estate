# 프로젝트 다음 단계 (TODO)

> 최종 업데이트: 2026-03-19
> 현재 상태: master 브랜치, 래미안 대치팰리스 로컬 시뮬레이션 (실제 건물 목적지 기반)

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

### 1. 건물 데이터 보강 (우선순위: 높음)

- [ ] **V-World 건축물 API 안정화** — `domain` 파라미터 이슈 해결 후 건물 폴리곤 다운로드
- [ ] **건축물대장 API 신청** — data.go.kr `국토교통부_건축물대장정보 서비스` 활용신청
  - 건물 용도(주거/상업/업무), 연면적, 층수 등 정밀 데이터
- [ ] 비상업 시설 추가 — 학교, 공원, 관공서 등 (현재 상권 API 기반이라 상업시설만 있음)

### 2. 시뮬레이션 고도화 (우선순위: 중간)

- [ ] **에이전트 유형 분화** — 직장인/학생/은퇴자/맞벌이 등 프로파일별 행동 차별화
- [ ] **시간대별 스케줄** — 출근(07~09), 점심(11~13), 퇴근(17~19) 등 시간 흐름 반영
- [ ] **연쇄 이동 (trip chain)** — "학원→카페→마트" 같은 복합 이동
- [ ] **소비 시뮬레이션 연동** — `local_spending.py`와 에이전트 이동 결합

### 3. 프로젝트 정리 (우선순위: 중간)

- [ ] `_remove/` 폴더로 미사용 파일 이동 (plan 참조: `rosy-inventing-lerdorf.md`)
- [ ] `dashboard/app.py`, `src/simulation/__init__.py` 정리
- [ ] README.md 업데이트 (현재 상태 반영)

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
