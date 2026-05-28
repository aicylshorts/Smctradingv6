"""
SMC Trading Bot - SMC Analyzer
Detects Smart Money Concepts patterns.
All timestamps in WAT (West African Time, UTC+1).
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta

from settings import (
    DISPLACEMENT_ATR_MULT, SWING_MIN_CANDLES, FVG_MIN_GAP_RATIO,
    SCORE_WEIGHTS, SCORE_THRESHOLDS, TP_SETTINGS, KILL_ZONES
)

# WAT timezone (UTC+1)
WAT = timezone(timedelta(hours=1))

def now_wat():
    return datetime.now(WAT)

def to_wat(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WAT)

@dataclass
class SwingPoint:
    index: int
    timestamp: datetime
    price: float
    type: str

@dataclass
class OrderBlock:
    index: int
    timestamp: datetime
    open_price: float
    high: float
    low: float
    close: float
    type: str
    is_breaker: bool = False
    is_mitigation: bool = False
    invalidated: bool = False

@dataclass
class FairValueGap:
    start_index: int
    end_index: int
    start_timestamp: datetime
    end_timestamp: datetime
    top: float
    bottom: float
    type: str
    filled: bool = False
    inverted: bool = False

@dataclass
class LiquiditySweep:
    index: int
    timestamp: datetime
    price: float
    level: float
    type: str
    swept_level: str

@dataclass
class SMCSetup:
    symbol: str
    timeframe: str
    direction: str
    timestamp: datetime
    liquidity_sweep: Optional[LiquiditySweep] = None
    structure_shift: Optional[str] = None
    displacement_candle: Optional[int] = None
    order_blocks: List[OrderBlock] = field(default_factory=list)
    fvgs: List[FairValueGap] = field(default_factory=list)
    entry_zone: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    stop_loss: float = 0.0
    take_profits: List[Dict] = field(default_factory=list)
    score: int = 0
    grade: str = ""
    htf_bias: str = ""
    is_kill_zone: bool = False
    risk_reward: float = 0.0
    confluence_count: int = 0

class SMCAnalyzer:
    def __init__(self):
        self.swings: List[SwingPoint] = []
        self.order_blocks: List[OrderBlock] = []
        self.fvgs: List[FairValueGap] = []
        self.sweeps: List[LiquiditySweep] = []

    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[SMCSetup]:
        if df is None or len(df) < 20:
            return None

        self.swings = []
        self.order_blocks = []
        self.fvgs = []
        self.sweeps = []

        df = self._calculate_atr(df)
        self._find_swings(df)
        structure = self._detect_structure(df)
        self._detect_liquidity_sweeps(df)
        self._detect_order_blocks(df)
        self._detect_fvgs(df)
        self._detect_breaker_blocks(df)
        setup = self._build_setup(df, symbol, timeframe, structure)

        return setup

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=period, min_periods=1).mean()
        df['atr'] = df['atr'].fillna(high_low)
        return df

    def _find_swings(self, df: pd.DataFrame):
        n = SWING_MIN_CANDLES
        for i in range(n, len(df) - n):
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and
                df['high'].iloc[i] > df['high'].iloc[i+1] and
                df['high'].iloc[i] > df['high'].iloc[i-2] and
                df['high'].iloc[i] > df['high'].iloc[i+2]):
                ts = df['timestamp'].iloc[i]
                if isinstance(ts, str):
                    ts = pd.to_datetime(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                self.swings.append(SwingPoint(
                    index=i, timestamp=ts.astimezone(WAT), price=df['high'].iloc[i], type="high"
                ))

            if (df['low'].iloc[i] < df['low'].iloc[i-1] and
                df['low'].iloc[i] < df['low'].iloc[i+1] and
                df['low'].iloc[i] < df['low'].iloc[i-2] and
                df['low'].iloc[i] < df['low'].iloc[i+2]):
                ts = df['timestamp'].iloc[i]
                if isinstance(ts, str):
                    ts = pd.to_datetime(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                self.swings.append(SwingPoint(
                    index=i, timestamp=ts.astimezone(WAT), price=df['low'].iloc[i], type="low"
                ))
        self.swings.sort(key=lambda x: x.index)

    def _detect_structure(self, df: pd.DataFrame) -> Dict:
        if len(self.swings) < 4:
            return {"type": "none", "direction": "neutral"}

        recent_swings = self.swings[-6:]
        highs = [s for s in recent_swings if s.type == "high"]
        lows = [s for s in recent_swings if s.type == "low"]

        if len(highs) < 2 or len(lows) < 2:
            return {"type": "none", "direction": "neutral"}

        last_high = highs[-1]
        prev_high = highs[-2]
        last_low = lows[-1]
        prev_low = lows[-2]

        structure_type = "none"
        direction = "neutral"

        if last_high.price > prev_high.price:
            structure_type = "BOS"
            direction = "bullish"
        elif last_low.price < prev_low.price:
            structure_type = "BOS"
            direction = "bearish"

        if len(df) > 3:
            recent_close = df['close'].iloc[-1]
            if recent_close < last_low.price and direction == "bullish":
                structure_type = "CHoCH"
                direction = "bearish"
            elif recent_close > last_high.price and direction == "bearish":
                structure_type = "CHoCH"
                direction = "bullish"

        if structure_type == "CHoCH":
            for i in range(-3, 0):
                if self._is_displacement(df, i):
                    structure_type = "MSS"
                    break

        return {
            "type": structure_type, "direction": direction,
            "last_high": last_high, "last_low": last_low,
            "prev_high": prev_high, "prev_low": prev_low,
        }

    def _is_displacement(self, df: pd.DataFrame, idx: int) -> bool:
        if idx >= 0 or abs(idx) > len(df):
            return False
        candle = df.iloc[idx]
        body_size = abs(candle['close'] - candle['open'])
        atr = candle['atr']
        if pd.isna(atr) or atr == 0:
            return False
        wick_size = (candle['high'] - candle['low']) - body_size
        wick_ratio = wick_size / (candle['high'] - candle['low']) if (candle['high'] - candle['low']) > 0 else 0
        return body_size > (atr * DISPLACEMENT_ATR_MULT) and wick_ratio < 0.3

    def _detect_liquidity_sweeps(self, df: pd.DataFrame):
        if len(self.swings) < 2 or len(df) < 5:
            return
        recent = df.iloc[-5:]
        for swing in self.swings[-5:]:
            if swing.type == "high":
                for i in range(len(recent)):
                    if (recent['high'].iloc[i] > swing.price and
                        recent['close'].iloc[i] < swing.price):
                        ts = recent['timestamp'].iloc[i]
                        if isinstance(ts, str):
                            ts = pd.to_datetime(ts)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        self.sweeps.append(LiquiditySweep(
                            index=len(df)-5+i, timestamp=ts.astimezone(WAT),
                            price=recent['high'].iloc[i], level=swing.price,
                            type="buy_side", swept_level=f"Swing High @ {swing.price:.5f}"
                        ))
        for swing in self.swings[-5:]:
            if swing.type == "low":
                for i in range(len(recent)):
                    if (recent['low'].iloc[i] < swing.price and
                        recent['close'].iloc[i] > swing.price):
                        ts = recent['timestamp'].iloc[i]
                        if isinstance(ts, str):
                            ts = pd.to_datetime(ts)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        self.sweeps.append(LiquiditySweep(
                            index=len(df)-5+i, timestamp=ts.astimezone(WAT),
                            price=recent['low'].iloc[i], level=swing.price,
                            type="sell_side", swept_level=f"Swing Low @ {swing.price:.5f}"
                        ))

    def _detect_order_blocks(self, df: pd.DataFrame):
        if len(df) < 10:
            return
        for i in range(5, len(df) - 1):
            if self._is_displacement(df, i):
                ob_idx = i - 1
                if ob_idx < 0:
                    continue
                ob_candle = df.iloc[ob_idx]
                ts = ob_candle['timestamp']
                if isinstance(ts, str):
                    ts = pd.to_datetime(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if df['close'].iloc[i] > df['open'].iloc[i]:
                    ob_type = "bullish"
                else:
                    ob_type = "bearish"
                self.order_blocks.append(OrderBlock(
                    index=ob_idx, timestamp=ts.astimezone(WAT),
                    open_price=ob_candle['open'], high=ob_candle['high'],
                    low=ob_candle['low'], close=ob_candle['close'], type=ob_type
                ))

    def _detect_fvgs(self, df: pd.DataFrame):
        if len(df) < 5:
            return
        for i in range(2, len(df) - 1):
            c1 = df.iloc[i-2]
            c2 = df.iloc[i-1]
            c3 = df.iloc[i]

            ts1 = c1['timestamp']
            ts3 = c3['timestamp']
            if isinstance(ts1, str):
                ts1 = pd.to_datetime(ts1)
            if isinstance(ts3, str):
                ts3 = pd.to_datetime(ts3)
            if ts1.tzinfo is None:
                ts1 = ts1.replace(tzinfo=timezone.utc)
            if ts3.tzinfo is None:
                ts3 = ts3.replace(tzinfo=timezone.utc)

            if c2['close'] > c2['open'] and c2['close'] > c1['close']:
                gap_bottom = c1['high']
                gap_top = c3['low']
                if gap_top > gap_bottom:
                    gap_size = gap_top - gap_bottom
                    price_level = (c1['close'] + c3['close']) / 2
                    if gap_size / price_level > FVG_MIN_GAP_RATIO:
                        self.fvgs.append(FairValueGap(
                            start_index=i-2, end_index=i,
                            start_timestamp=ts1.astimezone(WAT), end_timestamp=ts3.astimezone(WAT),
                            top=gap_top, bottom=gap_bottom, type="bullish"
                        ))

            if c2['close'] < c2['open'] and c2['close'] < c1['close']:
                gap_bottom = c3['high']
                gap_top = c1['low']
                if gap_top > gap_bottom:
                    gap_size = gap_top - gap_bottom
                    price_level = (c1['close'] + c3['close']) / 2
                    if gap_size / price_level > FVG_MIN_GAP_RATIO:
                        self.fvgs.append(FairValueGap(
                            start_index=i-2, end_index=i,
                            start_timestamp=ts1.astimezone(WAT), end_timestamp=ts3.astimezone(WAT),
                            top=gap_top, bottom=gap_bottom, type="bearish"
                        ))

    def _detect_breaker_blocks(self, df: pd.DataFrame):
        for ob in self.order_blocks:
            if ob.invalidated:
                continue
            recent_price = df['close'].iloc[-1]
            if ob.type == "bullish":
                if recent_price < ob.low:
                    if any(s.type == "sell_side" and s.index > ob.index for s in self.sweeps):
                        ob.is_breaker = True
                        ob.type = "bearish"
            else:
                if recent_price > ob.high:
                    if any(s.type == "buy_side" and s.index > ob.index for s in self.sweeps):
                        ob.is_breaker = True
                        ob.type = "bullish"

    def _build_setup(self, df: pd.DataFrame, symbol: str, timeframe: str, structure: Dict) -> Optional[SMCSetup]:
        if structure["type"] == "none":
            return None

        direction = structure["direction"]
        if not self.sweeps:
            return None

        relevant_obs = [ob for ob in self.order_blocks if ob.type == direction]
        relevant_fvgs = [fvg for fvg in self.fvgs if fvg.type == direction]

        if not relevant_obs and not relevant_fvgs:
            return None

        entry_zone = self._calculate_entry_zone(df, direction, relevant_obs, relevant_fvgs)
        if entry_zone is None:
            return None

        stop_loss = self._calculate_stop_loss(df, direction, entry_zone, relevant_obs)
        take_profits = self._calculate_take_profits(df, direction, entry_zone, structure)

        entry_price = (entry_zone[0] + entry_zone[1]) / 2
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            return None

        reward = take_profits[0]['price'] if take_profits else entry_price
        risk_reward = abs(reward - entry_price) / risk

        score, grade = self._score_setup(structure, relevant_obs, relevant_fvgs, risk_reward, direction)

        if score < SCORE_THRESHOLDS["A"]:
            return None

        last_ts = df['timestamp'].iloc[-1]
        if isinstance(last_ts, str):
            last_ts = pd.to_datetime(last_ts)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)

        is_kill_zone = self._is_kill_zone(last_ts.astimezone(WAT))

        setup = SMCSetup(
            symbol=symbol, timeframe=timeframe, direction=direction,
            timestamp=last_ts.astimezone(WAT),
            liquidity_sweep=self.sweeps[-1] if self.sweeps else None,
            structure_shift=structure["type"],
            order_blocks=relevant_obs[-3:] if relevant_obs else [],
            fvgs=relevant_fvgs[-3:] if relevant_fvgs else [],
            entry_zone=entry_zone, stop_loss=stop_loss,
            take_profits=take_profits, score=score, grade=grade,
            htf_bias=direction, is_kill_zone=is_kill_zone,
            risk_reward=risk_reward,
            confluence_count=len(relevant_obs) + len(relevant_fvgs)
        )
        return setup

    def _calculate_entry_zone(self, df, direction, obs, fvgs) -> Optional[Tuple[float, float]]:
        if not obs and not fvgs:
            return None
        zones = []
        for ob in obs[-2:]:
            zones.append((ob.low, ob.high))
        for fvg in fvgs[-2:]:
            zones.append((fvg.bottom, fvg.top))
        if not zones:
            return None
        return zones[-1]

    def _calculate_stop_loss(self, df, direction, entry_zone, obs) -> float:
        if direction == "bullish":
            if obs:
                return min(ob.low for ob in obs[-2:]) * 0.9995
            return entry_zone[0] * 0.998
        else:
            if obs:
                return max(ob.high for ob in obs[-2:]) * 1.0005
            return entry_zone[1] * 1.002

    def _calculate_take_profits(self, df, direction, entry_zone, structure) -> List[Dict]:
        entry = (entry_zone[0] + entry_zone[1]) / 2
        stop = self._calculate_stop_loss(df, direction, entry_zone, [])
        risk = abs(entry - stop)
        if risk == 0:
            return []
        tp_config = TP_SETTINGS["A_PLUS"]
        tps = []
        for key, config in tp_config.items():
            if direction == "bullish":
                tp_price = entry + (risk * config["ratio"])
            else:
                tp_price = entry - (risk * config["ratio"])
            tps.append({
                "level": key, "price": tp_price, "ratio": config["ratio"],
                "probability": config["prob"], "position_size": config["size"],
            })
        return tps

    def _score_setup(self, structure, obs, fvgs, risk_reward, direction) -> Tuple[int, str]:
        score = 0
        if structure["type"] == "MSS":
            score += 25
        elif structure["type"] == "CHoCH":
            score += 18
        elif structure["type"] == "BOS":
            score += 12

        if self.sweeps:
            score += 20
        else:
            score += 5

        if structure["type"] == "MSS":
            score += 20
        else:
            score += 10

        confluence = len(obs) + len(fvgs)
        if confluence >= 3:
            score += 15
        elif confluence == 2:
            score += 10
        elif confluence == 1:
            score += 5

        if self._is_kill_zone(now_wat()):
            score += 10
        else:
            score += 3

        if risk_reward >= 3.0:
            score += 10
        elif risk_reward >= 2.0:
            score += 7
        elif risk_reward >= 1.5:
            score += 4
        else:
            score += 1

        score = min(100, score)

        if score >= SCORE_THRESHOLDS["A_PLUS"]:
            grade = "A+"
        elif score >= SCORE_THRESHOLDS["A"]:
            grade = "A"
        else:
            grade = "B"

        return score, grade

    def _is_kill_zone(self, timestamp: datetime) -> bool:
        if timestamp is None:
            return False
        hour = timestamp.hour
        # WAT kill zones from settings
        if (9 <= hour <= 11) or (14 <= hour <= 17) or (20 <= hour <= 21):
            return True
        return False

_analyzer = None

def get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = SMCAnalyzer()
    return _analyzer
