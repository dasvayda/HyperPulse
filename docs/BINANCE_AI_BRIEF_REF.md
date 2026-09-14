# Binance AI Market Status — 벤치마크 메모

벤치마크만. API 연동·채팅봇 복제 아님.  
실행 티켓은 [PRODUCT_BACKLOG.md](./PRODUCT_BACKLOG.md) BL-14 ~ BL-17.

| | |
|--|--|
| 관찰일 | 2026-09-14 |
| 소스 | Binance 앱 Binance AI 화면 캡처 2장 |
| 질문 예 | `Conduct a BTC market analysis` |
| 우리 대응 제품 | Insights Market Brief + coin stance + Coin Pulse |

---

## 1. 스크린이 보여주는 것

### 화면 A — 코인 분석 답변

1. 사용자 질문: 코인 하나(BTC)에 대한 market analysis.
2. 생각 시간 표시 (`Thought for 8 sec`) — 신뢰 UX, 필수 아님.
3. **TLDER (TL;DR)** 3불릿이 먼저 옴.
4. 그 아래 **Current state** 가 접힌 본문 (가격, 날짜, 24h 시가 대비, 당일 레인지, 7d/30d 수익률).
5. 하단 모드: Trade / Analysis / Opportunity + 자유 질문창.
6. 면책: AI can make mistakes.

### 화면 B — 시작 질문 칩

분석과 무관한 입금/P2P는 우리 범위 밖. 참고할 칩만:

- today’s crypto market opportunities
- trending topics
- which cryptos show bullish momentum
- what is the market sentiment
- (뉴스) 전날 규제 표결 — HyperPulse는 온체인 스냅샷만, 뉴스 QA는 비목표

---

## 2. 답변 스타일 (이게 더 중요함)

레이아웃(3불릿)보다 **문장이 하는 일**을 베끼는 쪽이 맞음.

### 2.1 분석과 행동을 섞지 않음

Binance TLDER에는 **매수/매도 지시가 한 줄도 없음.**  
“soft”, “not uniformly bearish”는 **상태 설명**이지 “숏 가라”가 아님.  
Trade / Opportunity가 그 다음 층.

우리 갭: `headline`이 `"… — Prefer shorts"`처럼 **상태+행동을 한 줄에 붙임.**  
`market_status`는 이미 조언 금지인데, 첫 화면 제목이 조언을 새어 나가게 함.

규칙:

- TL;DR / `market_status` = 지금 북·테이프가 어떻게 생겼나 (서술)
- Suggestions = 그래서 어떻게 할지 (지시)
- Risks = 이 읽기가 깨지는 조건
- headline에서 Prefer/Wait를 빼거나, 배지로만 둠 (문장 안에 넣지 않음)

### 2.2 한 줄의 문법: 라벨 → 근거

Binance 2번째 불릿:

> Daily momentum **is soft**: MACD remains bearish **and** price is below the 7-day and 25-day MAs.

패턴: `[짧은 라벨]: [근거 A] and [근거 B]`

- 라벨은 형용사 하나 (soft / short-heavy / no clear lean)
- 근거는 같은 줄에. “약세다”만 두고 숫자는 아래에 숨기지 않음
- 근거는 2개를 넘기지 않음

우리 적용 예 (MACD 없이):

> Near-term tape is soft: Top3 whale book is 38/62 short-heavy and 1h liqs flushed $2.1M longs.

### 2.3 3번째 줄은 일부러 ‘그러나’

Binance 3번째 불릿은 2번째를 **취소하지 않고 범위를 좁힘.**

> Daily momentum is soft  
> **but** the broader structure is not uniformly bearish

이게 Wait 철학의 문장 버전임. 시그널이 같아도 3번째 줄은 “동의하면 그걸 확인하고, 다르면 충돌을 말함.”  
한 방향으로 점수를 합산하지 않음. “BTC 72점 약세” 같은 단일 스코어 없음.

### 2.4 서술 vs 조언 단어

| 써도 됨 (상태) | 쓰면 안 됨 (조언처럼 들림) |
|----------------|---------------------------|
| short-heavy, long-heavy, balanced | buy bias / sell now / entry |
| momentum is soft | bearish signal (매매 신호처럼) |
| not uniformly one way | mixed (우리 Strategy 태그랑 충돌) |
| remains / continues / sits | should long / consider buying |

Binance는 `bearish`를 **지표 상태**에만 씀 (“MACD remains bearish”).  
우리는 같은 자리에 `short-heavy` / `long flush`를 씀. 형용사를 조언으로 올리지 않음.

### 2.5 문장 톤

