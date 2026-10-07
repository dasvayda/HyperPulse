# HyperPulse Launch Plan

| | |
|--|--|
| 갱신 | 2026-10-06 (공개 런칭 중간 점검) |
| 현재 판단 | 핵심 제품 MVP 완료 · Closed Beta 조건부 가능 · 공개 런칭 준비 미완료 |
| 기능 백로그 | [PRODUCT_BACKLOG.md](./PRODUCT_BACKLOG.md) |

## 목적

현재 HyperPulse는 핵심 분석 기능과 Telegram 채널 알림이 구현된 상태다. 이 문서는 기능 backlog와 별도로, 실제 사용자에게 서비스를 제공하기 위한 운영 준비와 출시 기준을 정의한다.

기본 전략은 한 번에 공개하지 않고 다음 세 단계로 위험을 줄이는 것이다.

1. 운영 기반 정비
2. 제한된 사용자 대상 Closed Beta
3. 공개 런칭 및 안정화

각 단계는 기능 개수보다 안정성, 데이터 신뢰성, 장애 대응 가능 여부를 기준으로 종료한다.

## 현재 상태 요약

- 핵심 제품 기능: 대부분 완료
- Telegram: 단일 채널 발송 가능, Whale Move/Big Trade/Market Brief/LIQ WATCH·DANGER 운영
- Paper Portfolio: `$1,000` Forward Test 구현 완료, Shadow 관찰 중
- 프론트 production build: 컴파일 및 타입 검사 통과
- 백엔드 단위 테스트: 2026-10-06 기준 `69 passed, 1 skipped`
- 인증/사용자 계정: 없음
- 사용자별 Telegram 구독: 없음
- production Docker 설정: 개발/production compose 분리와 컨테이너 healthcheck 완료, 실제 배포·rollback 검증 필요
- 모니터링/알림/백업: 운영 수준 보완 필요

제품의 핵심 가치는 검증 가능한 상태다. 상위 고래 포지션, 최근 흐름, 시장 trend, funding과 실제 `liquidationPx`를 짧은 판단과 Telegram 알림으로 묶는 구성은 Hyperliquid 재량 트레이더에게 명확한 사용 이유가 있다.

다만 현재는 공개 런칭 직전이 아니다. **초대 기반 Closed Beta를 준비하는 단계**이며, 불특정 사용자 대상 공개 전에는 아래 네 가지 게이트를 모두 통과해야 한다.

| 공개 런칭 게이트 | 현재 | 핵심 미완료 항목 |
|---|---|---|
| 운영 안전성 | 미완료 | 인증, 운영 API 보호, migration, 백업/복구, 장애 감지 |
| 데이터 신뢰 | 일부 완료 | 화면별 freshness, coverage·출처·판단 근거, degraded mode |
| 사용자 관련성 | 미완료 | 관심 코인/알림 선택, Telegram deep link, 가입·해지 동선 |
| 성과 표현 | 관찰 중 | Paper Portfolio 30일·100개 완료 거래, 한계 고지, 컴플라이언스 |

---

## Phase 1 — 운영 기반 정비

### 목표

서비스를 외부에 공개하기 전에 보안, 배포, 데이터 보존, 장애 감지의 최소 기준을 갖춘다.

### 범위

#### 보안과 접근 제어

- [ ] 최소한의 사용자 인증 또는 초대 기반 접근 제어 추가
- [ ] 모든 공개 API와 특히 pipeline 실행 API 보호
- [x] `POST /api/v2/pipeline/run` 운영 토큰 보호 (production/staging에서 토큰 미설정 시 fail closed)
- [ ] production CORS 도메인 제한
- [x] API 문서 노출을 `API_DOCS_ENABLED`로 제어
- [x] CORS credential 허용을 `CORS_ALLOW_CREDENTIALS`로 제어하고 기본값을 비활성화
- [ ] PostgreSQL/Redis 기본 자격 증명을 환경변수 또는 secret store로 이동
- [x] 운영 환경에서 API 문서 노출 정책 결정: production은 `API_DOCS_ENABLED=false` 권장
- [ ] `.env`, Telegram token, AI API key가 로그·오류 화면에 노출되지 않는지 점검

#### 배포

