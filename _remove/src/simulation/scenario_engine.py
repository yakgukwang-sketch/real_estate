"""What-if 시나리오 엔진."""

import logging
from collections import deque
from copy import deepcopy
from pathlib import Path

import pandas as pd

from src.simulation.flow_model import FlowModel

logger = logging.getLogger(__name__)

SUBWAY_LINES: dict[str, list[str]] = {
    "1호선": ["서울역", "시청", "종각", "종로3가", "종로5가", "동대문", "신설동"],
    "2호선": ["시청", "을지로입구", "을지로3가", "을지로4가", "동대문역사문화공원",
              "신설동", "성수", "건대입구", "잠실", "삼성", "선릉", "역삼", "강남",
              "교대", "서초", "방배", "사당", "신림", "구로디지털단지", "홍대입구",
              "합정", "이대", "신촌", "아현", "충정로"],
    "3호선": ["구파발", "연신내", "불광", "독바위", "충정로", "을지로3가",
              "종로3가", "동대문", "압구정", "신사", "잠실"],
    "4호선": ["당고개", "수락산", "마들", "노원", "상계", "미아사거리", "미아",
              "길음", "혜화", "동대문", "동대문역사문화공원", "명동", "회현",
              "서울역", "숙대입구", "삼각지", "이수", "사당"],
    "5호선": ["목동", "오목교", "양천구청", "영등포구청", "여의도", "여의나루",
              "공덕", "마포", "을지로4가", "종로3가", "왕십리"],
    "6호선": ["디지털미디어시티", "합정", "이태원", "녹사평", "삼각지", "공덕"],
    "7호선": ["노원", "미아", "건대입구", "학동", "강남구청", "청담", "논현"],
    "9호선": ["여의도", "선릉", "삼성중앙", "봉은사"],
    "경의중앙선": ["서울역", "공덕", "홍대입구", "디지털미디어시티", "수색",
                  "왕십리", "한양대", "뚝섬", "성수"],
}


def build_subway_network_graph() -> dict[str, dict[str, int]]:
    """지하철 네트워크 그래프 구축 (역 간 최소 환승 횟수 계산).

    Returns:
        {역명: {역명: 최소환승횟수, ...}, ...}
    """
    from src.processors.geo_processor import SUBWAY_STATION_COORDS

    # Build adjacency: edges between consecutive stations on same line
    # Edge weight: 0 if same line, track which lines each station belongs to
    station_lines: dict[str, set[str]] = {}
    adj: dict[str, set[str]] = {}

    for line, stations in SUBWAY_LINES.items():
        for i, st in enumerate(stations):
            if st not in SUBWAY_STATION_COORDS:
                continue
            station_lines.setdefault(st, set()).add(line)
            adj.setdefault(st, set())
            # connect to adjacent stations on same line
            if i > 0 and stations[i - 1] in SUBWAY_STATION_COORDS:
                adj[st].add(stations[i - 1])
                adj.setdefault(stations[i - 1], set()).add(st)

    # BFS from each station to compute min transfers
    all_stations = list(adj.keys())
    result: dict[str, dict[str, int]] = {}

    for start in all_stations:
        # BFS state: (station, current_lines, transfers)
        # We track which lines we're "on" to count transfers
        distances: dict[str, int] = {start: 0}
        # Use BFS with transfer counting
        # State: (station, set_of_lines_at_station)
        queue = deque()
        queue.append((start, station_lines.get(start, set()), 0))
        visited: dict[str, int] = {start: 0}

        while queue:
            current, cur_lines, transfers = queue.popleft()
            for neighbor in adj.get(current, set()):
                neighbor_lines = station_lines.get(neighbor, set())
                # Check if we need a transfer
                shared = cur_lines & neighbor_lines
                if shared:
                    new_transfers = transfers
                    new_lines = shared  # stay on shared lines
                else:
                    new_transfers = transfers + 1
                    new_lines = neighbor_lines

                if neighbor not in visited or new_transfers < visited[neighbor]:
                    visited[neighbor] = new_transfers
                    distances[neighbor] = new_transfers
                    queue.append((neighbor, new_lines, new_transfers))

        result[start] = distances

    return result


