#!/usr/bin/env python
"""Layer 4 — 단순 baseline vs 파이프라인 쌍 선호 비교 (페르소나 P1).

판정 설계(프롬프트·페르소나 P1·JSON 스키마)는 팀(임석주) 설계를 그대로 사용한다.
이 스크립트가 더하는 것은 데이터 결선·위치편향 통제·집계뿐(판정 기준은 미변경):
  - 블라인드 A/B를 **두 순서**로 채점(order1: A=baseline/B=pipeline, order2: 뒤집기).
    네 차원(usefulness/readability/balance/overall) 각각 두 순서가 일치해야 승리 인정,
    불일치는 tie(위치편향) 처리.
  - judge = Gemini(독립 모델), temperature 0.

입력: baseline_summaries.json, pipeline_summaries.json (동일 20게임, user/critic 요약).
출력: pref_p1_results.csv + 콘솔 집계.
실행: python ai-pipeline/experiments/layer4_usefulness/run_pref_p1.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import csv

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _ln in open(os.path.join(_ROOT, ".env"), encoding="utf-8"):
    _ln = _ln.strip()
    if _ln and not _ln.startswith("#") and "=" in _ln:
        _k, _v = _ln.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

JUDGE_MODEL = os.environ.get("RAGAS_JUDGE_MODEL", "gemini-3.1-flash-lite")
SURFACES = ("user_summary", "critic_summary")
DIMS = ("usefulness_winner", "readability_winner", "balance_winner", "overall_preference")

# --- 팀(임석주) 설계: 규칙 + 페르소나 P1 + JSON 스키마 (원문 그대로) ---
PROMPT = """당신은 게임 리뷰 요약의 품질을 평가하는 평가자입니다.

한 게임에 대해 두 개의 요약(요약 A, 요약 B)이 주어집니다. 두 요약은 동일한
리뷰 데이터로부터 만들어졌습니다. 당신의 임무는 아래에 정의된 "당신의 사용자
유형" 관점에서, 어느 요약이 더 나은지 판단하는 것입니다.

[중요 규칙]
- 두 요약이 각각 어떤 방식으로 만들어졌는지는 알려주지 않습니다. 출처나 제작
  방식을 추측하지 말고, 오직 텍스트 자체만 보고 평가하십시오.
- A/B의 순서는 의미가 없습니다. 순서가 아니라 내용으로만 판단하십시오.
- "원문을 그대로 옮겼는지"가 아니라, "당신의 사용자 유형이 게임 구매를
  결정하는 데 실제로 더 도움이 되는지"를 기준으로 판단하십시오. 단순히 정보가
  많거나 길다고 좋은 것이 아닙니다.
- 당신의 사용자 유형의 가치관에 충실하게, 그 사람이라면 무엇을 중시할지를
  기준으로 평가하십시오.
- 반드시 지정된 JSON 형식으로만 답하십시오. 그 외 설명은 출력하지 마십시오.

[당신의 사용자 유형: P1 — 신중한 가성비 구매자]
당신은 돈을 신중하게 쓰는 구매자입니다. "이 돈을 주고 살 만한가"가 가장
중요합니다. 가격 대비 콘텐츠 양과 플레이타임, 그리고 최적화(돈을 내고도 제대로
실행 못 하면 최악)를 따집니다. 무엇보다 단점을 솔직하고 충분히 알려주는
요약을 신뢰합니다. 장점만 늘어놓고 단점이 모호하거나 빈약한 요약은 신뢰하지
않습니다. 핵심 질문: "이 요약이 나중에 후회하지 않을 구매 결정을 내리게
도와주는가?"

[게임: {title}]

[요약 A]
{a}

[요약 B]
{b}