- [x] production backend에서 `--reload` 제거
- [x] production frontend를 `next build` + standalone server로 실행
- [x] 개발용 compose와 production compose 분리
- [ ] HTTPS 및 도메인 연결
- [x] backend/frontend/DB/Redis 컨테이너 healthcheck 추가
- [x] 애플리케이션 readiness에서 DB/Redis/collector 상태 구분 (`GET /health/ready`; Redis memory fallback 별도 표시)
- [ ] 배포 및 rollback 절차를 문서화

#### 데이터와 운영

- [ ] PostgreSQL을 production 기본 DB로 확정
- [ ] Alembic 등 정식 schema migration 도입
- [ ] DB 백업 및 복구 테스트
- [ ] Redis 장애 시 동작과 재시작 후 복구 범위 명시
- [ ] Hyperliquid, AI provider, Telegram API의 timeout/retry/backoff 정책 점검
- [x] Telegram 발송 실패 재시도와 실패 이벤트 기록 추가 (최대 3회; 실패는 alert history와 최근 Telegram log에 보존)
- [x] 동일 Hyperliquid 원본 이벤트 ID의 Telegram 재발송 차단 (성공 건은 영구 차단, 실패 건은 같은 alert record로 재시도)

#### 관측성

- [ ] collector/inference/ranking/alert별 마지막 성공 시각 기록
- [ ] 외부 API 오류율과 latency 기록
- [ ] 로그 수집 및 보관 정책 결정
- [ ] 서비스 장애 및 Telegram 발송 실패 알림 채널 마련
- [ ] 운영자용 상태 확인 절차 작성

#### 데이터 신뢰 표시

- [x] Dashboard, Insights, Whale Alerts, Liquidations, Ranking에 collector freshness/stale 상태를 전역 헤더로 일관되게 표시
- [x] tracked whale 표본의 규모와 coverage를 전체 Hyperliquid 시장으로 오해하지 않도록 Insights·Smart Money 화면에 설명
- [ ] 주요 시그널에서 사용한 지갑/rank, 포지션 delta, 시장 확인 근거를 확인할 수 있는 provenance 화면 또는 펼침 영역 제공
- [ ] collector 일부 실패 시 마지막 정상 데이터와 degraded 상태를 구분하고 새 데이터처럼 표시하지 않음
- [x] Smart Money Score와 whale rank의 산정 기준·한계를 사용자 가까이에 공개 (2026-10-08: tracked 표본·계정가치 선별·과거 성과 정렬과 현재 포지션 매매 등급이 아님을 Ranking 화면에 명시)

#### 검증

- [x] `pytest` 실행 의존성 고정
- [x] backend 단위 테스트 전체 통과 (`69 passed, 1 skipped` · 2026-10-06)
- [ ] API 통합 테스트 추가
- [x] frontend production build 통과
- [ ] 핵심 화면 E2E smoke test 추가
- [ ] collector 중단, DB 재시작, Telegram 실패, 외부 API timeout 시나리오 점검

### Phase 1 종료 기준

- 인증되지 않은 사용자가 운영 API를 실행할 수 없다.
- 새 환경에서 한 번의 문서화된 절차로 배포할 수 있다.
- DB 백업에서 실제 데이터를 복구할 수 있다.
- collector와 Telegram 장애를 운영자가 감지할 수 있다.
- backend 테스트와 frontend build가 CI 또는 배포 전 검사에서 통과한다.
- 장애 발생 시 rollback 방법이 검증되어 있다.

### 중단 조건

- secrets가 소스 또는 로그에 노출됨
- DB 복구가 검증되지 않음
- pipeline이 중복 실행되거나 장애 후 무한 반복됨
- Telegram 실패가 사용자에게 조용히 유실됨

---

## Phase 2 — Closed Beta

### 목표

소수의 실제 사용자에게 제공해 데이터 신뢰성, 사용성, 알림 품질을 검증한다.

권장 규모는 운영자가 직접 피드백할 수 있는 5~20명이다.

### 범위

#### 사용자 경험

- [ ] 로그인 또는 초대 링크 기반 접근 제공
- [ ] 첫 방문 온보딩 추가
- [ ] HyperPulse가 추적하는 대상과 데이터 갱신 주기 설명
- [x] Telegram 채널 가입 링크를 `/alerts`에 노출 (`NEXT_PUBLIC_TELEGRAM_CHANNEL_URL`; public URL 또는 private invite URL)
- [ ] 첫 방문 온보딩에도 Telegram 채널 가입 링크 노출
- [ ] 알림이 없거나 데이터가 stale일 때 명확한 안내 제공
- [ ] 문의/버그 신고 경로 제공
- [x] Telegram 알림에서 관련 고래·청산·Market Brief 근거 화면으로 이동하는 deep link 제공 (`PUBLIC_APP_URL` 설정 시)

