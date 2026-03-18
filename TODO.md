# 프로젝트 다음 단계 (TODO)

> 작성일: 2026-03-18
> 현재 상태: master 브랜치, 기본 7페이지 대시보드 + 시뮬레이션 엔진 완료

---

## 1단계: stash된 변경사항 통합 (우선순위: 높음)

stash에 보류 중인 변경사항을 현재 코드에 통합해야 합니다.

- [ ] `collect_all.py` — 버스, 실시간 인구, 실시간 상권, 스냅샷 수집 타겟 추가
- [ ] `process_all.py` — 버스 데이터 처리 파이프라인 추가
- [ ] `config/settings.py` — 버스 API 엔드포인트, 실시간 API 설정 추가
- [ ] `src/simulation/agent_model.py` — CityModel에 `get_movement_summary()`, `get_daily_series()` 메서드 추가
- [ ] `src/simulation/flow_model.py` — 버스 데이터 통합 OD 모델 확장
- [ ] `README.md` — 10개 API, 9페이지 대시보드 등 문서 업데이트

---

## 2단계: 새 수집기 등록 (우선순위: 높음)

이미 코드가 작성되어 있지만 아직 untracked 상태인 모듈들:

- [ ] `src/collectors/bus_collector.py` — 서울시 버스 승하차 인원 수집기 (git add 필요)
- [ ] `src/collectors/live_commercial_collector.py` — 82개 장소 실시간 상권현황 수집기
- [ ] `src/collectors/live_population_collector.py` — 82개 장소 실시간 인구 데이터 수집기
- [ ] `src/collectors/live_snapshot_collector.py` — 실시간 인구 스냅샷 누적 수집기 (시간대별 유동 패턴 축적)

---

## 3단계: 새 분석 모듈 등록 (우선순위: 높음)

- [ ] `src/analysis/commute_analyzer.py` — 출퇴근 유동 분석 (시간대별 인구 유동, 목적지 유형 분류, OD 추정)
- [ ] `src/analysis/live_flow_analyzer.py` — 실시간 스냅샷 기반 유동 분석 (장소 기능 분류, 평일/주말 비교)

---

## 4단계: 새 대시보드 페이지 등록 (우선순위: 중간)

- [ ] `dashboard/pages/08_commute.py` — 출퇴근 유동 분석 페이지 (4탭: 시간대별 인구, 목적지 유형, OD 종합, 실시간 스냅샷)
- [ ] `dashboard/pages/09_sim_map.py` — 시뮬레이션 지도 시각화 (4개 지도: 소비 히트맵, 출퇴근 유동 화살표, 직주 분류, 1인당 소비 효율)

---

## 5단계: 새 테스트 등록 (우선순위: 중간)

- [ ] `tests/test_commute.py` — CommuteAnalyzer 유닛 테스트 (7개 테스트)
- [ ] `tests/test_live_flow.py` — LiveFlowAnalyzer + LiveSnapshotCollector 유닛 테스트 (8개 테스트)
- [ ] 전체 테스트 실행 확인: `python -m pytest tests/ -v`

---

## 6단계: 데이터 파이프라인 확장 (우선순위: 중간)

- [ ] `collect_all.py`에 새 타겟 추가:
  - `bus` — 버스 승하차 월별 수집
  - `live-population` — 실시간 인구 수집
  - `live-commercial` — 실시간 상권 수집
  - `live-snapshot` — 스냅샷 누적 수집 (cron으로 1시간마다 실행 권장)
- [ ] `process_all.py`에 버스 데이터 처리 + 통합 파이프라인 추가

---

## 7단계: 통합 테스트 및 검증 (우선순위: 낮음)

- [ ] 새 수집기 API 키 동작 확인
- [ ] 스냅샷 수집 → 분석 → 대시보드 end-to-end 검증
- [ ] 대시보드 9개 페이지 전체 구동 확인
- [ ] README.md 최종 업데이트 (10개 API, 9페이지, 76+ 테스트)

---

## 참고: 현재 파일 상태

### 이미 작성 완료 (untracked — git add 필요)
```
src/collectors/bus_collector.py
src/collectors/live_commercial_collector.py
src/collectors/live_population_collector.py
src/collectors/live_snapshot_collector.py
src/analysis/commute_analyzer.py
src/analysis/live_flow_analyzer.py
dashboard/pages/08_commute.py
dashboard/pages/09_sim_map.py
tests/test_commute.py
tests/test_live_flow.py
```

### stash에 보류 중 (git stash pop 필요)
```
README.md, config/settings.py, collect_all.py, process_all.py,
agent_model.py, flow_model.py, commercial_collector.py, realestate_collector.py
```
