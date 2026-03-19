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

st.title("서울 상권 시뮬레이션")
st.markdown("""
서울시 **상권 · 유동인구 · 소비 패턴** 시뮬레이션 대시보드입니다.

현재 **래미안 대치팰리스** 일대를 정밀 시뮬레이션하고 있으며,
점진적으로 서울 전역으로 확장할 예정입니다.

### 현재 기능
- **인도 네트워크**: 대치동 보행 네트워크 그래프
- **에이전트 시뮬레이션**: 보행자 이동 시뮬레이션
- **로컬 소비**: 상권 소비 시뮬레이션

👈 **사이드바에서 페이지를 선택하세요.**
""")

st.subheader("시작하기")
st.code("""
# 1. 환경 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 2. 대시보드 실행
streamlit run dashboard/app.py
""", language="bash")
