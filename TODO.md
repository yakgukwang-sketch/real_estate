# 프로젝트 다음 단계 (TODO)

> 작성일: 2026-03-18
> 현재 상태: master 브랜치, 9페이지 대시보드 + 세대수 기반 시뮬레이션 엔진 + 세대수/청약 수집기

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

### 1. 데이터 기간 확장 (우선순위: 높음)

- [ ] 지하철 승하차 2~12월 추가 수집 (현재 2024-01만)
- [ ] 부동산 실거래가 2~12월 추가 수집 (현재 2024-01만)
- [ ] 버스 승하차 추가 일자 수집 (평일/주말 비교용)

### 2. 청약 분양 대시보드 페이지 (우선순위: 중간)

- [ ] `dashboard/pages/10_subscription.py` — 청약 분양정보 시각화
  - 공급세대수 추이, 경쟁률 분석
  - 주택형별/지역별 분양 현황

### 3. 통합 테스트 및 검증 (우선순위: 낮음)

- [ ] 대시보드 전체 구동 확인
- [ ] 데이터 처리 파이프라인 재실행 (process_all.py)
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
