"""
SMC Trading Bot - Telegram Bot (v20 compatible)
All timestamps displayed in WAT (West African Time, UTC+1).
"""
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import traceback

from settings import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SCORE_THRESHOLDS
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

class TelegramNotifier:
    def __init__(self):
        self.bot = None
        self.chat_id = TELEGRAM_CHAT_ID
        self._init_bot()

    def _init_bot(self):
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
                print("[TELEGRAM] Bot initialized")
            except Exception as e:
                print(f"[TELEGRAM] Init failed: {e}")
                self.bot = None
        else:
            print("[TELEGRAM] Missing token or chat ID")
            self.bot = None

    async def send_alert(self, setup) -> bool:
        if not self.bot:
            return False
        try:
            message = self._format_alert(setup)
            await self._send_message(message)
            print(f"[TELEGRAM] Alert sent for {setup.symbol}")
            return True
        except Exception as e:
            print(f"[TELEGRAM] Alert failed: {e}")
            traceback.print_exc()
            return False

    async def _send_message(self, message: str):
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    def _format_alert(self, setup) -> str:
        direction = "BUY" if setup.direction == "bullish" else "SELL"
        grade_label = "A+" if setup.grade == "A+" else "A"
        entry_low = min(setup.entry_zone)
        entry_high = max(setup.entry_zone)

        # Convert timestamp to WAT
        ts_wat = setup.timestamp
        if ts_wat.tzinfo is None:
            ts_wat = ts_wat.replace(tzinfo=timezone.utc)
        ts_wat = ts_wat.astimezone(WAT)

        lines = [
            f"<b>SIGNAL: {direction} {setup.symbol}</b>",
            f"Grade: {grade_label} | Score: {setup.score}/100",
            f"Timeframe: {setup.timeframe}",
            f"",
            f"<b>ENTRY ZONE:</b> {entry_low:.5f} - {entry_high:.5f}",
            f"<b>STOP LOSS:</b> {setup.stop_loss:.5f}",
            f"",
        ]

        if setup.take_profits:
            lines.append("<b>TAKE PROFITS:</b>")
            for tp in setup.take_profits:
                prob_pct = int(tp['probability'] * 100)
                size_pct = int(tp['position_size'] * 100)
                lines.append(
                    f"  TP{tp['level'][-1]}: {tp['price']:.5f} "
                    f"(R:R {tp['ratio']:.1f}x, Prob: {prob_pct}%, Size: {size_pct}%)"
                )

        lines.extend([
            f"",
            f"<b>CONFLUENCE:</b>",
            f"  Structure: {setup.structure_shift}",
            f"  Order Blocks: {len(setup.order_blocks)}",
            f"  FVGs: {len(setup.fvgs)}",
            f"  Kill Zone: {'YES' if setup.is_kill_zone else 'NO'}",
            f"  R:R: {setup.risk_reward:.2f}x",
            f"",
            f"<b>SETUP TYPE:</b> {setup.structure_shift} + Liquidity Sweep",
        ])

        if setup.liquidity_sweep:
            lines.append(f"  Swept: {setup.liquidity_sweep.swept_level}")

        lines.append(f"")
        lines.append(f"Time: {ts_wat.strftime('%Y-%m-%d %H:%M WAT')}")
        lines.append(f"---")

        return "\n".join(lines)

    async def send_daily_summary(self, signals: List) -> bool:
        if not self.bot:
            return False
        try:
            message = self._format_summary(signals)
            await self._send_message(message)
            print("[TELEGRAM] Daily summary sent")
            return True
        except Exception as e:
            print(f"[TELEGRAM] Summary failed: {e}")
            return False

    def _format_summary(self, signals: List) -> str:
        today = now_wat().strftime("%Y-%m-%d")

        total = len(signals)
        a_plus = sum(1 for s in signals if s.grade == "A+")
        a_grade = sum(1 for s in signals if s.grade == "A")
        buy_signals = sum(1 for s in signals if s.direction == "bullish")
        sell_signals = sum(1 for s in signals if s.direction == "bearish")

        lines = [
            f"<b>DAILY SUMMARY: {today}</b>",
            f"",
            f"<b>OVERVIEW:</b>",
            f"  Total Signals: {total}",
            f"  A+ Setups: {a_plus}",
            f"  A Setups: {a_grade}",
            f"  BUY Signals: {buy_signals}",
            f"  SELL Signals: {sell_signals}",
            f"",
        ]

        if signals:
            lines.append("<b>SIGNALS BY SYMBOL:</b>")
            by_symbol = {}
            for sig in signals:
                if sig.symbol not in by_symbol:
                    by_symbol[sig.symbol] = []
                by_symbol[sig.symbol].append(sig)
            for symbol, sigs in sorted(by_symbol.items()):
                best = max(sigs, key=lambda x: x.score)
                lines.append(f"  {symbol}: {len(sigs)} signals, best grade {best.grade} ({best.score}pts)")
        else:
            lines.append("No A/A+ signals generated today.")

        lines.extend([
            f"",
            f"---",
            f"Next scan: Continuous (every 5 min)",
            f"Time zone: WAT (West African Time, UTC+1)",
        ])

        return "\n".join(lines)

    async def send_startup_message(self) -> bool:
        if not self.bot:
            return False
        try:
            wat_time = now_wat().strftime('%H:%M WAT')
            utc_time = datetime.now(timezone.utc).strftime('%H:%M UTC')

            message = (
                f"<b>SMC Trading Bot Online</b>\n"
                f"\n"
                f"Time: {wat_time} ({utc_time})\n"
                f"\n"
                f"Monitoring:\n"
                f"  - 12 Forex pairs (USD quoted)\n"
                f"  - 10 Crypto pairs (Binance USDT)\n"
                f"  - 4 Indices (OANDA CFDs)\n"
                f"\n"
                f"Filters:\n"
                f"  - High-impact news blackout\n"
                f"  - Kill zone time windows (WAT)\n"
                f"  - A/A+ grade minimum (70+ score)\n"
                f"\n"
                f"Alerts: Real-time via Telegram\n"
                f"Summary: Daily at 23:55 WAT\n"
                f"Time Zone: WAT (West African Time, UTC+1)\n"
                f"---"
            )

            await self._send_message(message)
            return True
        except Exception as e:
            print(f"[TELEGRAM] Startup failed: {e}")
            return False

_notifier = None

def get_notifier():
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
