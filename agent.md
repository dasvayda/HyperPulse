# HyperPulse Agent Guide

## Project Overview

HyperPulse is an AI-powered intelligence platform for Hyperliquid traders.

**Product goal:** strong *current-moment* insights that are simple, reliable, and actionable for trading — not selling accumulated data or dense metric dumps. See `README.md` (Product Goals), `docs/ARCHITECTURE.md` (constraints), and `docs/PRODUCT_BACKLOG.md` (canonical backlog + checkboxes).

**AI Insights page:** Market Brief hero is a 3-slot TL;DR (now = mark + vs prev day + funding; short = tracked book $/% + sampled 1h liq; however = tension or confirm). Prefer longs/shorts/Wait is a badge, not in the headline. Optional **15m Pulse** chip (direction probs + tick strip) sits beside Prefer — separate from Evidence card `confidence` (rule vote strength, not win rate). Coin tabs are live volume Top3. Dashboard teaser uses `tldr.now` (+ optional pulse one-liner). Evidence cards and the cohort heatmap (Smart / Rest / All long share, majors + thin coins) stay rule-based. Trader strategy tags are secondary.

**Rate-limited collectors:** `collectors/fills.py` (`userFillsByTime`) is fetched per address on trader-detail requests with a short cache, never swept across the tracked universe on a timer.

**LLM usage:** Primary = periodic market-wide Market Brief (`market_brief.py`). Coin briefs are rule/template only. Secondary = trader strategy labels. Market BUY/SELL evidence cards are **not** LLM.

Brief inputs: tape (mark, vs prev day, funding), Top3 whale book (+ per-asset), book-wide, coin stances, Top3 funding + extreme funding, sampled liq 1h/24h, biggest positions, coverage. Headline is descriptive; suggestions live in a collapsed "What this implies" block. Tracked-whale sample, not the full market.

- **Phase 1**: Whale Alerts, Trader Profiles, Basic Liquidation Radar
- **Phase 2**: Collectors, persistence, AI strategy inference, smart money ranking, Telegram alerts

## Repository Structure

```
HyperPulse/
├── frontend/                 # Next.js 15 + TypeScript + Tailwind
│   └── src/app/
│       ├── insights/         # Market Brief hero + rule evidence + style tags
│       ├── rankings/         # Smart money ranking UI
│       └── alerts/           # Telegram alert history UI
├── backend/
│   └── app/
│       ├── collectors/       # Hyperliquid collectors + scheduler
│       ├── services/         # inference, market_brief, ranking, alerts, cache, store
│       ├── models/           # Pydantic schemas + SQLAlchemy ORM
│       └── routers/          # api.py (v1), v2.py (phase 2)
├── docs/
├── docker-compose.yml
└── agent.md
```

## Design System (Nansen-inspired)

| Token | Value | Usage |
|-------|-------|-------|
| `bg-primary` | `#0b0e11` | Page background |
| `bg-surface` | `#12171c` | Cards, sidebar |
| `bg-elevated` | `#1a2028` | Hover, elevated panels |
| `accent` | `#00ffa3` | Primary CTA, active nav |
| `text-primary` | `#ffffff` | Headings, values |
| `text-muted` | `#8b949e` | Labels, metadata |
| `positive` | `#00ffa3` | Up trends |
| `negative` | `#ff6b6b` | Down trends |
| `border` | `#2a3140` | Card borders |

Typography: Inter (sans-serif). Border radius: 8–12px.

## Phase 2 Pipeline

```
Collectors -> Store/DB/Redis -> Feature/Ranking -> AI Inference -> Alerts -> API/UI
```

- Default DB: SQLite (`hyperpulse.db`) for local dev
- Redis optional (falls back to in-memory cache)
- AI provider auto-selects OpenAI/DeepSeek, otherwise heuristic classifier
- Telegram alerts queue locally when bot token is missing

## Development Commands

```bash
# Optional infrastructure
docker compose up -d postgres redis

# Backend (from backend/)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm install
npm run dev
```

## Verification

```bash
# Health + pipeline
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/pipeline/status
curl http://localhost:8000/api/v2/rankings
curl http://localhost:8000/api/v2/insights
curl http://localhost:8000/api/v2/insights/brief
curl http://localhost:8000/api/v2/alerts

# Force one pipeline cycle
curl -X POST http://localhost:8000/api/v2/pipeline/run
```

## API Base

- Local: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Phase 1: `/api/v1/*`
- Phase 2: `/api/v2/*`

## Conventions

- Frontend pages under `frontend/src/app/`
- Shared UI in `frontend/src/components/`
- API client in `frontend/src/lib/api.ts`
- Backend routers in `backend/app/routers/`
- Seed fallback data in `backend/app/data/seed.py`
- Runtime state in `backend/app/services/store.py`

## Next Steps (Phase 3)

- Personalized AI trading coach
- Portfolio intelligence
- Predictive analytics
- Full Hyperliquid account WebSocket collectors

## writing code rule (코드작성 규칙)
- 모듈화를 원칙으로 하되, 파편화는 경계한다.
- 인간과 AI 모두에게 합리적이고, 우아한 코드를 작성한다.

## Design rule
- 프론트 엔드의 UI는 User 관점에서 친화적이고, 의미있는 내용인지 검증하고 완료한다.

## Copy & terminology (리테일 트레이더)

User-facing 문자열(UI 라벨, insight/alert 문장, Telegram, stance 설명)은 **리테일 트레이더가 채팅·텔레그램에서 바로 알아듣는 말**로 쓴다. 리서치·애널리스트·기관 톤은 피한다.

적용 범위: `frontend` 카피, `inference` / alert 요약, 테이블·카드 라벨. 내부 변수명·코드 주석에는 강제하지 않는다.

| Prefer (친숙) | Avoid (낯설거나 애매) |
|---------------|----------------------|
| Prefer longs / Prefer shorts | Buy bias / Sell bias / Lean BUY·SELL |
| Mostly long / Mostly short / Long heavy / Short heavy / Mixed | Slightly bullish·bearish, Indecisive, directional bias |
| Cut longs / Cover shorts / Wait | Crowding thesis, magnet asymmetry (설명 없이) |
| BUY / SELL / HOLD 배지 + 짧은 행동 문장 | 배지 없이 soft 슬랭만 나열 |

규칙:
- 한 줄에 **행동**이 드러나야 함 (롱/숏/대기/줄이기).
- 약어·슬랭은 리테일이 이미 쓰는 것만 (long/short, funding, liq, OI). 새로 만든 제품어는 쓰지 않는다.
- 경쟁 제품(CMM 등)의 애널리스트형 라벨을 그대로 복제하지 않는다.
- 문구가 애매하면: “이 문장을 텔레그램에 붙여넣어도 바로 이해되나?”로 검증한다.
