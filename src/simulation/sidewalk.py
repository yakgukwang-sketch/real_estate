"""인도(보도) 네트워크 — 서울시 공공데이터 기반.

데이터 출처: 서울 열린데이터광장
- OA-21208: 자치구별 도보 네트워크 공간정보 (강남구 29,134건)
- OA-21209: 대로변 횡단보도 위치정보 (강남구 31,080건)
- 지하철역 좌표: subwayStationMaster API
"""

from __future__ import annotations

import json
import re
import math
from dataclasses import dataclass
from pathlib import Path
import heapq


WALK_SPEED = 1.2  # m/s (보행 속도, 약 4.3km/h)
APT_LAT, APT_LON = 37.4945, 127.0625
RADIUS = 0.008  # 약 800m

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "walk_network_gangnam.json"
CROSSWALK_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "crosswalk_gangnam.json"

# 래미안 대치팰리스 주변 지하철역 좌표 (subwayStationMaster API)
SUBWAY_STATIONS = {
    "대치역":    (37.494612, 127.063642),   # 3호선
    "한티역":    (37.496237, 127.052873),   # 분당선
    "학여울역":  (37.496663, 127.070594),   # 3호선
    "도곡역":    (37.490922, 127.055452),   # 3호선
    "매봉역":    (37.486947, 127.046769),   # 3호선
    "선릉역":    (37.504286, 127.048203),   # 2호선
}


@dataclass
class Node:
    id: str
    lat: float
    lon: float
    label: str = ""
    is_crosswalk: bool = False


@dataclass
class Edge:
    from_id: str
    to_id: str
    walk_sec: float = 30.0


