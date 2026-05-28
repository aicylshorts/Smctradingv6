"""
SMC Trading Bot - Configuration
All settings centralized for easy mobile editing.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# TELEGRAM CONFIG (Required)
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# =============================================================================
# OANDA CONFIG (Required for real-time forex + indices)
# Get free practice account at: https://www.oanda.com/demo-account/
# =============================================================================
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")

# OANDA Index CFD mappings (real-time, no delay)
OANDA_INDICES = {
    "^NDX": "NAS100_USD",   # US Tech 100 (Nasdaq)
    "^DJI": "US30_USD",    # US Wall St 30 (Dow)
    "^GSPC": "SPX500_USD", # US SPX 500
    "^RUT": "US2000_USD",  # US Russ 2000
}

# =============================================================================
# WATCHLIST - ALL USD-QUOTED
# =============================================================================
# FOREX PAIRS (via OANDA, all USD-quoted)
FOREX_PAIRS = [
    "EURUSD=X",  # Euro / US Dollar
    "GBPUSD=X",  # British Pound / US Dollar
    "USDJPY=X",  # US Dollar / Japanese Yen
    "USDCHF=X",  # US Dollar / Swiss Franc
    "AUDUSD=X",  # Australian Dollar / US Dollar
    "NZDUSD=X",  # New Zealand Dollar / US Dollar
    "USDCAD=X",  # US Dollar / Canadian Dollar
    "EURGBP=X",  # Euro / British Pound
    "EURJPY=X",  # Euro / Japanese Yen
    "GBPJPY=X",  # British Pound / Japanese Yen
    "XAUUSD=X",  # Gold / US Dollar
    "XAGUSD=X",  # Silver / US Dollar
]

# CRYPTO (via Binance public API, USDT pairs)
# Maps to Binance symbols: BTCUSDT, ETHUSDT, etc.
CRYPTO_PAIRS = [
    "BTCUSD",   # Bitcoin / US Dollar (display) -> BTCUSDT (Binance)
    "ETHUSD",   # Ethereum / US Dollar -> ETHUSDT
    "SOLUSD",   # Solana / US Dollar -> SOLUSDT
    "XRPUSD",   # Ripple / US Dollar -> XRPUSDT
    "ADAUSD",   # Cardano / US Dollar -> ADAUSDT
    "DOTUSD",   # Polkadot / US Dollar -> DOTUSDT
    "LINKUSD",  # Chainlink / US Dollar -> LINKUSDT
    "AVAXUSD",  # Avalanche / US Dollar -> AVAXUSDT
    "MATICUSD", # Polygon / US Dollar -> MATICUSDT
    "UNIUSD",   # Uniswap / US Dollar -> UNIUSDT
]

# INDICES (via OANDA CFDs, all USD-quoted, real-time)
INDICES = [
    "^NDX",   # US 100 (Nasdaq 100)
    "^DJI",   # US 30 (Dow Jones)
    "^GSPC",  # S&P 500
    "^RUT",   # Russell 2000
]

ALL_SYMBOLS = FOREX_PAIRS + CRYPTO_PAIRS + INDICES

# =============================================================================
# TIMEFRAMES
# =============================================================================
TIMEFRAMES = {
    "15m": {"yfinance": "15m", "binance": "15m", "oanda": "M15", "minutes": 15},
    "1h":  {"yfinance": "1h",  "binance": "1h",  "oanda": "H1",  "minutes": 60},
    "4h":  {"yfinance": "4h",  "binance": "4h",  "oanda": "H4",  "minutes": 240},
}

# =============================================================================
# SMC DETECTION SETTINGS
# =============================================================================
LOOKBACK_CANDLES = 50
DISPLACEMENT_ATR_MULT = 1.2
SWING_MIN_CANDLES = 3
FVG_MIN_GAP_RATIO = 0.0001

# =============================================================================
# SCORING SYSTEM (A = 70-79, A+ = 80-100)
# =============================================================================
SCORE_THRESHOLDS = {
    "A": 70,
    "A_PLUS": 80,
}

SCORE_WEIGHTS = {
    "structure_alignment": 25,
    "liquidity_sweep_quality": 20,
    "displacement_strength": 20,
    "confluence_count": 15,
    "time_window": 10,
    "risk_reward": 10,
}

# =============================================================================
# TAKE PROFIT SETTINGS (Probability-Based)
# =============================================================================
TP_SETTINGS = {
    "A": {
        "tp1": {"ratio": 1.5, "prob": 0.75, "size": 0.50},
        "tp2": {"ratio": 2.5, "prob": 0.50, "size": 0.30},
        "tp3": {"ratio": 3.5, "prob": 0.30, "size": 0.20},
    },
    "A_PLUS": {
        "tp1": {"ratio": 2.0, "prob": 0.85, "size": 0.40},
        "tp2": {"ratio": 3.5, "prob": 0.65, "size": 0.35},
        "tp3": {"ratio": 5.0, "prob": 0.45, "size": 0.25},
    },
}

# =============================================================================
# NEWS FILTER SETTINGS (Time-based, no API needed)
# =============================================================================
HIGH_IMPACT_EVENTS = [
    "Non-Farm Payrolls", "NFP",
    "FOMC", "Federal Reserve", "Interest Rate Decision",
    "CPI", "Inflation",
    "GDP", "Gross Domestic Product",
    "Unemployment Rate",
    "ECB", "BOE", "BOJ", "RBA", "RBNZ",
    "Press Conference",
    "Jackson Hole",
]

NEWS_BLACKOUT_MINUTES = 30

# =============================================================================
# KILL ZONE SETTINGS (WAT times - West African Time, UTC+1)
# London: 3-5 AM EST = 9-11 WAT
# NY AM: 8-11 AM EST = 14-17 WAT
# NY PM: 2-3 PM EST = 20-21 WAT
# =============================================================================
KILL_ZONES = {
    "london": {"start": "09:00", "end": "11:00", "weight": 1.0},
    "ny_am":  {"start": "14:00", "end": "17:00", "weight": 1.0},
    "ny_pm":  {"start": "20:00", "end": "21:00", "weight": 0.8},
}

# =============================================================================
# BOT OPERATION SETTINGS
# =============================================================================
SCAN_INTERVAL = 300  # 5 minutes
DAILY_SUMMARY_TIME = "23:55"  # WAT (22:55 UTC)
MAX_ALERTS_PER_HOUR = 2
ALERT_COOLDOWN_MINUTES = 30

# =============================================================================
# RENDER.COM SETTINGS
# =============================================================================
PORT = int(os.getenv("PORT", 10000))
