# HyperPulse Paper Portfolio 기획서 — 2026-10-05

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-10-05 |
| 상태 | 제안 · 구현 전 |
| Backlog | [PRODUCT_BACKLOG.md · BL-18](./PRODUCT_BACKLOG.md#bl-18--hyperpulse-paper-portfolio) |
| Launch 단계 | [Closed Beta](./LAUNCH_PLAN.md#phase-2--closed-beta)에서 Shadow Trading, 공개는 Phase 3 판단 |

## 1. 목적

Whale signal, Smart Money 포지셔닝, funding, liquidation pressure, 시장 방향성 등 HyperPulse가 이미 만드는 신호를 하나의 고정된 전략으로 조합하고, **$1,000의 가상 포트폴리오가 시간에 따라 어떻게 변했는지** 보여준다.

이 콘텐츠가 답해야 하는 질문은 하나다.

> HyperPulse의 신호를 사전에 정한 규칙대로 실제 체결 가능한 시점에 거래했다면, 비용과 손실을 포함한 결과는 어땠는가?

단순 신호 적중률을 수익률처럼 포장하지 않는다. 공개 전부터 같은 규칙으로 계속 실행되는 Forward Test를 통해 제품의 실용성과 한계를 함께 보여주는 것이 목적이다.

## 2. 제품 원칙

1. **Forward Test 우선** — 과거 결과에 맞춘 장기 백테스트를 대표 성과로 사용하지 않는다.
2. **전략 규칙 고정** — 공개된 전략 버전의 입력, 임계값, 포지션 크기, 비용 가정을 소급 변경하지 않는다.
3. **전체 결과 공개** — 이긴 거래만 뽑지 않고 모든 진입·청산과 손실 구간을 보존한다.
4. **Net 성과 우선** — 수수료, 슬리피지, funding을 반영한 순성과를 기본값으로 보여준다.
5. **재현 가능성** — 어떤 데이터로 언제 판단했고 어떤 가격으로 체결했다고 가정했는지 추적할 수 있어야 한다.
6. **운영 중 초기화 금지** — 손실 때문에 포트폴리오를 리셋하지 않는다. 새 규칙은 새 버전과 별도 성과 곡선으로 시작한다.
7. **가상 성과 명시** — 실제 계좌나 고객 자금의 실현 수익으로 오해할 표현을 사용하지 않는다.

## 3. 범위와 비범위

### MVP 범위

- 초기 가상 자산: **$1,000 USD**
- 대상 자산: BTC, ETH, SOL로 시작
- 방향: LONG / SHORT / CASH(Wait)
- 레버리지: 없음
- 최대 총 익스포저: 포트폴리오 NAV의 100%
- 동시 포지션: 최대 3개
- 공개 성과: 전체 포트폴리오 1개
- 기준 성과: BTC 단순 보유와 현금 $1,000
- 실행 방식: 실시간 수집 데이터를 사용한 Forward Test

### MVP 비범위

- 사용자 자금 또는 거래소 주문 실행
- 개인별 위험 성향 및 포트폴리오 최적화
- 다년간 backtest warehouse
- 결과가 좋은 코인이나 기간만 추출한 성과
- 레버리지, 교차·격리 마진, 청산 시뮬레이션
- 여러 전략을 동시에 나열하는 전략 마켓

BL-X5의 다년간 backtest warehouse 보류와 충돌하지 않는다. BL-18은 출시 시점 이후의 신호를 순차 기록하는 작고 검증 가능한 Forward Test다.

## 4. 전략 v1 초안

전략 식별자는 `top5_whale_trend_v1`을 사용한다. 모든 고래와 시장 지표를 하나의 점수로 섞지 않는다. **Top 5 Whale의 방향을 먼저 정하고, 최근 거래대금과 시장 추세가 그 방향을 확인할 때만 거래한다.** Funding과 liquidation은 방향 신호가 아니라 포지션을 줄이는 위험 필터다.

아래 값은 Shadow Trading 시작 전에 확정·동결할 초기안이며, 공개 성과가 시작된 뒤 같은 버전에서 변경하지 않는다.

### 4.1 평가 주기와 대상

- 평가 주기: 매시 정각 1회
- 거래 대상: BTC, ETH, SOL
- 판단 단위: 자산별 독립 판단
- 출력: LONG / SHORT / WAIT와 목표 비중
- 필수 데이터가 stale이거나 누락되면 해당 자산은 신규 진입하지 않는다.

LLM이 매매 방향이나 주문을 결정하지 않는다. Market Brief 문장은 설명에만 사용하고, 모든 판단은 저장된 구조화 데이터와 버전이 고정된 규칙으로 수행한다.

### 4.2 1차 방향 — Top 5 Whale 포지션

Top 5 Whale은 판단 시점에 이용 가능한 Smart Money ranking 상위 5개 지갑이다. 매일 00:00 UTC의 최신 ranking으로 그날의 명단을 고정하고 `rank_snapshot_id`, 주소, 순위, score를 decision과 함께 보존한다.

자산별 방향 계산:

1. Top 5 중 해당 자산의 유효 포지션을 가진 지갑만 사용한다.
2. LONG notional은 양수, SHORT notional은 음수로 본다.
3. 한 지갑이 전체 판단을 지배하지 않도록 지갑별 가중치는 최대 30%로 제한한다.
4. 유효 포지션 지갑이 3개 미만이면 합의 없음으로 처리한다.
5. 최소 3개 지갑이 같은 방향이고, 제한 적용 후 notional의 65% 이상이 그 방향이면 `LONG_CONSENSUS` 또는 `SHORT_CONSENSUS`다.
6. 조건을 만족하지 않으면 `MIXED`이며 Top 5 포지션만으로는 거래하지 않는다.

오래 유지된 큰 포지션은 방향을 보여주지만 현재 진입 타이밍까지 보장하지 않는다. 따라서 다음 단계에서 최근 거래 흐름을 별도로 확인한다.

### 4.3 2차 방향 — 최근 Top 5 Whale 거래대금

최근 1시간 동안 주기적으로 수집된 `clearinghouseState` 포지션 snapshot의 차이로 고래별 자산 노출 변화를 USD로 계산하고, 절대 변화액이 큰 서로 다른 지갑 5개를 선택한다. 동일 지갑의 여러 snapshot 변화는 하나의 net flow로 합쳐 반복 변화가 Top 5를 독점하지 않게 한다.

방향성 노출 변화는 다음처럼 계산한다.

- LONG 추가 또는 SHORT 청산: 양수 flow
- SHORT 추가 또는 LONG 청산: 음수 flow
- 단순 체결 side가 아니라 **포지션 노출이 늘거나 줄어든 방향**을 사용한다.

유효 flow가 3개 이상이고 거래대금의 60% 이상이 같은 방향이면 `LONG_FLOW` 또는 `SHORT_FLOW`, 아니면 `MIXED_FLOW`다. position snapshot이나 delta가 불완전하면 flow를 억지로 추정하지 않고 `FLOW_UNAVAILABLE`로 남긴다.

이 계산을 위해 `userFillsByTime`을 추적 지갑 전체에 배경 호출하지 않는다. Trader detail 요청으로 이미 캐시된 fill은 audit 보조 자료로만 사용할 수 있으며, 전략의 필수 입력은 collector가 보유한 position snapshot delta다.

### 4.4 시장 Trend 검증

시장 Trend는 새로운 거래 방향을 만들지 않고 Whale 방향을 승인하거나 거부한다. 캔들 기반 MACD 같은 별도 TA를 추가하지 않고 저장된 mark snapshot으로 계산한다.

초기 기준안:

- `UP`: 1h 수익률 `> +0.15%`이고 4h 수익률 `> 0%`
- `DOWN`: 1h 수익률 `< -0.15%`이고 4h 수익률 `< 0%`
- 그 외: `MIXED`

임계값, 가격 소스, 허용 가능한 snapshot 지연은 전략 config에 저장한다. 15m Pulse와 OI 변화는 판단 근거 화면에 보조 정보로 표시할 수 있지만 v1의 진입 필수 조건이나 별도 방향 투표로 사용하지 않는다.

### 4.5 최종 결정

| Top 5 포지션 | 최근 Top 5 flow | 시장 Trend | 결정 | 기본 목표 비중 |
|---|---|---|---|---:|
| LONG | LONG | UP | LONG | NAV의 40% |
| SHORT | SHORT | DOWN | SHORT | NAV의 40% |
| LONG | MIXED/UNAVAILABLE | UP | LONG | NAV의 20% |
| SHORT | MIXED/UNAVAILABLE | DOWN | SHORT | NAV의 20% |
| MIXED | LONG | UP | LONG | NAV의 20% |
| MIXED | SHORT | DOWN | SHORT | NAV의 20% |
| LONG | SHORT | 모든 상태 | WAIT | 0% |
| SHORT | LONG | 모든 상태 | WAIT | 0% |
| LONG | 모든 상태 | DOWN/MIXED | WAIT | 0% |
| SHORT | 모든 상태 | UP/MIXED | WAIT | 0% |
| MIXED | MIXED/UNAVAILABLE | 모든 상태 | WAIT | 0% |

Top 5 포지션과 flow가 충돌하면 Trend가 한쪽과 같더라도 거래하지 않는다. Top 5 포지션 합의가 없더라도 최근 대형 flow와 Trend가 일치하면 작은 포지션만 허용한다.

### 4.6 위험 감점

Funding과 liquidation은 LONG/SHORT을 새로 결정하지 않는다. 최종 방향이 나온 뒤 다음 조건에서만 목표 비중을 줄인다.

- 진입 방향과 같은 쪽의 funding이 전략 config의 extreme 기준을 넘으면 목표 비중을 절반으로 축소한다.
- 최근 liquidation 데이터가 비정상적으로 크거나 stale이면 목표 비중을 절반으로 축소하거나 신규 진입을 건너뛴다.
- 두 감점이 동시에 발생하면 신규 진입하지 않고 WAIT한다.
- 감점 사유와 적용 전·후 목표 비중을 decision에 저장한다.

Funding이나 liquidation 수치가 반대 방향을 가리킨다는 이유만으로 반대 포지션을 열지는 않는다.

### 4.7 포지션 제한

- 자산별 최대 목표 비중: NAV의 40%
- 전체 절대 익스포저 합계: NAV의 100% 이하
- 여러 자산이 동시에 한도를 넘으면 `40% 신호 → 20% 신호 → 자산 거래대금` 순으로 배정하고 비례 축소한다.
- 같은 방향의 반복 신호는 목표 비중을 초과해 누적하지 않는다.
- 레버리지는 사용하지 않는다.
- 데이터 stale, 가격 누락, 비용 계산 실패 시 주문을 생성하지 않는다.

### 4.8 진입과 청산

- 판단 시점의 mark로 즉시 체결한 것으로 간주하지 않는다.
- 신호 결정 이후 처음 수집된 유효 시장 스냅샷 가격에 슬리피지를 적용해 체결한다.
- 동일한 최종 결정이 두 번 연속 확인된 뒤 신규 진입하거나 비중을 확대해 일시적 데이터 변동을 줄인다.
- 기존 포지션의 근거가 사라져 WAIT가 두 번 연속 나오면 전량 청산한다.
- 반대 방향 결정이 두 번 연속 나오면 기존 포지션을 먼저 청산한 뒤 새 방향으로 진입한다.
- 수동 청산과 손익을 보고 정하는 임의 최대 보유 시간은 사용하지 않는다.
- 시스템 장애 중에는 가상 체결을 소급 생성하지 않는다. 해당 구간은 `execution_skipped`로 남긴다.

모든 비율과 임계값은 Shadow Trading 시작 전에 config hash로 고정한다. Shadow 결과의 손익을 보고 유리한 값만 골라 공개하는 방식은 금지한다.

## 5. 회계와 체결 가정

### 5.1 NAV 계산

```text
NAV = cash
    + long position market value
    + short position unrealized PnL
    - cumulative fees
    - cumulative slippage
    + cumulative funding
```

- 기준 통화는 USD다.
- 모든 계산은 동일한 `as_of` 시장 스냅샷을 사용한다.
- 실현 손익과 미실현 손익을 분리한다.
- 일별 마지막 NAV를 별도로 고정해 차트 재계산 오류를 방지한다.

### 5.2 거래 비용

- 수수료율은 코드 상수가 아니라 전략 버전 설정에 저장한다.
- 초기에는 실제 주문 유형을 과장하지 않도록 보수적인 taker 비용을 기본으로 둔다.
- 슬리피지는 방향별로 불리하게 적용한다.
- funding은 해당 포지션 보유 시간과 수집된 funding 데이터에 따라 반영한다.
- 비용 데이터가 없으면 0으로 처리하지 않고 결과를 `incomplete`로 표시한다.

### 5.3 벤치마크

- **BTC Buy & Hold:** 같은 시작 시각에 $1,000 전액 매수, 같은 평가 시각 사용
- **Cash:** $1,000 고정
- 전략과 벤치마크의 기간 및 가격 소스가 같아야 한다.

ETH·SOL을 포함한 복합 벤치마크는 MVP 이후 검토한다. 비교 대상을 늘려 유리한 기준만 강조하지 않는다.

## 6. 데이터 모델 제안

### `paper_strategy_versions`

- `id`, `strategy_key`, `version`
- `config_json`, `config_hash`
- `status`: draft / shadow / public / retired
- `started_at`, `public_at`, `retired_at`
- 비용, 임계값, universe, 포지션 제한 포함

### `paper_decisions`

- 평가 시각과 자산
- 입력 신호 값과 원본 snapshot 참조
- Top 5 ranking 명단, 포지션 합의, 최근 Top 5 flow, 1h/4h trend
- 위험 감점 전·후 목표 비중과 LONG / SHORT / WAIT 결정
- stale·결측·충돌에 따른 실행 제외 사유

### `paper_orders` / `paper_trades`

- decision 참조
- side, quantity, decision mark, fill mark
- fee, slippage, funding
- status와 체결·건너뜀 사유

### `paper_positions`

- asset, side, quantity, average entry
- realized/unrealized PnL
- opened_at, updated_at, closed_at

### `paper_equity_snapshots`

- timestamp, cash, gross exposure
- realized/unrealized PnL
- cumulative fees/funding/slippage
- NAV와 drawdown

현재 `PulseSignalRow`와 `PulseResultRow`는 입력 근거로 재사용할 수 있지만 포트폴리오 원장은 될 수 없다. 현재 Pulse 보존 한도도 짧으므로 Paper Portfolio 원장은 독립적으로 영구 보존해야 한다.

## 7. API와 UI

### API 초안

- `GET /api/v2/paper-portfolio/summary`
- `GET /api/v2/paper-portfolio/equity?range=all`
- `GET /api/v2/paper-portfolio/positions`
- `GET /api/v2/paper-portfolio/trades?cursor=...`
- `GET /api/v2/paper-portfolio/strategy`

공개 API는 계산 결과를 읽기만 한다. 전략 시작, 리셋, 수동 주문 같은 운영 API는 외부에 노출하지 않는다.

### Dashboard teaser

- `$1,000 → 현재 NAV`
- 누적 순수익률
- BTC benchmark 대비
- 최대 낙폭
- `Forward test since YYYY-MM-DD` 표시
- 상세 페이지 링크

### 상세 페이지

1. NAV 곡선과 BTC/Cash benchmark
2. 누적 수익률, 최대 낙폭, 완료 거래 수, 승률
3. 현재 LONG / SHORT / CASH 포지션
4. 모든 거래 내역과 비용
5. 전략 버전, 입력 신호, 체결 가정
6. 가상 성과 및 한계 고지

적중률은 보조 지표로만 제공한다. `Wait` 적중처럼 거래 손익이 발생하지 않는 결과를 포트폴리오 수익과 섞지 않는다.

## 8. 사용자 문구 원칙

권장 이름:

- `HyperPulse Paper Portfolio`
- `Signal Strategy Performance`
- `가상 $1,000 성과`

피해야 할 표현:

- `검증된 수익`
- `따라 하면 얻는 수익`
- `예상 수익률`
- `AI 자동매매 수익`
- `원금 보장`, `안전한 전략`

상시 고지 초안:

> 실제 자금이 아닌 $1,000 가상 포트폴리오의 Forward Test입니다. 표시된 성과는 수수료·슬리피지·funding 가정에 따라 달라질 수 있으며 미래 수익을 보장하지 않습니다.

상세 페이지에는 계산 기준, 데이터 누락, 가상 체결의 한계와 손실 가능성을 함께 설명한다. 공개 전 서비스 대상 국가의 금융·가상자산 광고 규정을 별도로 검토한다.

## 9. 출시 단계

### Stage A — 내부 Shadow Trading

- [ ] v1 입력과 규칙 확정 및 config hash 생성
- [ ] 독립 원장과 결정 audit trail 구현
- [ ] $1,000 포트폴리오를 내부에서 시작
- [ ] 재시작·중복 스케줄에도 주문이 한 번만 생성되는지 검증
- [ ] 최소 30일 및 100개 완료 거래 중 더 늦은 조건까지 관찰
- [ ] 비용 누락, stale 데이터, 장애 구간을 샘플 검수

성과가 나쁘다는 이유만으로 Stage A를 다시 시작하지 않는다. 규칙 결함이 발견되면 원인을 기록하고 v2를 별도 시작한다.

### Stage B — Closed Beta 공개

- [ ] Beta 사용자에게 상세 성과 페이지 공개
- [ ] 모든 거래와 전략 가정 열람 가능
- [ ] 데이터 누락 및 마지막 평가 시각 표시
- [ ] 잘못된 체결·손익 계산 신고 경로 제공
- [ ] 2주 이상 계산 오류 없이 운영

### Stage C — 공개 서비스

- [ ] 가상 성과 표시와 광고 문구에 대한 법률·컴플라이언스 검토
- [ ] 공개 시작 이후 수정·중단 이력 제공
- [ ] 성과 카드가 손익과 위험을 균형 있게 표현하는지 검수
- [ ] 운영 장애 시 차트 중단 시점과 사유를 사용자에게 노출

## 10. 검증과 완료 기준

### 계산 테스트

- [ ] LONG/SHORT 진입·추가·부분/전체 청산 계산
- [ ] 방향 전환 시 두 거래로 분리
- [ ] 수수료·슬리피지·funding 부호 검증
- [ ] 동일 이벤트 재처리 시 중복 주문 없음
- [ ] 프로세스 재시작 후 cash/position/NAV 일치
- [ ] 벤치마크 시작가와 평가 시각 일치
- [ ] drawdown과 누적 수익률 재현 가능

### 데이터 품질 테스트

- [ ] 미래 시점 데이터 참조 금지
- [ ] 신호 결정 이전 가격으로 체결 금지
- [ ] stale 또는 결측 신호의 거래 차단
- [ ] 자산 universe 변경 이력 보존
- [ ] 전략 설정 hash와 각 decision 연결
- [ ] Pulse pruning과 무관하게 Paper Portfolio 원장 보존

### 제품 완료 기준

- 동일 원장으로 API와 UI의 NAV를 재계산할 수 있다.
- 시작일 이후 모든 포지션 변화에 결정과 체결 근거가 있다.
- 총수익뿐 아니라 손실, 최대 낙폭, 비용, 거래 수가 노출된다.
- 전략 버전 변경이 과거 성과를 덮어쓰지 않는다.
- 공개 전 Shadow Trading 관찰 조건과 Closed Beta 검증을 통과한다.

## 11. 핵심 위험과 대응

| 위험 | 대응 |
|---|---|
| Look-ahead bias | 결정 이후 첫 유효 스냅샷으로만 체결 |
| 좋은 기간만 선택 | 공개 시작일과 전체 이력 고정, 리셋 이력 공개 |
| 거래 비용 과소평가 | 보수적인 fee/slippage, net 성과 기본 표시 |
| 작은 표본의 과장 | 운영 기간과 완료 거래 수를 성과 옆에 표시 |
| 전략 변경으로 비교 왜곡 | immutable version + config hash + 별도 곡선 |
| 데이터 장애 중 가짜 체결 | 소급 체결 금지, skipped/incomplete 상태 기록 |
| 적중률과 수익률 혼동 | Pulse 결과와 거래 원장을 분리 |
| 성과 광고 오해 | 가상 성과 고지, 가정·위험·손실을 동등하게 노출 |

## 12. 최종 결정

BL-18은 HyperPulse의 핵심 신호가 실제 거래 의사결정에 어떤 결과를 만드는지 보여주는 **제품 신뢰 기능**으로 추진할 가치가 있다. 단, 공개용 차트를 먼저 만들지 않고 독립 원장, 고정 전략, 비용 반영, audit trail을 먼저 완성한다.

MVP 성공 기준은 높은 수익률이 아니다. **성과가 좋든 나쁘든 동일한 규칙과 전체 기록을 사용자가 검증할 수 있는 상태**가 성공 기준이다.

## 13. 외부 참고

- [SEC · Investment Adviser Marketing](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/investment-adviser-marketing) — 가상 성과의 계산 기준·가정·위험·한계와 비용 차감 성과 표시 원칙 참고
- [NFA Rule 2-29](https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=RULE+2-29&Section=4) — hypothetical performance 고지 방식 참고

위 자료는 제품 표시 원칙을 정하기 위한 참고이며 HyperPulse에 적용될 관할 법률 판단을 대신하지 않는다.