{{
  "usefulness_winner": "A | B | tie",
  "readability_winner": "A | B | tie",
  "balance_winner": "A | B | tie",
  "overall_preference": "A | B | tie",
  "reason": "당신의 사용자 유형 관점에서 종합 선호를 택한 이유 (1~2문장)"
}}"""


def _load(name: str) -> dict[int, dict]:
    return {x["game_id"]: x for x in json.load(open(os.path.join(_HERE, name), encoding="utf-8"))}


def _norm(v: str) -> str:
    v = str(v).strip().upper()
    return v if v in ("A", "B") else "TIE"


def _judge(model, title: str, a: str, b: str, retries: int = 4) -> dict:
    import google.generativeai as genai
    prompt = PROMPT.format(title=title, a=a.strip(), b=b.strip())
    for i in range(retries):
        try:
            r = model.generate_content(
                prompt, generation_config=genai.types.GenerationConfig(temperature=0))
            txt = (r.text or "").strip()
            s, e = txt.find("{"), txt.rfind("}")
            obj = json.loads(txt[s:e + 1])
            return {d: _norm(obj.get(d, "tie")) for d in DIMS} | {"reason": str(obj.get("reason", ""))[:200]}
        except Exception as ex:
            if i == retries - 1:
                return {d: "TIE" for d in DIMS} | {"reason": f"[fail] {str(ex)[:80]}"}
            time.sleep(2 ** i * 2)


def _resolve(o1: str, o2: str) -> str:
    """o1: A=baseline,B=pipeline / o2: A=pipeline,B=baseline.
    pipeline 승 = o1 B & o2 A. baseline 승 = o1 A & o2 B. 그 외 tie(편향 포함)."""
    if o1 == "B" and o2 == "A":
        return "PIPELINE"
    if o1 == "A" and o2 == "B":
        return "BASELINE"
    return "TIE"


def _binom_p(wins: int, n: int) -> float:
    if n == 0:
        return 1.0
    from math import comb
    k = max(wins, n - wins)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / (2 ** n))


def main() -> int:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(JUDGE_MODEL)

    base, pipe = _load("baseline_summaries.json"), _load("pipeline_summaries.json")
    gids = sorted(set(base) & set(pipe))
    print(f"judge={JUDGE_MODEL} | 페르소나 P1 | 게임 {len(gids)} | 표면 {SURFACES}\n")

    rows = []
    for surface in SURFACES:
        print(f"=== {surface} ===")
        for gid in gids:
            title = base[gid].get("title", str(gid))
            ba, pa = (base[gid].get(surface) or "").strip(), (pipe[gid].get(surface) or "").strip()
            if not ba or not pa:
                print(f"  SKIP {gid} (결손)"); continue
            r1 = _judge(model, title, ba, pa)   # A=baseline, B=pipeline
            r2 = _judge(model, title, pa, ba)   # A=pipeline, B=baseline
            rec = {"surface": surface, "game_id": gid, "title": title}
            for d in DIMS:
                rec[d] = _resolve(r1[d], r2[d])
            rec["reason1"], rec["reason2"] = r1["reason"], r2["reason"]
            rows.append(rec)
            ov = {"PIPELINE": "🟢파이프라인", "BASELINE": "🔴단순", "TIE": "⚪tie"}[rec["overall_preference"]]
            print(f"  {gid:>3} {title[:24]:<24} overall={ov}  "
                  f"use={rec['usefulness_winner'][:4]} read={rec['readability_winner'][:4]} bal={rec['balance_winner'][:4]}")
            time.sleep(0.4)

    out = os.path.join(_HERE, "pref_p1_results.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\n행별 → {out}")

    print("\n=== 집계 (P1) ===")
    for surface in SURFACES:
        sub = [r for r in rows if r["surface"] == surface]
        print(f"\n[{surface}] n={len(sub)}")
        for d in DIMS:
            pw = sum(r[d] == "PIPELINE" for r in sub)
            bw = sum(r[d] == "BASELINE" for r in sub)
            tie = sum(r[d] == "TIE" for r in sub)
            dec = pw + bw
            wr = pw / dec if dec else 0.0
            p = _binom_p(pw, dec)
            print(f"  {d:<20} 🟢{pw:>2} 🔴{bw:>2} ⚪{tie:>2} | 파이프승률 {wr:>5.1%} "
                  f"(p={p:.3f}{' *' if p < 0.05 else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
