"""시뮬레이션 결과 지도 시각화 페이지."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import AntPath, HeatMap, MiniMap, FloatImage
from streamlit_folium import st_folium

st.set_page_config(layout="wide") if not hasattr(st, "_is_running_with_streamlit") else None

st.header("시뮬레이션 지도 시각화")

# ── GeoJSON 로드 ──
GEOJSON_PATH = Path("data/geo/seoul_dong.geojson")
geojson_data = None
GU_CENTERS = {}

if GEOJSON_PATH.exists():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)
    # 구별 중심 좌표 계산
    for feat in geojson_data["features"]:
        name_eng = feat["properties"]["name_eng"]
        gu_name = name_eng.replace("-gu", "구").replace("-", "")
        coords = feat["geometry"]["coordinates"]
        # MultiPolygon or Polygon
        if feat["geometry"]["type"] == "MultiPolygon":
            all_pts = [p for poly in coords for ring in poly for p in ring]
        else:
            all_pts = [p for ring in coords for p in ring]
        lons = [p[0] for p in all_pts]
        lats = [p[1] for p in all_pts]
        GU_CENTERS[name_eng] = ((min(lats)+max(lats))/2, (min(lons)+max(lons))/2)

# ── 서울 주요 지역 좌표 (50개 동) ──
DONG_COORDS = {
    # 강남·서초
    "강남동": (37.4979, 127.0276), "역삼동": (37.5006, 127.0369),
    "서초동": (37.4916, 127.0076), "삼성동": (37.5089, 127.0631),
    "논현동": (37.5105, 127.0289), "압구정동": (37.5270, 127.0286),
    "청담동": (37.5247, 127.0472), "대치동": (37.4943, 127.0578),
    # 잠실·송파·강동
    "잠실동": (37.5133, 127.1000), "송파동": (37.5048, 127.1120),
    "천호동": (37.5388, 127.1237), "길동": (37.5325, 127.1450),
    # 마포·서대문·은평
    "마포동": (37.5395, 126.9458), "홍대동": (37.5571, 126.9241),
    "신촌동": (37.5553, 126.9369), "연남동": (37.5660, 126.9258),
    "합정동": (37.5496, 126.9136), "상암동": (37.5775, 126.8916),
    # 영등포·여의도·구로
    "영등포동": (37.5246, 126.8961), "여의도동": (37.5215, 126.9243),
    "구로동": (37.4851, 126.9015), "가산동": (37.4795, 126.8830),
    "문래동": (37.5176, 126.8968),
    # 용산·중구·종로
    "이태원동": (37.5346, 126.9943), "명동": (37.5610, 126.9859),
    "종로동": (37.5701, 126.9830), "광화문": (37.5759, 126.9769),
    "을지로": (37.5660, 126.9910), "충무로": (37.5580, 126.9940),
    "남산동": (37.5540, 126.9850),
    # 성동·광진·건대
    "성수동": (37.5446, 127.0558), "건대동": (37.5406, 127.0697),
    "왕십리동": (37.5614, 127.0382), "자양동": (37.5352, 127.0734),
    "뚝섬": (37.5475, 127.0472),
    # 노원·도봉·강북·성북
    "노원동": (37.6554, 127.0613), "수유동": (37.6395, 127.0240),
    "미아동": (37.6260, 127.0280), "길음동": (37.6103, 127.0258),
    "상계동": (37.6620, 127.0710),
    # 동대문·중랑
    "회기동": (37.5897, 127.0574), "청량리": (37.5804, 127.0469),
    "면목동": (37.5762, 127.0905),
    # 관악·동작·금천
    "신림동": (37.4841, 126.9299), "봉천동": (37.4812, 126.9422),
    "사당동": (37.4765, 126.9816), "신대방동": (37.4894, 126.9236),
    # 양천·강서
    "목동": (37.5242, 126.8748), "화곡동": (37.5410, 126.8395),
    "발산동": (37.5510, 126.8379), "등촌동": (37.5510, 126.8589),
}

# ── 구별 주요 업종/특성 ──
DONG_FEATURES = {
    "강남동": "IT·스타트업 밀집, 테헤란로 오피스",
    "역삼동": "대기업 본사, 금융·IT",
    "서초동": "법원·검찰청, 법조타운",
    "삼성동": "코엑스·무역센터, 컨벤션",
    "논현동": "가구거리, 주거+상업 혼합",
    "압구정동": "고급 주거, 로데오거리",
    "청담동": "명품 상권, 고급 레스토랑",
    "대치동": "학원가, 교육특구",
    "잠실동": "롯데월드·잠실종합운동장, 관광",
    "송파동": "주거 밀집, 신도시형",
    "마포동": "주거+상업, 마포구청",
    "홍대동": "문화·예술, 클럽·카페",
    "신촌동": "대학가, 유동인구 많음",
    "연남동": "카페거리, MZ 트렌드",
    "영등포동": "영등포역 상권, 전통시장",
    "여의도동": "금융중심, 국회·증권가",
    "구로동": "구로디지털단지, IT·제조",
    "가산동": "가산디지털단지, 중소기업",
    "이태원동": "다국적 문화, 외국인 상권",
    "명동": "관광 중심, 쇼핑",
    "종로동": "전통 상권, 종묘·인사동",
    "광화문": "정부청사, 오피스",
    "성수동": "수제맥주·카페, 뜨는 상권",
    "건대동": "먹자골목, 대학가 상권",
    "왕십리동": "비투지, 교통 허브",
    "노원동": "주거 밀집, 베드타운",
    "신림동": "고시촌·대학가, 원룸 밀집",
    "목동": "주거 밀집, 학군 우수",
    "사당동": "교통 요지, 주거+상업",
    "청량리": "전통시장, 교통 허브",
}

# 기본 인구/고용 데이터 (50개 동)
BASE_POPULATION = {
    "강남동": 45000, "역삼동": 38000, "서초동": 42000, "삼성동": 18000,
    "논현동": 32000, "압구정동": 20000, "청담동": 15000, "대치동": 35000,
    "잠실동": 55000, "송파동": 60000, "천호동": 45000, "길동": 38000,
    "마포동": 35000, "홍대동": 28000, "신촌동": 32000, "연남동": 18000,
    "합정동": 22000, "상암동": 25000,
    "영등포동": 40000, "여의도동": 12000, "구로동": 48000, "가산동": 15000,
    "문래동": 20000,
    "이태원동": 15000, "명동": 8000, "종로동": 20000, "광화문": 5000,
    "을지로": 10000, "충무로": 12000, "남산동": 8000,
    "성수동": 22000, "건대동": 25000, "왕십리동": 30000, "자양동": 35000,
    "뚝섬": 15000,
    "노원동": 65000, "수유동": 45000, "미아동": 40000, "길음동": 35000,
    "상계동": 55000,
    "회기동": 25000, "청량리": 28000, "면목동": 42000,
    "신림동": 50000, "봉천동": 45000, "사당동": 38000, "신대방동": 32000,
    "목동": 52000, "화곡동": 48000, "발산동": 30000, "등촌동": 28000,
}

BASE_EMPLOYMENT = {
    "강남동": 120000, "역삼동": 95000, "서초동": 80000, "삼성동": 70000,
    "논현동": 30000, "압구정동": 25000, "청담동": 35000, "대치동": 40000,
    "잠실동": 40000, "송파동": 35000, "천호동": 25000, "길동": 15000,
    "마포동": 60000, "홍대동": 45000, "신촌동": 30000, "연남동": 20000,
    "합정동": 25000, "상암동": 55000,
    "영등포동": 70000, "여의도동": 90000, "구로동": 55000, "가산동": 65000,
    "문래동": 40000,
    "이태원동": 25000, "명동": 65000, "종로동": 45000, "광화문": 85000,
    "을지로": 55000, "충무로": 35000, "남산동": 20000,
    "성수동": 50000, "건대동": 35000, "왕십리동": 25000, "자양동": 18000,
    "뚝섬": 20000,
    "노원동": 20000, "수유동": 15000, "미아동": 18000, "길음동": 15000,
    "상계동": 12000,
    "회기동": 30000, "청량리": 35000, "면목동": 15000,
    "신림동": 15000, "봉천동": 12000, "사당동": 25000, "신대방동": 15000,
    "목동": 25000, "화곡동": 18000, "발산동": 15000, "등촌동": 12000,
}

# ── 시뮬레이션 설정 ──
st.sidebar.header("시뮬레이션 설정")

# 데이터 소스 선택
st.sidebar.subheader("데이터 소스")
use_real_data = st.sidebar.checkbox("실제 세대수 데이터 사용", value=True)
data_status = {}
housing_dist = {}
distance_matrix = {}

if use_real_data:
    try:
        from src.simulation.household_data_loader import HouseholdDataLoader
        loader = HouseholdDataLoader()
        data_status = loader.get_data_status()
        has_any_data = any(data_status.values())

        if has_any_data:
            sim_input = loader.build_simulation_input(
                fallback_population=BASE_POPULATION,
                fallback_employment=BASE_EMPLOYMENT,
            )
            REAL_POPULATION = sim_input["dong_population"]
            REAL_EMPLOYMENT = sim_input["dong_employment"]
            housing_dist = sim_input["housing_distribution"]
            distance_matrix = sim_input["distance_matrix"]

            avail = [k for k, v in data_status.items() if v]
            st.sidebar.success(f"데이터 로드: {', '.join(avail)}")
        else:
            st.sidebar.warning("수집된 데이터 없음 → 기본값 사용")
            use_real_data = False
    except Exception as e:
        st.sidebar.error(f"데이터 로드 실패: {e}")
        use_real_data = False

dong_options = list(DONG_COORDS.keys())
selected_dongs = st.sidebar.multiselect(
    "행정동 선택",
    dong_options,
    default=dong_options[:30],
)

n_days = st.sidebar.slider("시뮬레이션 일수", 1, 90, 30)

st.sidebar.subheader("인구 설정")
pop_scale = st.sidebar.selectbox("인구 규모", ["소규모 (테스트)", "중규모", "대규모"], index=1)

pop_multipliers = {"소규모 (테스트)": 0.3, "중규모": 1.0, "대규모": 2.0}
mult = pop_multipliers[pop_scale]

st.sidebar.subheader("지도 설정")
map_tile = st.sidebar.selectbox("배경 지도", [
    "CartoDB Positron", "CartoDB Dark", "OpenStreetMap", "Stamen Toner",
], index=0)
TILE_MAP = {
    "CartoDB Positron": "cartodbpositron",
    "CartoDB Dark": "cartodbdark_matter",
    "OpenStreetMap": "openstreetmap",
    "Stamen Toner": "stamentoner",
}
tile_name = TILE_MAP[map_tile]

show_gu_boundary = st.sidebar.checkbox("구 경계선 표시", value=True)
show_labels = st.sidebar.checkbox("동 이름 라벨", value=True)
map_height = st.sidebar.slider("지도 높이", 400, 800, 600, step=50)

if use_real_data and 'REAL_POPULATION' in dir():
    dong_pop = {d: int(REAL_POPULATION.get(d, BASE_POPULATION.get(d, 30000)) * mult) for d in selected_dongs}
    dong_emp = {d: int(REAL_EMPLOYMENT.get(d, BASE_EMPLOYMENT.get(d, 40000)) * mult) for d in selected_dongs}
else:
    dong_pop = {d: int(BASE_POPULATION.get(d, 30000) * mult) for d in selected_dongs}
    dong_emp = {d: int(BASE_EMPLOYMENT.get(d, 40000) * mult) for d in selected_dongs}


def _add_gu_boundaries(m):
    """구 경계선 GeoJSON 레이어 추가."""
    if geojson_data is None:
        return
    folium.GeoJson(
        geojson_data,
        name="구 경계",
        style_function=lambda feat: {
            "fillColor": "transparent",
            "color": "#555",
            "weight": 1.5,
            "dashArray": "5,3",
            "fillOpacity": 0,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["name_eng"],
            aliases=["구:"],
            style="font-size:12px;",
        ),
    ).add_to(m)


def _add_minimap(m):
    """미니맵 추가."""
    MiniMap(toggle_display=True, position="bottomright", width=120, height=120).add_to(m)


def _make_popup_html(dong, extra_rows=""):
    """상세 팝업 HTML 생성."""
    pop = dong_pop.get(dong, 0)
    emp = dong_emp.get(dong, 0)
    ratio = emp / pop if pop > 0 else 0
    feature = DONG_FEATURES.get(dong, "")

    if emp > pop * 1.5:
        type_badge = '<span style="background:#e74c3c;color:white;padding:2px 6px;border-radius:10px;font-size:11px;">직장밀집</span>'
    elif pop > emp * 1.5:
        type_badge = '<span style="background:#3498db;color:white;padding:2px 6px;border-radius:10px;font-size:11px;">주거밀집</span>'
    else:
        type_badge = '<span style="background:#95a5a6;color:white;padding:2px 6px;border-radius:10px;font-size:11px;">혼합</span>'

    # 인구 대비 고용 비율 바
    bar_pct = min(ratio * 50, 100)
    bar_color = "#e74c3c" if ratio > 1.5 else "#3498db" if ratio < 0.7 else "#95a5a6"

    html = f"""
    <div style="font-family:'맑은 고딕',sans-serif;min-width:220px;">
        <h4 style="margin:0 0 5px 0;border-bottom:2px solid #333;padding-bottom:3px;">
            {dong} {type_badge}
        </h4>
        <div style="font-size:11px;color:#666;margin-bottom:8px;">{feature}</div>
        <table style="font-size:12px;width:100%;border-collapse:collapse;">
            <tr><td style="padding:2px 0;">👤 거주인구</td><td style="text-align:right;font-weight:bold;">{pop:,}명</td></tr>
            <tr><td style="padding:2px 0;">💼 직장인구</td><td style="text-align:right;font-weight:bold;">{emp:,}명</td></tr>
            <tr><td style="padding:2px 0;">📊 직주비율</td><td style="text-align:right;">{ratio:.2f}</td></tr>
            {extra_rows}
        </table>
        <div style="margin-top:6px;">
            <div style="font-size:10px;color:#888;">직주비율</div>
            <div style="background:#eee;border-radius:3px;height:8px;overflow:hidden;">
                <div style="background:{bar_color};height:100%;width:{bar_pct}%;"></div>
            </div>
        </div>
    </div>
    """
    return html


# ── 시뮬레이션 실행 ──
if st.button("시뮬레이션 실행", type="primary"):
    from src.simulation.agent_model import CityModel

    with st.spinner(f"{len(selected_dongs)}개 동, {n_days}일 시뮬레이션 중..."):
        # 선택된 동만 포함하도록 필터링
        filtered_housing = {d: housing_dist[d] for d in selected_dongs if d in housing_dist} if housing_dist else None
        model = CityModel(
            dong_pop, dong_emp,
            housing_distribution=filtered_housing or None,
            distance_matrix=distance_matrix or None,
        )
        model.run(days=n_days)

    agents = list(model.agents)
    summary = model.get_summary()
    movements = model.get_movement_summary()
    daily = model.get_daily_series()

    data_label = "실제 세대수 데이터" if use_real_data and housing_dist else "기본 데이터"
    st.success(f"완료! 에이전트 {len(agents)}명, {n_days}일 시뮬레이션 ({data_label})")

    # 주거유형 분포 표시
    housing_summary = model.get_housing_type_summary()
    if not housing_summary.empty:
        st.subheader("주거유형별 에이전트 분포")
        cols = st.columns(len(housing_summary))
        type_labels = {"apt": "아파트", "officetel": "오피스텔", "villa": "빌라"}
        for i, (_, row) in enumerate(housing_summary.iterrows()):
            with cols[i]:
                label = type_labels.get(row["주거유형"], row["주거유형"])
                st.metric(label, f"{row['에이전트수']:,}명", f"{row['비율']}%")

    # ── 요약 메트릭 ──
    total_spending = sum(summary.values())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 소비액", f"{total_spending/100000000:.1f}억원")
    col2.metric("에이전트 수", f"{len(agents):,}명")
    col3.metric("일평균 소비", f"{total_spending/n_days/10000:,.0f}만원")
    col4.metric("행정동 수", f"{len(selected_dongs)}개")

    # ── 일별 소비 추이 차트 ──
    daily_df = daily if isinstance(daily, pd.DataFrame) else pd.DataFrame(daily)
    if not daily_df.empty and "일차" in daily_df.columns:
        st.subheader("📈 일별 소비 추이")
        col_a, col_b = st.columns(2)
        with col_a:
            # 전체 일별 합계
            daily_total = daily_df.groupby("일차")["소비액"].sum().reset_index()
            daily_total["소비액(만원)"] = daily_total["소비액"] / 10000
            st.line_chart(daily_total.set_index("일차")["소비액(만원)"], height=250)
            st.caption("전체 일별 소비 합계")
        with col_b:
            # 동별 일별 추이 (상위 5개)
            dong_totals = daily_df.groupby("행정동")["소비액"].sum().nlargest(5).index.tolist()
            top_daily = daily_df[daily_df["행정동"].isin(dong_totals)]
            pivot = top_daily.pivot(index="일차", columns="행정동", values="소비액") / 10000
            st.line_chart(pivot, height=250)
            st.caption("소비 상위 5개 동 일별 추이 (만원)")

    # ══════════════════════════════════════
    # 지도 1: 소비 히트맵
    # ══════════════════════════════════════
    st.subheader("🔥 행정동별 소비 히트맵")
    st.caption("원 크기 = 소비 규모, 색상 = 소비 강도 (진할수록 많음). 클릭하면 상세 정보.")

    m = folium.Map(location=[37.545, 127.00], zoom_start=12, tiles=tile_name)
    if show_gu_boundary:
        _add_gu_boundaries(m)
    _add_minimap(m)

    max_spending = max(summary.values()) if summary else 1

    # 히트맵 데이터
    heat_data = []
    for dong, total in summary.items():
        if dong in DONG_COORDS:
            lat, lon = DONG_COORDS[dong]
            heat_data.append([lat, lon, total / max_spending])

    HeatMap(
        heat_data,
        name="소비 히트맵",
        radius=35,
        blur=25,
        max_zoom=15,
        gradient={0.2: "#ffffb2", 0.4: "#fecc5c", 0.6: "#fd8d3c", 0.8: "#f03b20", 1.0: "#bd0026"},
    ).add_to(m)

    # 동별 마커
    for dong, total in summary.items():
        if dong not in DONG_COORDS:
            continue
        lat, lon = DONG_COORDS[dong]
        ratio = total / max_spending
        radius = 8 + ratio * 30
        daily_avg = total / n_days

        # 그라데이션 색상
        r = int(189 + 66 * ratio)
        g = int(max(0, 200 * (1 - ratio ** 0.5)))
        b = int(max(0, 100 * (1 - ratio)))
        color = f"#{min(r,255):02x}{g:02x}{b:02x}"

        extra = f"""
            <tr><td style="padding:2px 0;">💰 총 소비</td><td style="text-align:right;font-weight:bold;color:#e74c3c;">{total/10000:,.0f}만원</td></tr>
            <tr><td style="padding:2px 0;">📅 일평균</td><td style="text-align:right;">{daily_avg/10000:,.0f}만원/일</td></tr>
            <tr><td style="padding:2px 0;">🏆 소비순위</td><td style="text-align:right;">{sorted(summary.values(), reverse=True).index(total)+1}위/{len(summary)}개</td></tr>
        """
        popup_html = _make_popup_html(dong, extra)

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=2,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{dong}: {total/10000:,.0f}만원",
        ).add_to(m)

        if show_labels:
            folium.Marker(
                location=[lat + 0.002, lon],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:10px;font-weight:bold;color:#333;'
                         f'text-shadow:1px 1px 2px white,-1px -1px 2px white;'
                         f'white-space:nowrap;">{dong}</div>',
                    icon_size=(100, 16),
                    icon_anchor=(50, 8),
                ),
            ).add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width=None, height=map_height, returned_objects=[])

    # ══════════════════════════════════════
    # 지도 2: 출퇴근 유동 화살표
    # ══════════════════════════════════════
    st.subheader("🚇 출퇴근 유동 흐름")
    st.caption("애니메이션 화살표: 출근 이동 (주거지 → 직장지). 굵기 = 이동량, 색상 = 경로 구분")

    m2 = folium.Map(location=[37.545, 127.00], zoom_start=12, tiles=tile_name)
    if show_gu_boundary:
        _add_gu_boundaries(m2)
    _add_minimap(m2)

    if not movements.empty:
        # 출근 + 퇴근 분리
        commute_moves = movements[movements["목적"] == "출근"]
        return_moves = movements[movements["목적"] == "퇴근"]
        max_moves = commute_moves["이동횟수"].max() if not commute_moves.empty else 1

        flow_type = st.radio(
            "유동 유형", ["출근 (주거→직장)", "퇴근 (직장→주거)", "전체 이동"],
            horizontal=True,
        )

        if flow_type == "출근 (주거→직장)":
            display_moves = commute_moves.head(20)
        elif flow_type == "퇴근 (직장→주거)":
            display_moves = return_moves.head(20)
            max_moves = return_moves["이동횟수"].max() if not return_moves.empty else 1
        else:
            display_moves = movements.head(25)
            max_moves = movements["이동횟수"].max() if not movements.empty else 1

        colors = [
            "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
            "#2980b9", "#27ae60", "#d35400", "#8e44ad", "#2c3e50",
            "#e91e63", "#00bcd4", "#ff5722", "#607d8b", "#795548",
            "#4caf50", "#ff9800", "#673ab7", "#009688", "#f44336",
        ]

        # 출발지/도착지별 집계
        origin_counts = {}
        dest_counts = {}

        for i, (_, row) in enumerate(display_moves.iterrows()):
            origin = row["출발지"]
            dest = row["도착지"]
            count = row["이동횟수"]

            if origin not in DONG_COORDS or dest not in DONG_COORDS:
                continue

            origin_counts[origin] = origin_counts.get(origin, 0) + count
            dest_counts[dest] = dest_counts.get(dest, 0) + count

            lat1, lon1 = DONG_COORDS[origin]
            lat2, lon2 = DONG_COORDS[dest]
            weight = 2 + (count / max_moves) * 8
            color = colors[i % len(colors)]

            AntPath(
                locations=[[lat1, lon1], [lat2, lon2]],
                color=color,
                weight=weight,
                opacity=0.7,
                dash_array=[10, 20],
                delay=800,
                pulse_color="#ffffff",
            ).add_to(m2)

            # 중간점 라벨
            mid_lat = (lat1 + lat2) / 2 + 0.001
            mid_lon = (lon1 + lon2) / 2
            folium.Marker(
                [mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:9px;color:{color};font-weight:bold;'
                         f'background:rgba(255,255,255,0.9);padding:2px 5px;border-radius:3px;'
                         f'border:1px solid {color};white-space:nowrap;'
                         f'box-shadow:0 1px 3px rgba(0,0,0,0.2);">'
                         f'{origin}→{dest} ({count:,}회)</div>',
                    icon_size=(180, 22),
                    icon_anchor=(90, 11),
                ),
            ).add_to(m2)

        # 출발지 마커 (파란색, 크기 비례)
        max_origin = max(origin_counts.values()) if origin_counts else 1
        for dong, cnt in origin_counts.items():
            lat, lon = DONG_COORDS[dong]
            r = 8 + (cnt / max_origin) * 15
            folium.CircleMarker(
                [lat, lon], radius=r, color="#3498db", fill=True,
                fill_color="#3498db", fill_opacity=0.7, weight=2,
                tooltip=f"출발: {dong} ({cnt:,}회)",
                popup=folium.Popup(
                    f"<b>{dong}</b> (출발지)<br>출발 횟수: {cnt:,}회<br>"
                    f"거주인구: {dong_pop.get(dong,0):,}명",
                    max_width=200,
                ),
            ).add_to(m2)

        # 도착지 마커 (빨간색, 크기 비례)
        max_dest = max(dest_counts.values()) if dest_counts else 1
        for dong, cnt in dest_counts.items():
            if dong in origin_counts:
                continue  # 중복 방지
            lat, lon = DONG_COORDS[dong]
            r = 8 + (cnt / max_dest) * 15
            folium.CircleMarker(
                [lat, lon], radius=r, color="#e74c3c", fill=True,
                fill_color="#e74c3c", fill_opacity=0.7, weight=2,
                tooltip=f"도착: {dong} ({cnt:,}회)",
                popup=folium.Popup(
                    f"<b>{dong}</b> (도착지)<br>도착 횟수: {cnt:,}회<br>"
                    f"직장인구: {dong_emp.get(dong,0):,}명",
                    max_width=200,
                ),
            ).add_to(m2)

        # 범례
        legend2 = """
        <div style="position:fixed;top:80px;right:30px;z-index:9999;
            background:white;padding:10px 14px;border-radius:8px;
            border:1px solid #ddd;box-shadow:0 2px 6px rgba(0,0,0,0.15);font-size:12px;">
            <b>범례</b><br>
            <span style="color:#3498db;">●</span> 출발지 (주거)<br>
            <span style="color:#e74c3c;">●</span> 도착지 (직장)<br>
            <span style="font-size:16px;">⟿</span> 이동 경로 (굵기=이동량)
        </div>
        """
        m2.get_root().html.add_child(folium.Element(legend2))

    st_folium(m2, width=None, height=map_height, returned_objects=[])

    # ══════════════════════════════════════
    # 지도 3: 직장/주거 지역 분류 + Choropleth
    # ══════════════════════════════════════
    st.subheader("🏢 직장밀집 vs 🏠 주거밀집 지역")
    st.caption("빨강 = 직장밀집 (고용 > 거주×1.5), 파랑 = 주거밀집 (거주 > 고용×1.5), 회색 = 혼합")

    m3 = folium.Map(location=[37.545, 127.00], zoom_start=12, tiles=tile_name)
    if show_gu_boundary:
        _add_gu_boundaries(m3)
    _add_minimap(m3)

    for dong in selected_dongs:
        if dong not in DONG_COORDS:
            continue
        lat, lon = DONG_COORDS[dong]
        pop = dong_pop.get(dong, 0)
        emp = dong_emp.get(dong, 0)

        if emp > pop * 1.5:
            color = "#e74c3c"
            label = "직장밀집"
            icon_text = "💼"
        elif pop > emp * 1.5:
            color = "#3498db"
            label = "주거밀집"
            icon_text = "🏠"
        else:
            color = "#95a5a6"
            label = "혼합"
            icon_text = "🔄"

        radius = 8 + max(pop, emp) / max(max(dong_pop.values()), 1) * 25

        popup_html = _make_popup_html(dong)

        folium.CircleMarker(
            [lat, lon],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.55,
            weight=2,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{dong} ({label}) | 거주:{pop:,} 직장:{emp:,}",
        ).add_to(m3)

        if show_labels:
            folium.Marker(
                [lat, lon],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:10px;font-weight:bold;color:{color};'
                         f'text-shadow:1px 1px 2px white,-1px -1px 2px white;'
                         f'text-align:center;line-height:1.2;">'
                         f'{dong}<br><span style="font-size:8px;">({label})</span></div>',
                    icon_size=(90, 30),
                    icon_anchor=(45, 15),
                ),
            ).add_to(m3)

    # 범례
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;
        background:white;padding:12px 16px;border-radius:8px;
        border:1px solid #ddd;box-shadow:0 2px 6px rgba(0,0,0,0.15);font-size:12px;">
        <b style="font-size:13px;">지역 유형 분류</b><br><br>
        <span style="display:inline-block;width:14px;height:14px;background:#e74c3c;border-radius:50%;vertical-align:middle;"></span>
        <b style="color:#e74c3c;">직장밀집</b> — 고용인구 > 거주인구 × 1.5<br>
        <span style="display:inline-block;width:14px;height:14px;background:#3498db;border-radius:50%;vertical-align:middle;"></span>
        <b style="color:#3498db;">주거밀집</b> — 거주인구 > 고용인구 × 1.5<br>
        <span style="display:inline-block;width:14px;height:14px;background:#95a5a6;border-radius:50%;vertical-align:middle;"></span>
        <b style="color:#95a5a6;">혼합</b> — 직주 균형 지역<br>
        <br><span style="font-size:10px;color:#888;">원 크기 = 인구 규모</span>
    </div>
    """
    m3.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m3, width=None, height=map_height, returned_objects=[])

    # ══════════════════════════════════════
    # 지도 4: 1인당 소비 효율
    # ══════════════════════════════════════
    st.subheader("💡 1인당 소비 효율 지도")
    st.caption("총 인구(거주+직장) 대비 소비액. 높을수록 상권 활성도가 높은 지역.")

    m4 = folium.Map(location=[37.545, 127.00], zoom_start=12, tiles=tile_name)
    if show_gu_boundary:
        _add_gu_boundaries(m4)
    _add_minimap(m4)

    per_capita = {}
    for dong, total in summary.items():
        total_pop = dong_pop.get(dong, 0) + dong_emp.get(dong, 0)
        if total_pop > 0:
            per_capita[dong] = total / total_pop

    if per_capita:
        max_pc = max(per_capita.values())
        for dong, pc in per_capita.items():
            if dong not in DONG_COORDS:
                continue
            lat, lon = DONG_COORDS[dong]
            ratio = pc / max_pc
            radius = 8 + ratio * 25

            # 보라-노랑 그라데이션
            r = int(255 * ratio)
            g = int(200 * ratio)
            b = int(255 * (1 - ratio * 0.7))
            color = f"#{min(r,255):02x}{min(g,255):02x}{min(b,255):02x}"

            folium.CircleMarker(
                [lat, lon],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.65,
                weight=2,
                tooltip=f"{dong}: 1인당 {pc:,.0f}원",
                popup=folium.Popup(
                    f"<b>{dong}</b><br>"
                    f"1인당 소비: {pc:,.0f}원<br>"
                    f"총소비: {summary[dong]/10000:,.0f}만원<br>"
                    f"총인구: {dong_pop.get(dong,0)+dong_emp.get(dong,0):,}명",
                    max_width=250,
                ),
            ).add_to(m4)

            if show_labels:
                folium.Marker(
                    [lat + 0.002, lon],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size:9px;font-weight:bold;color:#555;'
                             f'text-shadow:1px 1px 2px white;white-space:nowrap;">'
                             f'{dong} ({pc:,.0f}원)</div>',
                        icon_size=(120, 16),
                        icon_anchor=(60, 8),
                    ),
                ).add_to(m4)

    st_folium(m4, width=None, height=map_height, returned_objects=[])

    # ── 소비 순위 테이블 ──
    st.subheader("행정동별 소비 순위")
    sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)
    rank_df = pd.DataFrame([
        {
            "순위": i + 1,
            "행정동": dong,
            "총소비(만원)": round(total / 10000),
            "일평균(만원)": round(total / 10000 / n_days),
            "거주인구": dong_pop.get(dong, 0),
            "직장인구": dong_emp.get(dong, 0),
            "1인당소비": round(total / max(dong_pop.get(dong,0)+dong_emp.get(dong,0), 1)),
            "유형": "직장밀집" if dong_emp.get(dong, 0) > dong_pop.get(dong, 0) * 1.5
                    else "주거밀집" if dong_pop.get(dong, 0) > dong_emp.get(dong, 0) * 1.5
                    else "혼합",
            "특성": DONG_FEATURES.get(dong, ""),
        }
        for i, (dong, total) in enumerate(sorted_summary)
    ])
    st.dataframe(rank_df, use_container_width=True, hide_index=True)

    # ── 이동 패턴 테이블 ──
    if not movements.empty:
        st.subheader("출퇴근 이동 패턴 TOP 20")
        st.dataframe(movements.head(20), use_container_width=True, hide_index=True)

    # ── 출퇴근 거리 분석 ──
    commute_dist = model.get_commute_distance_summary()
    if not commute_dist.empty:
        st.subheader("출퇴근 거리 분석")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            avg_dist = commute_dist["평균거리"].mean()
            st.metric("전체 평균 출퇴근 거리", f"{avg_dist:.1f} km")
        with col_d2:
            top_routes = commute_dist.head(10)
            st.dataframe(
                top_routes[["거주동", "직장동", "이동인원", "평균거리"]],
                use_container_width=True, hide_index=True,
            )

