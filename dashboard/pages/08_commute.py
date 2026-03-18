"""출퇴근 유동 분석 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from config.settings import PROCESSED_DIR
from dashboard.components.chart_builder import bar_chart, heatmap_chart, line_chart
from src.analysis.commute_analyzer import CommuteAnalyzer

st.header("출퇴근 유동 분석")
st.caption("아침에 사람들이 어디로 가고, 저녁에 어디로 돌아오는지 분석합니다.")

tab1, tab2, tab3, tab4 = st.tabs([
    "시간대별 인구 유동", "목적지 유형 분석", "출퇴근 OD 종합", "실시간 스냅샷 분석",
])


@st.cache_data
def load_data():
    data = {}
    for name in ["population", "commercial", "subway", "bus"]:
        path = PROCESSED_DIR / f"{name}.parquet"
        if path.exists():
            data[name] = pd.read_parquet(path)
    return data


data = load_data()
analyzer = CommuteAnalyzer()

# ---------- Tab 1: 시간대별 인구 유동 ----------
with tab1:
    st.subheader("시간대별 행정동 인구 변화")
    st.info("""
    야간(0~6시) 인구 = **상주인구** 추정
    주간(10~17시) 인구 = **활동인구** 추정
    **주간유입률** = (주간인구 - 야간인구) / 야간인구 × 100
    → 양수: 출근 유입지 (직장·학교 밀집) / 음수: 출근 유출지 (주거 밀집)
    """)

    if "population" in data and "시간대" in data["population"].columns:
        pop_df = data["population"]
        flow = analyzer.analyze_hourly_flow(pop_df)

        if not flow.empty:
            # 지역유형 요약
            type_counts = flow["지역유형"].value_counts()
            cols = st.columns(len(type_counts))
            for i, (t, c) in enumerate(type_counts.items()):
                with cols[i]:
                    st.metric(t, f"{c}개 동")

            # 주간유입률 상위/하위
            col1, col2 = st.columns(2)
            with col1:
                st.write("**직장·학교 밀집 지역 (유입 상위)**")
                top = flow.head(15)[["행정동코드", "야간인구", "주간인구", "주간유입률", "지역유형"]]
                st.dataframe(top, use_container_width=True)
            with col2:
                st.write("**주거 밀집 지역 (유출 상위)**")
                bottom = flow.tail(15)[["행정동코드", "야간인구", "주간인구", "주간유입률", "지역유형"]]
                st.dataframe(bottom, use_container_width=True)

            # 주간유입률 분포 차트
            chart_df = flow.dropna(subset=["주간유입률"]).sort_values("주간유입률", ascending=False).head(30)
            st.plotly_chart(
                bar_chart(chart_df, "행정동코드", "주간유입률",
                          title="주간유입률 상위 30개 행정동 (%)", color="지역유형"),
                use_container_width=True,
            )
        else:
            st.warning("시간대별 인구 분석 결과가 없습니다.")
    else:
        st.info("시간대별 생활인구 데이터가 필요합니다. `population` 데이터에 '시간대' 컬럼이 있어야 합니다.")


# ---------- Tab 2: 목적지 유형 분석 ----------
with tab2:
    st.subheader("행정동별 목적지 유형 분포")
    st.info("""
    상가 업종 데이터를 기반으로 각 행정동이 **어떤 목적**으로 방문되는지 추정합니다.
    - **직장**: 사무실, 금융, IT, 제조, 도매 등
    - **학교·학원**: 교육 관련 업종
    - **소비·여가**: 음식점, 카페, 여가시설
    - **의료**: 병원, 약국 등
    """)

    if "commercial" in data:
        dest_types = analyzer.classify_destination_types(data["commercial"])

        if not dest_types.empty:
            # 주요 목적지 유형 분포
            if "주요목적지" in dest_types.columns:
                type_dist = dest_types["주요목적지"].value_counts()
                cols = st.columns(len(type_dist))
                for i, (t, c) in enumerate(type_dist.items()):
                    with cols[i % len(cols)]:
                        st.metric(f"{t} 밀집", f"{c}개 동")

            # 업소수 상위 행정동
            st.write("**업소수 상위 행정동 + 목적지 유형 비율**")
            top_areas = dest_types.nlargest(20, "총업소수")
            st.dataframe(top_areas, use_container_width=True)

            # 특정 행정동 상세
            dong_list = sorted(dest_types["행정동코드"].unique())
            selected = st.selectbox("행정동 선택 (상세 보기)", dong_list[:100])
            if selected:
                row = dest_types[dest_types["행정동코드"] == selected]
                if not row.empty:
                    ratio_cols = [c for c in row.columns if c.endswith("_비율")]
                    if ratio_cols:
                        chart_data = pd.DataFrame({
                            "유형": [c.replace("_비율", "") for c in ratio_cols],
                            "비율": row.iloc[0][ratio_cols].values,
                        })
                        import plotly.express as px
                        fig = px.pie(chart_data, values="비율", names="유형",
                                     title=f"{selected} 목적지 유형 비율")
                        st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("목적지 유형 분석 결과가 없습니다.")
    else:
        st.info("상가 데이터가 필요합니다.")


# ---------- Tab 3: 출퇴근 OD 종합 ----------
with tab3:
    st.subheader("출퇴근 유동 종합 분석")
    st.info("""
    시간대별 인구 + 지하철/버스 승하차 + 상가 업종을 결합하여
    **아침에 사람들이 어디서 출발해서 어디로 가는지** 종합적으로 추정합니다.
    """)

    has_hourly_pop = "population" in data and "시간대" in data.get("population", pd.DataFrame()).columns

    if has_hourly_pop:
        if st.button("종합 분석 실행"):
            with st.spinner("출퇴근 유동 분석 중..."):
                result = analyzer.build_commute_matrix(
                    population_df=data["population"],
                    commercial_df=data.get("commercial"),
                    subway_df=data.get("subway"),
                )

            # 요약
            summary = result.get("summary", {})
            if summary:
                cols = st.columns(4)
                cols[0].metric("직장밀집 지역", f"{summary.get('직장밀집_동수', 0)}개 동")
                cols[1].metric("주거밀집 지역", f"{summary.get('주거밀집_동수', 0)}개 동")
                cols[2].metric("혼합 지역", f"{summary.get('혼합_동수', 0)}개 동")
                cols[3].metric("최대 유입률", f"{summary.get('최대유입률', 0)}%")

            # 출퇴근 도착지 (직장·학교) 순위
            dest_rank = result.get("dest_rankings")
            if dest_rank is not None and not dest_rank.empty:
                st.write("**아침 출근 도착지 TOP 20** (주간유입률 높은 동)")
                display_cols = ["행정동코드", "야간인구", "주간인구", "주간유입률", "지역유형"]
                if "교통순유입" in dest_rank.columns:
                    display_cols.append("교통순유입")
                if "지하철순유입" in dest_rank.columns:
                    display_cols.append("지하철순유입")
                available = [c for c in display_cols if c in dest_rank.columns]
                st.dataframe(dest_rank[available], use_container_width=True)

            # 출발지 (주거지) 순위
            origins = result.get("origins")
            if origins is not None and not origins.empty:
                st.write("**아침 출근 출발지 TOP 20** (주간유입률 낮은 동 = 주거지)")
                display_cols = ["행정동코드", "야간인구", "주간인구", "주간유입률", "지역유형"]
                if "교통순유입" in origins.columns:
                    display_cols.append("교통순유입")
                available = [c for c in display_cols if c in origins.columns]
                st.dataframe(origins[available], use_container_width=True)

            # 목적지 유형
            dest_types = result.get("destinations")
            if dest_types is not None and not dest_types.empty:
                st.divider()
                st.write("**도착지 행정동의 방문 목적 분포**")

                # 도착지 top 10의 업종 유형
                if dest_rank is not None and not dest_rank.empty:
                    top_dest_codes = dest_rank.head(10)["행정동코드"].tolist()
                    top_dest_types = dest_types[dest_types["행정동코드"].isin(top_dest_codes)]
                    if not top_dest_types.empty:
                        st.dataframe(top_dest_types, use_container_width=True)

            # 전체 flow 데이터
            flow = result.get("flow")
            if flow is not None and not flow.empty:
                with st.expander("전체 유동 데이터 보기"):
                    st.dataframe(flow, use_container_width=True)
    else:
        st.warning(
            "시간대별 생활인구 데이터가 필요합니다.\n\n"
            "생활인구 데이터에 '시간대' 컬럼이 포함되어야 시간대별 분석이 가능합니다."
        )


# ---------- Tab 4: 실시간 스냅샷 분석 ----------
with tab4:
    st.subheader("실시간 인구 스냅샷 기반 유동 분석")
    st.info("""
    82개 주요 장소의 실시간 인구 데이터를 **주기적으로 누적 수집**하여
    시간대별 실측 유동 패턴을 분석합니다.

    스냅샷 수집: `python scripts/collect_all.py --target live-snapshot`
    (1시간마다 실행하면 하루 24개 스냅샷 축적)
    """)

    from src.collectors.live_snapshot_collector import LiveSnapshotCollector
    from src.analysis.live_flow_analyzer import LiveFlowAnalyzer

    snapshot_collector = LiveSnapshotCollector()
    flow_analyzer = LiveFlowAnalyzer()

    snapshot_count = snapshot_collector.get_snapshot_count()
    st.metric("누적 스냅샷 수", f"{snapshot_count}회")

    if snapshot_count > 0:
        snapshots = snapshot_collector.load_all_snapshots()

        if not snapshots.empty:
            sub1, sub2, sub3, sub4 = st.tabs([
                "장소별 기능 분류", "시간대별 인구 곡선", "유입/유출 방향", "평일 vs 주말",
            ])

            with sub1:
                st.write("**시간대 패턴 기반 장소 기능 자동 분류**")
                classification = flow_analyzer.classify_area_function(snapshots)
                if not classification.empty:
                    # 기능별 카운트
                    func_counts = classification["장소기능"].value_counts()
                    cols = st.columns(min(len(func_counts), 5))
                    for i, (f, c) in enumerate(func_counts.items()):
                        with cols[i % len(cols)]:
                            st.metric(f, f"{c}개 장소")

                    st.dataframe(
                        classification[[
                            "장소명", "야간인구", "주간인구", "주야비율",
                            "피크시간", "피크인구", "장소기능",
                        ]],
                        use_container_width=True,
                    )

            with sub2:
                st.write("**장소별 24시간 인구 곡선**")
                area_list = sorted(snapshots["장소명"].unique())
                selected_areas = st.multiselect(
                    "장소 선택 (최대 5개)",
                    area_list,
                    default=area_list[:3] if len(area_list) >= 3 else area_list,
                    max_selections=5,
                )
                if selected_areas:
                    profile = flow_analyzer.build_hourly_profile(snapshots)
                    profile_selected = profile[profile["장소명"].isin(selected_areas)]
                    if not profile_selected.empty:
                        pivot = profile_selected.pivot(
                            index="수집시간", columns="장소명", values="추정인구"
                        ).reset_index()
                        cols_to_plot = [c for c in pivot.columns if c != "수집시간"]
                        st.plotly_chart(
                            line_chart(pivot, "수집시간", cols_to_plot,
                                       title="시간대별 추정 인구"),
                            use_container_width=True,
                        )

            with sub3:
                st.write("**오전 유입 / 저녁 유출 방향 분석**")
                flow_dir = flow_analyzer.detect_flow_direction(snapshots)
                if not flow_dir.empty:
                    display_cols = ["장소명", "최대유입시간", "최대유입량",
                                    "최대유출시간", "최대유출량"]
                    if "오전유입량" in flow_dir.columns:
                        display_cols.extend(["오전유입량", "저녁유출량", "출퇴근패턴"])
                    available = [c for c in display_cols if c in flow_dir.columns]
                    st.dataframe(flow_dir[available], use_container_width=True)

            with sub4:
                st.write("**평일 vs 주말 주간 인구 비교**")
                if "수집날짜" in snapshots.columns:
                    comparison = flow_analyzer.compare_weekday_weekend(snapshots)
                    if not comparison.empty:
                        st.dataframe(comparison, use_container_width=True)
                    else:
                        st.info("비교에 충분한 데이터가 없습니다.")
                else:
                    st.info("수집날짜 컬럼이 없습니다.")

            # 장소 상세
            st.divider()
            st.subheader("장소 상세 분석")
            area_list = sorted(snapshots["장소명"].unique())
            detail_area = st.selectbox("장소 선택", area_list, key="detail_area")
            if detail_area:
                detail = flow_analyzer.get_area_detail(snapshots, detail_area)
                if detail:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("총 스냅샷 수", detail["총스냅샷수"])
                        if detail.get("수집기간"):
                            st.caption(f"수집 기간: {detail['수집기간']['시작'][:10]} ~ {detail['수집기간']['종료'][:10]}")
                    with col2:
                        if detail.get("혼잡도분포"):
                            st.write("**혼잡도 분포**")
                            st.json(detail["혼잡도분포"])

                    hourly = detail.get("시간대별")
                    if hourly is not None and not hourly.empty:
                        st.plotly_chart(
                            line_chart(hourly, "시간", ["평균인구", "최소인구", "최대인구"],
                                       title=f"{detail_area} 시간대별 인구"),
                            use_container_width=True,
                        )

                    if detail.get("연령대비율"):
                        st.write("**평균 연령대 비율**")
                        st.json(detail["연령대비율"])
    else:
        st.info(
            "아직 수집된 스냅샷이 없습니다.\n\n"
            "다음 명령으로 스냅샷을 수집하세요:\n"
            "```bash\n"
            "python scripts/collect_all.py --target live-snapshot\n"
            "```\n"
            "1시간마다 실행하면 시간대별 유동 패턴을 축적할 수 있습니다."
        )
