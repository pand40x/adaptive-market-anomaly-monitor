# Market Anomaly Monitor Memory

## Project Intent

Build an adaptive market anomaly monitoring system for crypto, stocks, indexes, forex, and commodities.

The system should:
- collect regular market data from Binance for crypto and Yahoo Finance for stocks, indexes, forex, and commodities;
- analyze each market class with its own natural cadence;
- combine price deviation, volume expansion, volatility breakout, and short-term total movement into anomaly signals;
- explain every alert in clear user-facing language;
- measure whether each alert was followed by a meaningful price move;
- backtest and optimize thresholds/weights on historical data;
- keep separate settings per asset class to reduce noise and improve meaningful-move capture.

## Operating Preferences

- Keep progress updates short and non-technical.
- Do not expose secrets from `.env.local`.
- Treat this file as project memory and keep it current at each major stage.
- Prefer precise, end-to-end implementation decisions instead of open-ended options.

## Stage Log

### 2026-05-28 1. Context and Architecture Choice

The workspace was empty and not a git repository. I chose a Python CLI/service core because the first need is reliable data collection, backtesting, optimization, and auditable alert evaluation. A web UI can be added later without changing the analysis core.

### 2026-05-28 2. Test-First Scope

Initial tests will cover the most important behaviors: anomaly scoring, alert explanation, follow-through evaluation, and optimizer selection of lower-noise parameter sets per market class.

### 2026-05-28 3. Core Implementation

Added the Python package structure, default asset universe, signal scoring, alert explanations, follow-through evaluation, backtest optimization, data fetchers, storage, and CLI commands. During the first test run, follow-through timing was clarified to report the first meaningful threshold confirmation rather than the largest later move.

### 2026-05-28 4. Binance Backfill Depth

Added test coverage for Binance pagination because a single Binance kline response cannot cover 3-5 years. Updated the Binance fetcher to walk pages with `startTime` and `endTime`, so crypto backfill can collect multi-year history instead of only the most recent 1000 candles.

### 2026-05-28 5. Adaptive Parameter Reuse

Added storage support for loading saved optimized thresholds and weights. Scan and alert-evaluation commands now prefer optimized settings when they exist, falling back to default market-class settings otherwise.

### 2026-05-28 6. Follow-Through Metric Cleanup

Real 1-year backtest smoke testing worked against Binance and Yahoo Finance. It revealed that an alert with no favorable follow-through could report a negative max move. Added a regression test and clamped unfavorable follow-through to 0% so user-facing evaluations stay clear.

### 2026-05-28 7. Deployment Readiness

Added Docker and compose files so the monitor can be deployed on Dokploy or another Docker host. No `.env.local` file was present in the workspace at that stage, so no Dokploy API call was attempted and no secrets were read or printed.

### 2026-05-28 8. Regular Operation

Added `cycle` and `worker` CLI commands. `cycle` runs backfill, optional optimization, scan, and follow-through evaluation once. `worker` repeats cycles on a schedule and refreshes optimization periodically, matching the need for regular adaptive monitoring.

### 2026-05-28 9. End-to-End Verification

Ran `market-watch cycle --years 1 --tune` successfully before the MongoDB migration. It saved 8760 hourly candles for BTCUSDT and ETHUSDT, roughly one year of Yahoo daily candles for the default stock/index/commodity/forex assets, optimized parameters, scanned anomalies with explanations, and saved 53 alert follow-through evaluations.

### 2026-05-28 10. Workspace Hygiene

Added `.gitignore` so virtualenvs, caches, local generated market data, and real environment files stay out of source control.

### 2026-05-28 14. MongoDB Migration

User explicitly rejected SQL storage and allowed MongoDB with local Docker. Replaced the storage layer with MongoDB collections, added `pymongo`, changed Docker Compose to run a `mongo:7` service, updated `.env.local` to use `MONGO_URI=mongodb://localhost:27018/market_anomaly`, removed the old local database artifact, and added class calibration / anomaly benchmark CLI commands that store and read active settings from MongoDB.

