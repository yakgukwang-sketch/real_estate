# 프로젝트 다음 단계 (TODO)

> 작성일: 2026-03-18
> 현재 상태: master 브랜치, 9페이지 대시보드 + 시뮬레이션 엔진 + 세대수/청약 수집기

---

## 완료된 작업

- [x] stash 변경사항 통합 (collect_all, process_all, agent_model 등)
- [x] 버스/실시간 인구/실시간 상권/스냅샷 수집기 4개 추가
- [x] 출퇴근 유동 분석 모듈 2개 (commute_analyzer, live_flow_analyzer)
- [x] 대시보드 08_commute, 09_sim_map 페이지 추가
- [x] 테스트 15개 추가 (전체 61 passed)
- [x] 세대수 수집기 (household_collector.py) — 행안부 + 국토부 API
- [x] 청약홈 분양정보 수집기 (subscription_collector.py) — APT/오피스텔 공급세대수

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

### 1. 세대수 데이터 시뮬레이션 연동 (우선순위: 높음)

API 활성화 후:
- [ ] 세대수 데이터 수집 실행
- [ ] 행정동별 세대수 집계 (아파트/오피스텔/빌라 유형별)
- [ ] `agent_model.py`에 세대수 기반 인구 생성 로직 추가
- [ ] `09_sim_map.py`의 BASE_POPULATION을 실제 세대수 데이터로 교체

### 2. 청약 분양 대시보드 페이지 (우선순위: 중간)

- [ ] `dashboard/pages/10_subscription.py` — 청약 분양정보 시각화
  - 공급세대수 추이, 경쟁률 분석
  - 주택형별/지역별 분양 현황

### 3. 통합 테스트 및 검증 (우선순위: 낮음)

- [ ] 새 수집기 API 키 동작 확인 (활성화 후)
- [ ] 대시보드 전체 구동 확인
- [ ] README.md 최종 업데이트

---

## 수집 명령어 요약

```bash
# 기존 데이터
python scripts/collect_all.py --target subway --year 2024 --month 1
python scripts/collect_all.py --target realestate --year 2024 --month 1
python scripts/collect_all.py --target commercial
python scripts/collect_all.py --target population --year 2024 --month 1
python scripts/collect_all.py --target spending --year 2024 --month 1

# 버스/실시간
python scripts/collect_all.py --target bus --year 2024 --month 1
python scripts/collect_all.py --target live
python scripts/collect_all.py --target live-snapshot

# 세대수/청약 (신규)
python scripts/collect_all.py --target household        # 행안부 세대현황
python scripts/collect_all.py --target apt-household     # 국토부 공동주택
python scripts/collect_all.py --target subscription      # 청약홈 분양정보
```
