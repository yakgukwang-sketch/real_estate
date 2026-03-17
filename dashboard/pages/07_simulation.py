"""시뮬레이션 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import (
    bar_chart, forecast_chart, inflow_outflow_chart,
    phase_spending_chart, dong_ranking_chart,
)
from dashboard.components.map_viewer import create_flow_map, render_map
from src.processors.geo_processor import DONG_CENTROIDS, SUBWAY_STATION_COORDS
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
                        width="stretch",
                    )
                else:
                    st.warning("예측에 충분한 데이터가 없습니다.")
    else:
        st.info("부동산 데이터가 필요합니다.")

with tab3:
    st.subheader("에이전트 기반 유동인구 시뮬레이션")

    PHASE_MAP = {
        "출근시간(오전)": "morning",
        "주간": "daytime",
        "퇴근시간(저녁)": "evening",
        "야간": "night",
    }

    n_days = st.slider("시뮬레이션 일수", 1, 90, 7, key="agent_sim_days")

    if st.button("시뮬레이션 실행", key="agent_sim_run"):
        from src.simulation.agent_model import CityModel

        # 샘플 데이터 (처리된 데이터가 없을 경우)
        sample_pop = {
            "강남동": 50000, "역삼동": 40000, "서초동": 35000,
            "삼성동": 30000, "잠실동": 45000, "홍대동": 25000,
            "여의도동": 20000, "신림동": 55000, "노원동": 60000,
            "구로동": 35000, "마포동": 28000, "성수동": 22000,
            "종로동": 15000, "명동": 10000, "압구정동": 18000,
        }
        sample_emp = {
            "강남동": 100000, "역삼동": 80000, "서초동": 60000,
            "삼성동": 50000, "잠실동": 30000, "홍대동": 20000,
            "여의도동": 70000, "신림동": 15000, "노원동": 10000,
            "구로동": 40000, "마포동": 25000, "성수동": 35000,
            "종로동": 45000, "명동": 55000, "압구정동": 15000,
        }

        with st.spinner(f"{n_days}일 시뮬레이션 실행 중..."):
            model = CityModel(sample_pop, sample_emp)
            model.run(days=n_days)

        # 에이전트 1명 = 실제 100명이므로 실제 스케일로 환산
        SCALE = 100

        flow_df = model.get_flow_summary()
        if not flow_df.empty:
            flow_df["count"] = flow_df["count"] * SCALE

        spending_df = model.get_phase_spending()
        if not spending_df.empty:
            spending_df["spending"] = spending_df["spending"] * SCALE

        population_df = model.get_dong_population()
        if not population_df.empty:
            population_df["population"] = population_df["population"] * SCALE

        summary = model.get_summary()
        summary = {k: v * SCALE for k, v in summary.items()}

        st.session_state["sim_flow_df"] = flow_df
        st.session_state["sim_spending_df"] = spending_df
        st.session_state["sim_population_df"] = population_df
        st.session_state["sim_summary"] = summary
        st.session_state["sim_days"] = n_days
        st.session_state["sim_n_agents"] = len(list(model.agents)) * SCALE
        st.success("시뮬레이션 완료!")

    # 결과 표시 (세션 상태에 데이터가 있을 때)
    if "sim_flow_df" in st.session_state:
        flow_df = st.session_state["sim_flow_df"]
        spending_df = st.session_state["sim_spending_df"]
        population_df = st.session_state["sim_population_df"]
        sim_summary = st.session_state["sim_summary"]
        sim_days = st.session_state["sim_days"]
        sim_n_agents = st.session_state["sim_n_agents"]

        total_spending = sum(sim_summary.values())
        busiest_dong = max(sim_summary, key=sim_summary.get) if sim_summary else "-"

        # Row 1: 메트릭 카드
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.metric("총 에이전트 수", f"{sim_n_agents:,}명")
        with mc2:
            st.metric("총 소비액", f"{total_spending:,.0f}원")
        with mc3:
            st.metric("시뮬레이션 일수", f"{sim_days}일")
        with mc4:
            st.metric("가장 활발한 지역", busiest_dong)

        st.divider()

        # Row 2: 시간대 선택
        selected_phase_label = st.select_slider(
            "시간대 선택",
            options=list(PHASE_MAP.keys()),
            value="출근시간(오전)",
            key="sim_phase_slider",
        )
        selected_phase = PHASE_MAP[selected_phase_label]

        # Row 3: 지도 + 유입/유출 차트
        col_map, col_bar = st.columns([2, 1])
        with col_map:
            st.markdown(f"**{selected_phase_label} 유동인구 흐름 지도**")
            flow_map = create_flow_map(
                flow_df=flow_df,
                spending_df=spending_df,
                population_df=population_df,
                coord_map=DONG_CENTROIDS,
                phase=selected_phase,
                station_coords=SUBWAY_STATION_COORDS,
            )
            from streamlit_folium import st_folium
            st_folium(flow_map, width=None, height=500, returned_objects=[])

        with col_bar:
            st.markdown(f"**{selected_phase_label} 유입/유출 분석**")
            phase_flow = flow_df[flow_df["phase"] == selected_phase] if not flow_df.empty else flow_df
            fig_io = inflow_outflow_chart(phase_flow, title=f"{selected_phase_label} 순유입/유출")
            st.plotly_chart(fig_io, width="stretch")

        st.divider()

        # Row 4: 시간대별 소비 + 동별 랭킹 테이블
        col_spend, col_rank = st.columns([1, 1])
        with col_spend:
            fig_phase = phase_spending_chart(spending_df, title="시간대별 소비 비교")
            st.plotly_chart(fig_phase, width="stretch")

        with col_rank:
            st.markdown("**동별 인구 & 소비 순위**")
            # 랭킹 테이블
            pop_total = population_df.groupby("dong")["population"].sum().reset_index()
            spend_total = spending_df.groupby("dong")["spending"].sum().reset_index()
            rank_df = pd.merge(pop_total, spend_total, on="dong", how="outer").fillna(0)
            rank_df.columns = ["행정동", "총 인구(연인원)", "총 소비액"]
            rank_df["1인당 소비"] = (rank_df["총 소비액"] / rank_df["총 인구(연인원)"].replace(0, 1)).round(0)
            rank_df = rank_df.sort_values("총 소비액", ascending=False)
            rank_df["총 소비액"] = rank_df["총 소비액"].apply(lambda x: f"{x:,.0f}")
            rank_df["총 인구(연인원)"] = rank_df["총 인구(연인원)"].apply(lambda x: f"{x:,.0f}")
            rank_df["1인당 소비"] = rank_df["1인당 소비"].apply(lambda x: f"{x:,.0f}")
            st.dataframe(rank_df, width="stretch", hide_index=True)