else:
    st.info("👈 사이드바에서 행정동을 선택하고 '시뮬레이션 실행' 버튼을 누르세요.")

    # 미리보기 지도 (전체 동 + 구 경계)
    m_preview = folium.Map(location=[37.545, 127.00], zoom_start=11.5, tiles=tile_name)
    if show_gu_boundary:
        _add_gu_boundaries(m_preview)
    _add_minimap(m_preview)

    for dong in selected_dongs:
        if dong in DONG_COORDS:
            lat, lon = DONG_COORDS[dong]
            pop = BASE_POPULATION.get(dong, 30000)
            emp = BASE_EMPLOYMENT.get(dong, 40000)

            if emp > pop * 1.5:
                color = "#e74c3c"
            elif pop > emp * 1.5:
                color = "#3498db"
            else:
                color = "#95a5a6"

            folium.CircleMarker(
                [lat, lon], radius=6, color=color, fill=True, fill_opacity=0.6,
                tooltip=f"{dong} | 거주:{pop:,} 직장:{emp:,}",
                popup=folium.Popup(_make_popup_html(dong), max_width=280),
            ).add_to(m_preview)

            if show_labels:
                folium.Marker(
                    [lat, lon],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size:9px;color:#555;font-weight:bold;'
                             f'text-shadow:1px 1px white;">{dong}</div>',
                        icon_size=(80, 16),
                        icon_anchor=(40, 8),
                    ),
                ).add_to(m_preview)

    st_folium(m_preview, width=None, height=map_height, returned_objects=[])
