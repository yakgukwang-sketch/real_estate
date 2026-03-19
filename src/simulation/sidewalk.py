"""인도(보도) 네트워크 — 에이전트가 다닐 수 있는 길.

노드 = 교차점, 횡단보도, 건물 입구
엣지 = 인도 구간
에이전트는 이 네트워크 위에서만 이동 가능.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq


@dataclass
class Node:
    id: str
    lat: float
    lon: float
    label: str = ""
    is_crosswalk: bool = False  # 횡단보도 지점


@dataclass
class Edge:
    from_id: str
    to_id: str
    walk_sec: float = 30.0  # 이 구간 도보 시간 (초)


class SidewalkNetwork:
    """인도 네트워크 그래프."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, list[Edge]] = {}  # from_id → [Edge]

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

        # 경로 역추적
        if end_id not in prev and start_id != end_id:
            return []
        path = []
        cur = end_id
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        return list(reversed(path))

    def path_to_coords(self, path: list[str]) -> list[tuple[float, float]]:
        """노드 ID 경로 → 좌표 리스트."""
        return [(self.nodes[nid].lat, self.nodes[nid].lon) for nid in path if nid in self.nodes]

    def path_walk_time(self, path: list[str]) -> float:
        """경로 총 도보 시간 (초)."""
        total = 0.0
        for i in range(len(path) - 1):
            for edge in self.edges.get(path[i], []):
                if edge.to_id == path[i + 1]:
                    total += edge.walk_sec
                    break
        return total

    def to_geojson_edges(self) -> list[dict]:
        """엣지를 GeoJSON LineString으로 변환 (시각화용)."""
        seen = set()
        features = []
        for from_id, edges in self.edges.items():
            for e in edges:
                key = tuple(sorted([e.from_id, e.to_id]))
                if key in seen:
                    continue
                seen.add(key)
                n1 = self.nodes[e.from_id]
                n2 = self.nodes[e.to_id]
                features.append({
                    "from": e.from_id, "to": e.to_id,
                    "coords": [[n1.lat, n1.lon], [n2.lat, n2.lon]],
                    "walk_sec": e.walk_sec,
                    "is_crosswalk": n1.is_crosswalk or n2.is_crosswalk,
                })
        return features


