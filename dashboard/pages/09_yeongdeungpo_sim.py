"""영등포역 상권 보행자 시뮬레이션 — 다중 출발점 에이전트 시각화."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from src.simulation.local_agent import (
    simulate, agents_to_df, spending_summary, estimate_revenue,
    AREA_SALES, _get_area_data,
)

st.set_page_config(layout="wide")
st.header("영등포역 상권 — 보행자 시뮬레이션")

n_agents = st.sidebar.slider("시뮬레이션 인원", 10, 5000, 300, 10)
seed = st.sidebar.number_input("랜덤 시드", value=42)
show_max = st.sidebar.slider("지도 표시 에이전트 수", 10, 500, 200, 10)
anim_speed = st.sidebar.slider("시뮬레이션 속도", 1, 20, 8)

# 시뮬레이션 실행
area_data = _get_area_data("yeongdeungpo")

try:
    agents = simulate(n_agents=n_agents, seed=int(seed), area="yeongdeungpo")
except FileNotFoundError as e:
    st.error(f"데이터 파일 없음: {e}\n\n`python scripts/collect_yeongdeungpo.py`를 먼저 실행하세요.")
    st.stop()

df = agents_to_df(agents)
NETWORK = area_data.network
DESTINATIONS = area_data.destinations
CENTER = area_data.config.center

went_out = df["agent_id"].nunique() if not df.empty else 0
summary = spending_summary(df) if not df.empty else {}
revenue_df = estimate_revenue(df, n_agents, area="yeongdeungpo")

sales_info = AREA_SALES["yeongdeungpo"]

# 사이드바: 출발점별 에이전트 수
st.sidebar.divider()
st.sidebar.markdown("**출발점별 에이전트**")
if not df.empty and "출발점" in df.columns:
    origin_counts = df.groupby("출발점")["agent_id"].nunique()
    for origin, cnt in origin_counts.items():
        st.sidebar.write(f"  {origin}: {cnt}명")

m1, m2, m3, m4 = st.columns(4)
m1.metric("총 인원", f"{n_agents}명")
m2.metric("외출자", f"{went_out}명")
m3.metric("이동 횟수", f"{len(df)}회")
m4.metric("총 소비", f"{summary.get('총소비', 0):,}원")

st.divider()

TYPE_COLORS = {
    "음식점":       "#ef4444",
    "학원":         "#3b82f6",
    "학교":         "#1d4ed8",
    "상점":         "#f59e0b",
    "병원/약국":    "#22c55e",
    "생활서비스":    "#8b5cf6",
    "어린이집/복지": "#a855f7",
    "종교시설":     "#14b8a6",
    "운동시설":     "#06b6d4",
    "공원":         "#16a34a",
    "문화시설":     "#e11d48",
    "대형상가":     "#ec4899",
    "기타":         "#94a3b8",
}

# 인도 네트워크 엣지
CENTER_LAT, CENTER_LON = CENTER
_all_edges = NETWORK.to_geojson_edges()
sidewalk_edges = [
    e for e in _all_edges
    if any(abs(c[0] - CENTER_LAT) < 0.008 and abs(c[1] - CENTER_LON) < 0.008
           for c in e["coords"])
]
sidewalk_edges_json = json.dumps(sidewalk_edges, ensure_ascii=False)

# 출발점 마커 데이터
origin_markers = []
ORIGIN_ICONS = {
    "영등포역": "🚇",
    "영등포시장역": "🚇",
    "신길역": "🚇",
    "영등포동_주거": "🏘️",
    "영등포_업무": "🏢",
}
for name, (lat, lon) in area_data.config.origin_points.items():
    icon = ORIGIN_ICONS.get(name, "📍")
    origin_markers.append({"name": name, "lat": lat, "lon": lon, "icon": icon})
origin_markers_json = json.dumps(origin_markers, ensure_ascii=False)


def build_time_agents(agents, max_agents):
    result = []
    shown = 0
    for agent in agents:
        if not agent.log:
            continue
        if shown >= max_agents:
            break
        shown += 1

        trips = []
        for log in agent.log:
            road = log.get("road_path", [])
            if not road:
                road = [list(agent.home), list(log["dest_coords"])]
            else:
                road = [list(p) for p in road]

            color = TYPE_COLORS.get(log.get("dest_type", "기타"), "#94a3b8")

            trips.append({
                "road": road,
                "color": color,
                "label": log.get("motivation", ""),
                "dest_name": log.get("dest_name", ""),
                "dest_type": log.get("dest_type", ""),
                "depart": log.get("depart_min", 0),
                "walk": log.get("walk_min", 5),
                "stay": log.get("stay_min", 30),
                "spend": log.get("spend", 0),
            })

        result.append({
            "id": agent.id,
            "profile": agent.profile,
            "origin": agent.origin,
            "home": list(agent.home),
            "trips": trips,
        })
    return result


time_agents = build_time_agents(agents, show_max)


def build_hotspots(df):
    if df.empty:
        return []
    grouped = df.groupby(["목적지", "목적지유형"]).agg(
        방문=("agent_id", "count"),
        소비합=("소비(원)", "sum"),
        lat=("lat", "first"),
        lon=("lon", "first"),
    ).reset_index().sort_values("방문", ascending=False)

    spots = []
    for _, row in grouped.iterrows():
        spots.append({
            "name": row["목적지"],
            "type": row["목적지유형"],
            "visits": int(row["방문"]),
            "spend": int(row["소비합"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "color": TYPE_COLORS.get(row["목적지유형"], "#94a3b8"),
        })
    return spots

hotspots = build_hotspots(df)
hotspots_json = json.dumps(hotspots, ensure_ascii=False)
max_visits = max((h["visits"] for h in hotspots), default=1)


def build_all_buildings():
    visit_counts = {}
    if not df.empty:
        vc = df.groupby("목적지").size()
        visit_counts = vc.to_dict()

    buildings = []
    for d in DESTINATIONS:
        lat = d["coords"][-1][0] if d["coords"] else 0
        lon = d["coords"][-1][1] if d["coords"] else 0
        buildings.append({
            "name": d["name"],
            "type": d["dest_type"],
            "lat": lat,
            "lon": lon,
            "stores": d["store_count"],
            "walk_min": d["walk_min"],
            "exposure": round(d.get("exposure_norm", 0), 3),
            "visits": visit_counts.get(d["name"], 0),
            "color": TYPE_COLORS.get(d["dest_type"], "#94a3b8"),
        })
    return buildings

all_buildings = build_all_buildings()
all_buildings_json = json.dumps(all_buildings, ensure_ascii=False)

col_map, col_detail = st.columns([3, 2])

with col_map:
    center_json = json.dumps(list(CENTER))
    agents_json = json.dumps(time_agents, ensure_ascii=False)

    html = (
        '<!DOCTYPE html><html><head>'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        '<style>'
        'body{margin:0;font-family:sans-serif}'
        '#map{width:100%;height:680px}'
        '#clock{position:absolute;top:12px;left:50%;transform:translateX(-50%);z-index:1000;'
        'background:rgba(0,0,0,0.85);color:#fff;padding:10px 24px;border-radius:12px;'
        'font-size:32px;font-weight:bold;font-family:monospace;letter-spacing:2px;'
        'box-shadow:0 4px 12px rgba(0,0,0,0.3)}'
        '#controls{position:absolute;top:12px;right:12px;z-index:1000;'
        'background:rgba(255,255,255,0.96);padding:10px 14px;border-radius:10px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.2);font-size:13px}'
        '#controls button{padding:6px 16px;margin:2px;border:none;border-radius:5px;'
        'cursor:pointer;font-size:13px}'
        '.play{background:#3b82f6;color:white}'
        '.reset{background:#e5e7eb}'
        '#timeline{position:absolute;bottom:50px;left:50%;transform:translateX(-50%);'
        'z-index:1000;width:80%;max-width:700px}'
        '#timeline input{width:100%;cursor:pointer}'
        '#stats{position:absolute;bottom:12px;left:12px;z-index:1000;'
        'background:rgba(0,0,0,0.8);color:white;padding:8px 14px;border-radius:8px;'
        'font-size:12px;font-family:monospace;line-height:1.6}'
        '#legend{position:absolute;bottom:12px;right:12px;z-index:1000;'
        'background:rgba(255,255,255,0.95);padding:8px 12px;border-radius:8px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.2);font-size:11px;line-height:1.8}'
        '</style></head><body>'
        '<div id="map"></div>'
        '<div id="clock">06:00</div>'
        '<div id="controls">'
        '<button class="play" id="playBtn">⏸ 정지</button>'
        '<button class="reset" id="resetBtn">↺ 리셋</button>'
        '<button class="play" id="hotspotBtn" style="background:#ef4444">🔥 핫스팟</button>'
        '<button class="play" id="bldgBtn" style="background:#8b5cf6">🏬 건물</button>'
        '</div>'
        '<div id="timeline">'
        '<input type="range" id="timeSlider" min="360" max="1440" value="360" step="1">'
        '</div>'
        '<div id="stats">로딩 중...</div>'
        '<div id="legend">'
        '<b>목적지 유형</b><br>'
        '<span style="color:#ef4444">●</span> 음식점 '
        '<span style="color:#f59e0b">●</span> 상점<br>'
        '<span style="color:#22c55e">●</span> 병원/약국 '
        '<span style="color:#8b5cf6">●</span> 생활서비스<br>'
        '<span style="color:#ec4899">●</span> 대형상가 '
        '<span style="color:#94a3b8">●</span> 기타<br>'
        '<span style="color:#06b6d4">●</span> 운동시설 '
        '<span style="color:#16a34a">●</span> 공원<br>'
        '<hr style="margin:4px 0">'
        '<b>출발점</b><br>'
        '🚇 지하철역 🏘️ 주거지 🏢 업무지구<br>'
        '<hr style="margin:4px 0">'
        '<span style="color:#ccc">━━</span> 인도 '
        '<span style="color:#f97316">╍╍</span> 횡단보도'
        '</div>'
        '<script>'
        'var CENTER=' + center_json + ';'
        'var EDGES=' + sidewalk_edges_json + ';'
        'var AGENTS=' + agents_json + ';'
        'var HOTSPOTS=' + hotspots_json + ';'
        'var MAX_VISITS=' + str(max_visits) + ';'
        'var BUILDINGS=' + all_buildings_json + ';'
        'var ORIGINS=' + origin_markers_json + ';'
        'var SPEED=' + str(anim_speed) + ';'
        r"""

        var canvasRenderer = L.canvas({padding: 0.5});
        var map = L.map('map', {preferCanvas: true}).setView(CENTER, 16);

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

        // 다중 출발점 마커
        ORIGINS.forEach(function(o) {
            L.marker([o.lat, o.lon], {
                icon: L.divIcon({
                    html: '<div style="font-size:24px">' + o.icon + '</div>',
                    iconSize:[28,28], iconAnchor:[14,14], className:''
                })
            }).addTo(map).bindPopup('<b>' + o.name + '</b>');
        });

        // === 핫스팟 레이어 ===
        var hotspotLayer = L.layerGroup();
        var hotspotVisible = false;

        HOTSPOTS.forEach(function(h) {
            var radius = Math.max(8, Math.sqrt(h.visits / MAX_VISITS) * 45);
            var circle = L.circleMarker([h.lat, h.lon], {
                renderer: canvasRenderer,
                radius: radius,
                fillColor: h.color,
                fillOpacity: 0.35,
                color: h.color,
                weight: 2,
                opacity: 0.7
            });
            circle.bindPopup(
                '<b>' + h.name + '</b><br>'
                + '유형: ' + h.type + '<br>'
                + '방문: <b>' + h.visits + '회</b><br>'
                + '소비: ' + h.spend.toLocaleString() + '원'
            );
            if (h.visits >= 5) {
                var label = L.marker([h.lat, h.lon], {
                    icon: L.divIcon({
                        html: '<div style="font-size:11px;font-weight:bold;color:' + h.color
                            + ';text-shadow:1px 1px 2px white,-1px -1px 2px white,1px -1px 2px white,-1px 1px 2px white">'
                            + h.visits + '</div>',
                        iconSize: [30, 16], iconAnchor: [15, 8], className: ''
                    })
                });
                hotspotLayer.addLayer(label);
            }
            hotspotLayer.addLayer(circle);
        });

        document.getElementById('hotspotBtn').onclick = function() {
            hotspotVisible = !hotspotVisible;
            if (hotspotVisible) {
                hotspotLayer.addTo(map);
                this.style.background = '#16a34a';
                this.textContent = '🔥 핫스팟 ON';
            } else {
                map.removeLayer(hotspotLayer);
                this.style.background = '#ef4444';
                this.textContent = '🔥 핫스팟';
            }
        };

        // === 건물 레이어 ===
        var bldgLayer = L.layerGroup();
        var bldgVisible = false;

        BUILDINGS.forEach(function(b) {
            var r = 3 + b.exposure * 11;
            var opacity = b.visits > 0 ? 0.8 : 0.3;
            var fillOpacity = b.visits > 0 ? 0.6 : 0.15;
            var weight = b.visits > 0 ? 2 : 1;

            var circle = L.circleMarker([b.lat, b.lon], {
                renderer: canvasRenderer,
                radius: r,
                fillColor: b.color,
                fillOpacity: fillOpacity,
                color: b.visits > 0 ? b.color : '#999',
                weight: weight,
                opacity: opacity
            });
            circle.bindPopup(
                '<b>' + b.name + '</b><br>'
                + '유형: ' + b.type + '<br>'
                + '가게: ' + b.stores + '개 · 도보 ' + b.walk_min + '분<br>'
                + '노출도: <b>' + (b.exposure * 100).toFixed(0) + '%</b><br>'
                + '방문: ' + b.visits + '회'
            );
            bldgLayer.addLayer(circle);
        });

        document.getElementById('bldgBtn').onclick = function() {
            bldgVisible = !bldgVisible;
            if (bldgVisible) {
                bldgLayer.addTo(map);
                this.style.background = '#16a34a';
                this.textContent = '🏬 건물 ON';
            } else {
                map.removeLayer(bldgLayer);
                this.style.background = '#8b5cf6';
                this.textContent = '🏬 건물';
            }
        };

        // === 시간 기반 에이전트 시스템 ===
        var simTime = 360;
        var running = true;
        var lastFrame = performance.now();
        var markers = {};

        function getMarker(agId, color) {
            if (!markers[agId]) {
                markers[agId] = L.circleMarker([0, 0], {
                    renderer: canvasRenderer,
                    radius: 5,
                    fillColor: color,
                    fillOpacity: 0.9,
                    color: '#fff',
                    weight: 1.5
                });
            }
            return markers[agId];
        }

        function interpolatePath(road, progress) {
            if (road.length < 2) return road[0] || CENTER;
            var dists = [];
            var totalDist = 0;
            for (var i = 0; i < road.length - 1; i++) {
                var dlat = road[i+1][0] - road[i][0];
                var dlon = road[i+1][1] - road[i][1];
                var d = Math.sqrt(dlat*dlat + dlon*dlon);
                dists.push(d);
                totalDist += d;
            }
            if (totalDist === 0) return road[0];

            var target = progress * totalDist;
            var cum = 0;
            for (var i = 0; i < dists.length; i++) {
                if (cum + dists[i] >= target) {
                    var frac = dists[i] > 0 ? (target - cum) / dists[i] : 0;
                    return [
                        road[i][0] + (road[i+1][0] - road[i][0]) * frac,
                        road[i][1] + (road[i+1][1] - road[i][1]) * frac
                    ];
                }
                cum += dists[i];
            }
            return road[road.length - 1];
        }

        function formatTime(min) {
            var h = Math.floor(min / 60);
            var m = Math.floor(min % 60);
            return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
        }

        var profileEmoji = {
            '환승객': '🚉', '쇼핑객': '🛍️', '직장인(점심)': '💼',
            '주민': '🏠', '시장방문객': '🧺'
        };

        function updateSim() {
            var now = performance.now();
            var dt = (now - lastFrame) / 1000.0;
            lastFrame = now;

            if (running) {
                simTime += dt * SPEED * 2;
                if (simTime > 1440) simTime = 360;
            }

            document.getElementById('clock').textContent = formatTime(simTime);
            document.getElementById('timeSlider').value = Math.floor(simTime);

            var activeSet = {};
            var walkingCount = 0;
            var stayingCount = 0;
            var typeCounts = {};

            for (var i = 0; i < AGENTS.length; i++) {
                var ag = AGENTS[i];
                var pos = null;
                var color = '#94a3b8';
                var state = 'home';

                for (var t = 0; t < ag.trips.length; t++) {
                    var trip = ag.trips[t];
                    var dep = trip.depart;
                    var arriveAt = dep + trip.walk;
                    var leaveAt = arriveAt + trip.stay;
                    var homeAt = leaveAt + trip.walk;

                    if (simTime >= dep && simTime < arriveAt) {
                        var progress = (simTime - dep) / trip.walk;
                        pos = interpolatePath(trip.road, progress);
                        color = trip.color;
                        state = 'walking';
                        break;
                    } else if (simTime >= arriveAt && simTime < leaveAt) {
                        pos = trip.road[trip.road.length - 1];
                        color = trip.color;
                        state = 'staying';
                        break;
                    } else if (simTime >= leaveAt && simTime < homeAt) {
                        var progress = (simTime - leaveAt) / trip.walk;
                        var rev = trip.road.slice().reverse();
                        pos = interpolatePath(rev, progress);
                        color = trip.color;
                        state = 'walking';
                        break;
                    }
                }

                var m = markers[ag.id];
                if (pos) {
                    if (!m) {
                        m = getMarker(ag.id, color);
                    }
                    m.setLatLng(pos);
                    m.setStyle({fillColor: color, radius: state === 'staying' ? 6 : 5});
                    if (!m._map) m.addTo(map);
                    activeSet[ag.id] = true;

                    if (state === 'walking') walkingCount++;
                    else stayingCount++;

                    typeCounts[ag.profile] = (typeCounts[ag.profile] || 0) + 1;
                } else {
                    if (m && m._map) map.removeLayer(m);
                }
            }

            var statsHtml = '🕐 ' + formatTime(simTime) + '<br>'
                + '🚶 이동: ' + walkingCount + '명  📍 체류: ' + stayingCount + '명<br>'
                + '출발대기: ' + (AGENTS.length - walkingCount - stayingCount) + '명';

            var profileLine = '';
            for (var p in typeCounts) {
                profileLine += (profileEmoji[p] || '') + p + ':' + typeCounts[p] + ' ';
            }
            if (profileLine) statsHtml += '<br>' + profileLine;

            document.getElementById('stats').innerHTML = statsHtml;

            requestAnimationFrame(updateSim);
        }

        requestAnimationFrame(updateSim);

        document.getElementById('playBtn').onclick = function() {
            running = !running;
            lastFrame = performance.now();
            this.textContent = running ? '⏸ 정지' : '▶ 시작';
        };
        document.getElementById('resetBtn').onclick = function() {
            simTime = 360;
            lastFrame = performance.now();
            for (var id in markers) {
                if (markers[id]._map) map.removeLayer(markers[id]);
            }
        };
        document.getElementById('timeSlider').oninput = function() {
            simTime = parseInt(this.value);
            lastFrame = performance.now();
        };

        """
        '</script></body></html>'
    )
    components.html(html, height=710)

with col_detail:
    tab_hot, tab_mot, tab_profile, tab_spend, tab_agent, tab_timeline = st.tabs(
        ["🔥인기장소", "동기별", "프로파일", "소비", "에이전트", "타임라인"]
    )

    with tab_hot:
        if not df.empty:
            st.markdown("**방문 많은 목적지 TOP 20**")
            top = df.groupby(["목적지", "목적지유형"]).agg(
                방문=("agent_id", "count"),
                방문자=("agent_id", "nunique"),
                총소비=("소비(원)", "sum"),
                평균도보=("도보(분)", "mean"),
            ).sort_values("방문", ascending=False).head(20).reset_index()
            top["평균도보"] = top["평균도보"].round(1)
            top["총소비"] = top["총소비"].apply(lambda x: f"{x:,}")
            st.dataframe(top, use_container_width=True, hide_index=True)

            st.markdown("**목적지 유형별 방문 집계**")
            by_type = df.groupby("목적지유형").agg(
                방문=("agent_id", "count"),
                장소수=("목적지", "nunique"),
                총소비=("소비(원)", "sum"),
            ).sort_values("방문", ascending=False).reset_index()
            by_type["장소당방문"] = (by_type["방문"] / by_type["장소수"]).round(1)
            by_type["총소비"] = by_type["총소비"].apply(lambda x: f"{x:,}")
            st.dataframe(by_type, use_container_width=True, hide_index=True)

            st.markdown("**시간대별 인기 장소 (Top 3)**")
            for slot_name in ["이른아침", "오전", "점심", "오후", "저녁", "밤"]:
                slot_df = df[df["시간대"] == slot_name]
                if slot_df.empty:
                    continue
                top3 = slot_df.groupby("목적지").size().nlargest(3)
                items = ", ".join(f"{name}({cnt}회)" for name, cnt in top3.items())
                st.write(f"**{slot_name}**: {items}")

            # 매출 추정
            if not revenue_df.empty:
                st.divider()
                annual = sales_info["annual"]
                st.markdown(f"**실제 매출 기반 추정** (상권 총매출 {annual/1e8:,.0f}억원)")

                rev_display = revenue_df.head(20).copy()
                rev_display["방문비율"] = (rev_display["방문비율"] * 100).round(1).astype(str) + "%"
                rev_display["추정연매출"] = rev_display["추정연매출"].apply(lambda x: f"{x:,}")
                rev_display["추정월매출"] = rev_display["추정월매출"].apply(lambda x: f"{x:,}")
                st.dataframe(
                    rev_display[["목적지", "유형", "방문", "방문비율", "추정연매출", "추정월매출"]],
                    use_container_width=True, hide_index=True,
                )

                st.markdown("**유형별 추정 매출**")
                rev_by_type = revenue_df.groupby("유형").agg(
                    건물수=("목적지", "count"),
                    총방문=("방문", "sum"),
                    추정연매출=("추정연매출", "sum"),
                ).sort_values("추정연매출", ascending=False).reset_index()
                rev_by_type["매출비율"] = (rev_by_type["추정연매출"] / rev_by_type["추정연매출"].sum() * 100).round(1).astype(str) + "%"
                rev_by_type["추정연매출"] = rev_by_type["추정연매출"].apply(lambda x: f"{x:,}")
                st.dataframe(rev_by_type, use_container_width=True, hide_index=True)

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

            if "출발점" in df.columns:
                st.markdown("**출발점별 이동**")
                os = df.groupby("출발점").agg(
                    인원=("agent_id", "nunique"),
                    이동=("agent_id", "count"),
                ).sort_values("이동", ascending=False).reset_index()
                st.dataframe(os, use_container_width=True, hide_index=True)

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
                format_func=lambda i: f"#{went_out_agents[i].id} [{went_out_agents[i].profile}] ({went_out_agents[i].origin}) ({len(went_out_agents[i].log)}회)",
            )
            agent = went_out_agents[pick]
            st.write(f"**출발점**: {agent.origin}")
            for j, log in enumerate(agent.log, 1):
                mot = log.get("motivation", "")
                depart = log.get("depart_min", 0)
                stay = log.get("stay_min", 0)
                ret = log.get("return_min", 0)
                spend = log.get("spend", 0)
                chain = " 🔗" if log.get("is_chain") else ""
                cross_txt = f" · 횡단{log['crossings']}번" if log['crossings'] > 0 else ""
                spend_txt = f" · {spend:,}원" if spend > 0 else ""
                dep_str = f"{depart // 60:02d}:{depart % 60:02d}"
                ret_str = f"{ret // 60:02d}:{ret % 60:02d}"
                st.write(
                    f"**{j}. {dep_str}~{ret_str} {mot}{chain}**  \n"
                    f"  {log['dest_name']} · {log['walk_min']}분 · 체류{stay}분{cross_txt}{spend_txt}"
                )
        else:
            st.info("외출한 에이전트가 없습니다.")

    with tab_timeline:
        if not df.empty:
            st.markdown("**시간대별 외출자 수**")
            hour_data = {}
            for _, row in df.iterrows():
                dep_h = row["출발(분)"] // 60
                hour_data[dep_h] = hour_data.get(dep_h, 0) + 1

            timeline_rows = []
            for h in range(6, 25):
                timeline_rows.append({"시간": f"{h:02d}:00", "출발 건수": hour_data.get(h, 0)})
            tl_df = pd.DataFrame(timeline_rows)
            st.bar_chart(tl_df.set_index("시간")["출발 건수"])

            st.markdown("**프로파일별 시간대 분포**")
            if "유형" in df.columns:
                pt = df.copy()
                pt["시각"] = pt["출발(분)"].apply(lambda x: f"{x // 60:02d}:00")
                ptg = pt.groupby(["시각", "유형"]).size().unstack(fill_value=0)
                st.dataframe(ptg, use_container_width=True)
