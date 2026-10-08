# 데이터 신뢰·Paper Portfolio 검증 — 2026-10-09

## 수집 실패 표시

시장 조회 실패 시 마지막 성공 시각을 보존한다. 지갑 조회는 성공/전체
주소 수와 `ok`/`partial`/`error`를 pipeline API로 반환한다. 실패한 주소의
이전 포지션을 유지하되 전역 헤더에 데이터 불완전 상태를 표시한다.
상태 조회 자체가 실패한 경우도 정상 Live로 계속 표시하지 않는다.
collector 상태는 프로세스 메모리에 있으며 재시작 시 다시 확인한다.

## 원천 검토에서 발견한 청산 오분류

기존 수집기는 public `recentTrades` 전체를 청산으로 저장했다. 일반 거래의
매수/매도 방향만으로 청산 여부 또는 청산된 포지션 방향을 입증할 수 없다.
[공식 API 문서](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
및 [WebSocket 타입](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions)의
일반 거래와 user liquidation 이벤트 구분을 기준으로 해당 경로를 중지했다.

- 기존 DB 원장은 삭제하지 않고 audit 대상으로 보존한다.
- live 수집기는 기존 메모리 이벤트를 격리하고 source error를 반환한다.
- 청산 집계는 확인된 feed가 도입되기 전까지 unavailable로 취급한다.
- 실제 `liquidationPx` 기반 지갑별 위험 정보는 계속 제공한다.
- 불완전한 source가 존재하면 Paper Portfolio 평가를 건너뛴다.

향후 과제: 검증된 청산 feed 도입, 과거 오분류 이벤트의 집계 제외,
과거 Insights/Brief/가상매매에 사용된 청산 근거의 재검수. 기존 가상매매
기록을 삭제하거나 정상적인 검증 표본으로 확정하지 않는다.

## 로컬 원장 audit

다음 명령은 SQLite를 읽기 전용으로 열며 앱이나 collector를 기동하지 않는다.

```powershell
python backend/scripts/audit_paper_portfolio.py backend/hyperpulse.db
```

2026-10-09 검사 결과:

- 전략: `top5_whale_trend_v1`
- 기록된 시간 bucket: 37개 (시간 표본으로 환산하면 1.54일)
- 완전히 종료된 포지션: 3건, 전체 체결: 9건
- 기록 구간: 2026-10-07 03:16 UTC ~ 2026-10-08 15:01 UTC
- 현금: $995.750459, 누적 순 funding: +$0.030017
- 체결금액·수수료·슬리피지·실현손익 누적, 현금 및 equity NAV 등식 불일치: 0건
- 30일·100개 완료 거래 기준: 미충족

이 검사는 회계 등식의 정합성을 확인한다. 실제 funding 이력과의 정합성,
최초 신호의 원천 타당성, 연속 운영 여부를 승인하는 검사가 아니다.
특히 이전 청산 입력 오분류 때문에 기존 표본의 전략 유효성은 보류한다.
`reduce`는 완전히 종료된 포지션 수에 포함하지 않는다.

고정 사례 테스트는 롱/숏 양 방향에서 진입·종료 가격, 수수료, 슬리피지의
단일 반영, funding 지급/수령 방향과 NAV를 검증한다. 운영 DB·도메인은
이번 검증의 선행 조건이 아니다.
