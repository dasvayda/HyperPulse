# HyperPulse

AI-powered intelligence platform for Hyperliquid traders.

HyperIntel provides:

- Whale tracking
- Smart money analysis
- Liquidation radar
- AI-generated market insights
- Position intelligence

Unlike traditional whale alert services, HyperIntel focuses on understanding trader behavior, inferred strategies, and market context.

---

## Features

### Whale Intelligence

Track profitable traders on Hyperliquid.

Features:

- Position entry detection
- Position close detection
- PnL estimation
- Win-rate analysis
- Holding-time analysis
- Strategy inference

Example:

Trader A entered ETH Long.

AI Analysis:

- Historical win rate: 71%
- Average holding time: 9 hours
- Similar setup occurred 12 times
- Average profit after entry: +6.8%

Inferred strategy:
Momentum breakout trading

---

### Liquidation Radar

Monitor liquidation clusters across markets.

Features:

- Long liquidation zones
- Short liquidation zones
- Heatmaps
- Open interest shifts
- Funding analysis

Example:

BTC

145k
↑
$420M short liquidation zone

138k
↓
$680M long liquidation zone

---

### AI Market Commentary

Generate contextual explanations.

Example:

Why are whales accumulating ETH?

AI Summary:

- Open interest rising
- Funding remains neutral
- Spot inflows increasing
- Historical pattern similarity score: 82%

---

## Architecture

See:

docs/ARCHITECTURE.md

---

## Tech Stack

Frontend

- Next.js
- TypeScript
- Tailwind
- TradingView Charts

Backend

- FastAPI
- Python
- PostgreSQL
- Redis

AI

- OpenAI
- DeepSeek
- LangGraph

Infrastructure

- Railway
- AWS
- Docker

---

## Roadmap

Phase 1

- Whale Alert
- Trader Profiles
- Basic Liquidation Radar

Phase 2

- AI Strategy Inference
- Smart Money Ranking
- Telegram Alerts

Phase 3

- Personalized AI Trading Coach
- Portfolio Intelligence
- Predictive Analytics

---

## License

MIT
