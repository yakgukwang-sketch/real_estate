"""래미안 대치팰리스 로컬 소비 시뮬레이션 — 롤코타 스타일 에이전트 시각화."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from src.simulation.local_agent import (
    simulate, agents_to_df, APT_COORDS, NEEDS, NETWORK,
)

st.set_page_config(layout="wide")
st.header("래미안 대치팰리스 — 주민 이동 시뮬레이션")

n_agents = st.sidebar.slider("시뮬레이션 인원", 10, 4960, 200, 10)
seed = st.sidebar.number_input("랜덤 시드", value=42)
show_max = st.sidebar.slider("지도 표시 에이전트 수", 10, 300, 120, 10)
anim_speed = st.sidebar.slider("애니메이션 속도", 1, 10, 5)

agents = simulate(n_agents=n_agents, seed=int(seed))
df = agents_to_df(agents)

went_out = df["agent_id"].nunique() if not df.empty else 0
total_spend = int(df["소비금액"].sum()) if not df.empty else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("총 인원", f"{n_agents}명")
m2.metric("외출자", f"{went_out}명")
m3.metric("이동 횟수", f"{len(df)}회")
m4.metric("총 소비", f"{total_spend:,}원")

st.divider()

CATEGORY_COLORS = {
    "편의점": "#22c55e",
    "카페": "#a855f7",
    "음식점": "#ef4444",
    "마트/슈퍼": "#f59e0b",
    "기타": "#6b7280",
}

# 인도 네트워크 엣지 데이터
sidewalk_edges = NETWORK.to_geojson_edges()
sidewalk_edges_json = json.dumps(sidewalk_edges, ensure_ascii=False)

# 네트워크 노드 중 횡단보도 표시용
crosswalk_nodes = [
    {"lat": n.lat, "lon": n.lon, "label": n.label}
    for n in NETWORK.nodes.values() if n.is_crosswalk
]
crosswalk_json = json.dumps(crosswalk_nodes, ensure_ascii=False)

# 구역 노드 (목적지 마커용)
zone_nodes = [
    n for n in NETWORK.nodes.values() if n.id.startswith("zone_")
]
zone_stats = {}
if not df.empty:
    for name, row in df.groupby("구역").agg(
        방문수=("agent_id", "count"), 매출=("소비금액", "sum"),
    ).iterrows():
        zone_stats[name] = {"방문수": int(row["방문수"]), "매출": int(row["매출"])}

zone_data = []
zone_color_map = {
    "zone_front": "#22c55e", "zone_cross": "#f59e0b",
    "zone_daechi": "#a855f7", "zone_hanti": "#ef4444", "zone_academy": "#3b82f6",
}
zone_name_map = {
    "zone_front": "단지 앞 도곡로", "zone_cross": "도곡로 건너편",
    "zone_daechi": "대치역 상권", "zone_hanti": "한티역 상권", "zone_academy": "학원가 뒷길",
}
for zn in zone_nodes:
    label = zone_name_map.get(zn.id, zn.label)
    stats = zone_stats.get(label, {"방문수": 0, "매출": 0})
    zone_data.append({
        "lat": zn.lat, "lon": zn.lon, "name": label,
        "visits": stats["방문수"], "revenue": stats["매출"],
        "color": zone_color_map.get(zn.id, "#999"),
    })
zone_data_json = json.dumps(zone_data, ensure_ascii=False)

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
                road = [APT_COORDS, log["zone_coords"]]
            waypoints.append({
                "road": [list(p) for p in road],
                "color": CATEGORY_COLORS.get(log["need"], "#999"),
                "label": f"{log['need']} → {log['zone']}",
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
        '<b>주민 이동</b><br>'
        '<span style="color:#ef4444">●</span> 음식점 '
        '<span style="color:#a855f7">●</span> 카페<br>'
        '<span style="color:#22c55e">●</span> 편의점 '
        '<span style="color:#f59e0b">●</span> 마트<br>'
        '<span style="color:#6b7280">●</span> 기타 '
        '<span style="color:#94a3b8">●</span> 집<br>'
        '<hr style="margin:4px 0">'
        '<span style="color:#bbb">━━</span> 인도 '
        '<span style="color:#f97316">╍╍</span> 횡단보도'
        '</div>'
        '<script>'
        'var APT=' + apt_json + ';'
        'var EDGES=' + sidewalk_edges_json + ';'
        'var CROSSWALKS=' + crosswalk_json + ';'
        'var ZONE_DATA=' + zone_data_json + ';'
        'var PATHS=' + paths_json + ';'
        'var SPEED=' + str(anim_speed) + ';'
        r"""

        // Canvas 렌더러 — 수백 개 마커도 60fps
        var canvasRenderer = L.canvas({padding: 0.5});
        var map = L.map('map', {preferCanvas: true}).setView(APT, 16);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png', {
            maxZoom: 19
        }).addTo(map);

        // 인도 네트워크
        EDGES.forEach(function(e) {
            var isCx = e.is_crosswalk;
            L.polyline(e.coords, {
                color: isCx ? '#f97316' : '#cccccc',
                weight: isCx ? 3.5 : 2,
                opacity: isCx ? 0.8 : 0.5,
                dashArray: isCx ? '8 6' : null
            }).addTo(map);
        });

        // 횡단보도
        CROSSWALKS.forEach(function(c) {
            L.circleMarker([c.lat, c.lon], {
                radius: 5, color: '#f97316', fillColor: '#fff',
                fillOpacity: 1, weight: 2
            }).addTo(map).bindTooltip('횡단보도', {direction:'top', offset:[0,-5]});
        });

        // 아파트
        L.marker(APT, {
            icon: L.divIcon({
                html: '<div style="font-size:28px">🏢</div>',
                iconSize:[30,30], iconAnchor:[15,15], className:''
            })
        }).addTo(map).bindPopup('<b>래미안 대치팰리스</b><br>1,600세대');

        // 구역 마커
        var maxV = Math.max.apply(null, ZONE_DATA.map(function(z){return z.visits})) || 1;
        ZONE_DATA.forEach(function(z) {
            var r = 10 + (z.visits / maxV) * 25;
            L.circleMarker([z.lat, z.lon], {
                radius: r, color: z.color, fillColor: z.color,
                fillOpacity: 0.15, weight: 1.5
            }).addTo(map).bindPopup(
                '<b>'+z.name+'</b><hr>방문: <b>'+z.visits.toLocaleString()
                +'회</b><br>매출: <b>'+z.revenue.toLocaleString()+'원</b>'
            );
            L.marker([z.lat, z.lon], {
                icon: L.divIcon({
                    html: '<div style="font-size:11px;font-weight:bold;color:'+z.color
                        +';text-shadow:1px 1px 2px #fff,-1px -1px 2px #fff,0 0 4px #fff;white-space:nowrap">'
                        +z.name+'</div>',
                    iconSize:[0,0], iconAnchor:[-12,-12], className:''
                })
            }).addTo(map);
        });

        // === 롤코타 스타일 에이전트 ===

        function randOff() { return (Math.random() - 0.5) * 0.00012; }

        var agents = [];
        PATHS.forEach(function(p, idx) {
            var m = L.circleMarker(APT, {
                renderer: canvasRenderer,
                radius: 3.5,
                fillColor: '#94a3b8',
                fillOpacity: 0.0,
                color: '#ffffff',
                weight: 0.5
            }).addTo(map);
            agents.push({
                marker: m,
                latOff: randOff(),
                lonOff: randOff(),
                speedMul: 0.85 + Math.random() * 0.3
            });
        });

        // 경로 보간
        function interpPath(path, t) {
            if (!path || path.length < 2) return APT;
            var n = path.length - 1;
            var raw = t * n;
            var idx = Math.min(Math.floor(raw), n - 1);
            var frac = raw - idx;
            return [
                path[idx][0] + (path[idx+1][0] - path[idx][0]) * frac,
                path[idx][1] + (path[idx+1][1] - path[idx][1]) * frac
            ];
        }

        // 스케줄 — 집↔외출을 반복 (연속 루프)
        var SIM_FPS = 2.5 * SPEED;
        var schedules = [];

        PATHS.forEach(function(p, idx) {
            var segs = [];
            var cf = Math.floor(Math.random() * 15 * 60 * SIM_FPS);

            for (var loop = 0; loop < 3; loop++) {
                // 집 대기
                var hw = Math.floor((2 + Math.random() * 8) * 60 * SIM_FPS);
                segs.push({type:'home', s:cf, e:cf+hw});
                cf += hw;

                p.waypoints.forEach(function(wp) {
                    var spd = agents[idx].speedMul;
                    var tf = Math.max(8, Math.round(wp.walk_sec * SIM_FPS * spd));
                    var stayT = Math.floor((3 + Math.random() * 12) * 60 * SIM_FPS);

                    segs.push({type:'go', s:cf, e:cf+tf, path:wp.road, color:wp.color});
                    cf += tf;

                    var dest = wp.road[wp.road.length - 1];
                    segs.push({type:'stay', s:cf, e:cf+stayT, at:dest, color:wp.color});
                    cf += stayT;

                    var rev = wp.road.slice().reverse();
                    segs.push({type:'go', s:cf, e:cf+tf, path:rev, color:wp.color});
                    cf += tf;
                });
            }
            schedules.push({total: cf, segs: segs});
        });

        // 애니메이션 루프 — requestAnimationFrame 기반
        var tick = 0;
        var running = true;
        var lastTs = 0;

        function animate(ts) {
            if (!running) { lastTs = 0; requestAnimationFrame(animate); return; }
            if (!lastTs) lastTs = ts;
            var dt = ts - lastTs;

            if (dt >= 25) {
                lastTs = ts;
                tick++;
                var outCnt = 0, moveCnt = 0;

                for (var i = 0; i < schedules.length; i++) {
                    var sc = schedules[i];
                    var lt = tick % sc.total;
                    var ag = agents[i];
                    var mk = ag.marker;
                    var found = false;

                    for (var j = 0; j < sc.segs.length; j++) {
                        var sg = sc.segs[j];
                        if (lt >= sg.s && lt < sg.e) {
                            found = true;
                            if (sg.type === 'go') {
                                var t = (lt - sg.s) / (sg.e - sg.s);
                                var pos = interpPath(sg.path, t);
                                mk.setLatLng([pos[0]+ag.latOff, pos[1]+ag.lonOff]);
                                mk.setStyle({fillColor:sg.color, radius:3.5, fillOpacity:0.9, weight:0.5});
                                moveCnt++; outCnt++;
                            } else if (sg.type === 'stay') {
                                var w = Math.sin(tick*0.15+i)*0.00003;
                                mk.setLatLng([sg.at[0]+ag.latOff+w, sg.at[1]+ag.lonOff+w]);
                                mk.setStyle({fillColor:sg.color, radius:4, fillOpacity:0.95, weight:0.5});
                                outCnt++;
                            } else {
                                var hw2 = Math.sin(tick*0.08+i*2)*0.00004;
                                mk.setLatLng([APT[0]+ag.latOff*2+hw2, APT[1]+ag.lonOff*2+hw2]);
                                mk.setStyle({fillColor:'#94a3b8', radius:2, fillOpacity:0.2, weight:0});
                            }
                            break;
                        }
                    }
                    if (!found) {
                        mk.setLatLng([APT[0]+ag.latOff*2, APT[1]+ag.lonOff*2]);
                        mk.setStyle({fillColor:'#94a3b8', radius:2, fillOpacity:0.15, weight:0});
                    }
                }

                var secs = Math.floor(tick / SIM_FPS);
                var hrs = Math.floor(secs / 3600);
                var mins = Math.floor((secs % 3600) / 60);
                var ss = secs % 60;
                var tStr = (hrs > 0 ? hrs+'시간 ' : '') + mins+'분 '+ss+'초';
                document.getElementById('status').textContent =
                    tStr+'  |  이동:'+moveCnt+'  체류:'+(outCnt-moveCnt)+'  집:'+(agents.length-outCnt);
            }
            requestAnimationFrame(animate);
        }

        // 자동 시작!
        requestAnimationFrame(animate);

        document.getElementById('playBtn').onclick = function() {
            running = !running;
            this.textContent = running ? '⏸ 정지' : '▶ 시작';
        };
        document.getElementById('resetBtn').onclick = function() {
            tick = 0;
            for (var i = 0; i < agents.length; i++) {
                agents[i].marker.setLatLng(APT);
                agents[i].marker.setStyle({fillColor:'#94a3b8', radius:2, fillOpacity:0.15, weight:0});
            }
            document.getElementById('status').textContent = '리셋 완료';
        };

        """
        '</script></body></html>'
    )
    components.html(html, height=690)

with col_detail:
    st.markdown("**구역별 매출**")
    if not df.empty:
        zs = df.groupby("구역").agg(
            방문수=("agent_id", "count"), 매출=("소비금액", "sum"),
        ).sort_values("매출", ascending=False).reset_index()
        zs["매출"] = zs["매출"].apply(lambda x: f"{x:,}원")
        st.dataframe(zs, use_container_width=True, hide_index=True)

    st.markdown("**업종별 매출**")
    if not df.empty:
        cs = df.groupby("업종").agg(
            방문수=("agent_id", "count"), 매출=("소비금액", "sum"),
        ).sort_values("매출", ascending=False).reset_index()
        cs["매출"] = cs["매출"].apply(lambda x: f"{x:,}원")
        st.dataframe(cs, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**에이전트 추적**")
    went_out_agents = [a for a in agents if a.log]
    if went_out_agents:
        pick = st.selectbox(
            "에이전트 선택",
            range(len(went_out_agents)),
            format_func=lambda i: f"#{went_out_agents[i].id} ({len(went_out_agents[i].log)}곳 방문)",
        )
        agent = went_out_agents[pick]
        for j, log in enumerate(agent.log, 1):
            cross_txt = f"횡단보도 {log['crossings']}번" if log['crossings'] > 0 else "횡단보도 없음"
            st.write(
                f"**{j}.** {log['need']} → {log['zone']} "
                f"(도보 {log['walk_min']}분, {cross_txt}) "
                f"— **{log['spend']:,}원**"
            )
    else:
        st.info("외출한 에이전트가 없습니다.")
