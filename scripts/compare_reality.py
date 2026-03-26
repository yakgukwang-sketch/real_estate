"""시뮬레이션 vs 현실 비교 스크립트."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.simulation.calibration import load_calibration
from src.simulation.local_agent import simulate, agents_to_df, estimate_revenue

AREA_SALES = {
    "daechi": {"annual": 1_202_800_000_000, "apt_share": 1600 / 20000},
    "yeongdeungpo": {"annual": 628_800_000_000, "apt_share": 1.0},
}

N = 1000

for area in ["daechi", "yeongdeungpo"]:
    label = "대치동" if area == "daechi" else "영등포역"
    print(f"\n{'='*60}")
    print(f"  {label} 시뮬레이션 ({N}명)")
    print(f"{'='*60}")

    agents = simulate(n_agents=N, seed=42, area=area)
    df = agents_to_df(agents)

    out_agents = sum(1 for a in agents if a.log)
    print(f"에이전트: {N}명, 외출: {out_agents}명, 이동: {len(df)}건")

    # 프로파일별 소비
    print("\n[프로파일별 소비]")
    profile_col = [c for c in df.columns if "프로파일" in c or "profile" in c.lower()]
    if profile_col:
        pc = profile_col[0]
        for p, grp in df.groupby(pc):
            print(f"  {p}: {grp.iloc[:, -2].sum():,.0f}원 ({len(grp)}건)")

    # 업종별 분포
    type_col = [c for c in df.columns if "목적지유형" in c or "dest_type" in c.lower()]
    spend_col = [c for c in df.columns if "소비" in c or "spend" in c.lower()]

    if type_col and spend_col:
        tc, sc = type_col[0], spend_col[0]
        print(f"\n[업종별 소비 분포]")
        type_spend = df.groupby(tc)[sc].sum()
        total_spend = type_spend.sum()
        type_pct = type_spend / total_spend * 100
        for t in type_pct.sort_values(ascending=False).index:
            print(f"  {t}: {type_spend[t]:,.0f}원 ({type_pct[t]:.1f}%)")

        # 방문 비중
        print(f"\n[업종별 방문 비중]")
        visit_pct = df[tc].value_counts(normalize=True) * 100
        for t in visit_pct.index:
            print(f"  {t}: {visit_pct[t]:.1f}%")

    # 매출 비교
    info = AREA_SALES[area]
    sim_total = df[spend_col[0]].sum() if spend_col else 0

    if area == "daechi":
        # 대치동: 하루 유동인구 약 5만명 (학원가 + 주민 + 직장인)
        scale = 50
        sim_daily = sim_total * scale
        real_daily = info["annual"] / 365
        print(f"\n[매출 비교 - 유동인구 5만명 기준]")
    else:
        scale = 50  # 하루 약 5만명 유동인구 / 1000 에이전트
        sim_daily = sim_total * scale
        real_daily = info["annual"] / 365
        print(f"\n[매출 비교 - 유동인구 5만명 기준]")

    print(f"  시뮬 일일소비 (스케일업): {sim_daily:,.0f}원")
    print(f"  실제 일일매출 추정:       {real_daily:,.0f}원")
    ratio = sim_daily / real_daily if real_daily > 0 else 0
    print(f"  시뮬/실제 비율:           {ratio:.3f}")

    if ratio > 1:
        print(f"  → 시뮬레이션이 실제보다 {(ratio-1)*100:.1f}% 과대추정")
    else:
        print(f"  → 시뮬레이션이 실제보다 {(1-ratio)*100:.1f}% 과소추정")

    # estimate_revenue 사용
    rev = estimate_revenue(df, n_agents=N, area=area)
    print(f"\n[estimate_revenue 함수 결과]")
    for k, v in rev.items():
        if isinstance(v, (int, float)):
            print(f"  {k}: {v:,.0f}")

# 보정 데이터 비교
cal = load_calibration()
if cal and cal.get("spending_df") is not None:
    from src.simulation.validation import validate

    agents_d = simulate(1000, seed=42, area="daechi")
    df_d = agents_to_df(agents_d)

    print(f"\n{'='*60}")
    print("  보정 데이터 기반 현실 비교 (대치동)")
    print(f"{'='*60}")

    result = validate(
        df_d,
        cal["spending_df"],
        cal.get("population_df"),
        cal.get("hourly_pattern"),
        n_agents=1000,
    )
    print(f"매치 스코어: {result['match_score']}%")
    print(f"방문 비중 코사인 유사도: {result['visit_share']['cosine_similarity']}")
    print(f"시간대 상관계수: {result['hourly']['correlation']}")

    print("\n객단가 비교:")
    for dt, v in sorted(result["unit_prices"].items()):
        print(f"  {dt}: 시뮬 {v['sim']:,}원 / 실제 {v['real']:,}원 (차이 {v['diff_pct']}%)")
else:
    print(f"\n{'='*60}")
    print("  보정 parquet 데이터 없음 — 하드코딩 기준으로만 비교")
    print(f"{'='*60}")

print("\n\n=== 현실과의 주요 차이점 분석 ===")
print("""
1. 에이전트 수 vs 실제 유동인구
   - 시뮬: 1000명 기반 → 스케일업 추정
   - 현실: 대치동 약 2만세대 중 1600세대(래미안), 영등포 하루 5만+

2. 시간대 패턴
   - 시뮬: 고정 스케줄 기반 (이른아침→점심→오후→저녁→밤)
   - 현실: 날씨/요일/계절에 따라 큰 변동

3. 소비 금액
   - 시뮬: 업종별 고정 객단가 (음식점 15,300원 등)
   - 현실: 객단가 편차가 크고 시간대/요일별 차이

4. 연쇄 이동 (체인)
   - 시뮬: 약 85% 확률로 다음 목적지 이동
   - 현실: 동선이 더 복잡하고 목적에 따라 다름

5. 목적지 선택
   - 시뮬: 거리 선호도(near/mid/far) + 인기도 가중
   - 현실: 브랜드, 리뷰, 습관, 동반자 등 다양한 요인
""")