- 날짜를 붙임: `as of 2026-09-14` → 우리 `as_of`
- 한 불릿 = 한 생각. 세미콜론으로 두 결론을 넣지 않음
- 말하듯이 씀. 테이블을 문장으로 읽은 느낌 (`BTCUSDT is at $76,844 … versus a 24h open of …`)
- 숫자는 비교쌍으로: 지금 vs 시가, 지금 vs 이평, 24h vs 7d
- 면책은 본문 밖 한 줄 (우리 hero 하단 메타와 같음)

가져오지 말 톤: 호들갑, 목표가, 뉴스 촉매 추측. 우리 프롬프트의 “invent RSI/ETF/news 금지”는 유지.

---

## 3. 컨텐츠 구성 (슬롯)

화면 A는 사실상 **5단 구성**임.

```text
1. 질문 재진술   “Conduct a BTC market analysis”
2. TL;DR          분석만. 고정 3슬롯 (아래)
3. Current state  같은 이야기의 숫자 확대. 새 논지 없음
4. 모드 탭        Analysis | Trade | Opportunity
5. 입력/면책
```

우리 Brief 매핑:

| Binance 단 | 하는 일 | 지금 HyperPulse | 맞출 방법 |
|------------|---------|-----------------|-----------|
| 질문 재진술 | 이 답이 무엇에 대한 답인지 | 없음 (항상 시장 전체) | BL-15 코인 탭 라벨 |
| TL;DR 1 Now | 가격·날짜·짧은 % | headline이 행동까지 포함 | 테이프 1줄, 행동 배지는 옆 |
| TL;DR 2 Short | 라벨 + 근거 2개 | market_status 문단에 섞임 | 불릿 2 = 짧은 구간만 |
| TL;DR 3 However | 넓은 그림 / 충돌 | wait few-shot에만 있음 | 불릿 3 고정 슬롯 |
| Current state | 시가, 레인지, 더 긴 창 | Evidence 보드가 이 역할에 가까움 | 접기/아래로. 논지 추가 금지 |
| Trade | 실행 | (없음, HL 앱 아님) | 안 만듦 |
| Opportunity | 다음에 할 일 | Suggestions | TL;DR 밖에 유지 |
| (없음에 가까움) | 깨지는 조건 | Risks | 유지. Binance 캡처엔 거의 안 보임 |

### TL;DR 3슬롯 고정 (복제할 뼈대)

캡처 문장을 역할로만 치환:

| # | 역할 | Binance 원문 역할 | 우리 필드 |
|---|------|-------------------|-----------|
| 1 | Now tape | 가격 + as-of + 24h + 7d | mark / as_of / (있으면 24h) + Top3 % 한 숫자 |
| 2 | Short read | 모멘텀 라벨 + 근거 2 | 1h liq + 해당 코인(또는 Top3) 북 |
| 3 | However | 구조가 같은 방향인지 | funding 극단 여부 **또는** 북 vs 가격(liq) 충돌 |

슬롯 3이 비면 안 됨. 동의하면 “구조도 같은 쪽(북도 short-heavy, funding도 극단 아님)”이라고 **확인**함.  
Binance가 SuperTrend를 넣은 이유가 “2번만 보면 전체가 약세처럼 보여서”.

### Current state 규칙

TLDER을 **다른 말로 반복 + 숫자만 늘림.** 새 스토리(뉴스, 목표가) 금지.

Binance: 같은 BTC, 같은 날, 시가 $77,251 vs 지금, 레인지 $76,500–$77,450, 7d/30d.  
우리: 같은 코인/Top3의 long_usd·short_usd, funding %, liq 1h vs 24h. Evidence 카드가 이미 이 층.

### 모드 분리에서 배울 점

Analysis 본문에 Opportunity를 끼워 넣지 않음.  
지금 Suggestions가 hero 안에 바로 있어서, 사용자는 분석 문단을 **이미 조언으로** 읽기 쉬움.  
순서만 지켜도 됨: TL;DR → (펼친) 상태 → Suggestions / Risks.

---

## 4. 답변 패턴 한 장 요약

Binance는 **한 방향으로 단정하지 않고**, 짧은 구간과 긴 구간이 다를 수 있음을 먼저 말함.

가져올 문장 규칙:

- 첫 화면은 3줄. 문단은 접거나 아래로.
- 1줄 = 라벨 + 근거(숫자). 형용만 두지 않음
- 3번째 줄은 always however/확인
- TL;DR에 Prefer/Wait 문장 금지 (배지는 OK)
- Suggestions는 분석 뒤

가져오지 말 것:

- 자유형 챗봇, 입금/P2P/구매 가이드
- 뉴스·규제 QA
- MACD / SuperTrend / 99일 이평을 제품 지표로 들이는 것 (우리는 HL 고래 북이 핵)

---

## 5. 지표 맵 — 그들이 쓴 것 vs 우리가 쓰는 것

