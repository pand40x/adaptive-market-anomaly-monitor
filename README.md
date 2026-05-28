# Adaptive Market Anomaly Monitor

Python-based market anomaly monitor for crypto, stocks, indexes, forex, and commodities.

Crypto data comes from Binance klines. Stocks, indexes, forex, and commodities come from Yahoo Finance.

## Quick Start

```bash
uv sync
uv run market-watch --help
uv run pytest
```

## Core Commands

```bash
uv run market-watch backfill --years 3
uv run market-watch scan
uv run market-watch backtest --years 3
uv run market-watch optimize --years 3
uv run market-watch evaluate-alerts
```

Data is stored in MongoDB. For local development, run the included Mongo service:

```bash
docker compose up -d mongo
```

The local Compose setup exposes Mongo on `localhost:27018` to avoid clashing with any existing Mongo service.

## Suggested Operating Loop

Run these on a schedule:

```bash
uv run market-watch backfill --years 3
uv run market-watch calibrate-classes --years 3
uv run market-watch anomaly-benchmark --years 3
uv run market-watch scan
uv run market-watch evaluate-alerts
uv run market-watch active-anomalies
```

For Dokploy or another Docker host, build the included `Dockerfile` and provide `MONGO_URI` / `MONGO_DATABASE`. Put real API values in `.env.local`; the file is intentionally ignored by Docker copy rules.

Continuous mode:

```bash
uv run market-watch worker --years 3 --cycle-minutes 60 --optimize-every-cycles 24
```

Telegram alerts use `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `.env.local`.
To discover the chat id, send the bot any message and run:

```bash
uv run market-watch telegram-chat-ids
```

## Markets Covered

- Crypto: Binance klines, 24/7 rhythm.
- US stocks and indexes: Yahoo Finance, weekday/session-aware rhythm.
- Forex: Yahoo Finance, weekday FX rhythm.
- Commodities: Yahoo Finance futures symbols.
- BIST: Yahoo Finance `.IS` symbols with Istanbul session metadata.

Symbols are normalized in user-facing output, so coded tickers like `GC=F`, `EURUSD=X`, and `THYAO.IS` show readable names.

## Active Anomaly Tracking

After `scan`, each alert is tracked as:

- `pending`: not enough future bars yet.
- `confirmed`: follow-through move happened inside the configured window.
- `expired`: follow-through did not happen inside the window.
