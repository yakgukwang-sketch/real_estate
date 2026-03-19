"""단일 아파트 에이전트 시뮬레이션.

래미안 대치팰리스 주민들이 인도 네트워크 위에서 실제 건물로 이동.
목적지: 상권정보 API에서 가져온 585개 실제 건물 (음식점, 학원, 상점 등)
"""

from __future__ import annotations

import json
import math
import random
import heapq
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.simulation.sidewalk import build_daechi_network, _distance_m


@dataclass
class Agent:
    id: int
    home: tuple[float, float]
    log: list[dict] = field(default_factory=list)


# 래미안 대치팰리스 좌표
APT_COORDS = (37.4945, 127.0625)

# 인도 네트워크
NETWORK = build_daechi_network()

# 실제 건물 데이터 로드
_BUILDINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "buildings_classified.json"


def _load_buildings() -> list[dict]:
    if not _BUILDINGS_PATH.exists():
        return []
    with open(_BUILDINGS_PATH, encoding="utf-8") as f:
        buildings = json.load(f)

    results = []
    for b in buildings:
        lat, lon = b.get("lat", 0), b.get("lon", 0)
        if not lat or not lon:
            continue

        cats = b.get("categories", {})
        btype = b.get("bld_type", "")

        # 목적지 유형 매핑
        if "음식" in cats:
            dest_type = "음식점"
        elif "교육" in cats and cats.get("교육", 0) >= 3:
            dest_type = "학원"
        elif "소매" in cats:
            dest_type = "상점"
        elif "보건의료" in cats:
            dest_type = "병원/약국"
        elif "생활서비스" in cats:
            dest_type = "생활서비스"
        elif btype == "대형상가/백화점":
            dest_type = "대형상가"
        else:
            dest_type = "기타"

        results.append({
            "name": b.get("bld_nm") or b.get("rdnm_adr", ""),
            "lat": float(lat),
            "lon": float(lon),
            "dest_type": dest_type,
            "store_count": b.get("store_count", 1),
        })
    return results


BUILDINGS = _load_buildings()

# --- apt에서 모든 노드까지 최단 거리 (1회 다익스트라) ---
def _dijkstra_from_apt():
    dist = {"apt": 0.0}
    prev = {"apt": None}
    heap = [(0.0, "apt")]
    while heap:
        d, nid = heapq.heappop(heap)
        if d > dist.get(nid, float("inf")):
            continue
        for edge in NETWORK.edges.get(nid, []):
            nd = d + edge.walk_sec
            if nd < dist.get(edge.to_id, float("inf")):
                dist[edge.to_id] = nd
                prev[edge.to_id] = nid
                heapq.heappush(heap, (nd, edge.to_id))
    return dist, prev


_APT_DIST, _APT_PREV = _dijkstra_from_apt()


def _reconstruct_path(end_id: str) -> list[str]:
    path = []
    cur = end_id
    while cur is not None:
        path.append(cur)
        cur = _APT_PREV.get(cur)
    return list(reversed(path))


# --- 각 건물에서 가장 가까운 네트워크 노드 + 경로 캐시 ---
def _build_building_destinations():
    """각 건물의 최근접 네트워크 노드를 찾고, apt에서의 경로를 계산."""
    dests = []
    skip = {"apt"} | {nid for nid in NETWORK.nodes if nid.startswith("subway_")}

    for bld in BUILDINGS:
        # 가장 가까운 네트워크 노드
        nearest = NETWORK.nearest_node(bld["lat"], bld["lon"], exclude=skip)
        if not nearest or nearest not in _APT_DIST:
            continue

        dist_sec = _APT_DIST[nearest]
        if dist_sec < 20 or dist_sec > 2400:  # 20초~40분
            continue

        path_ids = _reconstruct_path(nearest)
        coords = NETWORK.path_to_coords(path_ids)
        crossings = sum(1 for n in path_ids if NETWORK.nodes.get(n) and NETWORK.nodes[n].is_crosswalk)

        dests.append({
            "name": bld["name"],
            "dest_type": bld["dest_type"],
            "store_count": bld["store_count"],
            "node_id": nearest,
            "coords": coords,
            "walk_sec": dist_sec,
            "walk_min": max(1, round(dist_sec / 60)),
            "crossings": crossings,
        })
    return dests


DESTINATIONS = _build_building_destinations()

