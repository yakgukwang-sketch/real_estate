"""서울 상권 & 부동산 시뮬레이션 - Streamlit 메인 앱."""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

st.set_page_config(
    page_title="서울 상권 & 부동산 시뮬레이션",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("서울 상권 & 부동산 시뮬레이션")
st.markdown("""
서울시의 **사람 이동 패턴**과 **소비 패턴**을 분석하는 시뮬레이션 대시보드입니다.

### 데이터 소스
- **지하철 승하차**: 호선별 역별 일별 승하차 인원
- **부동산 실거래가**: 아파트/빌라 매매 실거래 데이터
- **상권 정보**: 소상공인 상가업소 정보
- **생활인구**: 행정동 단위 시간대별 생활인구
- **추정매출**: 상권별 업종별 추정매출

### 분석 기능
1. **서울 전체 현황**: 주요 지표 요약
2. **지하철 승하차 분석**: 역별/행정동별 유동인구
3. **부동산 실거래가**: 아파트/빌라 가격 추이
4. **상권 분석**: 업종 분포, 상권 활성도
5. **생활/직장 인구**: 인구 분포 및 이동 패턴
6. **상관관계 종합**: 교차 상관분석
7. **시뮬레이션**: What-if 시나리오

👈 **사이드바에서 페이지를 선택하세요.**
""")

# 데이터 상태 확인
from config.settings import PROCESSED_DIR, GEO_DIR

col1, col2 = st.columns(2)
with col1:
    st.subheader("데이터 상태")
    geo_exists = (GEO_DIR / "seoul_dong.geojson").exists()
    st.write(f"- GeoJSON: {'✅' if geo_exists else '❌ scripts/seed_geodata.py 실행 필요'}")

    parquet_files = list(PROCESSED_DIR.glob("*.parquet")) if PROCESSED_DIR.exists() else []
    st.write(f"- 처리된 데이터: {len(parquet_files)}개 파일")

with col2:
    st.subheader("시작하기")
    st.code("""
# 1. 환경 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 2. GeoJSON 다운로드
python scripts/seed_geodata.py

# 3. 데이터 수집
python scripts/collect_all.py

# 4. 데이터 처리
python scripts/process_all.py

# 5. 대시보드 실행
streamlit run dashboard/app.py
    """, language="bash")
