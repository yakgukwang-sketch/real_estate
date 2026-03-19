"""시뮬레이션 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import (
    bar_chart, line_chart, forecast_chart, inflow_outflow_chart,
    phase_spending_chart, dong_ranking_chart,
)
from dashboard.components.map_viewer import create_flow_map, render_map
from src.processors.geo_processor import DONG_CENTROIDS, SUBWAY_STATION_COORDS
from src.simulation.scenario_engine import ScenarioEngine
from src.simulation.forecast import Forecaster

st.header("시뮬레이션")

tab1, tab2, tab3, tab4 = st.tabs([
    "What-if 시나리오", "시계열 예측", "에이전트 시뮬레이션", "OD 유동 분석",
])


@st.cache_data
def load_all_data():
    data = {}
    for name in ["subway", "realestate", "commercial", "population", "spending", "bus"]:
        path = PROCESSED_DIR / f"{name}.parquet"
        if path.exists():
            data[name] = pd.read_parquet(path)
    return data


data = load_all_data()

# ---------- Tab 1: What-if 시나리오 ----------
with tab1:
    st.subheader("What-if 시나리오 분석")

    scenario_type = st.selectbox(
        "시나리오 유형",
        ["신규 지하철역 개통", "임대료 변동", "인구 변화", "복합 시나리오"],
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

            st.write("**파급효과 (인접 행정동)**")
            ripple = result.get("ripple_effects", [])
            if ripple:
                ripple_df = pd.DataFrame(ripple)
                st.dataframe(ripple_df, use_container_width=True)
            else:
                st.info("파급효과 데이터가 없습니다. GeoJSON 파일을 확인하세요.")

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

    elif scenario_type == "복합 시나리오":
        st.write("여러 시나리오를 조합하여 복합 효과를 분석합니다.")
        dong_code = st.text_input("대상 행정동코드", "1168010100", key="combined_dong")

        col1, col2, col3 = st.columns(3)
        with col1:
            enable_station = st.checkbox("신규 지하철역 개통")
            if enable_station:
                station_passengers = st.number_input("일일 승하차", 5000, 100000, 30000, 5000)
        with col2:
            enable_rent = st.checkbox("임대료 변동")
            if enable_rent:
                rent_pct = st.number_input("임대료 변동률 (%)", -50, 50, 10)
        with col3:
            enable_pop = st.checkbox("인구 변화")
            if enable_pop:
                pop_pct = st.number_input("인구 변동률 (%)", -50, 100, 20)

        if st.button("복합 시나리오 실행"):
            engine = ScenarioEngine(data)
            sub_results = []
            if enable_station:
                sub_results.append(
                    engine.new_station_scenario("신규역", dong_code, station_passengers)
                )
            if enable_rent:
                sub_results.append(engine.rent_change_scenario(dong_code, rent_pct))
            if enable_pop:
                sub_results.append(engine.population_change_scenario(dong_code, pop_pct))

            if sub_results:
                # 개별 시나리오 비교
                st.subheader("개별 시나리오 비교")
                comparison = engine.compare_scenarios(sub_results)
                st.dataframe(comparison, use_container_width=True)

                # 복합 효과
                combined = engine.combined_scenario(sub_results)
                st.subheader("복합 효과 (합산)")
                changes = combined["changes"]
                cols = st.columns(max(len(changes), 1))
                for i, (k, v) in enumerate(changes.items()):
                    with cols[i]:
                        delta = f"+{v}%" if v > 0 else f"{v}%"
                        st.metric(k, delta)
            else:
                st.warning("최소 하나의 시나리오를 선택하세요.")


# ---------- Tab 2: 시계열 예측 ----------
with tab2:
    st.subheader("시계열 예측")

    # 예측 대상 선택
    forecast_targets = {}
    if "realestate" in data and not data["realestate"].empty:
        forecast_targets["부동산 거래금액"] = ("realestate", "평균거래금액")
    if "spending" in data and not data["spending"].empty:
        for col in ["추정매출", "매출금액"]:
            if col in data["spending"].columns:
                forecast_targets["추정매출"] = ("spending", col)
                break
    if "subway" in data and not data["subway"].empty:
        for col in ["하차총승객수", "총하차"]:
            if col in data["subway"].columns:
                forecast_targets["유동인구 (지하철 하차)"] = ("subway", col)
                break
    if "population" in data and not data["population"].empty:
        for col in ["평균생활인구", "생활인구"]:
            if col in data["population"].columns:
                forecast_targets["생활인구"] = ("population", col)
                break

    if forecast_targets:
        target_name = st.selectbox("예측 대상", list(forecast_targets.keys()))
        ds_name, value_col = forecast_targets[target_name]
        df = data[ds_name]

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
                        dong_df, date_col="연월", value_col=value_col, periods=periods
                    )
                if not result.empty:
                    st.plotly_chart(
                        forecast_chart(result, title=f"{selected_dong} {target_name} 예측"),
                        use_container_width=True,
                    )
                else:
                    st.warning("예측에 충분한 데이터가 없습니다.")
        else:
            st.warning(f"{ds_name} 데이터에 행정동코드/연월 컬럼이 없습니다.")
    else:
        st.info("예측 가능한 데이터가 없습니다. 데이터를 먼저 수집/처리하세요.")


# ---------- Tab 3: 에이전트 시뮬레이션 ----------
with tab3:
    st.subheader("에이전트 기반 유동인구 시뮬레이션")
    st.info("""
    에이전트 기반 시뮬레이션은 다음을 모델링합니다:
    - **Resident 에이전트**: 거주동, 직장동, 소득수준, 소비패턴
    - **하루 행동**: 출근 → 주간 소비 → 퇴근 → 야간 소비
    - 결과: 행정동별 일일 소비액 추정
    """)

    PHASE_MAP = {
        "출근시간(오전)": "morning",
        "주간": "daytime",
        "퇴근시간(저녁)": "evening",
        "야간": "night",
    }

    # 데이터 소스 선택
    use_real_data = (
        "population" in data
        and not data["population"].empty
        and "행정동코드" in data["population"].columns
    )

    if use_real_data:
        data_source = st.radio(
            "데이터 소스",
            ["실제 데이터 (처리된 인구/지하철)", "샘플 데이터"],
            index=0,
        )
    else:
        data_source = "샘플 데이터"
        st.caption("처리된 인구 데이터가 없어 샘플 데이터를 사용합니다.")

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
            if data_source == "실제 데이터 (처리된 인구/지하철)" and use_real_data:
                try:
                    model = CityModel.from_processed_data(
                        population_df=data["population"],
                        subway_df=data.get("subway"),
                    )
                    st.success(f"실제 데이터 기반 모델 생성 (에이전트 {len(list(model.agents))}명)")
                except Exception as e:
                    st.warning(f"실제 데이터 로드 실패, 샘플 데이터 사용: {e}")
                    model = CityModel(sample_pop, sample_emp)
            else:
                model = CityModel(sample_pop, sample_emp)

            records = model.run(days=n_days)

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

        # 총 소비액 요약
        summary = model.get_summary()
        summary = {k: v * SCALE for k, v in summary.items()}

        st.session_state["sim_flow_df"] = flow_df
        st.session_state["sim_spending_df"] = spending_df
        st.session_state["sim_population_df"] = population_df
        st.session_state["sim_summary"] = summary
        st.session_state["sim_days"] = n_days
        st.session_state["sim_n_agents"] = len(list(model.agents)) * SCALE
        st.session_state["sim_model"] = model
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
            st.plotly_chart(fig_io, use_container_width=True)

        st.divider()

        # Row 4: 시간대별 소비 + 동별 랭킹 테이블
        col_spend, col_rank = st.columns([1, 1])
        with col_spend:
            fig_phase = phase_spending_chart(spending_df, title="시간대별 소비 비교")
            st.plotly_chart(fig_phase, use_container_width=True)

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
            st.dataframe(rank_df, use_container_width=True, hide_index=True)

        # Row 5: 일별 소비 추이 (stash에서 추가된 기능)
        if "sim_model" in st.session_state:
            model = st.session_state["sim_model"]
            daily_df = model.get_daily_series()
            if not daily_df.empty:
                st.divider()
                st.subheader("일별 소비 추이")
                summary_df = pd.DataFrame([
                    {"행정동": k, "총소비액": v} for k, v in sim_summary.items()
                ]).sort_values("총소비액", ascending=False)
                top_dongs = summary_df.head(5)["행정동"].tolist()
                daily_top = daily_df[daily_df["행정동"].isin(top_dongs)]
                if not daily_top.empty:
                    pivot = daily_top.pivot_table(
                        index="일차", columns="행정동", values="소비액", aggfunc="sum"
                    ).reset_index()
                    cols = [c for c in pivot.columns if c != "일차"]
                    st.plotly_chart(
                        line_chart(pivot, "일차", cols, title="상위 5개 행정동 일별 소비 추이"),
                        use_container_width=True,
                    )


# ---------- Tab 4: OD 유동 분석 ----------
with tab4:
    st.subheader("OD 유동 분석")
    st.info("""
    지하철/버스 승하차 데이터 기반 행정동 간 유동 패턴을 분석합니다.
    - **지역유형 분류**: 직장지역 / 주거지역 / 혼합지역
    - **유동 영향 추정**: 특정 동의 변화가 다른 동에 미치는 영향
    """)

    from src.simulation.flow_model import FlowModel

    subway_available = "subway" in data and not data["subway"].empty
    bus_available = "bus" in data and not data["bus"].empty

    if subway_available:
        flow_model = FlowModel()
        subway_df = data["subway"]

        # 지역유형 분류
        if st.button("지역유형 분류 실행"):
            required_cols = {"행정동코드", "승차총승객수", "하차총승객수"}
            if required_cols.issubset(subway_df.columns):
                type_df = flow_model.classify_dong_type(subway_df)

                type_counts = type_df["지역유형"].value_counts()
                cols = st.columns(3)
                for i, (t, c) in enumerate(type_counts.items()):
                    with cols[i % 3]:
                        st.metric(t, f"{c}개 동")

                st.dataframe(
                    type_df[["행정동코드", "총승차", "총하차", "순유입", "유입비율", "지역유형"]]
                    .sort_values("순유입", ascending=False),
                    use_container_width=True,
                )

                if bus_available:
                    st.caption("버스 데이터도 로드됨 — OD 행렬 구축 시 통합 분석 가능")
            else:
                st.warning(f"필요한 컬럼이 없습니다: {required_cols - set(subway_df.columns)}")

        # 유동 영향 추정
        st.divider()
        st.subheader("유동 영향 추정")
        st.caption("특정 행정동의 유동인구 변화가 다른 동에 미치는 영향")

        if "행정동코드" in subway_df.columns:
            dong_list = sorted(subway_df["행정동코드"].dropna().unique())
            target = st.selectbox("대상 행정동코드", dong_list[:50], key="od_target")
            change = st.slider("유동인구 변화율 (%)", -50, 100, 20, key="od_change")

            if st.button("영향 추정"):
                st.info("OD 행렬을 구축합니다. 행정동 중심좌표가 필요합니다.")
                # 간이 영향 추정: 승하차량 기반
                dong_agg = (
                    subway_df.groupby("행정동코드")
                    .agg(총승차=("승차총승객수", "sum"), 총하차=("하차총승객수", "sum"))
                    .reset_index()
                )
                if target in dong_agg["행정동코드"].values:
                    center = dong_agg[dong_agg["행정동코드"] == target].iloc[0]
                    center_total = center["총승차"] + center["총하차"]

                    impacts = []
                    for _, row in dong_agg.iterrows():
                        if row["행정동코드"] == target:
                            continue
                        other_total = row["총승차"] + row["총하차"]
                        ratio = min(other_total, center_total) / max(other_total, center_total, 1)
                        impact = change * ratio * 0.3
                        if abs(impact) > 0.5:
                            impacts.append({
                                "행정동코드": row["행정동코드"],
                                "연관도": round(ratio, 3),
                                "예상변화율(%)": round(impact, 1),
                            })

                    if impacts:
                        impact_df = pd.DataFrame(impacts).sort_values(
                            "예상변화율(%)", key=abs, ascending=False
                        )
                        st.dataframe(impact_df.head(15), use_container_width=True)
                    else:
                        st.info("유의미한 영향이 있는 동이 없습니다.")
    else:
        st.warning("지하철 데이터가 필요합니다. 데이터를 먼저 수집/처리하세요.")
