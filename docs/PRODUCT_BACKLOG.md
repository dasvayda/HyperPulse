# HyperPulse Product Backlog

**Canonical doc** — 벤치마크 배경 + 실행 백로그를 이 파일 하나로 본다.  
(구 `.cursor/plans/2026-07-22-coinmarketman-ideation.md`, `2026-07-23-hyperpulse-backlog.md` 병합)

| | |
|--|--|
| 작성 | 2026-07-22 ~ 07-23 |
| 갱신 | 2026-09-14 (BL-01 Fresh entries + BL-03 liq windows) |
| 제품 목표 | [README Product Goals](../README.md#product-goals) |
| 설계 제약 | [ARCHITECTURE](./ARCHITECTURE.md#product-goals--design-constraints) |
| 벤치마크 참고 | [HyperTracker Perps](https://app.coinmarketman.com/hypertracker/perps) (시그널·UX만). [Binance AI Brief](./BINANCE_AI_BRIEF_REF.md) (답변 패턴만, 챗/TA 복제 아님) |

### 사용법

- 진행/완료 시 아래 체크박스를 `[x]`로 바꾼다.
- **참고 우선순위:** 일상 실행은 [§4 Backlog](#4-backlog--실행-체크리스트)만 보면 됨.  
  왜 이 항목인지가 필요하면 [§1–3 벤치마크](#1-벤치마크-관점)를 본다.

---

## 0. 진행 현황 (한눈에)

### Shipped (유지보수만)

- [x] Whale book + WhaleBiasPanel (count/value)
- [x] Coin Pulse (funding/OI/bias 일부)
- [x] Open positions on trader detail
- [x] Open ROI / uPnL (position + ranking) — `clearinghouseState` + mark
- [x] Smart money ranking / AI insights / Telegram alerts
- [x] Live-fetch trader positions
- [x] BL-02 Per-coin stance (whale + funding/liq)
- [x] BL-04 Biggest Positions (tracked notional Top N)
- [x] Coin Pulse live board (vol sort, OI bar, bias label, liq timeline)
- [x] BL-05 Alert quality (entry/mark, uPnL/ROI, book %, stale, no Unknown)
- [x] BL-11 Funding crowdedness callout
- [x] Telegram alert mix — Consensus / Whale Move / Big Trade (short templates)
- [x] Market Brief (LLM desk commentary + template fallback) + Insights evidence board
- [x] BL-14/15/16/17 Binance-style Brief TL;DR, coin tabs, tension, chips
- [x] BL-01 Fresh whale entries (24h filter + size delta)
- [x] BL-03 Liquidation windows (1h / 4h / 24h)

### Active backlog

- [x] **P0** BL-01 Fresh whale entries
- [x] **P0** BL-02 Whale bias → actionable insight card
- [x] **P0** BL-03 Liquidation windows (1h / 4h / 24h)
- [x] **P0** BL-04 Biggest open positions (tracked)
- [x] **P0** BL-05 Alert quality pass
- [ ] **P1** BL-06 Smart-money vs rest bias
- [ ] **P1** BL-07 Thin coin × cohort heatmap
- [ ] **P1** BL-08 Copy-worthiness / due-diligence strip
- [ ] **P1** BL-09 userFills recent behavior
- [x] **P1** BL-15 Coin-scoped Market Brief
- [ ] **P2** BL-10 Market pulse strip (3 cards)
- [x] **P2** BL-11 Funding crowdedness callout
- [ ] **P2** BL-12 Liquidation proximity (tracked whales)
- [x] **P2** BL-14 Brief TL;DR strip (3 bullets)
- [x] **P2** BL-16 Price vs whale-book tension
- [x] **P2** BL-17 Insights starter prompts

### Deferred (의도적 보류)

- [ ] ~~BL-X1~~ Full-network Shrimp~Leviathan cohorts — 전수 인덱싱, 목표 충돌
- [ ] ~~BL-X2~~ 30d liq heatmap / Net TWAP 숲 — 밀도↑
- [ ] ~~BL-X3~~ Claimed / favourites / referrals — 소셜, 비핵심
- [ ] ~~BL-X4~~ Order/stop Market Radar — 복잡도↑ (알림 트리거로만 재검토)
- [ ] ~~BL-X5~~ Multi-year backtest warehouse — 축적 판매 모델
- [ ] ~~BL-X6~~ Competitor API integration — 벤치마크만
- [ ] ~~BL-X7~~ Binance-style chat / 뉴스·규제 QA — 제품 축이 챗이 아님
- [ ] ~~BL-X8~~ Classic TA (MACD, SuperTrend, 99d MA) — HL 고래 북과 축 충돌

---

## 1. 벤치마크 관점

| | CoinMarketMan HyperTracker | HyperPulse |
|--|---------------------------|------------|
| 초점 | 전수 스캐너 + 코호트 데이터 플랫폼 | AI whale / smart money intelligence |
| UX | 고밀도 테이블·스파크라인 | 짧고 행동 가능한 insight + alert |
| 범위 | 지갑 ~수백만, 16 cohort | tracked whale / top traders |
| 벤치마크 포인트 | 어떤 시그널이 먹히는가 | 같은 시그널을 더 짧게·더 해석해서 주는가 |

**Binance AI (2026-09-14)** — 답변 뼈대만. 상세: [BINANCE_AI_BRIEF_REF.md](./BINANCE_AI_BRIEF_REF.md)

| | Binance AI | HyperPulse |
|--|------------|------------|
| 질문 | `BTC market analysis` (코인 1개 + 챗) | 시장 전체 Market Brief (Top3) + coin stance 카드 |
| 첫 화면 | TLDER 3불릿 → Current state 접기 | headline 1줄 + market_status 문단 |
| 지표 | 가격·24h/7d/30d, MACD, MA, SuperTrend | 고래 북, funding, liq, stance |
| 배울 점 | 분석과 행동을 분리, 라벨→근거, 3번째 줄은 however, Current state는 숫자만 확대 | 그 문장 규칙을 **우리 스냅샷 필드**에 입힘. 챗/MACD는 안 가져옴 |

**원칙**
- 산만한 perps 테이블 복제 금지
- 시그널의 핵만 가져와 우리 파이프라인(수집 → ranking → inference → alert → insight)에 재설계
- 데이터 = Hyperliquid 직접 수집 + 우리 집계 (경쟁사 API 연동 없음)
- Now-insight · 심플 · 신뢰 · 트레이딩 실용 (축적 데이터 판매 비목표)

---

## 2. 벤치마크 item 맵 (참고용)

### A. Perps 보드
- Summary: OI, Daily Volume, Active Traders (+Δ, sparkline)
- Per-coin: Last, 24h Vol, OI, Funding, Net TWAP, 24h Liq Timeline, Whale Bias
- Whale Bias: long/short % + $ + sentiment 라벨

### B. Wallet Cohorts
- Equity: Shrimp → Leviathan / PnL: Giga-Rekt → Money Printer
- 카드: count, sparkline, sentiment, avg lev, % in position
- Position Age: `<24h` / 7d / 30d / all

### C. Docs 기능 카탈로그 (연동 대상 아님)
Trader & Wallet · Positions (uPnL) · Cohort · Heatmap · Orders · Liquidation · Leaderboards · Stats/WS

우리는 **L2 알파 스크리너 + L3 스마트머니 센티먼트 + 알림형 L5**에 가깝게 가져감.

### 벤치마크 → 재해석

| 그들이 보여줌 | 우리는 이렇게 |
|---------------|---------------|
| Slightly Bearish 배지 | `Sell/Hold` + tracked whale long/short 근거 |
| Cohort 카드 8×2 | Ranking 상위 vs tracked 전체 bias 1패널 |
| 24h Liq Timeline | 1h/4h/24h 요약 + alert 한 줄 |
| Position Age `<24h` | Fresh whale entries |
| Biggest Positions | Tracked whale Top 5 + ROI + link |
| Money Printer cohort | AI strategy + ROI/consistency |
| Binance TLDER 문장 | 분석만 3슬롯 (Now / short / however). Prefer는 배지+Suggestions (BL-14) |
| BTC market analysis 챗 | 코인 탭 Brief. 챗/뉴스 없음 (BL-15) |
| MACD vs 99일선 충돌 | 24h 가격 vs 고래 북 충돌 1줄 (BL-16). 이평/MACD 안 씀 |

---

## 3. 갭에서 나온 후보 → 백로그 ID 매핑

| 옛 ideation | Backlog | 상태 |
|-------------|---------|------|
| I1 Open Position ROI/uPnL | (shipped) | [x] |
| I2 Bias → Insight | BL-02 (+ BL-11) | [x] |
| I3 Position Age / Fresh | BL-01 | [x] |
| I4 Smart money cohort 축소 | BL-06 | [ ] |
| I5 Thin heatmap | BL-07 | [ ] |
| I6 Due diligence | BL-08 | [ ] |
| I7 Market pulse | BL-10 | [ ] |
| I8 Funding + Liq timeline | BL-03, BL-11 / Coin Pulse liq | [x] |
| Biggest Positions | BL-04 | [x] |
| Market Brief / Insights hero | (shipped 2026-07-25) | [x] |
| Binance TLDER 3불릿 | BL-14 | [x] |
| Binance 코인 단위 분석 | BL-15 | [x] |
| 짧은 구간 vs 구조 충돌 | BL-16 | [x] |
| 시작 질문 칩 | BL-17 | [x] |

---

## 4. Backlog — 실행 체크리스트

Priority: **P0** now-insight → **P1** smart-money 해석 → **P2** 맥락 1~2개 → **Later** 보류

### P0 — Now-insight

#### BL-01 · Fresh whale entries
- [x] Done (2026-09-14)
- **Why:** `<24h` 필터가 시그널을 날카롭게 함
- **HL:** whale size-change + `clearinghouseState` (+ `userFills` 보강)
- **Deliverable:** Fresh(24h) vs Open book 토글 또는 `fresh entry` 알림 태그
- **Done when:** 최근 진입 필터 + 진입 시각/size delta 표시
- **Effort:** M
- 세부:
  - [x] 진입 시각/delta 소스 확정 (`classify_size_change` + `size_delta_usd`)
  - [x] UI 또는 alert 태그 (Whale Alerts Fresh 24h + Telegram FRESH)
  - [x] Done when 검증 (`tests/test_fresh_liq_p0.py`)

#### BL-02 · Whale bias → actionable insight card
- [x] Done (2026-07-23)
- **Why:** 숫자는 있음 → Buy/Sell/Hold + 근거 1줄
- **HL:** whale book + funding (`metaAndAssetCtxs`) + liq skew
- **Deliverable:** 코인별 stance 최대 3장
- **Done when:** bias·funding·liq 중 ≥2개 근거
- **Effort:** S–M
- 세부:
  - [x] stance 규칙 (`_build_coin_stance_insights` in `inference.py`)
  - [x] Insight UI 연결 (homepage prefers coin stance cards)
  - [x] Done when 검증 (unit smoke: card당 ≥2 signal families)

#### BL-03 · Liquidation windows (1h / 4h / 24h)
- [x] Done (2026-09-14: 1h dashboard + 4h/24h Liquidations strip)
- **Why:** “지금 청산이 어느 쪽인가” 요약
- **HL:** `recentTrades` liq + 짧은 persist
- **Deliverable:** 윈도우별 long/short $ + pressure 한 줄
- **Out of scope:** 30d heatmap, velocity 게이지 복제
- **Effort:** M
- 세부:
  - [x] 1h rollup → `MarketStatus.liq_1h_*` + dashboard StatCard (Latest Consensus 대체)
  - [x] 4h / 24h strip (Liquidations 상단; 대시보드는 1h만)
  - [x] insight/alert 재사용 (`Liq pressure · 1h/4h` card)

#### BL-04 · Biggest open positions (tracked)
- [x] Done (2026-07-23)
- **Why:** 카피/센티먼트에 바로 쓰임 (전수 불필요)
- **HL:** whale book `clearinghouseState`
- **Deliverable:** Top 8 — asset / side / size / entry / uPnL·ROI / trader link
- **Effort:** S
- 세부:
  - [x] API `/api/v2/whale-book/biggest-positions`
  - [x] 대시보드 테이블 + trader 상세 링크
  - [x] mark 기반 ROI/uPnL (market_ticks)

#### BL-05 · Alert quality pass
- [x] Done (2026-07-24)
- **Why:** 신뢰는 알림 한 줄에서 결정
- **HL:** entry/mark, uPnL/ROI, asset whale long%
- **Deliverable:** 템플릿 표준 + rate limit 유지 + stale 표시
- **Done when:** 샘플 20건 필수 필드 누락 0
- **Effort:** S
- 세부:
  - [x] 템플릿 필드 체크리스트 (entry/mark, uPnL/ROI, book %, strategy)
  - [x] Unknown strategy 비율 개선 (collect + send heuristic fallback)
  - [x] STALE (>45m) Telegram title + whale-alerts badge
  - [x] whale-alerts UI: Entry/Mark, uPnL/ROI, Book (Win Rate 컬럼 제거)
---

### P1 — Smart money 해석

#### BL-06 · Smart-money vs rest bias (2-cohort)
- [ ]
- **HL:** ranking 상위 N vs tracked 전체 positions
- **Deliverable:** 주요 코인 3~5개, 두 집단 long% 비교 패널
- **Effort:** M
- 세부:
  - [ ] 집계
  - [ ] 패널 UI
  - [ ] insight 인용

#### BL-07 · Thin coin × cohort heatmap (2~4열)
- [ ]
- **HL:** BL-06 재사용
- **Deliverable:** 자산 × smart/rest/(optional style) 색 매트릭스
- **Effort:** M
- 세부:
  - [ ] 매트릭스 UI
  - [ ] 모바일 가독성
  - [ ] 범례 1줄

#### BL-08 · Copy-worthiness / due-diligence strip
- [ ]
- **HL:** leaderboard + open ROI/uPnL + lev + inference
- **Deliverable:** 상세 상단 5필드 + `Watch / Caution / Skip`
- **Effort:** M
- 세부:
  - [ ] 휴리스틱 규칙 문서
  - [ ] UI
  - [ ] 재현성 검증

#### BL-09 · userFills recent behavior (tracked only)
- [ ]
- **HL:** `userFills` / `userFillsByTime` (rate limit 주의)
- **Deliverable:** Last 24h fills summary (buy/sell notional, 코인)
- **Effort:** M–L
- 세부:
  - [ ] collector + 캐시
  - [ ] 트레이더 상세 UI
  - [ ] open position과 정합성 표시

---

### P2 — 시장 맥락 (제품 노출 최대 1~2개)

#### BL-10 · Market pulse strip (3 cards)
- [ ]
- **HL:** `metaAndAssetCtxs` + BL-03
- **Deliverable:** OI / Vol / Liq(24h) + 짧은 Δ
- **Effort:** M
- 세부:
  - [ ] 스냅샷 저장
  - [ ] 대시보드 3카드 (메인 테이블화 금지)

#### BL-11 · Funding crowdedness callout
- [x] Done (2026-07-24, 2026-07-25 개편)
- **HL:** assetCtx funding + dayNtlVlm
- **Deliverable:** 거래대금 Top20 ∩ |funding| ≥ 0.02% 인 코인만 "Extreme funding" callout (바닥/천장 후보). 극단 없으면 callout 없음
- **Effort:** S
- 세부:
  - [x] 집계 (`_build_funding_crowdedness_insight`)
  - [x] InsightCard callout + homepage preview 노출
  - [x] 2026-07-25: 상위 유동성 ∩ 극단 필터로 변경 — thin alt(STX 등)가 callout 독점하는 문제 제거. Consensus는 거래대금 Top3 고래 북만 사용, funding 완전 분리

#### BL-13 · Market Brief (Insights hero)
- [x] Done (2026-07-25)
- **Why:** AI는 트레이더 Speculative 태그가 아니라 시장 상태·포지션 제안이어야 함
- **HL:** Top3 whale book + coin stance + extreme funding + liq 1h/24h + biggest positions (기존 집계만)
- **Deliverable:** `GET /api/v2/insights/brief` + Insights 히어로 + Dashboard 헤드라인 1줄; Style mix 제거; strategy 라벨 canonicalize
- **Effort:** M
- 세부:
  - [x] `market_brief.py` 스냅샷 + template + LLM 쿨다운/검증
  - [x] Evidence 보드 (Prefer 정렬 + Top3 Consensus 카드)
  - [x] Dashboard 티저(헤드라인만) / Insights 전문 분리
  - [x] agent.md / ARCHITECTURE / PRODUCT_BACKLOG 페이지 소유권·LLM 용도 기록

#### BL-12 · Liquidation proximity (tracked whales)
- [ ]
- **HL:** `liquidationPx` / margin + mark
- **Deliverable:** distance% Top N + optional alert
- **Effort:** M
- 세부:
  - [ ] distance 계산
  - [ ] 리스트 UI
  - [ ] (선택) alert

#### BL-14 · Brief TL;DR strip (3 bullets)
- [x] Done (2026-09-14)
- **Why:** Binance는 3줄이라서가 아니라 **분석과 매매 지시를 안 섞고**, 줄마다 역할이 다름. 우리 headline은 `"… — Prefer shorts"`로 둘을 붙임
- **Ref:** [BINANCE_AI_BRIEF_REF.md](./BINANCE_AI_BRIEF_REF.md) §2–3, §8
- **HL:** 기존 Brief 필드 + **이미 있는** `market_ticks` (mark, 24h%, OI, volume). 캔들/MACD 없음. 7d 없이도 슬롯1 가능
- **Deliverable:** Insights hero 불릿 3개 고정 슬롯 + 카피 계약
  - 1 Now tape (숫자 + as_of)
  - 2 Short read (`라벨: 근거 A and 근거 B`)
  - 3 However / 확인 (넓은 그림이 같은 쪽인지)
  - TL;DR 문장에 Prefer/Wait 금지. stance는 배지. Suggestions/Risks는 아래
  - `market_status` 문단은 Current state처럼 **같은 논지 숫자 확대** (새 스토리 금지)
- **Done when:** 불릿이 형용만 쓰지 않음. headline/TL;DR에 매매 지시 없음. 슬롯 3이 비지 않음
- **Effort:** S–M
- 세부:
  - [x] snapshot → 3불릿 템플릿 (규칙 우선, LLM은 문장만)
  - [x] headline에서 Prefer 분리 (배지 / Suggestions만)
  - [x] `BRIEF_SYSTEM_PROMPT` + few-shot을 §2 카피 계약에 맞춤
  - [x] `MarketBriefHero` TL;DR → status → suggestions 순서
  - [x] Dashboard 티저는 서술 headline만 (불릿·Prefer 덤프 금지)

#### BL-15 · Coin-scoped Market Brief
- [x] Done (2026-09-14)
- **Why:** 사용자가 실제로 던지는 질문은 “BTC 지금 어때?”임. 지금은 시장 전체 Brief + 코인 stance 카드만 있음
- **Ref:** [BINANCE_AI_BRIEF_REF.md](./BINANCE_AI_BRIEF_REF.md) §4
- **HL:** 해당 코인 whale book + funding + liq + (있으면) mark. 기존 집계 재사용
- **Deliverable:** Insights에서 BTC/ETH/SOL(또는 Top3) 선택 → 그 코인 headline + TL;DR 3줄 + stance. 챗 입력창 없음
- **Out of scope:** 자유 질문, 전 코인 검색창
- **Done when:** 코인 Brief가 다른 코인 숫자를 인용하지 않음
- **Effort:** M
- 세부:
  - [x] `GET /api/v2/insights/brief?asset=BTC` 또는 snapshot slice
  - [x] 코인 탭/칩 UI
  - [x] 시장 전체 Brief와 공존 (기본은 전체)

#### BL-16 · Price vs whale-book tension
- [x] Done (2026-09-14)
- **Why:** Binance 답의 핵은 “일봉은 약한데 큰 그림은 아직 아니다”. MACD 대신 **24h 가격 vs 고래 북**으로 같은 충돌을 말함
- **Ref:** [BINANCE_AI_BRIEF_REF.md](./BINANCE_AI_BRIEF_REF.md) §3, §8
- **HL:** ticks의 `change_pct_24h` (`prevDayPx`) + 기존 Top3·coin book. 새 캔들 창고 없음. 30d·이평·MACD 금지
- **Deliverable:** 메이저 1~3코인, “가격 24h ↓ / 북은 long-heavy” 같은 충돌 1줄 → Brief TL;DR 3번째 슬롯 또는 stance Wait 근거
- **Done when:** 가격과 북이 같으면 충돌 줄 없음. 다를 때만 노출
- **Effort:** M
- 세부:
  - [x] 24h Δ 소스 확정 (캔들 창고 없이)
  - [x] 충돌 규칙 (가격 vs long_pct)
  - [x] BL-14 3번째 불릿 또는 evidence 1장

#### BL-17 · Insights starter prompts
- [x] Done (2026-09-14)
- **Why:** Binance 시작 칩이 “어디로 보면 되는지”를 가르침. 챗이 아니라 **있는 섹션으로 점프**
- **Ref:** [BINANCE_AI_BRIEF_REF.md](./BINANCE_AI_BRIEF_REF.md) 화면 B
- **HL:** 없음 (UI only)
- **Deliverable:** Insights 상단 칩 3~4개 예: `Top3 lean?` / `극단 funding?` / `1h liq 어느 쪽?` / `BTC Brief`
- **Out of scope:** 입력창, 뉴스 칩, 입금/구매 칩
- **Effort:** S
- 세부:
  - [x] 칩 → 앵커 (Brief / funding callout / liq / coin brief)
  - [x] 라이브 Top3 티커 칩 (질문 투어 아님)

---

## 5. 추천 구현 순서

```text
BL-05 Alert quality
  → Telegram alert mix (Consensus / Whale Move / Big Trade)
  → BL-02 Bias insight
  → BL-04 Biggest positions
  → BL-01 Fresh entries
  → BL-03 Liq windows
  → BL-11 Funding (또는 BL-02에 흡수)
  → BL-06 Smart vs rest
  → BL-12 Liq proximity
  → BL-08 Due diligence
  → BL-09 userFills
  → BL-07 Heatmap / BL-10 Pulse (둘 중 하나만 먼저)
  → BL-14 Brief TL;DR
  → BL-17 starter chips
  → BL-16 price vs book (24h Δ 가능할 때)
  → BL-15 coin-scoped Brief
```

한 화면에 동시 상륙 금지. 완료 후 “트레이더 다음 행동에 쓰는가?”로 검수.

---

## 6. HL source ↔ backlog

| HL source | IDs |
|-----------|-----|
| `clearinghouseState` | BL-01, 04, 05, 06, 08, 12 |
| `metaAndAssetCtxs` | BL-02, 10, 11, 16 |
| `recentTrades` (liq) | BL-03, 05, 10 |
| leaderboard stats | BL-06, 08 |
| `userFills` / ByTime | BL-01, 09 |
| `openOrders` (later) | BL-X4 재검토 시 |
| 기존 Brief snapshot만 | BL-14, 15, 17 |

---

## 7. Acceptance template (티켓 공통)

완료 체크 전에 모두 만족하는지 확인:

- [ ] **Decision use** — 바꾸게 하는 결정이 무엇인가?
- [ ] **HL provenance** — 필드 → endpoint 매핑이 코드/주석에 있는가?
- [ ] **Simplicity** — 새 숫자 ≤ 3개 (또는 기존 교체)?
- [ ] **Insight link** — alert 또는 insight 문장에 연결되는가?
- [ ] **Non-goal** — 전수/장기 아카이브/스캐너 밀도 증가가 아닌가?

---

## 8. 한 줄 결론

경쟁사는 **무엇을 보여주면 먹히는지**의 벤치마크다.  
HyperPulse는 HL 온체인으로 **ROI(완료) / Fresh bias / Smart-money 대비 / Liq 요약**을 골라, **지금 쓸 수 있는 insight**로만 제품화한다.  
Binance AI는 **분석/행동 분리 + 3슬롯 TL;DR(Now / short / however)**만 가져오고, 챗·이평·MACD는 가져오지 않는다.