def build_adjacency_graph(geo_dir: Path | None = None) -> dict[str, list[str]]:
    """GeoJSON에서 행정동 인접성 그래프 구축 (공유 경계 기반).

    Returns:
        {행정동코드: [인접 행정동코드, ...]}
    """
    try:
        import geopandas as gpd
        from config.settings import GEO_DIR

        geo_dir = geo_dir or GEO_DIR
        geojson_path = geo_dir / "seoul_dong.geojson"
        if not geojson_path.exists():
            return {}

        gdf = gpd.read_file(geojson_path)
        code_col = "adm_cd"
        if code_col not in gdf.columns:
            return {}

        adjacency: dict[str, list[str]] = {}
        for idx, row in gdf.iterrows():
            code = str(row[code_col])
            neighbors = gdf[gdf.geometry.touches(row.geometry)]
            adjacency[code] = [str(r[code_col]) for _, r in neighbors.iterrows()]

        return adjacency
    except Exception:
        logger.warning("인접성 그래프 구축 실패, 빈 그래프 사용")
        return {}


class ScenarioEngine:
    """What-if 시나리오 시뮬레이션.

    - 신규 지하철역 개통
    - 임대료 변동
    - 인구 변화
    - 복합 시나리오
    """

    def __init__(self, baseline_data: dict[str, pd.DataFrame]):
        """
        Args:
            baseline_data: 기준 데이터 딕셔너리
                - "subway": 지하철 승하차
                - "realestate": 부동산 실거래
                - "population": 생활인구
                - "spending": 추정매출
                - "commercial": 상가업소
        """
        self.baseline = baseline_data
        self.flow_model = FlowModel()
        self._adjacency: dict[str, list[str]] | None = None

    @property
    def adjacency(self) -> dict[str, list[str]]:
        """인접성 그래프 (lazy load)."""
        if self._adjacency is None:
            self._adjacency = build_adjacency_graph()
        return self._adjacency

    def new_station_scenario(
        self,
        station_name: str,
        dong_code: str,
        estimated_daily_passengers: int = 30000,
        use_subway_network: bool = False,
    ) -> dict:
        """신규 지하철역 개통 시나리오.

        Args:
            station_name: 신규역 이름
            dong_code: 해당 행정동코드
            estimated_daily_passengers: 예상 일일 승하차 인원

        Returns:
            before/after 비교 데이터
        """
        result = {
            "scenario": "new_station",
            "station_name": station_name,
            "dong_code": dong_code,
            "before": {},
            "after": {},
            "changes": {},
        }

        # Before 상태
        subway_df = self.baseline.get("subway", pd.DataFrame())
        if not subway_df.empty and "행정동코드" in subway_df.columns:
            dong_before = subway_df[subway_df["행정동코드"] == dong_code]
            result["before"]["일평균_하차"] = (
                dong_before["하차총승객수"].sum() / max(dong_before["날짜"].nunique(), 1)
                if not dong_before.empty else 0
            )
        else:
            result["before"]["일평균_하차"] = 0

        # After: 유동인구 증가
        new_daily = estimated_daily_passengers
        result["after"]["일평균_하차"] = result["before"]["일평균_하차"] + new_daily

        # 영향 추정 (경험적 계수)
        population_increase_pct = min(new_daily / 10000 * 5, 30)  # 최대 30%
        spending_increase_pct = population_increase_pct * 0.8  # 매출은 인구의 80%
        realestate_increase_pct = population_increase_pct * 0.3  # 부동산은 더 느림

        result["changes"] = {
            "유동인구_변화율": round(population_increase_pct, 1),
            "추정매출_변화율": round(spending_increase_pct, 1),
            "부동산가격_변화율": round(realestate_increase_pct, 1),
            "신규업소_예상": int(new_daily / 1000 * 5),
        }

        # 주변 동 영향
        if use_subway_network:
            result["ripple_effects"] = self._estimate_ripple_subway(
                station_name, dong_code, population_increase_pct
            )
        else:
            result["ripple_effects"] = self._estimate_ripple(
                dong_code, population_increase_pct
            )

        return result

    def rent_change_scenario(
        self,
        dong_code: str,
        rent_change_pct: float,
    ) -> dict:
        """임대료 변동 시나리오.

        rent_change_pct > 0: 임대료 상승
        rent_change_pct < 0: 임대료 하락
        """
        result = {
            "scenario": "rent_change",
            "dong_code": dong_code,
            "rent_change_pct": rent_change_pct,
            "changes": {},
        }

        # 임대료 상승 시 업소 이탈, 소비 감소
        if rent_change_pct > 0:
            business_exit_rate = min(rent_change_pct * 0.3, 20)  # 최대 20% 이탈
            spending_change = -rent_change_pct * 0.2
            population_change = -rent_change_pct * 0.1
        else:
            business_exit_rate = rent_change_pct * 0.2  # 음수 = 신규 진입
            spending_change = -rent_change_pct * 0.15
            population_change = -rent_change_pct * 0.05

        result["changes"] = {
            "업소_변화율": round(-business_exit_rate, 1),
            "매출_변화율": round(spending_change, 1),
            "인구_변화율": round(population_change, 1),
        }

        return result

    def population_change_scenario(
        self,
        dong_code: str,
        population_change_pct: float,
    ) -> dict:
        """인구 변화 시나리오 (재개발, 대규모 아파트 입주 등)."""
        result = {
            "scenario": "population_change",
            "dong_code": dong_code,
            "population_change_pct": population_change_pct,
            "changes": {},
        }

        spending_change = population_change_pct * 0.7
        realestate_change = population_change_pct * 0.2
        commercial_change = population_change_pct * 0.4

        result["changes"] = {
            "매출_변화율": round(spending_change, 1),
            "부동산가격_변화율": round(realestate_change, 1),
            "업소수_변화율": round(commercial_change, 1),
        }

        return result

    def _estimate_ripple(
        self, center_dong: str, change_pct: float
    ) -> list[dict]:
        """실제 GeoJSON 인접성 그래프 기반 파급효과 추정.

        1차 인접동: 변화율 × 0.5
        2차 인접동: 변화율 × 0.2
        """
        neighbors = self.adjacency.get(center_dong, [])

        if not neighbors:
            # 인접성 그래프가 없으면 OD 행렬 기반 fallback
            return self._estimate_ripple_from_od(center_dong, change_pct)

        results = []
        seen = {center_dong}

        # 1차 인접동
        for dong in neighbors:
            if dong in seen:
                continue
            seen.add(dong)
            results.append({
                "행정동코드": dong,
                "차수": 1,
                "변화율": round(change_pct * 0.5, 1),
            })

        # 2차 인접동
        for dong in neighbors:
            for dong2 in self.adjacency.get(dong, []):
                if dong2 in seen:
                    continue
                seen.add(dong2)
                results.append({
                    "행정동코드": dong2,
                    "차수": 2,
                    "변화율": round(change_pct * 0.2, 1),
                })

        return sorted(results, key=lambda x: abs(x["변화율"]), reverse=True)

    def _estimate_ripple_subway(
        self,
        station_name: str,
        dong_code: str,
        change_pct: float,
    ) -> list[dict]:
        """지하철 네트워크 기반 파급효과 추정.

        감쇠:
        - 같은 노선 (0 환승): 1.0 × 0.9^stops
        - 1회 환승: 0.4 × 0.9^stops
        - 2회+ 환승: 0.15 × 0.9^stops
        """
        from src.processors.geo_processor import SUBWAY_STATION_COORDS

        network = build_subway_network_graph()

        if station_name not in network:
            return self._estimate_ripple(dong_code, change_pct)

        transfer_map = network[station_name]

        # Calculate stops (BFS shortest path length, not transfers)
        # Build simple adjacency for hop counting
        adj: dict[str, set[str]] = {}
        for line, stations in SUBWAY_LINES.items():
            for i, st in enumerate(stations):
                if st not in SUBWAY_STATION_COORDS:
                    continue
                adj.setdefault(st, set())
                if i > 0 and stations[i - 1] in SUBWAY_STATION_COORDS:
                    adj[st].add(stations[i - 1])
                    adj.setdefault(stations[i - 1], set()).add(st)

        # BFS for hop distances
        hop_dist: dict[str, int] = {station_name: 0}
        queue = deque([(station_name, 0)])
        while queue:
            cur, dist = queue.popleft()
            for nb in adj.get(cur, set()):
                if nb not in hop_dist:
                    hop_dist[nb] = dist + 1
                    queue.append((nb, dist + 1))

        # Compute impact per station → per dong
        dong_impact: dict[str, float] = {}
        seen_stations = set()

        for target_station, transfers in transfer_map.items():
            if target_station == station_name:
                continue
            seen_stations.add(target_station)

            stops = hop_dist.get(target_station, 10)

            if transfers == 0:
                decay = 1.0 * (0.9 ** stops)
            elif transfers == 1:
                decay = 0.4 * (0.9 ** stops)
            else:
                decay = 0.15 * (0.9 ** stops)

            impact = change_pct * decay

            # Station → dong mapping (use coordinates)
            coords = SUBWAY_STATION_COORDS.get(target_station)
            if coords is None:
                continue

            # Simple dong mapping: use the dong_code from geo_processor if available,
            # otherwise use station name as proxy key
            # For simplicity, use station name as dong key
            # In production, this would use GeoProcessor.coord_to_dong()
            station_key = target_station
            if station_key not in dong_impact or abs(impact) > abs(dong_impact[station_key]):
                dong_impact[station_key] = impact

        results = []
        for station_key, impact in dong_impact.items():
            if abs(impact) < 0.1:
                continue
            transfers = transfer_map.get(station_key, 0)
            results.append({
                "역명": station_key,
                "환승횟수": transfers,
                "변화율": round(impact, 1),
            })

        return sorted(results, key=lambda x: abs(x["변화율"]), reverse=True)

    def _estimate_ripple_from_od(
        self, center_dong: str, change_pct: float
    ) -> list[dict]:
        """OD 행렬 기반 파급효과 (인접성 그래프 없을 때 fallback)."""
        subway_df = self.baseline.get("subway", pd.DataFrame())
        if subway_df.empty:
            return []

        dong_agg = (
            subway_df.groupby("행정동코드")
            .agg(총승차=("승차총승객수", "sum"), 총하차=("하차총승객수", "sum"))
            .reset_index()
        )
        if center_dong not in dong_agg["행정동코드"].values:
            return []

        # 승하차량 비율로 연관도 추정
        center = dong_agg[dong_agg["행정동코드"] == center_dong].iloc[0]
        center_total = center["총승차"] + center["총하차"]
        if center_total == 0:
            return []

        results = []
        for _, row in dong_agg.iterrows():
            code = row["행정동코드"]
            if code == center_dong:
                continue
            other_total = row["총승차"] + row["총하차"]
            ratio = min(other_total, center_total) / max(other_total, center_total, 1)
            impact = change_pct * ratio * 0.3
            if abs(impact) > 0.5:
                results.append({
                    "행정동코드": code,
                    "차수": 0,
                    "변화율": round(impact, 1),
                })

        return sorted(results, key=lambda x: abs(x["변화율"]), reverse=True)[:10]

    def combined_scenario(self, scenarios: list[dict]) -> dict:
        """복합 시나리오 - 여러 시나리오의 효과를 합산.

        Args:
            scenarios: 개별 시나리오 결과 리스트

        Returns:
            합산된 변화율 딕셔너리
        """
        combined_changes: dict[str, float] = {}
        for s in scenarios:
            for key, val in s.get("changes", {}).items():
                combined_changes[key] = combined_changes.get(key, 0) + val

        combined_changes = {k: round(v, 1) for k, v in combined_changes.items()}

        return {
            "scenario": "combined",
            "sub_scenarios": [s.get("scenario", "") for s in scenarios],
            "changes": combined_changes,
        }

    def compare_scenarios(self, scenarios: list[dict]) -> pd.DataFrame:
        """여러 시나리오 결과 비교."""
        rows = []
        for s in scenarios:
            row = {
                "시나리오": s.get("scenario", ""),
                "대상": s.get("dong_code", s.get("station_name", "")),
            }
            row.update(s.get("changes", {}))
            rows.append(row)
        return pd.DataFrame(rows)