### 2026-05-28 15. 3-Year Calibration and Benchmark

Adjusted local Mongo to use host port `27018` because `27017` was already allocated. Ran 3-year class calibration on MongoDB. Selected active settings: crypto score 4.0 / follow-through 3.0% with 51 historical alerts and 39.22% precision; stock score 3.2 / follow-through 3.0% with 4 alerts and 100% precision; index score 3.2 / follow-through 3.0% with 2 alerts and 50% precision; forex score 1.8 / follow-through 1.0% with 2 alerts and 100% precision; commodity score 4.0 / follow-through 3.0% with 2 alerts and 100% precision. Ran anomaly benchmark with active settings and then scan/evaluate; MongoDB now has 56,349 candles, 5 class calibrations, 45 alerts, and 45 alert evaluations.

### 2026-05-28 16. Readable Alert Report

User said the Markdown table was too narrow. Generated `anomaly_alerts_report.html`, a wide browser-friendly report with summary cards, per-symbol alarm counts, sticky columns, horizontal scrolling, trigger conditions, signal components, weights, and explanations for all 45 stored alerts.

### 2026-05-28 17. Asset Normalization, Market Sessions, BIST, Active Tracking

Added human-readable asset names so coded Yahoo/Binance symbols render as labels such as Gold Futures, EUR/USD, S&P 500, Bitcoin / Tether, and Turkish Airlines. Added BIST as its own market class with THYAO.IS, ASELS.IS, BIMAS.IS, and TUPRS.IS. Added natural market-time logic: crypto is always active, daily Yahoo bars are weekday-filtered, BIST uses Istanbul session hours for intraday data, US stocks/indexes use New York regular hours, forex follows weekday FX availability, and commodity futures use a near-24h futures session. Added active anomaly tracking with pending/confirmed/expired status after alerts. Re-ran 3-year calibration with BIST: BIST selected score 3.2 / follow-through 3.0%, 10 historical alerts, 80% precision, 20% noise, average reaction 2.62 bars. Mongo now has 59,354 candles, 6 class calibrations, 55 alerts, 55 active anomalies, and 45 alert evaluations.

### 2026-05-28 18. GitHub and Dokploy Deployment

Initialized git, created/pushed GitHub repo `pand40x/adaptive-market-anomaly-monitor`, and made it public so Dokploy can build from the GitHub context. Created a Dokploy raw Docker Compose service in the existing `anomaly-detector` production environment. Initial deploy failed because the compose source type was missing; updating the compose to `sourceType=raw` fixed it. Final Dokploy deployment status is `done`, compose status is `done`, and both `market-watch` and `mongo` containers are running. Do not print Dokploy API responses that include raw compose content because they may include environment secrets.

### 2026-05-28 11. Secret Handling and Telegram Alerts

User provided Dokploy and Telegram credentials in chat. Do not repeat or store the raw secret values in memory. Added Telegram notifier support through `.env.local` variables, including `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DOKPLOY_API_KEY`, and optional `DOKPLOY_API_URL`. Scan now sends a short Telegram summary when both token and chat id are configured. Added a `telegram-chat-ids` helper command for discovering chat ids after the user messages the bot.

### 2026-05-28 12. Local Secret File

Created local `.env.local` with the provided Dokploy API key and Telegram bot token. The file is ignored by git and has owner-only permissions. `DOKPLOY_API_URL` and `TELEGRAM_CHAT_ID` are still empty. Running `telegram-chat-ids` found no chats yet, so the user needs to send any message to the bot before Telegram alerts can be delivered.

### 2026-05-28 13. Dokploy API URL

User provided the Dokploy host. Updated local `.env.local` with `DOKPLOY_API_URL=https://dokploy.anilsahin.tr`. The Dokploy API key remains stored locally and masked in command output. Telegram chat id is still not configured.
