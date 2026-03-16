"""시뮬레이션 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import bar_chart, forecast_chart
from src.simulation.scenario_engine import ScenarioEngine
from src.simulation.forecast import Forecaster

st.header("시뮬레이션")

tab1, tab2, tab3 = st.tabs(["What-if 시나리오", "시계열 예측", "에이전트 시뮬레이션"])


@st.cache_data
def load_all_data():
    data = {}
    for name in ["subway", "realestate", "commercial", "population", "spending"]:
        path = PROCESSED_DIR / f"{name}.parquet"
        if path.exists():
            data[name] = pd.read_parquet(path)
    return data


data = load_all_data()

with tab1:
    st.subheader("What-if 시나리오 분석")

    scenario_type = st.selectbox(
        "시나리오 유형",
        ["신규 지하철역 개통", "임대료 변동", "인구 변화"],
    )

    if scenario_type == "신규 지하철역 개통":
        col1, col2 = st.columns(2)
        with col1:
            station_name = st.text_input("신규역 이름", "신규역")
            dong_code = st.text_input("해당 행정동코드", "1168010100")
        with col2:
            daily_passengers = st.slider("예상 일일 승하차 인원", 5000, 100000, 30000, 5000)

        if st.button("시나리오 실행", key="new_station"):
            engine = ScenarioEngine(data)
            result = engine.new_station_scenario(station_name, dong_code, daily_passengers)

            st.subheader("시나리오 결과")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Before**")
                st.json(result["before"])
            with col2:
                st.write("**After**")
                st.json(result["after"])

            st.write("**변화 예측**")
            changes = result["changes"]
            cols = st.columns(len(changes))
            for i, (k, v) in enumerate(changes.items()):
                with cols[i]:
                    delta = f"+{v}%" if v > 0 else f"{v}%"
                    st.metric(k, delta)

            st.write("**파급효과**")
            st.dataframe(pd.DataFrame(result.get("ripple_effects", [])))

    elif scenario_type == "임대료 변동":
        dong_code = st.text_input("대상 행정동코드", "1168010100", key="rent_dong")
        rent_change = st.slider("임대료 변동률 (%)", -50, 50, 20)

        if st.button("시나리오 실행", key="rent_change"):
            engine = ScenarioEngine(data)
            result = engine.rent_change_scenario(dong_code, rent_change)
            st.subheader("변화 예측")
            changes = result["changes"]
            cols = st.columns(len(changes))
            for i, (k, v) in enumerate(changes.items()):
                with cols[i]:
                    delta = f"+{v}%" if v > 0 else f"{v}%"
                    st.metric(k, delta)

    elif scenario_type == "인구 변화":
        dong_code = st.text_input("대상 행정동코드", "1168010100", key="pop_dong")
        pop_change = st.slider("인구 변동률 (%)", -50, 100, 30)

        if st.button("시나리오 실행", key="pop_change"):
            engine = ScenarioEngine(data)
            result = engine.population_change_scenario(dong_code, pop_change)
            st.subheader("변화 예측")
            changes = result["changes"]
            cols = st.columns(len(changes))
            for i, (k, v) in enumerate(changes.items()):
                with cols[i]:
                    delta = f"+{v}%" if v > 0 else f"{v}%"
                    st.metric(k, delta)

with tab2:
    st.subheader("시계열 예측")
    if "realestate" in data and not data["realestate"].empty:
        df = data["realestate"]
        if "행정동코드" in df.columns and "연월" in df.columns:
            dong_codes = df["행정동코드"].dropna().unique()
            selected_dong = st.selectbox("행정동 선택", sorted(dong_codes)[:50])
            periods = st.slider("예측 기간 (월)", 3, 24, 12)
            method = st.selectbox("예측 방법", ["prophet", "arima"])

            if st.button("예측 실행"):
                forecaster = Forecaster(method=method)
                dong_df = df[df["행정동코드"] == selected_dong]
                with st.spinner("예측 중..."):
                    result = forecaster.forecast(
                        dong_df, date_col="연월", value_col="평균거래금액", periods=periods
                    )
                if not result.empty:
                    st.plotly_chart(
                        forecast_chart(result, title=f"{selected_dong} 거래금액 예측"),
                        use_container_width=True,
                    )
                else:
                    st.warning("예측에 충분한 데이터가 없습니다.")
    else:
        st.info("부동산 데이터가 필요합니다.")

with tab3:
    st.subheader("에이전트 기반 시뮬레이션")
    st.info("""
    에이전트 기반 시뮬레이션은 다음을 모델링합니다:
    - **Resident 에이전트**: 거주동, 직장동, 소득수준, 소비패턴
    - **하루 행동**: 출근 → 주간 소비 → 퇴근 → 야간 소비
    - 결과: 행정동별 일일 소비액 추정

    대규모 시뮬레이션은 시간이 소요될 수 있습니다.
    """)

    n_days = st.slider("시뮬레이션 일수", 1, 90, 30)

    if st.button("시뮬레이션 실행"):
        from src.simulation.agent_model import CityModel

        # 간단한 테스트 데이터
        sample_pop = {"강남동": 50000, "역삼동": 40000, "서초동": 35000}
        sample_emp = {"강남동": 100000, "역삼동": 80000, "서초동": 60000}

        with st.spinner(f"{n_days}일 시뮬레이션 실행 중..."):
            model = CityModel(sample_pop, sample_emp)
            records = model.run(days=n_days)

        summary = model.get_summary()
        summary_df = pd.DataFrame([
            {"행정동": k, "총소비액": v} for k, v in summary.items()
        ]).sort_values("총소비액", ascending=False)

        st.plotly_chart(
            bar_chart(summary_df, "행정동", "총소비액", title=f"{n_days}일 간 행정동별 추정 소비액"),
            use_container_width=True,
        )