class SidewalkNetwork:
    """인도 네트워크 그래프."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, list[Edge]] = {}

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []

    def add_edge(self, from_id: str, to_id: str, walk_sec: float = 30.0):
        """양방향 엣지 추가."""
        self.edges.setdefault(from_id, []).append(Edge(from_id, to_id, walk_sec))
        self.edges.setdefault(to_id, []).append(Edge(to_id, from_id, walk_sec))

    def shortest_path(self, start_id: str, end_id: str) -> list[str]:
        """다익스트라 최단 경로."""
        dist = {start_id: 0.0}
        prev = {}
        heap = [(0.0, start_id)]

        while heap:
            d, nid = heapq.heappop(heap)
            if nid == end_id:
                break
            if d > dist.get(nid, float('inf')):
                continue
            for edge in self.edges.get(nid, []):
                nd = d + edge.walk_sec
                if nd < dist.get(edge.to_id, float('inf')):
                    dist[edge.to_id] = nd
                    prev[edge.to_id] = nid
                    heapq.heappush(heap, (nd, edge.to_id))

        if end_id not in prev and start_id != end_id:
            return []
        path = []
        cur = end_id
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        return list(reversed(path))

    def path_to_coords(self, path: list[str]) -> list[tuple[float, float]]:
        return [(self.nodes[nid].lat, self.nodes[nid].lon) for nid in path if nid in self.nodes]

    def path_walk_time(self, path: list[str]) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            for edge in self.edges.get(path[i], []):
                if edge.to_id == path[i + 1]:
                    total += edge.walk_sec
                    break
        return total

    def nearest_node(self, lat: float, lon: float, exclude: set[str] | None = None) -> str | None:
        """좌표에서 가장 가까운 노드 ID."""
        best_id = None
        best_dist = float('inf')
        skip = exclude or set()
        for nid, node in self.nodes.items():
            if nid in skip:
                continue
            d = (node.lat - lat) ** 2 + (node.lon - lon) ** 2
            if d < best_dist:
                best_dist = d
                best_id = nid
        return best_id

    def to_geojson_edges(self) -> list[dict]:
        seen = set()
        features = []
        for from_id, edges in self.edges.items():
            for e in edges:
                key = tuple(sorted([e.from_id, e.to_id]))
                if key in seen:
                    continue
                seen.add(key)
                n1 = self.nodes.get(e.from_id)
                n2 = self.nodes.get(e.to_id)
                if not n1 or not n2:
                    continue
                features.append({
                    "from": e.from_id, "to": e.to_id,
                    "coords": [[n1.lat, n1.lon], [n2.lat, n2.lon]],
                    "walk_sec": e.walk_sec,
                    "is_crosswalk": n1.is_crosswalk or n2.is_crosswalk,
                })
        return features


def _parse_point(wkt: str) -> tuple[float, float] | None:
    """POINT(lon lat) → (lat, lon)"""
    m = re.match(r'POINT\(([\d.]+)\s+([\d.]+)\)', wkt)
    if m:
        return float(m.group(2)), float(m.group(1))
    return None


def _parse_linestring(wkt: str) -> list[tuple[float, float]]:
    """LINESTRING(lon lat, lon lat, ...) → [(lat, lon), ...]"""
    m = re.match(r'LINESTRING\((.+)\)', wkt)
    if not m:
        return []
    coords = []
    for pair in m.group(1).split(","):
        parts = pair.strip().split()
        if len(parts) == 2:
            coords.append((float(parts[1]), float(parts[0])))
    return coords


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이 거리 (미터, 간이 계산)."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_daechi_network() -> SidewalkNetwork:
    """서울시 공공데이터에서 래미안 대치팰리스 주변 인도 네트워크 구축."""
    net = SidewalkNetwork()

    with open(DATA_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    # --- 1) 모든 노드 파싱 (좌표 인덱스 구축) ---
    all_node_info: dict[int, dict] = {}
    for r in rows:
        if r["NODE_TYPE"] != "NODE":
            continue
        pt = _parse_point(r.get("NODE_WKT", ""))
        if not pt:
            continue
        nid = int(r["NODE_ID"])
        is_cx = str(r.get("CRSWK", "0")) == "1"
        all_node_info[nid] = {"lat": pt[0], "lon": pt[1], "is_crosswalk": is_cx}

    # --- 2) 모든 링크를 엣지로 등록 (강남구 전체) ---
    all_links = [r for r in rows if r["NODE_TYPE"] == "LINK"]
    used_nodes: dict[int, dict] = {}

    for r in all_links:
        bgn = int(r["BGNG_LNKG_ID"])
        end = int(r["END_LNKG_ID"])

        coords = _parse_linestring(r.get("LNKG_WKT", ""))
        if not coords:
            continue

        is_cx = str(r.get("CRSWK", "0")) == "1"
        lnkg_type = r.get("LNKG_TYPE_CD", "")
        length_m = float(r.get("LNKG_LEN", 0) or 0)

        if bgn in all_node_info:
            used_nodes[bgn] = all_node_info[bgn]
        elif bgn not in used_nodes:
            used_nodes[bgn] = {"lat": coords[0][0], "lon": coords[0][1], "is_crosswalk": is_cx}
        if end in all_node_info:
            used_nodes[end] = all_node_info[end]
        elif end not in used_nodes:
            used_nodes[end] = {"lat": coords[-1][0], "lon": coords[-1][1], "is_crosswalk": is_cx}

        walk_sec = length_m / WALK_SPEED if length_m > 0 else 10.0
        if lnkg_type == "1011":  # 횡단보도 링크
            walk_sec += 30.0  # 신호 대기 평균 30초

        net.add_edge(str(bgn), str(end), walk_sec=round(walk_sec, 1))

    all_nodes = used_nodes

    # --- 3) 노드 등록 ---
    for nid, info in all_nodes.items():
        net.add_node(Node(
            id=str(nid),
            lat=info["lat"],
            lon=info["lon"],
            is_crosswalk=info["is_crosswalk"],
        ))

    # --- 4) 횡단보도 전용 데이터 합치기 (OA-21209) ---
    if CROSSWALK_PATH.exists():
        with open(CROSSWALK_PATH, encoding="utf-8") as f:
            cx_rows = json.load(f)

        # 횡단보도 노드 추가
        for r in cx_rows:
            if r["NODE_TYPE"] != "NODE":
                continue
            pt = _parse_point(r.get("NODE_WKT", ""))
            if not pt:
                continue
            nid = int(r["NODE_ID"])
            if nid not in all_nodes:
                all_nodes[nid] = {"lat": pt[0], "lon": pt[1], "is_crosswalk": True}
                net.add_node(Node(str(nid), pt[0], pt[1], is_crosswalk=True))

        # 횡단보도 링크 추가 (도로 횡단 연결)
        for r in cx_rows:
            if r["NODE_TYPE"] != "LINK":
                continue
            bgn = int(r["BGNG_LNKG_ID"])
            end = int(r["END_LNKG_ID"])
            coords = _parse_linestring(r.get("LNKG_WKT", ""))
            if not coords:
                continue

            length_m = float(r.get("LNKG_LEN", 0) or 0)

            # 노드가 없으면 LINESTRING 끝점에서 생성
            if bgn not in all_nodes:
                all_nodes[bgn] = {"lat": coords[0][0], "lon": coords[0][1], "is_crosswalk": True}
                net.add_node(Node(str(bgn), coords[0][0], coords[0][1], is_crosswalk=True))
            if end not in all_nodes:
                all_nodes[end] = {"lat": coords[-1][0], "lon": coords[-1][1], "is_crosswalk": True}
                net.add_node(Node(str(end), coords[-1][0], coords[-1][1], is_crosswalk=True))

            # 횡단보도 = 도보시간 + 신호대기
            walk_sec = length_m / WALK_SPEED if length_m > 0 else 10.0
            walk_sec += 30.0  # 신호 대기
            net.add_edge(str(bgn), str(end), walk_sec=round(walk_sec, 1))

    # --- 5) 단절된 컴포넌트 자동 연결 (30m 이내 노드끼리) ---
    # 래미안 근처 노드만 대상 (성능)
    nearby_nids = [
        nid for nid, node in net.nodes.items()
        if abs(node.lat - APT_LAT) <= RADIUS and abs(node.lon - APT_LON) <= RADIUS
    ]

    # BFS로 컴포넌트 찾기 (근처 노드만)
    nearby_set = set(nearby_nids)
    remaining = set(nearby_nids)
    components: list[set[str]] = []
    while remaining:
        start = remaining.pop()
        comp = {start}
        q = [start]
        while q:
            n = q.pop(0)
            for e in net.edges.get(n, []):
                if e.to_id in remaining:
                    remaining.discard(e.to_id)
                    comp.add(e.to_id)
                    q.append(e.to_id)
        components.append(comp)

    # 컴포넌트 간 30m 이내 노드 쌍을 찾아 연결
    BRIDGE_DIST = 30.0
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            best_d = float('inf')
            best_pair = None
            for a in components[i]:
                na = net.nodes[a]
                for b in components[j]:
                    nb = net.nodes[b]
                    d = _distance_m(na.lat, na.lon, nb.lat, nb.lon)
                    if d < best_d:
                        best_d = d
                        best_pair = (a, b)
            if best_pair and best_d <= BRIDGE_DIST:
                walk_sec = round(best_d / WALK_SPEED, 1)
                net.add_edge(best_pair[0], best_pair[1], walk_sec=max(walk_sec, 5.0))

    # --- 6) 지하철역 노드 추가 & 가장 가까운 도로 노드에 연결 ---
    special_ids = set()
    for stn_name, (slat, slon) in SUBWAY_STATIONS.items():
        stn_id = f"subway_{stn_name}"
        special_ids.add(stn_id)
        net.add_node(Node(stn_id, slat, slon, stn_name))
        nearest = net.nearest_node(slat, slon, exclude=special_ids | {"apt"})
        if nearest:
            d = _distance_m(slat, slon, net.nodes[nearest].lat, net.nodes[nearest].lon)
            net.add_edge(stn_id, nearest, walk_sec=round(d / WALK_SPEED, 1))

    # --- 7) 아파트 정문 노드 추가 & 가장 가까운 도로 노드에 연결 ---
    net.add_node(Node("apt", APT_LAT, APT_LON, "래미안 대치팰리스 정문"))
    nearest = net.nearest_node(APT_LAT, APT_LON, exclude=special_ids | {"apt"})
    if nearest:
        d = _distance_m(APT_LAT, APT_LON, net.nodes[nearest].lat, net.nodes[nearest].lon)
        net.add_edge("apt", nearest, walk_sec=round(d / WALK_SPEED, 1))

    return net