def build_daechi_network() -> SidewalkNetwork:
    """래미안 대치팰리스 주변 인도 네트워크 구축.

    도곡로 = 동서 방향 대로 (북측 인도 / 남측 인도)
    남북 골목 = 도곡로에서 갈라지는 길
    횡단보도 = 북측↔남측 연결 지점
    """
    net = SidewalkNetwork()

    # === 노드 정의 ===

    # 아파트 출입구
    net.add_node(Node("apt", 37.4945, 127.0625, "래미안 대치팰리스 정문"))

    # 도곡로 북측 인도 (서→동)
    net.add_node(Node("n_w3", 37.4940, 127.0555, "도곡로북 서쪽끝"))
    net.add_node(Node("n_w2", 37.4940, 127.0570, "도곡로북"))
    net.add_node(Node("n_w1", 37.4940, 127.0590, "도곡로북"))
    net.add_node(Node("n_cx1", 37.4940, 127.0610, "도곡로북 횡단보도1", is_crosswalk=True))
    net.add_node(Node("n_apt", 37.4940, 127.0625, "도곡로북 아파트앞"))
    net.add_node(Node("n_cx2", 37.4940, 127.0645, "도곡로북 횡단보도2", is_crosswalk=True))
    net.add_node(Node("n_e1", 37.4940, 127.0660, "도곡로북"))
    net.add_node(Node("n_e2", 37.4940, 127.0675, "도곡로북 동쪽끝"))

    # 도곡로 남측 인도 (서→동)
    net.add_node(Node("s_w3", 37.4935, 127.0555, "도곡로남 서쪽끝"))
    net.add_node(Node("s_w2", 37.4935, 127.0570, "도곡로남"))
    net.add_node(Node("s_w1", 37.4935, 127.0590, "도곡로남"))
    net.add_node(Node("s_cx1", 37.4935, 127.0610, "도곡로남 횡단보도1", is_crosswalk=True))
    net.add_node(Node("s_apt", 37.4935, 127.0625, "도곡로남 아파트맞은편"))
    net.add_node(Node("s_cx2", 37.4935, 127.0645, "도곡로남 횡단보도2", is_crosswalk=True))
    net.add_node(Node("s_e1", 37.4935, 127.0660, "도곡로남"))
    net.add_node(Node("s_e2", 37.4935, 127.0675, "도곡로남 동쪽끝"))

    # 상권 목적지 노드
    net.add_node(Node("zone_front", 37.4940, 127.0640, "단지 앞 도곡로 상가"))
    net.add_node(Node("zone_cross", 37.4930, 127.0610, "도곡로 건너편 상가"))
    net.add_node(Node("zone_daechi", 37.4945, 127.0555, "대치역 상권"))
    net.add_node(Node("zone_hanti", 37.4980, 127.0675, "한티역 상권"))
    net.add_node(Node("zone_academy", 37.4915, 127.0645, "학원가 뒷길"))

    # 북쪽 골목 (한티역 방향)
    net.add_node(Node("north1", 37.4950, 127.0675, "북쪽골목1"))
    net.add_node(Node("north2", 37.4960, 127.0675, "북쪽골목2"))
    net.add_node(Node("north3", 37.4970, 127.0675, "북쪽골목3"))

    # 남쪽 골목 (학원가 방향)
    net.add_node(Node("south1", 37.4930, 127.0645, "남쪽골목1"))
    net.add_node(Node("south2", 37.4922, 127.0645, "남쪽골목2"))

    # 대치역 방향 북쪽 진입
    net.add_node(Node("daechi_s", 37.4940, 127.0555, "대치역남쪽"))

    # === 엣지 정의 ===

    # 아파트 → 도곡로 북측 (단지에서 도로까지)
    net.add_edge("apt", "n_apt", walk_sec=40)

    # 도곡로 북측 인도 (동서 연결)
    net.add_edge("n_w3", "n_w2", walk_sec=30)
    net.add_edge("n_w2", "n_w1", walk_sec=30)
    net.add_edge("n_w1", "n_cx1", walk_sec=30)
    net.add_edge("n_cx1", "n_apt", walk_sec=25)
    net.add_edge("n_apt", "n_cx2", walk_sec=30)
    net.add_edge("n_cx2", "n_e1", walk_sec=25)
    net.add_edge("n_e1", "n_e2", walk_sec=25)

    # 도곡로 남측 인도 (동서 연결)
    net.add_edge("s_w3", "s_w2", walk_sec=30)
    net.add_edge("s_w2", "s_w1", walk_sec=30)
    net.add_edge("s_w1", "s_cx1", walk_sec=30)
    net.add_edge("s_cx1", "s_apt", walk_sec=25)
    net.add_edge("s_apt", "s_cx2", walk_sec=30)
    net.add_edge("s_cx2", "s_e1", walk_sec=25)
    net.add_edge("s_e1", "s_e2", walk_sec=25)

    # 횡단보도 (북↔남 연결, 횡단보도 위치에서만 건넘)
    net.add_edge("n_cx1", "s_cx1", walk_sec=20)  # 횡단보도1
    net.add_edge("n_cx2", "s_cx2", walk_sec=20)  # 횡단보도2

    # 상권 연결
    # 단지 앞 상가: 도곡로 북측 횡단보도2 근처
    net.add_edge("n_cx2", "zone_front", walk_sec=15)

    # 건너편 상가: 남측 횡단보도1에서 남쪽 골목으로
    net.add_edge("s_cx1", "zone_cross", walk_sec=25)

    # 대치역: 도곡로 북측 서쪽 끝 → 대치역
    net.add_edge("n_w3", "daechi_s", walk_sec=10)
    net.add_edge("daechi_s", "zone_daechi", walk_sec=20)

    # 한티역: 도곡로 북측 동쪽 끝 → 북쪽 골목 → 한티역
    net.add_edge("n_e2", "north1", walk_sec=25)
    net.add_edge("north1", "north2", walk_sec=25)
    net.add_edge("north2", "north3", walk_sec=25)
    net.add_edge("north3", "zone_hanti", walk_sec=25)

    # 학원가: 남측 횡단보도2에서 남쪽 골목 → 학원가
    net.add_edge("s_cx2", "south1", walk_sec=20)
    net.add_edge("south1", "south2", walk_sec=25)
    net.add_edge("south2", "zone_academy", walk_sec=25)

    return net


# 상권 구역 → 네트워크 노드 매핑
ZONE_TO_NODE = {
    "단지 앞 도곡로": "zone_front",
    "도곡로 건너편": "zone_cross",
    "대치역 상권": "zone_daechi",
    "한티역 상권": "zone_hanti",
    "학원가 뒷길": "zone_academy",
}
