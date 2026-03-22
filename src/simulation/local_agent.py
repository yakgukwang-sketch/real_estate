"""단일 아파트 에이전트 시뮬레이션 (v2).

래미안 대치팰리스 주민들이 인도 네트워크 위에서 실제 건물로 이동.
v2: 에이전트 유형 분화, 시간대별 스케줄, 연쇄 이동(trip chain), 소비 시뮬레이션.
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


# ── 보정 데이터 로드 ──

def _load_calibration_data():
    """보정 데이터 로드 (없으면 None)."""
    try:
        from src.simulation.calibration import load_calibration
        return load_calibration()
    except Exception:
        return None


_CALIBRATION = _load_calibration_data()


# ── 에이전트 유형 프로파일 ──

AGENT_PROFILES: dict[str, dict] = {
    "직장인": {
        "prob": 0.35,
        "schedule": [
            {"time": "07:00", "slot": "이른아침", "actions": [
                {"name": "출근", "prob": 0.90, "dest_types": None, "dist_pref": "far", "spend": 0},
                {"name": "출근 전 커피", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "near", "spend": 5500},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.50, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 9000},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 15000},
                {"name": "장보기", "prob": 0.15, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 25000},
            ]},
            {"time": "20:00", "slot": "밤", "actions": [
                {"name": "산책/운동", "prob": 0.10, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
                {"name": "친구 약속", "prob": 0.08, "dest_types": ["음식점"], "dist_pref": "far", "spend": 20000},
            ]},
        ],
        "chain_prob": 0.15,  # 연쇄 이동 확률
    },
    "맞벌이": {
        "prob": 0.20,
        "schedule": [
            {"time": "07:30", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.60, "dest_types": ["학원", "학교", "어린이집/복지"], "dist_pref": "mid", "spend": 0},
                {"name": "출근", "prob": 0.85, "dest_types": None, "dist_pref": "far", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.40, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 9000},
            ]},
            {"time": "17:00", "slot": "오후", "actions": [
                {"name": "학원 픽업", "prob": 0.50, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "19:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "near", "spend": 12000},
                {"name": "장보기", "prob": 0.20, "dest_types": ["상점", "대형상가"], "dist_pref": "near", "spend": 30000},
            ]},
        ],
        "chain_prob": 0.25,
    },
    "주부/주부": {
        "prob": 0.15,
        "schedule": [
            {"time": "08:00", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.50, "dest_types": ["학원", "학교", "어린이집/복지"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "10:00", "slot": "오전", "actions": [
                {"name": "장보기", "prob": 0.35, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 35000},
                {"name": "동네 볼일", "prob": 0.20, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 5000},
                {"name": "병원/약국", "prob": 0.08, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 10000},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 12000},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "학원 픽업", "prob": 0.45, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
                {"name": "산책/운동", "prob": 0.15, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 5000},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 15000},
            ]},
        ],
        "chain_prob": 0.30,
    },
    "학생": {
        "prob": 0.15,
        "schedule": [
            {"time": "07:30", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.85, "dest_types": ["학교"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "등원/등교", "prob": 0.70, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.15, "dest_types": ["음식점"], "dist_pref": "near", "spend": 7000},
            ]},
            {"time": "20:00", "slot": "밤", "actions": [
                {"name": "산책/운동", "prob": 0.10, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.20,
    },
    "은퇴자": {
        "prob": 0.15,
        "schedule": [
            {"time": "06:00", "slot": "이른아침", "actions": [
                {"name": "산책/운동", "prob": 0.40, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "09:00", "slot": "오전", "actions": [
                {"name": "병원/약국", "prob": 0.15, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 15000},
                {"name": "동네 볼일", "prob": 0.15, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 5000},
                {"name": "종교 활동", "prob": 0.08, "dest_types": ["종교시설"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "near", "spend": 8000},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "장보기", "prob": 0.20, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 20000},
                {"name": "산책/운동", "prob": 0.15, "dest_types": ["운동시설", "공원"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.10, "dest_types": ["음식점"], "dist_pref": "near", "spend": 10000},
            ]},
        ],
        "chain_prob": 0.10,
    },
}

# 연쇄 이동: 현재 목적지 유형 → 다음 가능한 유형
CHAIN_RULES: dict[str, list[dict]] = {
    "학원":      [{"dest_types": ["음식점"], "prob": 0.3, "spend": 5000}],
    "학교":      [{"dest_types": ["음식점"], "prob": 0.2, "spend": 5000}],
    "음식점":    [{"dest_types": ["상점"], "prob": 0.15, "spend": 10000},
                  {"dest_types": ["음식점"], "prob": 0.10, "spend": 5500}],
    "상점":      [{"dest_types": ["음식점"], "prob": 0.20, "spend": 8000}],
    "병원/약국": [{"dest_types": ["상점"], "prob": 0.15, "spend": 5000}],
    "운동시설":  [{"dest_types": ["음식점"], "prob": 0.25, "spend": 5500}],
    "공원":      [{"dest_types": ["음식점"], "prob": 0.20, "spend": 5500}],
}


# ── 업종별 객단가 (소비 시뮬레이션) ──

_SPEND_BY_DEST_DEFAULT: dict[str, int] = {
    "음식점": 9000,
    "상점": 15000,
    "대형상가": 30000,
    "병원/약국": 12000,
    "생활서비스": 5000,
    "기타": 7000,
}

def _apply_visit_multipliers(profiles: dict, multipliers: dict[str, float], spend_map: dict[str, int]) -> dict:
    """방문 보정계수를 프로파일의 action prob에 적용."""
    import copy
    profiles = copy.deepcopy(profiles)
    for _name, profile in profiles.items():
        for slot in profile["schedule"]:
            for action in slot["actions"]:
                dest_types = action.get("dest_types")
                if not dest_types:
                    continue
                # dest_types에 해당하는 보정계수의 평균
                mults = [multipliers.get(dt, 1.0) for dt in dest_types]
                avg_mult = sum(mults) / len(mults)
                action["prob"] = max(0.01, min(action["prob"] * avg_mult, 0.95))
                # spend도 보정된 객단가로 스케일링
                if action.get("spend", 0) > 0 and dest_types:
                    primary_dt = dest_types[0]
                    if primary_dt in spend_map:
                        action["spend"] = spend_map[primary_dt]
    return profiles


# 보정 데이터가 있으면 객단가 교체
if _CALIBRATION and _CALIBRATION.get("unit_prices"):
    SPEND_BY_DEST = {**_SPEND_BY_DEST_DEFAULT, **_CALIBRATION["unit_prices"]}
else:
    SPEND_BY_DEST = _SPEND_BY_DEST_DEFAULT.copy()

# 보정 데이터가 있으면 방문 보정계수 적용
if _CALIBRATION and _CALIBRATION.get("visit_multipliers"):
    AGENT_PROFILES = _apply_visit_multipliers(AGENT_PROFILES, _CALIBRATION["visit_multipliers"], SPEND_BY_DEST)


@dataclass
class Agent:
    id: int
    home: tuple[float, float]
    profile: str = ""
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

        # 목적지 유형 매핑 (상가 API 대분류 + 건축물대장 용도)
        if "음식" in cats:
            dest_type = "음식점"
        elif "교육연구시설" in cats:
            dest_type = "학교"
        elif "교육" in cats and cats.get("교육", 0) >= 3:
            dest_type = "학원"
        elif "소매" in cats:
            dest_type = "상점"
        elif "보건의료" in cats or "의료시설" in cats:
            dest_type = "병원/약국"
        elif "수리·개인" in cats or "생활서비스" in cats:
            dest_type = "생활서비스"
        elif "노유자시설" in cats:
            dest_type = "어린이집/복지"
        elif "종교시설" in cats:
            dest_type = "종교시설"
        elif "공원" in cats:
            dest_type = "공원"
        elif "운동시설" in cats:
            dest_type = "운동시설"
        elif "문화및집회시설" in cats:
            dest_type = "문화시설"
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
DEST_TYPES = sorted(set(d["dest_type"] for d in DESTINATIONS))

# v1 호환용 MOTIVATIONS (대시보드 참조)
MOTIVATIONS = [
    {"name": "출근",           "prob": 0.25, "dest_types": None,                             "dist_pref": "far"},
    {"name": "출근 전 커피",   "prob": 0.12, "dest_types": ["음식점"],                       "dist_pref": "near"},
    {"name": "등원/등교",      "prob": 0.08, "dest_types": ["학원", "학교"],                 "dist_pref": "mid"},
    {"name": "점심 외식",      "prob": 0.12, "dest_types": ["음식점"],                       "dist_pref": "mid"},
    {"name": "산책/운동",      "prob": 0.08, "dest_types": ["운동시설", "공원"],                     "dist_pref": "mid"},
    {"name": "장보기",         "prob": 0.08, "dest_types": ["상점", "대형상가"],             "dist_pref": "mid"},
    {"name": "학원 픽업",      "prob": 0.07, "dest_types": ["학원"],                         "dist_pref": "mid"},
    {"name": "병원/약국",      "prob": 0.04, "dest_types": ["병원/약국"],                    "dist_pref": "near"},
    {"name": "저녁 외식",      "prob": 0.10, "dest_types": ["음식점"],                       "dist_pref": "mid"},
    {"name": "동네 볼일",      "prob": 0.08, "dest_types": ["생활서비스", "어린이집/복지", "기타"], "dist_pref": "near"},
    {"name": "친구 약속",      "prob": 0.06, "dest_types": ["음식점"],                       "dist_pref": "far"},
    {"name": "종교 활동",      "prob": 0.03, "dest_types": ["종교시설"],                     "dist_pref": "mid"},
]


def _pick_destination(dest_types: list[str] | None, dist_pref: str) -> dict | None:
    """동기에 맞는 건물 목적지 선택."""
    if dest_types:
        pool = [d for d in DESTINATIONS if d["dest_type"] in dest_types]
    else:
        pool = DESTINATIONS

    if not pool:
        return None

    weights = []
    for d in pool:
        sec = d["walk_sec"]
        if dist_pref == "near":
            w = math.exp(-sec / 200.0)
        elif dist_pref == "mid":
            w = math.exp(-((sec - 400) ** 2) / 80000.0)
        else:
            w = 1.0 - math.exp(-sec / 400.0)
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


def _assign_profile() -> str:
    """가중 확률로 에이전트 유형 배정."""
    r = random.random()
    cumulative = 0.0
    for name, profile in AGENT_PROFILES.items():
        cumulative += profile["prob"]
        if r <= cumulative:
            return name
    return list(AGENT_PROFILES.keys())[-1]


def _try_chain(current_dest_type: str, chain_prob: float) -> dict | None:
    """연쇄 이동 시도: 현재 목적지에서 다음 목적지로."""
    rules = CHAIN_RULES.get(current_dest_type, [])
    if not rules or random.random() > chain_prob:
        return None

    for rule in rules:
        if random.random() < rule["prob"]:
            dest = _pick_destination(rule["dest_types"], "near")
            if dest:
                return {"dest": dest, "spend": rule["spend"]}
    return None


def simulate(n_agents: int = 100, seed: int | None = 42) -> list[Agent]:
    """v2 시뮬레이션: 유형별 시간대 스케줄 + 연쇄 이동 + 소비."""
    if seed is not None:
        random.seed(seed)

    agents = []
    for i in range(n_agents):
        profile_name = _assign_profile()
        profile = AGENT_PROFILES[profile_name]
        agent = Agent(id=i, home=APT_COORDS, profile=profile_name)

        for slot in profile["schedule"]:
            for action in slot["actions"]:
                if random.random() >= action["prob"]:
                    continue

                dest = _pick_destination(action["dest_types"], action.get("dist_pref", "mid"))
                if dest is None:
                    continue

                spend = action.get("spend", 0)
                if spend == 0:
                    spend = SPEND_BY_DEST.get(dest["dest_type"], 0)

                agent.log.append({
                    "motivation": action["name"],
                    "time": slot["time"],
                    "slot": slot["slot"],
                    "dest_name": dest["name"],
                    "dest_type": dest["dest_type"],
                    "dest_coords": dest["coords"][-1] if dest["coords"] else APT_COORDS,
                    "road_path": dest["coords"],
                    "walk_min": dest["walk_min"],
                    "walk_sec": dest["walk_sec"],
                    "crossings": dest["crossings"],
                    "spend": spend,
                    "is_chain": False,
                })

                # 연쇄 이동
                chain = _try_chain(dest["dest_type"], profile["chain_prob"])
                if chain:
                    cd = chain["dest"]
                    agent.log.append({
                        "motivation": f"→ {cd['dest_type']}",
                        "time": slot["time"],
                        "slot": slot["slot"],
                        "dest_name": cd["name"],
                        "dest_type": cd["dest_type"],
                        "dest_coords": cd["coords"][-1] if cd["coords"] else APT_COORDS,
                        "road_path": cd["coords"],
                        "walk_min": cd["walk_min"],
                        "walk_sec": cd["walk_sec"],
                        "crossings": cd["crossings"],
                        "spend": chain["spend"],
                        "is_chain": True,
                    })

        agents.append(agent)

    return agents


def agents_to_df(agents: list[Agent]) -> pd.DataFrame:
    rows = []
    for agent in agents:
        for log in agent.log:
            rows.append({
                "agent_id": agent.id,
                "유형": agent.profile,
                "시간": log.get("time", ""),
                "시간대": log.get("slot", ""),
                "동기": log.get("motivation", ""),
                "목적지": log.get("dest_name", ""),
                "목적지유형": log.get("dest_type", ""),
                "lat": log["dest_coords"][0],
                "lon": log["dest_coords"][1],
                "도보(분)": log["walk_min"],
                "횡단보도": log["crossings"],
                "소비(원)": log.get("spend", 0),
                "연쇄": log.get("is_chain", False),
            })
    return pd.DataFrame(rows)


def spending_summary(df: pd.DataFrame) -> dict:
    """소비 요약 통계."""
    if df.empty:
        return {}
    return {
        "총소비": int(df["소비(원)"].sum()),
        "건당평균": int(df["소비(원)"].mean()),
        "외출자수": df["agent_id"].nunique(),
        "총이동": len(df),
        "연쇄이동": int(df["연쇄"].sum()),
        "유형별소비": df.groupby("목적지유형")["소비(원)"].sum().sort_values(ascending=False).to_dict(),
        "시간대별소비": df.groupby("시간대")["소비(원)"].sum().to_dict(),
        "프로파일별소비": df.groupby("유형")["소비(원)"].sum().sort_values(ascending=False).to_dict(),
    }


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

    print("\n프로파일 분포:")
    profile_counts = Counter(a.profile for a in agents)
    for p, c in profile_counts.most_common():
        print(f"  {p}: {c}명")

    print("\n시간대별:")
    print(df.groupby("시간대")["agent_id"].count().to_string())

    print("\n동기별:")
    print(df["동기"].value_counts().to_string())

    print("\n연쇄 이동:", df["연쇄"].sum(), "건")

    summary = spending_summary(df)
    print(f"\n총 소비: {summary['총소비']:,}원")
    print(f"건당 평균: {summary['건당평균']:,}원")
    print("\n프로파일별 소비:")
    for p, s in summary["프로파일별소비"].items():
        print(f"  {p}: {s:,}원")
    print("\n시간대별 소비:")
    for t, s in summary["시간대별소비"].items():
        print(f"  {t}: {s:,}원")