#### Telegram 운영

- [ ] 채널 공개 링크 또는 private invite link 확정
- [ ] 봇의 채널 관리자 권한과 게시 권한 확인
- [ ] 알림 형식과 빈도에 대한 사용자 안내
- [x] 발송 성공률과 실패율 측정 (`GET /api/v2/alerts/summary`, Alerts 화면 최근 24h 표시)
- [ ] 중복 알림, 늦은 알림, 잘못된 stale 표시 수집
- [ ] 초기에는 단일 채널 운영을 유지하고 사용자별 구독은 후속 범위로 명시

#### 데이터 품질

- [ ] 주요 화면의 as-of 시각과 stale 표시 검증
- [ ] Hyperliquid 데이터 누락/지연 케이스 확인
- [ ] Smart Money, whale size, funding, liquidation 문구가 실제 원천 데이터와 일치하는지 샘플 검수
- [ ] AI 결과가 실패하거나 heuristic fallback으로 전환될 때 UI가 오해를 만들지 않는지 확인
- [ ] Whale/Smart Money 시그널의 15분·1시간 후 가격 결과를 표본 검수해 잘못된 해석 패턴 기록

#### Paper Portfolio 검증

- [x] `top5_whale_trend_v1` 규칙·비용 가정·version hash 동결
- [x] `$1,000` Forward Test 원장과 NAV/BTC benchmark/최대 낙폭/거래 내역 구현
- [ ] 최소 30일 및 100개 완료 거래 Shadow Trading 확보
- [ ] 거래·equity·수수료·slippage·funding 계산 audit 표본 검증
- [ ] Beta 화면에 `실험 전략`, 가상 체결, 손실 가능성, 표본 수를 명확히 표시
- [ ] 관찰 중인 수익률을 마케팅 성과나 실제 수익 보장처럼 사용하지 않음

#### 제품 지표

- [ ] 일간 활성 사용자
- [ ] 재방문율
- [ ] Insights/Market Brief 열람률
- [ ] Telegram 채널 가입자 수
- [ ] Telegram 발송 성공률
- [ ] 데이터 stale 발생 시간
- [ ] 사용자 신고 오류 수와 평균 해결 시간

### Phase 2 종료 기준

- 2주 이상 중대한 장애 없이 운영된다.
- 테스트 사용자들이 핵심 화면과 Telegram 알림을 혼동 없이 사용한다.
- 치명적인 잘못된 알림 또는 데이터 출처 오류가 없다.
- Telegram 발송 성공률과 장애 대응 절차가 확인된다.
- 가장 빈번한 사용자 피드백을 backlog에 반영하거나 의도적으로 보류한다.
- 운영자가 하루 1회 상태 점검으로 서비스 상태를 파악할 수 있다.
- Paper Portfolio가 공개되는 경우 기간·거래 수·비용·최대 낙폭과 전체 이력이 함께 보인다.

### 중단 조건

- 잘못된 방향성/수치의 알림이 반복됨
- 데이터 stale 상태가 사용자에게 숨겨짐
- Telegram 메시지 유실 또는 중복이 지속됨
- 운영자가 장애 원인을 추적할 수 없음
- 사용자 접근 제어 우회가 발견됨

---

## Phase 3 — 공개 런칭 및 안정화

### 목표

불특정 사용자가 접근해도 예측 가능한 품질과 운영 대응이 가능한 상태로 전환한다.

### 공개 전 필수 항목

- [ ] 공개 서비스 URL과 HTTPS 확정
- [ ] 회원가입/로그인/세션 만료 정책 확정
- [ ] 개인정보처리방침, 이용약관, 데이터 사용 안내 게시
- [ ] 투자 조언이 아닌 데이터 기반 분석/알림이라는 한계 고지
- [ ] rate limit과 abuse 방지 적용
- [ ] API 및 frontend 오류 페이지 정비
- [ ] 사용자별 Telegram 구독/해지 필요 여부 결정
- [ ] 최소 관심 코인 watchlist와 알림 종류 on/off 제공
- [ ] Telegram 가입·해지·알림 빈도·지연 가능성을 한 화면에서 안내
- [ ] 비용 상한과 외부 API 사용량 모니터링 설정
- [ ] 온콜 또는 장애 대응 담당자와 대응 시간 정의
- [ ] tracked whale 표본, Smart Money Score, AI/heuristic 사용 여부를 서비스 내에서 설명
- [ ] Paper Portfolio 공개 조건 충족 여부와 공개 시작일·전략 버전·전체 이력 고정

