# HyperPulse Agent Guide

## Project Overview

HyperPulse is an AI-powered intelligence platform for Hyperliquid traders.

**Product goal:** strong *current-moment* insights that are simple, reliable, and actionable for trading — not selling accumulated data or dense metric dumps. See `README.md` (Product Goals), `docs/ARCHITECTURE.md` (constraints), and `docs/PRODUCT_BACKLOG.md` (canonical backlog + checkboxes).

- **Phase 1**: Whale Alerts, Trader Profiles, Basic Liquidation Radar
- **Phase 2**: Collectors, persistence, AI strategy inference, smart money ranking, Telegram alerts

## Repository Structure

```
HyperPulse/
├── frontend/                 # Next.js 15 + TypeScript + Tailwind
│   └── src/app/
│       ├── insights/         # AI strategy inference UI
│       ├── rankings/         # Smart money ranking UI
│       └── alerts/           # Telegram alert history UI
├── backend/
│   └── app/
│       ├── collectors/       # Hyperliquid collectors + scheduler
│       ├── services/         # inference, ranking, alerts, cache, store
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