| Binance | 역할 | HyperPulse 현재 | 갭 |
|---------|------|-----------------|----|
| 현물/선물 가격, 날짜 | Now | `market_ticks` mark는 있음. Brief 스냅샷에는 가격·등락 없음 | 가격 테이프 미노출 |
| 24h % vs open | 짧은 움직임 | 없음 (mark 스냅샷만) | 24h Δ 없음 |
| Session range | 당일 박스 | 없음 | 있으면 Now에만 1개 |
| 7d / 30d return | 조금 더 긴 그림 | 없음. 캔들 파이프라인 없음 | 7d만 저비용으로 검토. 30d는 Later |
| MACD | 일봉 모멘텀 | 없음. Brief 프롬프트가 RSI/목표가 창작 금지 | **복제 금지** |
| 7 / 25 / 99 MA, SuperTrend | 단기 vs 추세 | 없음 | **복제 금지**. 충돌 표현만 차용 |
| (화면 B) sentiment / momentum / opportunities | 질문 진입 | Insights는 스크롤만. 칩 없음 | 칩 → 기존 카드로 점프 |

우리 핵 (유지):

- Top3 whale book long/short
- coin stance (북 + funding + liq)
- extreme funding
- liq 1h / 24h
- biggest tracked positions

Binance 핵을 우리 말로 바꾸면:

> **짧은 구간** = 1h liq + (있으면) 24h 가격  
> **구조** = 고래 북 lean + funding이 극단인지  
> 둘이 같으면 Prefer, 다르면 Wait + 왜 다른지 1줄

---

## 6. 이미 있는 유사 기능

| 사용자 기대 (Binance 말) | 우리 화면 | 얼마나 닮았나 |
|--------------------------|-----------|---------------|
| BTC market analysis | Market Brief는 **시장 전체(Top3)**. 코인 카드는 stance 몇 장 | 부분. 코인 전용 Brief 없음 |
| TL;DR | `headline` 1줄 + `market_status` 2~4문장 | 패턴은 있음. 3불릿 스캔은 없음 |
| Current state | Evidence 보드 + Dashboard KPI | 가격/레인지/7d는 없음 |
| Opportunity | Suggestions + Prefer 카드 | 있음 |
| Sentiment | Top3 mood, whale bias | 있음 (가격 센티먼트 아님) |
| Bullish momentum 코인 | coin stance Prefer longs | 있음. “모멘텀” 가격 정의는 아님 |
| 시작 질문 칩 | 없음 | 없음 |
| 챗 + Trade/Analysis 탭 | 없음. Insights 한 페이지 | 챗은 비목표 |

---

## 7. 백로그로 넘긴 것 / 버린 것

하기로 넘김 (BL-14~17):

1. Brief를 3불릿 TL;DR로 + **분석/행동 분리, 라벨→근거, 3번째 however** (BL-14)
2. 코인 하나 고르면 그 코인 Brief
3. 24h(선택 7d) 가격 vs 고래 북이 다를 때 충돌 1줄
4. Insights 상단 질문 칩 → 이미 있는 섹션으로 스크롤

버림:

- Binance AI 챗 / 음성
- 입금, 구매, P2P
- 뉴스·매크로 QA
- MACD, SuperTrend, 장기 이평선 제품화
- 30d 가격 창고 (목표 충돌: archive 금지)

---

## 8. 데이터 충분성 — 바이낸스식 리포트를 만들 수 있나

결론부터:

- **같은 스타일**(3슬롯 + 라벨→근거 + however) → **지금 지표로 가능.** 새 TA 파이프라인 불필요.
- **같은 내용**(MACD, 7/25/99 이평, SuperTrend, 당일 레인지, 7d/30d) → **부족. 만들지 않음.**
- 진짜 구멍은 “데이터 없음”보다 **이미 있는 숫자를 Brief 스냅샷에 안 넣는 것.**

바이낸스 리포트는 가격 차트 지표로 “짧은 힘 vs 큰 그림”을 말함.  
우리는 같은 역할을 **고래 북 / funding / 청산**으로 하면 됨. 그게 이 제품의 핵.

### 8.1 슬롯별로 있음 / 없음

| 슬롯 | 바이낸스가 쓰는 것 | 우리 소스 | 판정 |
|------|-------------------|-----------|------|
| 1 Now | 가격, as-of, 24h %, 7d % | `market_ticks.mark_price`, `updated_at`, `prev_day_price` → `change_pct_24h` (HL `prevDayPx`) | **24h까지는 있음.** 7d는 없음 |
| 1 보강 | 시가, 세션 레인지 | `prev_day_price` ≈ 전일 종가(시가 대용). high/low는 ctx에 없음 | 레인지 **없음.** 시가 대용만 |
| 2 Short | MACD, 7·25일선 | 코인/Top3 `whale_summary.by_asset` long/short %·$, `liq_1h` | **대체 충분.** MACD 불필요 |
| 3 However | 99일선, SuperTrend | 같은 코인 북 vs funding 극단, (있으면) 24h 가격 vs 북, `liq_1h` vs `liq_24h`, `book_wide` vs Top3 | **대체 충분** |
| Current state | 시가, 레인지, 7d, 30d | 북 $ / funding % / liq 1h·24h / OI / day volume / biggest pos / coverage | **숫자 확대는 됨.** 가격 창(7d/30d/range)만 약함 |
| Opportunity | (탭) | coin_stances, Suggestions | 있음 |