### 공개 런칭 제품 계약

공개 서비스의 첫 화면과 알림은 다음 질문에 답해야 한다.

1. **무슨 일이 생겼는가?** — 가격·포지션·funding·liq 변화
2. **누가 어느 방향인가?** — tracked Top whale/Smart Money의 표본과 방향
3. **사용자가 무엇을 확인해야 하는가?** — Long/Short/Wait 또는 위험 축소 행동
4. **얼마나 최신이고 믿을 수 있는가?** — as-of, stale, coverage, source

AI 문장 자체를 핵심 가치로 판매하지 않는다. 공개 런칭의 핵심 약속은 **상위 고래 포지션 + 최근 흐름 + 시장 상태 + 청산 위험을 검증 가능한 근거와 함께 빠르게 전달하는 것**이다.

### 출시 방식

1. 5~20명 private Closed Beta
2. watchlist·가입 동선·운영 지표를 갖춘 invite-only 공개
3. 30일 안정성 확인 후 공개 가입 확대

대규모 홍보와 Paper Portfolio 성과 홍보는 오류율, 비용, Shadow 표본과 컴플라이언스 검토가 안정된 후 진행한다.

### Phase 3 종료 기준

- 30일간 치명적 장애 없이 운영된다.
- 주요 의존성 장애에 대한 fallback 또는 사용자 안내가 있다.
- 백업/복구와 rollback을 실제로 재검증했다.
- 보안 점검과 기본 부하 테스트를 통과했다.
- 사용자 문의 및 장애 처리 SLA를 지킬 수 있다.

---

## 출시하지 않는 기능

다음 항목은 현재 공개 런칭의 선행 조건으로 보지 않는다.

- 전체 네트워크의 모든 지갑을 대상으로 하는 완전한 스캐너
- 30일 이상 장기 청산 heatmap
- 다년간 backtest warehouse
- Binance식 자유 대화형 AI 채팅
- 고급 주문/stop radar
- 개인화된 portfolio coach
- 실제 주문 실행 또는 지갑 서명 권한 요청

이 기능들은 현재 제품 목표와 운영 리스크를 고려해 공개 런칭 이후 별도 판단한다.

읽기 전용 Hyperliquid 주소 연결과 포지션 기반 알림은 실제 주문 기능과 분리한다. 초기 공개 런칭의 필수 조건은 아니지만, watchlist 다음의 최우선 개인화 후보로 둔다.

## 실행 우선순위

### L0 — Closed Beta를 열기 전에

1. 인증/초대 접근과 `POST /api/v2/pipeline/run` 보호
2. 전 화면 freshness/degraded 상태와 tracked-sample 설명
3. Telegram 가입 링크·deep link·발송 성공/실패 기록
4. PostgreSQL migration, 백업/복구, rollback 검증
5. collector/Telegram 장애 알림과 운영 runbook

### L1 — Invite-only 공개 전에

1. 관심 코인 watchlist와 알림 on/off
2. provenance 상세: 사용 지갑, rank, delta, market confirmation
3. 이용약관·개인정보·투자 비조언·데이터 한계 고지
4. API rate limit, abuse 방지, 기본 부하 테스트
5. Paper Portfolio Shadow 기준 충족 또는 공개 화면 비활성화 유지

### L2 — 공개 가입 확대 전에

1. 30일 안정 운영과 오류·비용 상한 확인
2. 알림 결과의 15분·1시간 사후 측정
3. 읽기 전용 지갑 연결과 포지션 연계 알림의 우선순위 재평가
4. 사용자 피드백과 이탈 원인을 근거로 유료 기능 범위 결정

## 의사결정 기준

기능이 backlog에 `[x]`로 표시되어 있어도 다음 질문에 `아니오`라면 출시 완료로 보지 않는다.

1. 사용자가 결과의 기준 시각과 출처를 이해할 수 있는가?
2. 데이터 수집 또는 외부 API가 실패해도 오해를 만들지 않는가?
3. 운영자가 장애를 감지하고 복구할 수 있는가?
4. 잘못된 알림과 보안 사고를 막을 수 있는가?
5. 현재 사용자 수보다 커져도 비용과 성능을 통제할 수 있는가?
