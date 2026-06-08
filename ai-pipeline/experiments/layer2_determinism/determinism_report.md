# 실험 1 — 결정성/재현성 (reduce 리플레이)

- 표본 7개 | 게임당 reduce 5회 반복 (같은 payload, Map 재실행 없음) | model meta-llama/llama-4-scout-17b-16e-instruct
- 주장: 점수는 코드가 결정(LLM은 검증된 delta만) → 같은 입력에 같은 점수.

## 집계
- sentiment_score(0–100) 표준편차 평균: **0.814** (완전 동일 3/7 게임)
- aspect 점수(0–10) 게임별 std 평균: **0.119** (모든 aspect 완전 동일 0/7 게임)

## 게임별 (std=0이면 N회 반복에도 점수 불변)

| id | 게임 | 반복 | sentiment 평균 | sentiment std | aspect std 평균 | aspect std 최대 |
|---|---|---|---|---|---|---|
| 11 | Dragon Age: The Veilguard | 5 | 52.0 | 2.53 | 0.236 | 0.748 |
| 12 | The Witcher 3: Wild Hunt | 5 | 92.0 | 0.0 | 0.062 | 0.214 |
| 20 | Star Wars Jedi: Fallen Order | 5 | 75.8 | 1.166 | 0.132 | 0.49 |
| 32 | Death Stranding | 5 | 82.0 | 0.0 | 0.039 | 0.16 |
| 79 | Dead by Daylight | 5 | 58.4 | 1.2 | 0.112 | 0.463 |
| 94 | Overwatch 2 | 5 | 37.4 | 0.8 | 0.134 | 0.431 |
| 99 | Balatro | 5 | 94.0 | 0.0 | 0.118 | 0.388 |

## 해석
sentiment·aspect 점수의 std가 0(또는 ≈0)이면, reduce LLM 출력이 매번 달라도 최종 점수는 코드가 결정론적으로 산출함을 의미한다. std가 큰 항목이 있으면 어디서 비결정성이 들어오는지 함께 보고한다(LLM delta가 코드 가드를 통과해 점수에 반영되는 경계).