`metaAndAssetCtxs`가 **이미 주는 것** (`collect_market_snapshot` → `store.market_ticks` + `market_snapshots` 테이블):

- mark, prevDayPx, 24h %, funding, OI, 24h notional volume (`dayNtlVlm`)
- 주기: collector ~60초. 행은 지우지 않음 → 켜 둔 기간만큼 시계열은 쌓임. 다만 차트용 OHLCV가 아니고, 재시작 전에는 당일 min/max를 믿을 수 없음.

Brief JSON이 **지금 넣는 것:** Top3 북, book_wide, coin_stances, funding, liq 1h/24h, biggest, coverage.  
**안 넣는 것:** mark, 24h %, OI, volume. Coin Pulse는 쓰는데 Brief는 안 씀.

### 8.2 있어도 품질 주의

| 필드 | 주의 |
|------|------|
| 고래 북 | tracked whale 샘플. “시장 전체 포지션”이 아님. 문장에 tracked / coverage(예: 55/100)를 남김 |
| `change_pct_24h` | HL `prevDayPx` 대비. 바이낸스 “24h open”과 거의 같은 역할이지만 세션 시가는 아님 |
| `liq_1h` / `liq_24h` | `recentTrades` + 메모리 최근 200건. **24h 전수가 아님.** 방향(롱플러시 vs 숏플러시)용. 절대 $를 시장 전체처럼 쓰지 말 것 |
| funding | **지금 값 하나.** 펀딩 추세(어제보다 올라감)는 스냅샷 시계열을 읽어야 함. Brief는 아직 안 읽음 |
| coin_stances | 북+funding+liq를 이미 합친 투표. TL;DR 근거로 다시 섞으면 동어반복. 슬롯2는 생숫자, stance는 배지/Opportunity |

### 8.3 슬롯을 우리 필드로 채우는 최소 세트

새 collector 없이 Brief 스냅샷만 넓히면 됨.

**슬롯 1 Now** (코인 또는 Top3 대표 1개)

- `mark_price` + `as_of` + `change_pct_24h`
- 7d는 빼도 스타일 유지. “24h −0.5%”면 충분. 7d를 꼭 넣으려면 HL `candleSnapshot`을 Brief 생성 때 메이저만 한 번 치는 수준 (창고 아님). 기본은 안 함.

**슬롯 2 Short** — 근거 정확히 2개

- A: 해당 코인(또는 Top3) whale long% / short% + $
- B: `liq_1h` long vs short $ (없으면 24h, 둘 다 작으면 “liq quiet”)

**슬롯 3 However** — 아래 중 다른 축 1개

- funding 극단 vs 플랫 (Top3 funding은 이미 있음)
- 24h 가격 방향 vs 북 방향 (BL-16, ticks에 24h% 있음)
- Top3 북 vs book_wide
- 동의하면: “북도 같은 쪽이고 funding도 극단 아님” **확인 문장** (빈 슬롯 금지)

**Current state** (같은 논지 확대)

- long_usd / short_usd, funding %, liq 1h vs 24h, OI, day volume, coverage, biggest 1줄
- 세션 레인지·30d·MACD 없음. 없는 숫자를 LLM이 만들면 안 됨 (지금 프롬프트와 동일)

### 8.4 일부러 안 만드는 것

| 바이낸스 지표 | 왜 안 만드나 |
|---------------|--------------|
| MACD, 7/25/99 MA, SuperTrend | 일봉 창고 + 차트 엔진. 제품 축이 가격 TA가 아님 |
| 당일 high/low 레인지 | ctx에 없음. 스냅샷 min/max는 프로세스 업타임에 묶임 |
| 30d 수익률 | 아카이브 금지 |
| 뉴스/규제 | 소스 없음 |

OI Δ(전일 대비)는 `market_snapshots`로 **가능하지만** Brief에 아직 없음. 넣으면 슬롯3 보강용. 필수는 아님.

### 8.5 한 줄 판정

스타일 리포트: **데이터는 충분. Brief가 ticks(가격·24h·OI)를 안 받아서 빈약해 보임.**  
바이낸스 복제 리포트: **캔들 TA가 없어서 불가능하고, 목표에도 안 맞음.**
