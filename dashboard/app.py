"""서울 상권 시뮬레이션 - Streamlit 메인 앱."""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

st.set_page_config(
    page_title="서울 상권 시뮬레이션",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("래미안 대치팰리스 상권 시뮬레이션")
st.markdown("""
래미안 대치팰리스 주민의 **이동 · 소비 패턴**을 시뮬레이션합니다.

### 시뮬레이션 구성
- **보행 네트워크**: 서울시 도보 네트워크 (11,366노드) + 횡단보도 (1,121개)
- **건물 데이터**: 상가정보 + 건축물대장 통합 (599건물, 487개 도달 가능)
- **에이전트**: 5개 유형 (직장인/맞벌이/주부/학생/은퇴자)
- **시간대**: 이른아침~밤 6개 시간대별 행동 스케줄
- **소비**: 업종별 객단가, 연쇄 이동(trip chain) 포함
""")

st.page_link("pages/08_local_sim.py", label="주민 이동 시뮬레이션", icon="🚶")

st.divider()
st.caption("streamlit run dashboard/app.py")