# 동기(motivation) — "왜 나가는가" + 어떤 건물로 가는가
MOTIVATIONS = [
    {"name": "출근",           "prob": 0.25, "dest_types": None,          "dist_pref": "far"},
    {"name": "출근 전 커피",   "prob": 0.12, "dest_types": ["음식점"],    "dist_pref": "near"},
    {"name": "등원/학원",      "prob": 0.08, "dest_types": ["학원"],      "dist_pref": "mid"},
    {"name": "점심 외식",      "prob": 0.15, "dest_types": ["음식점"],    "dist_pref": "mid"},
    {"name": "산책",           "prob": 0.08, "dest_types": None,          "dist_pref": "mid"},
    {"name": "장보기",         "prob": 0.08, "dest_types": ["상점", "대형상가"], "dist_pref": "mid"},
    {"name": "학원 픽업",      "prob": 0.07, "dest_types": ["학원"],      "dist_pref": "mid"},
    {"name": "병원/약국",      "prob": 0.04, "dest_types": ["병원/약국"], "dist_pref": "near"},
    {"name": "저녁 외식",      "prob": 0.10, "dest_types": ["음식점"],    "dist_pref": "mid"},
    {"name": "동네 볼일",      "prob": 0.08, "dest_types": ["생활서비스", "기타"], "dist_pref": "near"},
    {"name": "친구 약속",      "prob": 0.06, "dest_types": ["음식점"],    "dist_pref": "far"},
]

DEST_TYPES = sorted(set(d["dest_type"] for d in DESTINATIONS))


def _pick_destination(dest_types: list[str] | None, dist_pref: str) -> dict | None:
    """동기에 맞는 건물 목적지 선택."""
    if dest_types:
        pool = [d for d in DESTINATIONS if d["dest_type"] in dest_types]
    else:
        pool = DESTINATIONS

    if not pool:
        return None

    # 거리 선호 + 가게 수(인기도) 가중치
    weights = []
    for d in pool:
        sec = d["walk_sec"]
        if dist_pref == "near":
            w = math.exp(-sec / 200.0)
        elif dist_pref == "mid":
            w = math.exp(-((sec - 400) ** 2) / 80000.0)
        else:
            w = 1.0 - math.exp(-sec / 400.0)
        # 가게 많은 건물일수록 선택 확률 높음
        w *= max(1, min(d["store_count"], 20)) ** 0.5
        weights.append(max(w, 0.001))

    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0
    for d, w in zip(pool, weights):
        cumulative += w
        if r <= cumulative:
            return d
    return pool[-1]


def simulate(n_agents: int = 100, seed: int | None = 42) -> list[Agent]:
    if seed is not None:
        random.seed(seed)

    agents = []
    for i in range(n_agents):
        agent = Agent(id=i, home=APT_COORDS)

        for mot in MOTIVATIONS:
            if random.random() < mot["prob"]:
                dest = _pick_destination(mot["dest_types"], mot["dist_pref"])
                if dest is None:
                    continue

                agent.log.append({
                    "motivation": mot["name"],
                    "dest_name": dest["name"],
                    "dest_type": dest["dest_type"],
                    "dest_coords": dest["coords"][-1] if dest["coords"] else APT_COORDS,
                    "road_path": dest["coords"],
                    "walk_min": dest["walk_min"],
                    "walk_sec": dest["walk_sec"],
                    "crossings": dest["crossings"],
                })

        agents.append(agent)

    return agents


def agents_to_df(agents: list[Agent]) -> pd.DataFrame:
    rows = []
    for agent in agents:
        for log in agent.log:
            rows.append({
                "agent_id": agent.id,
                "동기": log.get("motivation", ""),
                "목적지": log.get("dest_name", ""),
                "유형": log.get("dest_type", ""),
                "lat": log["dest_coords"][0],
                "lon": log["dest_coords"][1],
                "도보(분)": log["walk_min"],
                "횡단보도": log["crossings"],
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print(f"건물 목적지: {len(DESTINATIONS)}개")
    from collections import Counter
    tc = Counter(d["dest_type"] for d in DESTINATIONS)
    for t, c in tc.most_common():
        print(f"  {t}: {c}개")

    agents = simulate(n_agents=100, seed=42)
    df = agents_to_df(agents)

    print(f"\n에이전트: {len(agents)}명, 외출: {df['agent_id'].nunique()}명, 이동: {len(df)}건")
    print("\n동기별:")
    print(df["동기"].value_counts().to_string())
    print("\n유형별:")
    print(df["유형"].value_counts().to_string())
    print("\n인기 목적지:")
    print(df["목적지"].value_counts().head(10).to_string())
