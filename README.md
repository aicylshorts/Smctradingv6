# SMC Trading Bot

## 24/7 Smart Money Concepts Trading Signal Bot

Scans 26 markets for A/A+ grade SMC setups. All timestamps in WAT (West African Time, UTC+1).

---

## Data Sources

| Market | Source | Quote | Quality |
|--------|--------|-------|---------|
| Forex | OANDA Practice API | USD | Real-time |
| Indices | OANDA CFDs | USD | Real-time |
| Crypto | Binance Public API | USDT | Real-time |

---

## Setup

### Step 1: Telegram Bot
1. Search **@BotFather** → `/newbot`
2. Copy **token**
3. Search **@userinfobot** → Copy **Chat ID**

### Step 2: OANDA Practice Account
1. **oanda.com/demo-account** → Free signup
2. Account Management → Manage API Access
3. Copy **API Token** and **Account ID**

### Step 3: GitHub + Render
1. Create repo, upload files
2. Render.com → New Web Service → Connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `python app.py`
5. Add env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`

---

## Time Zone

All bot operations, alerts, and summaries use **WAT (West African Time, UTC+1)**.
- Daily summary: 23:55 WAT
- Kill zones: London 09:00-11:00 WAT, NY AM 14:00-17:00 WAT, NY PM 20:00-21:00 WAT

---

## Disclaimer

Educational purposes only. Trading carries risk. Max 1% per trade.
