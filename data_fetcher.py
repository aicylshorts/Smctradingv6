"""
SMC Trading Bot - Data Fetcher v6
CHANGES:
- Binance is PRIMARY for crypto (replaced Coinbase)
- All timestamps handled with explicit timezone awareness
- No more tz-naive vs tz-aware crashes
- Aggressive logging for debugging
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time
import os

from settings import (
    FOREX_PAIRS, CRYPTO_PAIRS, INDICES, TIMEFRAMES
)

# WAT timezone (West African Time, UTC+1)
WAT = timezone(timedelta(hours=1))

def now_wat():
    """Get current time in WAT."""
    return datetime.now(WAT)

def now_utc():
    """Get current time in UTC."""
    return datetime.now(timezone.utc)

def to_wat(dt):
    """Convert any datetime to WAT."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WAT)

class DataFetcher:
    """Fetches real-time USD-quoted market data."""

    def __init__(self):
        self.session = requests.Session()
        self.binance_base = "https://api.binance.com/api/v3"

        # OANDA Configuration
        self.oanda_enabled = False
        self.oanda_token = os.getenv("OANDA_API_TOKEN", "")
        self.oanda_account_id = os.getenv("OANDA_ACCOUNT_ID", "")
        self.oanda_domain = "api-fxpractice.oanda.com"

        if self.oanda_token and self.oanda_account_id:
            self.oanda_enabled = True
            print(f"[OANDA] Config loaded - Token: {self.oanda_token[:8]}... Account: {self.oanda_account_id}")
            self._test_oanda_connection()
        else:
            print("[OANDA] NOT CONFIGURED - Set OANDA_API_TOKEN and OANDA_ACCOUNT_ID env vars")

        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 15

        self.oanda_indices = {
            "^NDX": "NAS100_USD",
            "^DJI": "US30_USD",
            "^GSPC": "SPX500_USD",
            "^RUT": "US2000_USD",
        }

    def _test_oanda_connection(self):
        """Test OANDA connectivity on startup."""
        try:
            url = f"https://{self.oanda_domain}/v3/accounts/{self.oanda_account_id}"
            headers = {"Authorization": f"Bearer {self.oanda_token}"}
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print("[OANDA] Connection test PASSED")
            elif response.status_code == 401:
                print(f"[OANDA] Connection test FAILED - 401 Unauthorized")
                self.oanda_enabled = False
            elif response.status_code == 404:
                print(f"[OANDA] Connection test FAILED - 404 Account not found")
                self.oanda_enabled = False
            else:
                print(f"[OANDA] Connection test FAILED - HTTP {response.status_code}")
                self.oanda_enabled = False
        except Exception as e:
            print(f"[OANDA] Connection test FAILED - {e}")
            self.oanda_enabled = False

    def _get_cache_key(self, symbol, timeframe):
        return f"{symbol}_{timeframe}"

    def _get_cached(self, symbol, timeframe):
        key = self._get_cache_key(symbol, timeframe)
        if key in self._cache:
            age = time.time() - self._cache_time.get(key, 0)
            if age < self.cache_ttl:
                df = self._cache[key]
                if self._is_data_fresh(df, max_age_minutes=10):
                    return df
                else:
                    print(f"[CACHE] Stale data for {symbol} {timeframe}, invalidating")
                    del self._cache[key]
                    del self._cache_time[key]
        return None

    def _set_cached(self, symbol, timeframe, data):
        key = self._get_cache_key(symbol, timeframe)
        self._cache[key] = data
        self._cache_time[key] = time.time()

    def _is_data_fresh(self, df, max_age_minutes=10):
        if df is None or df.empty:
            return False
        try:
            last_ts = pd.to_datetime(df['timestamp'].iloc[-1])
            now = now_utc()
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            age_min = (now - last_ts).total_seconds() / 60
            if age_min > max_age_minutes:
                return False
            return True
        except Exception as e:
            print(f"[FRESHNESS] Check failed: {e}")
            return False

    def fetch_oanda_candles(self, instrument, granularity="H1", count=100):
        """Fetch real-time data from OANDA with incomplete candles."""
        if not self.oanda_enabled:
            return None

        cached = self._get_cached(instrument, granularity)
        if cached is not None:
            return cached

        try:
            url = f"https://{self.oanda_domain}/v3/instruments/{instrument}/candles"
            headers = {
                "Authorization": f"Bearer {self.oanda_token}",
                "Content-Type": "application/json"
            }
            params = {
                "granularity": granularity,
                "count": min(count, 500),
                "price": "M",
                "includeIncomplete": "true"
            }

            response = self.session.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                candles = data.get("candles", [])

                if not candles:
                    print(f"[OANDA] No candles for {instrument}")
                    return None

                df_data = []
                for candle in candles:
                    is_complete = candle.get("complete", False)
                    df_data.append({
                        "timestamp": pd.to_datetime(candle["time"]),
                        "open": float(candle["mid"]["o"]),
                        "high": float(candle["mid"]["h"]),
                        "low": float(candle["mid"]["l"]),
                        "close": float(candle["mid"]["c"]),
                        "volume": int(candle.get("volume", 0)),
                        "complete": is_complete
                    })

                df = pd.DataFrame(df_data)

                last_candle = df.iloc[-1]
                last_ts = last_candle['timestamp']
                is_complete = last_candle.get('complete', True)
                now = now_utc()
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                age_sec = (now - last_ts).total_seconds()

                print(f"[OANDA] {instrument} {granularity}: {len(df)} candles, last={last_ts.strftime('%H:%M')}, complete={is_complete}, age={age_sec:.0f}s")

                if len(df) >= 20:
                    self._set_cached(instrument, granularity, df)
                    return df
                else:
                    print(f"[OANDA] Insufficient candles for {instrument}: {len(df)}")
                    return None

            elif response.status_code == 401:
                print(f"[OANDA] 401 Unauthorized for {instrument}")
                return None
            elif response.status_code == 404:
                print(f"[OANDA] 404 Instrument not found: {instrument}")
                return None
            else:
                print(f"[OANDA] Error {response.status_code} for {instrument}")
                return None

        except Exception as e:
            print(f"[OANDA] Exception fetching {instrument}: {e}")
            return None

    def fetch_binance(self, symbol, interval="1h", limit=100):
        """Fetch crypto data from Binance public API (USDT pairs)."""
        cached = self._get_cached(symbol, interval)
        if cached is not None:
            return cached

        try:
            url = f"{self.binance_base}/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code != 200:
                print(f"[BINANCE] HTTP {response.status_code} for {symbol}")
                return None

            data = response.json()

            if not data or not isinstance(data, list):
                print(f"[BINANCE] No data for {symbol}")
                return None

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

            last_ts = df['timestamp'].iloc[-1]
            now = now_utc()
            age_sec = (now - last_ts).total_seconds()
            print(f"[BINANCE] {symbol}: {len(df)} candles, last={last_ts.strftime('%H:%M')}, age={age_sec:.0f}s")

            if self._is_data_fresh(df, max_age_minutes=10):
                self._set_cached(symbol, interval, df)
                return df
            else:
                print(f"[BINANCE] Stale data for {symbol}, rejecting")
                return None

        except Exception as e:
            print(f"[BINANCE] Exception for {symbol}: {e}")
            return None

    def fetch_yfinance(self, symbol, interval="1h", period="1mo"):
        """Fetch data from Yahoo Finance (DELAYED fallback)."""
        import yfinance as yf

        yf_interval = interval
        needs_resample = False

        if interval == "4h":
            yf_interval = "1h"
            needs_resample = True
            period = "5d"
        elif interval == "15m":
            period = "5d"

        cached = self._get_cached(symbol, interval)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=yf_interval)

            if df.empty:
                print(f"[YFINANCE] Empty for {symbol} {interval}")
                return None

            df = df.reset_index()
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'timestamp'})
            elif 'Date' in df.columns:
                df = df.rename(columns={'Date': 'timestamp'})

            df = df.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Ensure UTC
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

            if needs_resample and interval == "4h":
                df = self._resample_to_4h(df)
                if df is None or df.empty:
                    return None

            last_ts = df['timestamp'].iloc[-1]
            now = now_utc()
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            age_sec = (now - last_ts).total_seconds()
            print(f"[YFINANCE] {symbol} {interval}: {len(df)} candles, last={last_ts.strftime('%H:%M')}, age={age_sec:.0f}s")

            if self._is_data_fresh(df, max_age_minutes=30):
                self._set_cached(symbol, interval, df)
                return df
            else:
                print(f"[YFINANCE] Stale for {symbol} {interval}, rejecting")
                return None

        except Exception as e:
            print(f"[YFINANCE] Exception for {symbol} {interval}: {e}")
            return None

    def _resample_to_4h(self, df_1h):
        try:
            df = df_1h.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            df = df.set_index('timestamp')

            df_4h = df.resample('4h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            df_4h = df_4h.reset_index()
            return df_4h
        except Exception as e:
            print(f"[RESAMPLE] Failed: {e}")
            return None

    def fetch_all(self, symbol, timeframe_key="1h"):
        """Unified fetch with Binance primary for crypto."""
        tf_config = TIMEFRAMES.get(timeframe_key, TIMEFRAMES["1h"])
        yf_interval = tf_config["yfinance"]

        # CRYPTO - Binance primary (USDT pairs, real-time)
        if symbol in CRYPTO_PAIRS:
            binance_symbol = symbol.replace("USD", "USDT")
            print(f"[FETCH] {symbol} {timeframe_key} -> Binance {binance_symbol}")
            df = self.fetch_binance(binance_symbol, interval=tf_config["binance"], limit=100)
            if df is not None:
                return df

            # Fallback to yfinance
            yf_symbol = symbol.replace("USD", "-USD") + "=X"
            print(f"[FETCH] {symbol} {timeframe_key} -> yfinance {yf_symbol} (fallback)")
            return self.fetch_yfinance(yf_symbol, interval=yf_interval)

        # FOREX - OANDA (real-time)
        elif symbol in FOREX_PAIRS:
            if self.oanda_enabled:
                oanda_symbol = self._to_oanda_format(symbol)
                oanda_granularity = self._to_oanda_granularity(yf_interval)
                print(f"[FETCH] {symbol} {timeframe_key} -> OANDA {oanda_symbol} {oanda_granularity}")
                df = self.fetch_oanda_candles(oanda_symbol, oanda_granularity, 100)
                if df is not None:
                    return df
                print(f"[FETCH] {symbol} {timeframe_key} -> OANDA FAILED, trying yfinance")
            else:
                print(f"[FETCH] {symbol} {timeframe_key} -> yfinance (OANDA not configured)")
            return self.fetch_yfinance(symbol, interval=yf_interval)

        # INDICES - OANDA CFDs (real-time)
        elif symbol in INDICES:
            if self.oanda_enabled:
                oanda_index = self.oanda_indices.get(symbol)
                if oanda_index:
                    oanda_granularity = self._to_oanda_granularity(yf_interval)
                    print(f"[FETCH] {symbol} {timeframe_key} -> OANDA {oanda_index} {oanda_granularity}")
                    df = self.fetch_oanda_candles(oanda_index, oanda_granularity, 100)
                    if df is not None:
                        return df
                    print(f"[FETCH] {symbol} {timeframe_key} -> OANDA FAILED, trying yfinance")
                else:
                    print(f"[FETCH] {symbol} {timeframe_key} -> No OANDA mapping, trying yfinance")
            else:
                print(f"[FETCH] {symbol} {timeframe_key} -> yfinance (OANDA not configured)")
            return self.fetch_yfinance(symbol, interval=yf_interval)

        else:
            return self.fetch_yfinance(symbol, interval=yf_interval)

    def _to_oanda_format(self, symbol):
        symbol = symbol.replace("=X", "").replace("-USD", "")
        if len(symbol) == 6:
            return f"{symbol[:3]}_{symbol[3:]}"
        return symbol

    def _to_oanda_granularity(self, tf):
        mapping = {"15m": "M15", "1h": "H1", "4h": "H4", "1d": "D"}
        return mapping.get(tf, "H1")

    def fetch_multi_timeframe(self, symbol):
        """Fetch all configured timeframes for a symbol."""
        result = {}
        for tf_key in TIMEFRAMES.keys():
            df = self.fetch_all(symbol, tf_key)
            if df is None or len(df) < 20:
                print(f"[MTF] FAILED {symbol} {tf_key}: got {len(df) if df is not None else 0} rows")
                return None
            result[tf_key] = df
        return result

    def get_current_price(self, symbol):
        if symbol in CRYPTO_PAIRS:
            binance_symbol = symbol.replace("USD", "USDT")
            try:
                url = f"{self.binance_base}/ticker/price"
                response = self.session.get(url, params={"symbol": binance_symbol}, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return float(data.get("price", 0))
            except Exception:
                pass
            df = self.fetch_all(symbol, "1h")
            if df is not None and not df.empty:
                return float(df['close'].iloc[-1])
            return None

        if self.oanda_enabled:
            if symbol in FOREX_PAIRS:
                oanda_symbol = self._to_oanda_format(symbol)
                url = f"https://{self.oanda_domain}/v3/accounts/{self.oanda_account_id}/pricing"
                headers = {"Authorization": f"Bearer {self.oanda_token}"}
                try:
                    response = self.session.get(url, headers=headers, params={"instruments": oanda_symbol}, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        prices = data.get("prices", [])
                        if prices:
                            return (float(prices[0]["bid"]) + float(prices[0]["ask"])) / 2
                except Exception:
                    pass
            elif symbol in INDICES:
                oanda_index = self.oanda_indices.get(symbol)
                if oanda_index:
                    url = f"https://{self.oanda_domain}/v3/accounts/{self.oanda_account_id}/pricing"
                    headers = {"Authorization": f"Bearer {self.oanda_token}"}
                    try:
                        response = self.session.get(url, headers=headers, params={"instruments": oanda_index}, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            prices = data.get("prices", [])
                            if prices:
                                return (float(prices[0]["bid"]) + float(prices[0]["ask"])) / 2
                    except Exception:
                        pass

        df = self.fetch_all(symbol, "1h")
        if df is not None and not df.empty:
            return float(df['close'].iloc[-1])
        return None

# Singleton
_fetcher = None

def get_fetcher():
    global _fetcher
    if _fetcher is None:
        _fetcher = DataFetcher()
    return _fetcher
