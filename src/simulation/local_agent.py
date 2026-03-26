"""에이전트 시뮬레이션 — 다중 지역 지원 (v3).

대치동: 아파트 주민이 나가는 모델 (단일 출발점)
영등포역: 여러 곳에서 사람이 들어오는 상업지구 모델 (다중 출발점)
"""

from __future__ import annotations

import json
import math
import random
import heapq
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.simulation.sidewalk import (
    build_network, build_daechi_network, _distance_m,
    AreaConfig, DAECHI_CONFIG, YEONGDEUNGPO_CONFIG, _DATA_ROOT,
)


# ── 보정 데이터 로드 ──

def _load_calibration_data():
    """보정 데이터 로드 (없으면 None)."""
    try:
        from src.simulation.calibration import load_calibration
        return load_calibration()
    except Exception:
        return None


_CALIBRATION = _load_calibration_data()


# ══════════════════════════════════════════════════════════════
#  대치동 프로파일 (기존)
# ══════════════════════════════════════════════════════════════

DAECHI_PROFILES: dict[str, dict] = {
    "직장인": {
        "prob": 0.14,
        "origins": {"대치_주거": 1.0},
        "schedule": [
            {"time": "07:00", "slot": "이른아침", "actions": [
                {"name": "출근", "prob": 0.90, "dest_types": None, "dist_pref": "far", "spend": 0},
                {"name": "출근 전 커피", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.50, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "장보기", "prob": 0.15, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "약국 방문", "prob": 0.06, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "20:00", "slot": "밤", "actions": [
                {"name": "산책/운동", "prob": 0.10, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
                {"name": "친구 약속", "prob": 0.08, "dest_types": ["음식점"], "dist_pref": "far", "spend": 0},
            ]},
        ],
        "chain_prob": 0.15,
    },
    "맞벌이": {
        "prob": 0.08,
        "origins": {"대치_주거": 1.0},
        "schedule": [
            {"time": "07:30", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.60, "dest_types": ["학원", "학교", "어린이집/복지"], "dist_pref": "mid", "spend": 0},
                {"name": "출근", "prob": 0.85, "dest_types": None, "dist_pref": "far", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.40, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "17:00", "slot": "오후", "actions": [
                {"name": "학원 픽업", "prob": 0.50, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "19:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
                {"name": "장보기", "prob": 0.20, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "near", "spend": 0},
                {"name": "약국 방문", "prob": 0.07, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.25,
    },
    "주부/주부": {
        "prob": 0.06,
        "origins": {"대치_주거": 1.0},
        "schedule": [
            {"time": "08:00", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.50, "dest_types": ["학원", "학교", "어린이집/복지"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "10:00", "slot": "오전", "actions": [
                {"name": "장보기", "prob": 0.35, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "동네 볼일", "prob": 0.20, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 0},
                {"name": "병원/약국", "prob": 0.08, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "학원 픽업", "prob": 0.45, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
                {"name": "산책/운동", "prob": 0.15, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.30,
    },
    "학생": {
        "prob": 0.06,
        "origins": {"대치_주거": 1.0},
        "schedule": [
            {"time": "07:30", "slot": "이른아침", "actions": [
                {"name": "등원/등교", "prob": 0.85, "dest_types": ["학교"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "등원/등교", "prob": 0.70, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.15, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "20:00", "slot": "밤", "actions": [
                {"name": "산책/운동", "prob": 0.10, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.20,
    },
    "은퇴자": {
        "prob": 0.06,
        "origins": {"대치_주거": 1.0},
        "schedule": [
            {"time": "06:00", "slot": "이른아침", "actions": [
                {"name": "산책/운동", "prob": 0.40, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "09:00", "slot": "오전", "actions": [
                {"name": "병원/약국", "prob": 0.15, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
                {"name": "동네 볼일", "prob": 0.15, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 0},
                {"name": "종교 활동", "prob": 0.08, "dest_types": ["종교시설"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "장보기", "prob": 0.20, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "산책/운동", "prob": 0.15, "dest_types": ["운동시설", "공원"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.10, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.10,
    },
    # ── 외부 유입 프로파일 (학원가 + 직장인 + 방문객) ──
    "학원학생(외부)": {
        "prob": 0.30,
        "origins": {"대치역": 0.35, "한티역": 0.25, "학여울역": 0.20, "선릉역": 0.10, "도곡역": 0.10},
        "schedule": [
            {"time": "09:00", "slot": "오전", "actions": [
                {"name": "등원/등교", "prob": 0.40, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
                {"name": "출근 전 커피", "prob": 0.15, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.65, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
                {"name": "장보기", "prob": 0.10, "dest_types": ["식료품점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "등원/등교", "prob": 0.60, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
                {"name": "장보기", "prob": 0.08, "dest_types": ["식료품점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.50, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "21:00", "slot": "밤", "actions": [
                {"name": "간단 식사", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.20,
    },
    "외부직장인": {
        "prob": 0.18,
        "origins": {"대치역": 0.25, "한티역": 0.20, "선릉역": 0.30, "도곡역": 0.15, "학여울역": 0.10},
        "schedule": [
            {"time": "08:00", "slot": "이른아침", "actions": [
                {"name": "출근 전 커피", "prob": 0.35, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.75, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "약국 방문", "prob": 0.05, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "14:00", "slot": "오후", "actions": [
                {"name": "출근 전 커피", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "퇴근 후 쇼핑", "prob": 0.15, "dest_types": ["상점", "식료품점"], "dist_pref": "near", "spend": 0},
                {"name": "약국 방문", "prob": 0.06, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "19:00", "slot": "저녁", "actions": [
                {"name": "약속/회식", "prob": 0.15, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.15,
    },
    "방문객(학부모등)": {
        "prob": 0.12,
        "origins": {"대치역": 0.30, "한티역": 0.25, "학여울역": 0.15, "도곡역": 0.15, "선릉역": 0.15},
        "schedule": [
            {"time": "10:00", "slot": "오전", "actions": [
                {"name": "쇼핑", "prob": 0.35, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "병원/약국", "prob": 0.12, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
                {"name": "동네 볼일", "prob": 0.10, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.50, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "학원 픽업", "prob": 0.40, "dest_types": ["학원"], "dist_pref": "mid", "spend": 0},
                {"name": "쇼핑", "prob": 0.20, "dest_types": ["상점", "식료품점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "장보기", "prob": 0.15, "dest_types": ["식료품점", "상점"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.25,
    },
}

# ══════════════════════════════════════════════════════════════
#  영등포역 프로파일
# ══════════════════════════════════════════════════════════════

YEONGDEUNGPO_PROFILES: dict[str, dict] = {
    "환승객": {
        "prob": 0.20,
        "origins": {"영등포역": 0.70, "영등포시장역": 0.20, "신길역": 0.10},
        "schedule": [
            {"time": "08:00", "slot": "이른아침", "actions": [
                {"name": "커피/간식", "prob": 0.45, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
                {"name": "약국 방문", "prob": 0.08, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
                {"name": "쇼핑", "prob": 0.20, "dest_types": ["상점", "식료품점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "간단 식사", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
                {"name": "쇼핑", "prob": 0.15, "dest_types": ["상점", "식료품점"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.10,
    },
    "쇼핑객": {
        "prob": 0.25,
        "origins": {"영등포역": 0.45, "영등포시장역": 0.20, "영등포동_주거": 0.25, "신길역": 0.10},
        "schedule": [
            {"time": "10:00", "slot": "오전", "actions": [
                {"name": "쇼핑", "prob": 0.60, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "약국 방문", "prob": 0.10, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.45, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "쇼핑", "prob": 0.25, "dest_types": ["상점", "식료품점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "14:00", "slot": "오후", "actions": [
                {"name": "쇼핑", "prob": 0.50, "dest_types": ["상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "생활서비스", "prob": 0.10, "dest_types": ["생활서비스"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.25, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "쇼핑", "prob": 0.20, "dest_types": ["상점", "식료품점"], "dist_pref": "near", "spend": 0},
            ]},
        ],
        "chain_prob": 0.30,
    },
    "직장인(점심)": {
        "prob": 0.20,
        "origins": {"영등포_업무": 0.60, "영등포역": 0.30, "영등포시장역": 0.10},
        "schedule": [
            {"time": "08:00", "slot": "이른아침", "actions": [
                {"name": "출근 커피", "prob": 0.35, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.70, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "약국 방문", "prob": 0.06, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
                {"name": "쇼핑", "prob": 0.15, "dest_types": ["상점", "식료품점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "퇴근 후 식사", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
                {"name": "퇴근 후 쇼핑", "prob": 0.25, "dest_types": ["상점", "식료품점", "대형상가"], "dist_pref": "near", "spend": 0},
                {"name": "병원/약국", "prob": 0.08, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "19:00", "slot": "저녁", "actions": [
                {"name": "약속/회식", "prob": 0.12, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.15,
    },
    "주민": {
        "prob": 0.20,
        "origins": {"영등포동_주거": 0.70, "영등포시장역": 0.15, "신길역": 0.15},
        "schedule": [
            {"time": "09:00", "slot": "오전", "actions": [
                {"name": "장보기", "prob": 0.35, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "mid", "spend": 0},
                {"name": "병원/약국", "prob": 0.18, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
                {"name": "동네 볼일", "prob": 0.15, "dest_types": ["생활서비스", "기타"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "점심 외식", "prob": 0.30, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "산책/운동", "prob": 0.15, "dest_types": ["운동시설", "공원"], "dist_pref": "mid", "spend": 0},
                {"name": "장보기", "prob": 0.20, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "near", "spend": 0},
                {"name": "약국 방문", "prob": 0.08, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "18:00", "slot": "저녁", "actions": [
                {"name": "저녁 외식", "prob": 0.20, "dest_types": ["음식점"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.25,
    },
    "시장방문객": {
        "prob": 0.15,
        "origins": {"영등포역": 0.35, "영등포시장역": 0.30, "영등포동_주거": 0.25, "신길역": 0.10},
        "schedule": [
            {"time": "09:00", "slot": "오전", "actions": [
                {"name": "시장 장보기", "prob": 0.60, "dest_types": ["식료품점", "상점"], "dist_pref": "mid", "spend": 0},
                {"name": "약국 방문", "prob": 0.10, "dest_types": ["병원/약국"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "12:00", "slot": "점심", "actions": [
                {"name": "시장 먹거리", "prob": 0.45, "dest_types": ["음식점"], "dist_pref": "near", "spend": 0},
            ]},
            {"time": "15:00", "slot": "오후", "actions": [
                {"name": "추가 장보기", "prob": 0.30, "dest_types": ["식료품점", "상점", "대형상가"], "dist_pref": "mid", "spend": 0},
            ]},
        ],
        "chain_prob": 0.25,
    },
}


# 연쇄 이동: 현재 목적지 유형 → 다음 가능한 유형
CHAIN_RULES: dict[str, list[dict]] = {
    "학원":      [{"dest_types": ["음식점"], "prob": 0.3, "spend": 0}],
    "학교":      [{"dest_types": ["음식점"], "prob": 0.2, "spend": 0}],
    "음식점":    [{"dest_types": ["상점", "식료품점"], "prob": 0.15, "spend": 0},
                  {"dest_types": ["음식점"], "prob": 0.10, "spend": 0}],
    "상점":      [{"dest_types": ["음식점"], "prob": 0.20, "spend": 0}],
    "식료품점":  [{"dest_types": ["음식점"], "prob": 0.15, "spend": 0},
                  {"dest_types": ["병원/약국"], "prob": 0.10, "spend": 0}],
    "병원/약국": [{"dest_types": ["식료품점"], "prob": 0.20, "spend": 0}],
    "운동시설":  [{"dest_types": ["음식점"], "prob": 0.25, "spend": 0}],
    "공원":      [{"dest_types": ["음식점"], "prob": 0.20, "spend": 0}],
    "대형상가":  [{"dest_types": ["음식점"], "prob": 0.25, "spend": 0}],
    "숙박/유흥": [{"dest_types": ["음식점"], "prob": 0.20, "spend": 0}],
}


# ── 실제 매출 데이터 ──

AREA_SALES: dict[str, dict] = {
    "daechi": {
        "annual": 1_202_800_000_000,  # 1조 2,028억원 (대치/은마/도곡 상권 2024년)
        "apt_share": 1.0,              # 다중 출발점 모델: 상권 전체 커버
    },
    "yeongdeungpo": {
        "annual": 628_800_000_000,     # 6,288억원 (영등포역 상권 2024년)
        "apt_share": 1.0,              # 상권 전체 커버
    },
}

# 하위호환
REAL_ANNUAL_SALES: int = AREA_SALES["daechi"]["annual"]

# 업종별 객단가 (기본값)
_SPEND_BY_DEST_DEFAULT: dict[str, int] = {
    "음식점": 15300,
    "학원": 0,
    "학교": 0,
    "상점": 15000,       # 의류/잡화 (실제 매출 반영 상향)
    "식료품점": 10000,   # 슈퍼/편의점/반찬 등
    "대형상가": 30000,
    "병원/약국": 25000,  # 약국+의원 평균 (기존 39700은 과대)
    "생활서비스": 18000,  # 미용실/세탁소 평균 (기존 60900 과대)
    "운동시설": 13000,
    "숙박/유흥": 35000,  # 여관/노래방/PC방
    "기타": 15000,
    "종교시설": 0,
    "공원": 0,
    "어린이집/복지": 0,
}

# 보정 데이터가 있으면 객단가 교체
if _CALIBRATION and _CALIBRATION.get("unit_prices"):
    SPEND_BY_DEST: dict[str, int] = {**_SPEND_BY_DEST_DEFAULT, **_CALIBRATION["unit_prices"]}
else:
    SPEND_BY_DEST: dict[str, int] = _SPEND_BY_DEST_DEFAULT.copy()


@dataclass
class Agent:
    id: int
    home: tuple[float, float]
    profile: str = ""
    origin: str = ""  # 출발점 이름 (다중 출발점)
    log: list[dict] = field(default_factory=list)


# 래미안 대치팰리스 좌표 (하위호환)
APT_COORDS = (37.4945, 127.0625)


# ══════════════════════════════════════════════════════════════
#  Lazy-loaded 지역별 시뮬레이션 데이터
# ══════════════════════════════════════════════════════════════

class _AreaData:
    """한 지역의 네트워크 + 목적지 + 경로를 lazy-load."""

    def __init__(self, config: AreaConfig, profiles: dict[str, dict]):
        self.config = config
        self.profiles = profiles
        self._network = None
        self._buildings = None
        self._destinations = None
        self._origin_dists: dict[str, dict] = {}   # origin → {node: dist}
        self._origin_prevs: dict[str, dict] = {}   # origin → {node: prev}

    @property
    def network(self):
        if self._network is None:
            self._network = build_network(self.config)
        return self._network

    @property
    def buildings(self):
        if self._buildings is None:
            self._buildings = _load_buildings(
                _DATA_ROOT / self.config.buildings_file
            )
        return self._buildings

    @property
    def destinations(self):
        if self._destinations is None:
            self._init_destinations()
        return self._destinations

    def _dijkstra_from(self, start_id: str):
        """start_id에서 전체 노드까지 최단 거리."""
        if start_id in self._origin_dists:
            return self._origin_dists[start_id], self._origin_prevs[start_id]

        dist = {start_id: 0.0}
        prev = {start_id: None}
        heap = [(0.0, start_id)]
        while heap:
            d, nid = heapq.heappop(heap)
            if d > dist.get(nid, float("inf")):
                continue
            for edge in self.network.edges.get(nid, []):
                nd = d + edge.walk_sec
                if nd < dist.get(edge.to_id, float("inf")):
                    dist[edge.to_id] = nd
                    prev[edge.to_id] = nid
                    heapq.heappush(heap, (nd, edge.to_id))

        self._origin_dists[start_id] = dist
        self._origin_prevs[start_id] = prev
        return dist, prev

    def _reconstruct_path(self, origin_id: str, end_id: str) -> list[str]:
        prev = self._origin_prevs.get(origin_id, {})
        path = []
        cur = end_id
        while cur is not None:
            path.append(cur)
            cur = prev.get(cur)
        return list(reversed(path))

    def get_origin_ids(self) -> list[str]:
        """사용 가능한 출발점 노드 ID 목록."""
        if self.config.apt_node:
            return ["apt"]
        ids = []
        for name in self.config.origin_points:
            stn_id = f"subway_{name}"
            if stn_id in self.network.nodes:
                ids.append(stn_id)
            else:
                oid = f"origin_{name}"
                if oid in self.network.nodes:
                    ids.append(oid)
        return ids

    def resolve_origin_id(self, origin_name: str) -> str:
        """출발점 이름 → 네트워크 노드 ID."""
        if origin_name == "apt":
            return "apt"
        stn_id = f"subway_{origin_name}"
        if stn_id in self.network.nodes:
            return stn_id
        return f"origin_{origin_name}"

    def _init_destinations(self):
        """모든 출발점에서 Dijkstra 실행 후 목적지 빌드."""
        net = self.network

        # 모든 출발점에서 Dijkstra
        origin_ids = self.get_origin_ids()
        for oid in origin_ids:
            self._dijkstra_from(oid)

        # 대표 출발점 (첫 번째)
        primary_id = origin_ids[0] if origin_ids else "apt"
        primary_dist = self._origin_dists.get(primary_id, {})
        primary_prev = self._origin_prevs.get(primary_id, {})

        skip = {"apt"} | {nid for nid in net.nodes if nid.startswith("subway_") or nid.startswith("origin_")}

        dests = []
        for bld in self.buildings:
            nearest = net.nearest_node(bld["lat"], bld["lon"], exclude=skip)
            if not nearest or nearest not in primary_dist:
                continue

            dist_sec = primary_dist[nearest]
            if dist_sec < 20 or dist_sec > 2400:
                continue

            path_ids = self._reconstruct_path(primary_id, nearest)
            coords = net.path_to_coords(path_ids)
            crossings = sum(1 for n in path_ids if net.nodes.get(n) and net.nodes[n].is_crosswalk)

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

        # 노출도 계산
        node_traffic: dict[str, int] = {}
        for d in dests:
            path = self._reconstruct_path(primary_id, d["node_id"])
            for nid in path:
                node_traffic[nid] = node_traffic.get(nid, 0) + 1

        for d in dests:
            nid = d["node_id"]
            exposure = node_traffic.get(nid, 0)
            for edge in net.edges.get(nid, []):
                exposure += node_traffic.get(edge.to_id, 0) * 0.5
            d["exposure"] = exposure

        max_exp = max((d["exposure"] for d in dests), default=1)
        for d in dests:
            d["exposure_norm"] = d["exposure"] / max_exp if max_exp > 0 else 0

        self._destinations = dests

    def get_dest_for_origin(self, origin_id: str, bld: dict) -> dict | None:
        """특정 출발점에서 건물까지의 경로 정보."""
        dist_map = self._origin_dists.get(origin_id, {})
        nearest = bld["node_id"]
        if nearest not in dist_map:
            return None

        dist_sec = dist_map[nearest]
        if dist_sec < 20 or dist_sec > 2400:
            return None

        path_ids = self._reconstruct_path(origin_id, nearest)
        coords = self.network.path_to_coords(path_ids)
        crossings = sum(1 for n in path_ids if self.network.nodes.get(n) and self.network.nodes[n].is_crosswalk)

        return {
            **bld,
            "coords": coords,
            "walk_sec": dist_sec,
            "walk_min": max(1, round(dist_sec / 60)),
            "crossings": crossings,
        }


# 소분류(indsSclsNm) → dest_type 매핑 (약국/의료 관련)
_SUB_CAT_PHARMACY = {"약국", "의약품소매점", "건강보조식품 소매업", "의료기기 소매업"}
_SUB_CAT_FOOD = {
    "슈퍼마켓", "편의점", "반찬/식료품 소매업", "채소/과일 소매업",
    "정육점", "건어물/젓갈 소매업", "수산물 소매업", "주류 소매업",
    "아이스크림 할인점",
}
_SUB_CAT_LODGING = {"여관/모텔", "펜션", "기숙사/고시원", "그 외 기타 숙박업"}


def _classify_retail(sub_cats: dict) -> str:
    """소매 건물의 소분류 기반 세분화."""
    # 약국이 포함된 건물 → 병원/약국
    if sub_cats.keys() & _SUB_CAT_PHARMACY:
        return "병원/약국"
    # 식료품 위주 → 식료품점
    food_count = sum(sub_cats.get(k, 0) for k in _SUB_CAT_FOOD if k in sub_cats)
    total = sum(sub_cats.values())
    if total > 0 and food_count / total > 0.5:
        return "식료품점"
    return "상점"


def _load_buildings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        buildings = json.load(f)

    results = []
    for b in buildings:
        lat, lon = b.get("lat", 0), b.get("lon", 0)
        if not lat or not lon:
            continue

        cats = b.get("categories", {})
        sub_cats = b.get("sub_categories", {})
        btype = b.get("bld_type", "")

        # 숙박 체크 (sub_categories 우선)
        if sub_cats.keys() & _SUB_CAT_LODGING:
            dest_type = "숙박/유흥"
        elif "숙박" in cats:
            dest_type = "숙박/유흥"
        elif "음식" in cats:
            dest_type = "음식점"
        elif "교육연구시설" in cats:
            dest_type = "학교"
        elif "교육" in cats and cats.get("교육", 0) >= 3:
            dest_type = "학원"
        elif "소매" in cats:
            if sub_cats:
                dest_type = _classify_retail(sub_cats)
            else:
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


# ── 지역별 데이터 캐시 (lazy) ──

_area_data_cache: dict[str, _AreaData] = {}


def _get_area_data(area: str) -> _AreaData:
    if area not in _area_data_cache:
        if area == "daechi":
            _area_data_cache[area] = _AreaData(DAECHI_CONFIG, DAECHI_PROFILES)
        elif area == "yeongdeungpo":
            _area_data_cache[area] = _AreaData(YEONGDEUNGPO_CONFIG, YEONGDEUNGPO_PROFILES)
        else:
            raise ValueError(f"Unknown area: {area}")
    return _area_data_cache[area]


# 하위호환: module-level 전역 (대치동 데이터는 첫 접근 시 로드)
def _get_daechi():
    return _get_area_data("daechi")


class _LazyProxy:
    """Module-level 전역변수를 lazy-load하기 위한 프록시."""
    def __init__(self, attr):
        self._attr = attr
        self._resolved = False
        self._value = None

    def _resolve(self):
        if not self._resolved:
            ad = _get_daechi()
            if self._attr == "network":
                self._value = ad.network
            elif self._attr == "destinations":
                self._value = ad.destinations
            self._resolved = True
        return self._value


# 대치동 전역 (하위호환)  — 실제 접근은 lazy
_network_proxy = _LazyProxy("network")
_destinations_proxy = _LazyProxy("destinations")


class _NetworkAccessor:
    """NETWORK 전역변수 프록시."""
    def __getattr__(self, name):
        return getattr(_network_proxy._resolve(), name)


NETWORK = _NetworkAccessor()
DESTINATIONS = []  # 실제론 simulate 내부에서 area_data.destinations 사용


def _ensure_legacy_globals():
    """하위호환 전역변수를 실제 값으로 채움."""
    global DESTINATIONS, NETWORK
    ad = _get_daechi()
    NETWORK = ad.network
    DESTINATIONS = ad.destinations


# ── 체류 시간 ──

STAY_MINUTES: dict[str, tuple[int, int]] = {
    "출근":          (420, 540),
    "출근 전 커피":  (5, 15),
    "등원/등교":     (180, 360),
    "점심 외식":     (30, 60),
    "산책/운동":     (20, 60),
    "장보기":        (15, 45),
    "학원 픽업":     (5, 15),
    "병원/약국":     (20, 60),
    "저녁 외식":     (40, 90),
    "동네 볼일":     (10, 30),
    "친구 약속":     (60, 150),
    "종교 활동":     (40, 90),
    # 영등포 추가
    "커피/간식":     (5, 20),
    "쇼핑":          (30, 90),
    "생활서비스":    (15, 45),
    "간단 식사":     (20, 40),
    "출근 커피":     (5, 15),
    "퇴근 후 식사":  (30, 60),
    "퇴근 후 쇼핑":  (15, 45),
    "약속/회식":     (60, 120),
    "시장 장보기":   (20, 60),
    "시장 먹거리":   (15, 40),
    "추가 장보기":   (15, 40),
    "약국 방문":     (5, 15),
}


# ── 시뮬레이션 ──

def _pick_destination(
    destinations: list[dict],
    dest_types: list[str] | None,
    dist_pref: str,
) -> dict | None:
    """동기에 맞는 건물 목적지 선택."""
    if dest_types:
        pool = [d for d in destinations if d["dest_type"] in dest_types]
    else:
        pool = destinations

    if not pool:
        return None

    weights = []
    for d in pool:
        sec = d["walk_sec"]
        if dist_pref == "near":
            w = math.exp(-sec / 200.0)
        elif dist_pref == "mid":
            w = math.exp(-sec / 400.0)
        else:
            w = 1.0 - math.exp(-sec / 400.0)

        w *= max(1, min(d["store_count"], 20)) ** 0.5
        exposure_boost = 1.0 + d.get("exposure_norm", 0) * 1.5
        w *= exposure_boost
        weights.append(max(w, 0.001))

    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0
    for d, w in zip(pool, weights):
        cumulative += w
        if r <= cumulative:
            return d
    return pool[-1]


def _assign_profile(profiles: dict[str, dict]) -> str:
    r = random.random()
    cumulative = 0.0
    for name, profile in profiles.items():
        cumulative += profile["prob"]
        if r <= cumulative:
            return name
    return list(profiles.keys())[-1]


def _assign_origin(profile: dict, config: AreaConfig) -> str:
    """에이전트의 출발점 배정."""
    origins = profile.get("origins")
    if not origins:
        return "apt"

    r = random.random()
    cumulative = 0.0
    for name, prob in origins.items():
        cumulative += prob
        if r <= cumulative:
            return name
    return list(origins.keys())[-1]


def _try_chain(
    destinations: list[dict],
    current_dest_type: str,
    chain_prob: float,
) -> dict | None:
    rules = CHAIN_RULES.get(current_dest_type, [])
    if not rules or random.random() > chain_prob:
        return None

    for rule in rules:
        if random.random() < rule["prob"]:
            dest = _pick_destination(destinations, rule["dest_types"], "near")
            if dest:
                return {"dest": dest, "spend": rule["spend"]}
    return None


def _time_to_min(time_str: str) -> int:
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def simulate(
    n_agents: int = 100,
    seed: int | None = 42,
    area: str = "daechi",
) -> list[Agent]:
    """시뮬레이션 실행.

    Args:
        n_agents: 에이전트 수
        seed: 랜덤 시드
        area: "daechi" 또는 "yeongdeungpo"
    """
    if seed is not None:
        random.seed(seed)

    area_data = _get_area_data(area)
    config = area_data.config
    profiles = area_data.profiles
    destinations = area_data.destinations

    # 다중 출발점인 경우 각 출발점별 목적지 캐시
    is_multi_origin = bool(config.origin_points)
    home_coords = config.center

    agents = []
    for i in range(n_agents):
        profile_name = _assign_profile(profiles)
        profile = profiles[profile_name]
        origin_name = _assign_origin(profile, config)
        origin_id = area_data.resolve_origin_id(origin_name)

        # 출발점 좌표
        if origin_id in area_data.network.nodes:
            node = area_data.network.nodes[origin_id]
            home = (node.lat, node.lon)
        else:
            home = home_coords

        agent = Agent(id=i, home=home, profile=profile_name, origin=origin_name)

        # 해당 출발점에서 Dijkstra 실행 (캐시됨)
        area_data._dijkstra_from(origin_id)
        dist_map = area_data._origin_dists.get(origin_id, {})

        # 이 출발점에서 도달 가능한 목적지 목록 빌드
        origin_dests = []
        for d in destinations:
            nid = d["node_id"]
            if nid in dist_map:
                sec = dist_map[nid]
                if 20 <= sec <= 2400:
                    # 출발점별 경로 정보로 덮어쓰기
                    path_ids = area_data._reconstruct_path(origin_id, nid)
                    coords = area_data.network.path_to_coords(path_ids)
                    crossings = sum(
                        1 for n in path_ids
                        if area_data.network.nodes.get(n) and area_data.network.nodes[n].is_crosswalk
                    )
                    origin_dests.append({
                        **d,
                        "coords": coords,
                        "walk_sec": sec,
                        "walk_min": max(1, round(sec / 60)),
                        "crossings": crossings,
                    })

        if not origin_dests:
            origin_dests = destinations  # fallback

        next_available_min = 0

        for slot in profile["schedule"]:
            base_min = _time_to_min(slot["time"])

            for action in slot["actions"]:
                if random.random() >= action["prob"]:
                    continue

                dest = _pick_destination(origin_dests, action["dest_types"], action.get("dist_pref", "mid"))
                if dest is None:
                    continue

                jitter = random.randint(-10, 20)
                depart_min = max(base_min + jitter, next_available_min)

                stay_range = STAY_MINUTES.get(action["name"], (15, 45))
                stay_min = random.randint(stay_range[0], stay_range[1])

                walk_min = dest["walk_min"]
                return_min = depart_min + walk_min + stay_min + walk_min

                spend = action.get("spend", 0)
                if spend == 0:
                    spend = SPEND_BY_DEST.get(dest["dest_type"], 0)
                    # 시간대별 객단가 보정 (저녁/회식은 더 비쌈)
                    if spend > 0 and action["name"] in ("저녁 외식", "퇴근 후 식사"):
                        spend = int(spend * 1.8)
                    elif spend > 0 and action["name"] in ("약속/회식", "친구 약속"):
                        spend = int(spend * 2.5)

                agent.log.append({
                    "motivation": action["name"],
                    "time": slot["time"],
                    "slot": slot["slot"],
                    "dest_name": dest["name"],
                    "dest_type": dest["dest_type"],
                    "dest_coords": dest["coords"][-1] if dest["coords"] else home,
                    "road_path": dest["coords"],
                    "walk_min": walk_min,
                    "walk_sec": dest["walk_sec"],
                    "crossings": dest["crossings"],
                    "spend": spend,
                    "is_chain": False,
                    "depart_min": depart_min,
                    "stay_min": stay_min,
                    "return_min": return_min,
                    "origin": origin_name,
                })

                next_available_min = return_min

                chain = _try_chain(origin_dests, dest["dest_type"], profile["chain_prob"])
                if chain:
                    cd = chain["dest"]
                    chain_depart = depart_min + walk_min + stay_min
                    chain_stay = random.randint(10, 30)
                    chain_return = chain_depart + cd["walk_min"] + chain_stay + cd["walk_min"]

                    agent.log.append({
                        "motivation": f"→ {cd['dest_type']}",
                        "time": slot["time"],
                        "slot": slot["slot"],
                        "dest_name": cd["name"],
                        "dest_type": cd["dest_type"],
                        "dest_coords": cd["coords"][-1] if cd["coords"] else home,
                        "road_path": cd["coords"],
                        "walk_min": cd["walk_min"],
                        "walk_sec": cd["walk_sec"],
                        "crossings": cd["crossings"],
                        "spend": chain["spend"],
                        "is_chain": True,
                        "depart_min": chain_depart,
                        "stay_min": chain_stay,
                        "return_min": chain_return,
                        "origin": origin_name,
                    })

                    next_available_min = chain_return

        agents.append(agent)

    return agents


def agents_to_df(agents: list[Agent]) -> pd.DataFrame:
    rows = []
    for agent in agents:
        for log in agent.log:
            rows.append({
                "agent_id": agent.id,
                "유형": agent.profile,
                "출발점": log.get("origin", agent.origin),
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
                "출발(분)": log.get("depart_min", 0),
                "체류(분)": log.get("stay_min", 0),
                "귀가(분)": log.get("return_min", 0),
            })
    return pd.DataFrame(rows)


def spending_summary(df: pd.DataFrame) -> dict:
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


def estimate_revenue(
    df: pd.DataFrame,
    n_agents: int,
    area: str = "daechi",
) -> pd.DataFrame:
    """시뮬레이션 방문 비율 → 실제 매출 비례 배분."""
    if df.empty:
        return pd.DataFrame()

    sales_info = AREA_SALES.get(area, AREA_SALES["daechi"])

    visit_counts = df.groupby("목적지").agg(
        방문=("agent_id", "count"),
        유형=("목적지유형", "first"),
        lat=("lat", "first"),
        lon=("lon", "first"),
    ).reset_index()

    total_visits = visit_counts["방문"].sum()
    visit_counts["방문비율"] = visit_counts["방문"] / total_visits

    apt_share = sales_info["apt_share"]
    allocatable = sales_info["annual"] * apt_share

    visit_counts["추정연매출"] = (visit_counts["방문비율"] * allocatable).astype(int)
    visit_counts["추정월매출"] = (visit_counts["추정연매출"] / 12).astype(int)

    return visit_counts.sort_values("추정연매출", ascending=False)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    area = sys.argv[1] if len(sys.argv) > 1 else "daechi"
    print(f"=== {area} 시뮬레이션 ===\n")

    area_data = _get_area_data(area)
    dests = area_data.destinations
    print(f"건물 목적지: {len(dests)}개")
    from collections import Counter
    tc = Counter(d["dest_type"] for d in dests)
    for t, c in tc.most_common():
        print(f"  {t}: {c}개")

    agents = simulate(n_agents=100, seed=42, area=area)
    df = agents_to_df(agents)

    print(f"\n에이전트: {len(agents)}명, 외출: {df['agent_id'].nunique()}명, 이동: {len(df)}건")

    print("\n프로파일 분포:")
    profile_counts = Counter(a.profile for a in agents)
    for p, c in profile_counts.most_common():
        print(f"  {p}: {c}명")

    if "출발점" in df.columns:
        print("\n출발점 분포:")
        print(df.groupby("출발점")["agent_id"].nunique().to_string())

    print("\n시간대별:")
    print(df.groupby("시간대")["agent_id"].count().to_string())

    print("\n동기별:")
    print(df["동기"].value_counts().to_string())

    print(f"\n연쇄 이동: {df['연쇄'].sum()}건")

    summary = spending_summary(df)
    print(f"\n총 소비: {summary['총소비']:,}원")
    print(f"건당 평균: {summary['건당평균']:,}원")
    print("\n프로파일별 소비:")
    for p, s in summary["프로파일별소비"].items():
        print(f"  {p}: {s:,}원")

    rev = estimate_revenue(df, 100, area=area)
    if not rev.empty:
        print(f"\n추정 매출 Top 10:")
        for _, r in rev.head(10).iterrows():
            print(f"  {r['목적지']} ({r['유형']}): 연 {r['추정연매출']:,}원")
