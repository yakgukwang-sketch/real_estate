"""래미안 대치팰리스 로컬 시뮬레이션 — 에이전트 자유 이동 시각화."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from src.simulation.local_agent import simulate, agents_to_df, spending_summary, APT_COORDS, NETWORK

st.set_page_config(layout="wide")
st.header("래미안 대치팰리스 — 주민 이동 시뮬레이션")

n_agents = st.sidebar.slider("시뮬레이션 인원", 10, 4960, 200, 10)
seed = st.sidebar.number_input("랜덤 시드", value=42)
show_max = st.sidebar.slider("지도 표시 에이전트 수", 10, 300, 120, 10)
anim_speed = st.sidebar.slider("애니메이션 속도", 1, 10, 5)

agents = simulate(n_agents=n_agents, seed=int(seed))
df = agents_to_df(agents)

went_out = df["agent_id"].nunique() if not df.empty else 0
summary = spending_summary(df) if not df.empty else {}

m1, m2, m3, m4 = st.columns(4)
m1.metric("총 인원", f"{n_agents}명")
m2.metric("외출자", f"{went_out}명")
m3.metric("이동 횟수", f"{len(df)}회")
m4.metric("총 소비", f"{summary.get('총소비', 0):,}원")

st.divider()

TYPE_COLORS = {
    "음식점":       "#ef4444",   # 빨강
    "학원":         "#3b82f6",   # 파랑
    "학교":         "#1d4ed8",   # 진파랑
    "상점":         "#f59e0b",   # 주황
    "병원/약국":    "#22c55e",   # 초록
    "생활서비스":    "#8b5cf6",   # 보라
    "어린이집/복지": "#a855f7",   # 연보라
    "종교시설":     "#14b8a6",   # 청록
    "운동시설":     "#06b6d4",   # 하늘
    "공원":         "#16a34a",   # 녹색
    "문화시설":     "#e11d48",   # 자홍
    "대형상가":     "#ec4899",   # 핑크
    "기타":         "#94a3b8",   # 회색
}

# 인도 네트워크 엣지 — 래미안 근처만
APT_LAT, APT_LON = APT_COORDS
_all_edges = NETWORK.to_geojson_edges()
sidewalk_edges = [
    e for e in _all_edges
    if any(abs(c[0] - APT_LAT) < 0.008 and abs(c[1] - APT_LON) < 0.008
           for c in e["coords"])
]
sidewalk_edges_json = json.dumps(sidewalk_edges, ensure_ascii=False)

# 에이전트 경로
def build_agent_paths(agents, max_agents):
    paths = []
    shown = 0
    for agent in agents:
        if not agent.log:
            continue
        if shown >= max_agents:
            break
        shown += 1
        waypoints = []
        for log in agent.log:
            road = log.get("road_path", [])
            if not road:
                road = [APT_COORDS, log["dest_coords"]]
            color = TYPE_COLORS.get(log.get("dest_type", "기타"), "#94a3b8")
            waypoints.append({
                "road": [list(p) for p in road],
                "color": color,
                "label": log.get("motivation", ""),
                "dest_name": log.get("dest_name", ""),
                "walk_sec": log.get("walk_sec", log["walk_min"] * 60),
            })
        paths.append({"id": agent.id, "waypoints": waypoints})
    return paths

agent_paths = build_agent_paths(agents, show_max)

col_map, col_detail = st.columns([3, 2])

with col_map:
    apt_json = json.dumps(list(APT_COORDS))
    paths_json = json.dumps(agent_paths, ensure_ascii=False)

    html = (
        '<!DOCTYPE html><html><head>'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        '<style>'
        'body{margin:0}'
        '#map{width:100%;height:660px}'
        '#controls{position:absolute;top:10px;right:10px;z-index:1000;'
        'background:rgba(255,255,255,0.95);padding:8px 12px;border-radius:8px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.25);font-size:13px}'
        '#controls button{padding:5px 14px;margin:2px;border:none;border-radius:4px;'
        'cursor:pointer;font-size:13px}'
        '.play{background:#3b82f6;color:white}'
        '.reset{background:#e5e7eb}'
        '#status{position:absolute;bottom:10px;left:10px;z-index:1000;'
        'background:rgba(0,0,0,0.8);color:white;padding:8px 14px;border-radius:8px;'
        'font-size:13px;font-family:monospace}'
        '#legend{position:absolute;bottom:10px;right:10px;z-index:1000;'
        'background:rgba(255,255,255,0.95);padding:8px 12px;border-radius:8px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.25);font-size:11px;line-height:1.9}'
        '</style></head><body>'
        '<div id="map"></div>'
        '<div id="controls">'
        '<button class="play" id="playBtn">⏸ 정지</button>'
        '<button class="reset" id="resetBtn">↺ 리셋</button>'
        '</div>'
        '<div id="status">로딩 중...</div>'
        '<div id="legend">'
        '<b>목적지 유형</b><br>'
        '<span style="color:#ef4444">●</span> 음식점 '
        '<span style="color:#3b82f6">●</span> 학원<br>'
        '<span style="color:#f59e0b">●</span> 상점 '
        '<span style="color:#22c55e">●</span> 병원/약국<br>'
        '<span style="color:#8b5cf6">●</span> 생활서비스 '
        '<span style="color:#94a3b8">●</span> 기타<br>'
        '<hr style="margin:4px 0">'
        '<span style="color:#ccc">━━</span> 인도 '
        '<span style="color:#f97316">╍╍</span> 횡단보도'
        '</div>'
        '<script>'
        'var APT=' + apt_json + ';'
        'var EDGES=' + sidewalk_edges_json + ';'
        'var PATHS=' + paths_json + ';'
        'var SPEED=' + str(anim_speed) + ';'
        r"""

        var canvasRenderer = L.canvas({padding: 0.5});
        var map = L.map('map', {preferCanvas: true}).setView(APT, 16);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png', {
            maxZoom: 19
        }).addTo(map);

        // 인도 네트워크
        EDGES.forEach(function(e) {
            var isCx = e.is_crosswalk;
            L.polyline(e.coords, {
                color: isCx ? '#f97316' : '#ddd',
                weight: isCx ? 3 : 1.5,
                opacity: isCx ? 0.7 : 0.4,
                dashArray: isCx ? '8 6' : null
            }).addTo(map);
        });

        // 아파트
        L.marker(APT, {
            icon: L.divIcon({
                html: '<div style="font-size:28px">🏢</div>',
                iconSize:[30,30], iconAnchor:[15,15], className:''
            })
        }).addTo(map).bindPopup('<b>래미안 대치팰리스</b><br>1,600세대');

        // === 에이전트: 끊임없이 도로 위를 이동 ===

        // 모든 waypoint 경로를 이어붙여 하나의 연속 경로로 만듦
        // 가는길 → 오는길 → 다음 가는길 → 오는길 ... 무한 반복
        var agents = [];

        PATHS.forEach(function(p, idx) {
            // 모든 waypoint의 경로를 연결 (갈 때 + 올 때)
            var fullPath = [];
            var colors = [];
            p.waypoints.forEach(function(wp) {
                // 갈 때
                for (var k = 0; k < wp.road.length; k++) {
                    fullPath.push(wp.road[k]);
                    colors.push(wp.color);
                }
                // 올 때 (역순)
                for (var k = wp.road.length - 1; k >= 0; k--) {
                    fullPath.push(wp.road[k]);
                    colors.push(wp.color);
                }
            });

            if (fullPath.length < 2) return;

            // 구간별 거리 계산 (애니메이션 속도 균일화)
            var segDists = [];
            var totalDist = 0;
            for (var k = 0; k < fullPath.length - 1; k++) {
                var dlat = fullPath[k+1][0] - fullPath[k][0];
                var dlon = fullPath[k+1][1] - fullPath[k][1];
                var d = Math.sqrt(dlat*dlat + dlon*dlon);
                segDists.push(d);
                totalDist += d;
            }

            var m = L.circleMarker(fullPath[0], {
                renderer: canvasRenderer,
                radius: 5,
                fillColor: colors[0],
                fillOpacity: 0.85,
                color: '#fff',
                weight: 1
            }).addTo(map);

            agents.push({
                marker: m,
                path: fullPath,
                colors: colors,
                segDists: segDists,
                totalDist: totalDist,
                offset: Math.random(),  // 시작 위치 랜덤
                speed: (0.7 + Math.random() * 0.6) * 0.0003 * SPEED
            });
        });

        // 애니메이션 — 모든 점이 경로 위를 끊임없이 순환
        var running = true;
        var tick = 0;

        function animate() {
            if (!running) { requestAnimationFrame(animate); return; }
            tick++;

            var moveCnt = 0;
            for (var i = 0; i < agents.length; i++) {
                var ag = agents[i];
                // 전체 경로에서 현재 위치 (0~1 순환)
                var t = (ag.offset + tick * ag.speed) % 1.0;
                var targetDist = t * ag.totalDist;

                // 어느 구간에 있는지 찾기
                var cumDist = 0;
                var pos = ag.path[0];
                var colorIdx = 0;
                for (var k = 0; k < ag.segDists.length; k++) {
                    if (cumDist + ag.segDists[k] >= targetDist) {
                        var frac = (ag.segDists[k] > 0) ? (targetDist - cumDist) / ag.segDists[k] : 0;
                        pos = [
                            ag.path[k][0] + (ag.path[k+1][0] - ag.path[k][0]) * frac,
                            ag.path[k][1] + (ag.path[k+1][1] - ag.path[k][1]) * frac
                        ];
                        colorIdx = k;
                        break;
                    }
                    cumDist += ag.segDists[k];
                }

                ag.marker.setLatLng(pos);
                ag.marker.setStyle({fillColor: ag.colors[colorIdx]});
                moveCnt++;
            }

            document.getElementById('status').textContent =
                '이동 중: ' + moveCnt + '명  |  속도: ' + SPEED + 'x';

            requestAnimationFrame(animate);
        }

        requestAnimationFrame(animate);

        document.getElementById('playBtn').onclick = function() {
            running = !running;
            this.textContent = running ? '⏸ 정지' : '▶ 시작';
        };
        document.getElementById('resetBtn').onclick = function() {
            tick = 0;
            for (var i = 0; i < agents.length; i++) {
                agents[i].offset = Math.random();
            }
            document.getElementById('status').textContent = '리셋 완료';
        };

        """
        '</script></body></html>'
    )
    components.html(html, height=690)

with col_detail:
    tab_mot, tab_profile, tab_spend, tab_agent = st.tabs(["동기별", "프로파일", "소비", "에이전트"])

    with tab_mot:
        if not df.empty and "동기" in df.columns:
            ms = df.groupby("동기").agg(
                건수=("agent_id", "count"),
            ).sort_values("건수", ascending=False).reset_index()
            st.dataframe(ms, use_container_width=True, hide_index=True)

        st.markdown("**도보 시간 분포**")
        if not df.empty:
            bins = {"~3분": 0, "3~5분": 0, "5~10분": 0, "10~15분": 0, "15분+": 0}
            for _, row in df.iterrows():
                m = row["도보(분)"]
                if m <= 3: bins["~3분"] += 1
                elif m <= 5: bins["3~5분"] += 1
                elif m <= 10: bins["5~10분"] += 1
                elif m <= 15: bins["10~15분"] += 1
                else: bins["15분+"] += 1
            dist_df = pd.DataFrame({"거리구간": bins.keys(), "건수": bins.values()})
            st.dataframe(dist_df, use_container_width=True, hide_index=True)

    with tab_profile:
        if not df.empty and "유형" in df.columns:
            st.markdown("**프로파일별 이동**")
            ps = df.groupby("유형").agg(
                인원=("agent_id", "nunique"),
                이동=("agent_id", "count"),
                연쇄=("연쇄", "sum"),
            ).sort_values("이동", ascending=False).reset_index()
            st.dataframe(ps, use_container_width=True, hide_index=True)

            st.markdown("**시간대별 이동**")
            ts = df.groupby("시간대").agg(
                건수=("agent_id", "count"),
            ).reset_index()
            st.dataframe(ts, use_container_width=True, hide_index=True)

    with tab_spend:
        if summary:
            st.metric("건당 평균 소비", f"{summary.get('건당평균', 0):,}원")
            st.metric("연쇄 이동", f"{summary.get('연쇄이동', 0)}건")

            st.markdown("**프로파일별 소비**")
            if "프로파일별소비" in summary:
                sp_df = pd.DataFrame([
                    {"프로파일": k, "소비(원)": v}
                    for k, v in summary["프로파일별소비"].items()
                ])
                st.dataframe(sp_df, use_container_width=True, hide_index=True)

            st.markdown("**시간대별 소비**")
            if "시간대별소비" in summary:
                st_df = pd.DataFrame([
                    {"시간대": k, "소비(원)": v}
                    for k, v in summary["시간대별소비"].items()
                ])
                st.dataframe(st_df, use_container_width=True, hide_index=True)

    with tab_agent:
        went_out_agents = [a for a in agents if a.log]
        if went_out_agents:
            pick = st.selectbox(
                "에이전트 선택",
                range(len(went_out_agents)),
                format_func=lambda i: f"#{went_out_agents[i].id} [{went_out_agents[i].profile}] ({len(went_out_agents[i].log)}회)",
            )
            agent = went_out_agents[pick]
            for j, log in enumerate(agent.log, 1):
                mot = log.get("motivation", "")
                time_str = log.get("time", "")
                spend = log.get("spend", 0)
                chain = " 🔗" if log.get("is_chain") else ""
                cross_txt = f"횡단{log['crossings']}번" if log['crossings'] > 0 else ""
                spend_txt = f" · {spend:,}원" if spend > 0 else ""
                st.write(
                    f"**{j}. [{time_str}] {mot}{chain}** — {log['walk_min']}분 {cross_txt}{spend_txt}"
                )
        else:
            st.info("외출한 에이전트가 없습니다.")
