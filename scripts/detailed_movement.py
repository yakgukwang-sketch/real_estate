"""상세 이동 경로 분석 — 실제 도로 기반."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from collections import Counter, defaultdict
from src.simulation.local_agent import simulate, agents_to_df, _get_area_data


def analyze_area(area: str, n: int = 500):
    label = "대치동" if area == "daechi" else "영등포역"
    print(f"\n{'='*70}")
    print(f"  {label} 상세 이동 분석 ({n}명)")
    print(f"{'='*70}")

    area_data = _get_area_data(area)
    agents = simulate(n_agents=n, seed=42, area=area)
    df = agents_to_df(agents)

    # 1. 출발점 → 목적지 유형 흐름
    print(f"\n[1] 출발점 → 목적지유형 흐름")
    flow = df.groupby(["출발점", "목적지유형"]).size().reset_index(name="건수")
    flow = flow.sort_values(["출발점", "건수"], ascending=[True, False])
    for origin, grp in flow.groupby("출발점"):
        total = grp["건수"].sum()
        print(f"\n  {origin} ({total}건):")
        for _, row in grp.iterrows():
            pct = row["건수"] / total * 100
            bar = "█" * int(pct / 2)
            print(f"    {row['목적지유형']:10s} {row['건수']:3d}건 ({pct:4.1f}%) {bar}")

    # 2. 인기 목적지 Top 20 (실제 건물명 + 좌표)
    print(f"\n[2] 인기 목적지 Top 20")
    dest_stats = df.groupby(["목적지", "목적지유형"]).agg(
        방문=("agent_id", "count"),
        평균도보분=("도보(분)", "mean"),
        총소비=("소비(원)", "sum"),
        lat=("lat", "first"),
        lon=("lon", "first"),
    ).reset_index().sort_values("방문", ascending=False).head(20)

    for i, (_, r) in enumerate(dest_stats.iterrows(), 1):
        print(f"  {i:2d}. {r['목적지'][:20]:20s} ({r['목적지유형']:8s}) "
              f"방문 {r['방문']:3d}회 | 도보 {r['평균도보분']:.0f}분 | "
              f"소비 {r['총소비']:>10,}원 | "
              f"({r['lat']:.6f}, {r['lon']:.6f})")

    # 3. 시간대별 이동 패턴
    print(f"\n[3] 시간대별 이동 패턴")
    time_flow = df.groupby(["시간", "동기"]).size().reset_index(name="건수")
    time_flow = time_flow.sort_values(["시간", "건수"], ascending=[True, False])
    for time, grp in time_flow.groupby("시간"):
        total = grp["건수"].sum()
        print(f"\n  {time} ({total}건):")
        for _, row in grp.head(5).iterrows():
            pct = row["건수"] / total * 100
            print(f"    {row['동기']:15s} {row['건수']:3d}건 ({pct:4.1f}%)")

    # 4. 도보 거리 분포
    print(f"\n[4] 도보 거리 분포")
    walk_bins = [(0, 3, "3분 이내"), (3, 5, "3~5분"), (5, 10, "5~10분"),
                 (10, 15, "10~15분"), (15, 20, "15~20분"), (20, 40, "20분+")]
    for lo, hi, label in walk_bins:
        count = len(df[(df["도보(분)"] >= lo) & (df["도보(분)"] < hi)])
        pct = count / len(df) * 100
        bar = "█" * int(pct / 2)
        print(f"  {label:10s} {count:4d}건 ({pct:4.1f}%) {bar}")

    # 5. 프로파일별 평균 이동 횟수 & 소비
    print(f"\n[5] 프로파일별 행동 요약")
    for profile in df["유형"].unique():
        p_df = df[df["유형"] == profile]
        n_agents_p = p_df["agent_id"].nunique()
        if n_agents_p == 0:
            continue
        avg_moves = len(p_df) / n_agents_p
        avg_spend = p_df["소비(원)"].sum() / n_agents_p
        avg_walk = p_df["도보(분)"].mean()
        top_dest = p_df["목적지유형"].value_counts().head(3)
        top_str = ", ".join(f"{k}({v})" for k, v in top_dest.items())
        print(f"  {profile:15s} | {n_agents_p:3d}명 | 평균 {avg_moves:.1f}회 이동 | "
              f"인당 {avg_spend:,.0f}원 | 도보 {avg_walk:.0f}분 | 주요: {top_str}")

    # 6. 연쇄 이동 패턴
    chain_df = df[df["연쇄"] == True]
    if not chain_df.empty:
        print(f"\n[6] 연쇄 이동 패턴 ({len(chain_df)}건)")
        chain_types = chain_df["목적지유형"].value_counts()
        for t, c in chain_types.items():
            print(f"  → {t}: {c}건")

    # 7. 횡단보도 통과 분석
    print(f"\n[7] 횡단보도 통과 분석")
    print(f"  평균 횡단보도: {df['횡단보도'].mean():.1f}개")
    print(f"  최대 횡단보도: {df['횡단보도'].max()}개")
    cross_by_type = df.groupby("목적지유형")["횡단보도"].mean().sort_values(ascending=False)
    for t, c in cross_by_type.head(5).items():
        print(f"  {t}: 평균 {c:.1f}개")


for area in ["daechi", "yeongdeungpo"]:
    analyze_area(area, n=500)
