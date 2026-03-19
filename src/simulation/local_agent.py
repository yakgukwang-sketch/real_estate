"""단일 아파트 에이전트 시뮬레이션.

래미안 대치팰리스 주민들이 인도 네트워크 위에서만 이동.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pandas as pd

from src.simulation.sidewalk import build_daechi_network, ZONE_TO_NODE


@dataclass
class Agent:
    id: int
    home: tuple[float, float]
    needs: list[str] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)


# 래미안 대치팰리스 좌표
APT_COORDS = (37.4945, 127.0625)

# 인도 네트워크 (모듈 로드 시 한 번만 생성)
NETWORK = build_daechi_network()

# 구역 정보 (접근성 계산용)
ZONES = {
    "단지 앞 도곡로": {"stores": ["편의점", "카페", "음식점", "기타"], "node": "zone_front"},
    "도곡로 건너편":  {"stores": ["음식점", "카페", "편의점"],         "node": "zone_cross"},
    "대치역 상권":    {"stores": ["음식점", "카페", "편의점", "기타"], "node": "zone_daechi"},
    "한티역 상권":    {"stores": ["음식점", "카페", "마트/슈퍼"],      "node": "zone_hanti"},
    "학원가 뒷길":    {"stores": ["카페", "편의점", "음식점"],         "node": "zone_academy"},
}

# 각 구역의 도보시간(초)과 횡단보도 수를 네트워크에서 계산
_ZONE_PATHS: dict[str, dict] = {}
for zname, zinfo in ZONES.items():
    path_ids = NETWORK.shortest_path("apt", zinfo["node"])
    coords = NETWORK.path_to_coords(path_ids)
    walk_sec = NETWORK.path_walk_time(path_ids)
    crossings = sum(1 for nid in path_ids if NETWORK.nodes[nid].is_crosswalk)
    _ZONE_PATHS[zname] = {
        "path_ids": path_ids,
        "coords": coords,
        "walk_sec": walk_sec,
        "walk_min": max(1, round(walk_sec / 60)),
        "crossings": crossings,
    }

NEEDS = {
    "편의점":    {"prob": 0.10, "spend": 4_000},
    "카페":      {"prob": 0.20, "spend": 5_500},
    "음식점":    {"prob": 0.25, "spend": 9_000},
    "마트/슈퍼": {"prob": 0.06, "spend": 25_000},
    "기타":      {"prob": 0.12, "spend": 7_000},
}


def _accessibility(walk_sec: float, crossings: int) -> float:
    walk_decay = math.exp(-walk_sec / 300.0)  # 5분(300초) 기준 감쇠
    crossing_penalty = 0.3 ** crossings
    return walk_decay * crossing_penalty


def _pick_zone(need: str) -> str | None:
    """접근성 기반으로 구역 선택."""
    available = [(zn, zi) for zn, zi in ZONES.items() if need in zi["stores"]]
    if not available:
        return None

    scores = []
    for zname, _ in available:
        zp = _ZONE_PATHS[zname]
        scores.append(_accessibility(zp["walk_sec"], zp["crossings"]))

    total = sum(scores)
    if total <= 0:
        return None

    r = random.random() * total
    cumulative = 0.0
    for (zname, _), s in zip(available, scores):
        cumulative += s
        if r <= cumulative:
            return zname
    return available[-1][0]


def simulate(n_agents: int = 100, seed: int | None = 42) -> list[Agent]:
    if seed is not None:
        random.seed(seed)

    agents = []
    for i in range(n_agents):
        agent = Agent(id=i, home=APT_COORDS)

        for category, params in NEEDS.items():
            if random.random() < params["prob"]:
                agent.needs.append(category)

        for need in agent.needs:
            zname = _pick_zone(need)
            if zname is None:
                continue

            zp = _ZONE_PATHS[zname]
            spend = round(NEEDS[need]["spend"] * random.uniform(0.7, 1.3))

            agent.log.append({
                "need": need,
                "zone": zname,
                "zone_coords": zp["coords"][-1] if zp["coords"] else APT_COORDS,
                "road_path": zp["coords"],
                "walk_min": zp["walk_min"],
                "walk_sec": zp["walk_sec"],
                "crossings": zp["crossings"],
                "spend": spend,
            })

        agents.append(agent)

    return agents


def agents_to_df(agents: list[Agent]) -> pd.DataFrame:
    rows = []
    for agent in agents:
        for log in agent.log:
            rows.append({
                "agent_id": agent.id,
                "업종": log["need"],
                "구역": log["zone"],
                "lat": log["zone_coords"][0],
                "lon": log["zone_coords"][1],
                "도보(분)": log["walk_min"],
                "횡단보도": log["crossings"],
                "소비금액": log["spend"],
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    agents = simulate(n_agents=100, seed=42)
    df = agents_to_df(agents)

    print(f"=== 래미안 대치팰리스 (인도 네트워크 기반) ===")
    print(f"에이전트: {len(agents)}명, 외출: {df['agent_id'].nunique()}명")
    print(f"총 소비: {df['소비금액'].sum():,}원\n")

    for zname, zp in _ZONE_PATHS.items():
        n = len(zp["coords"])
        print(f"  {zname}: {zp['walk_min']}분, 횡단보도 {zp['crossings']}번, 경로 {n}개 노드")

    print()
    for agent in agents[:5]:
        if agent.log:
            for l in agent.log:
                print(f"  #{agent.id}: {l['need']}→{l['zone']} ({len(l['road_path'])}노드, {l['walk_min']}분)")
        else:
            print(f"  #{agent.id}: 외출 안 함")
