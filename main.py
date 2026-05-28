"""
SMC Trading Bot - Main Orchestrator
24/7 trading signal detection system.
All times in WAT (West African Time, UTC+1).
"""
import asyncio
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import List
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from settings import (
    ALL_SYMBOLS, TIMEFRAMES, SCAN_INTERVAL,
    DAILY_SUMMARY_TIME, SCORE_THRESHOLDS
)
from data_fetcher import get_fetcher
from smc_analyzer import get_analyzer
from news_filter import get_news_filter
from telegram_bot import get_notifier
from alert_manager import get_alert_manager

# WAT timezone (UTC+1)
WAT = timezone(timedelta(hours=1))

def now_wat():
    return datetime.now(WAT)

def now_utc():
    return datetime.now(timezone.utc)

class SMCTradingBot:
    def __init__(self):
        self.fetcher = get_fetcher()
        self.analyzer = get_analyzer()
        self.news_filter = get_news_filter()
        self.notifier = get_notifier()
        self.alert_manager = get_alert_manager()

        self.scheduler = AsyncIOScheduler()
        self.running = False

        self.today_signals: List = []
        self.last_summary_date = now_wat().date()

        self.scans_completed = 0
        self.signals_found = 0
        self.last_scan_time = None

    async def start(self):
        print("=" * 60)
        print("SMC TRADING BOT STARTING")
        print("=" * 60)
        print("WAT Time: " + now_wat().strftime('%Y-%m-%d %H:%M:%S WAT'))
        print("UTC Time: " + now_utc().strftime('%Y-%m-%d %H:%M:%S UTC'))
        print("Symbols: " + str(len(ALL_SYMBOLS)))
        print("Timeframes: " + str(list(TIMEFRAMES.keys())))
        print("Min Grade: A (" + str(SCORE_THRESHOLDS['A']) + "+ score)")
        print("-" * 60)

        await self.notifier.send_startup_message()

        self.scheduler.add_job(
            self.scan_markets,
            'interval',
            seconds=SCAN_INTERVAL,
            id='market_scan',
            replace_existing=True
        )

        hour, minute = DAILY_SUMMARY_TIME.split(':')
        self.scheduler.add_job(
            self.send_daily_summary,
            CronTrigger(hour=int(hour), minute=int(minute), timezone='Africa/Lagos'),
            id='daily_summary',
            replace_existing=True
        )

        self.scheduler.start()
        self.running = True

        print("[BOT] Scheduler started")
        print("[BOT] Scan interval: Every 5 minutes")
        print("[BOT] Daily summary: " + DAILY_SUMMARY_TIME + " WAT")
        print("-" * 60)

        await self.scan_markets()

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        print("[BOT] Shutting down...")
        self.running = False
        self.scheduler.shutdown()
        print("[BOT] Scheduler stopped")
        print("[BOT] Goodbye")

    async def scan_markets(self):
        scan_start = time.time()
        self.scans_completed += 1
        self.last_scan_time = now_wat().strftime('%Y-%m-%d %H:%M:%S WAT')

        print("")
        print("[SCAN #" + str(self.scans_completed) + "] " + now_wat().strftime('%H:%M:%S WAT') + " (" + now_utc().strftime('%H:%M:%S UTC') + ")")
        print("-" * 40)

        if self.news_filter.is_high_impact_time():
            print("[SCAN] NEWS BLACKOUT ACTIVE - Skipping alerts")
            blackout = True
        else:
            blackout = False

        new_signals = []
        symbols_scanned = 0
        symbols_failed = 0

        for symbol in ALL_SYMBOLS:
            try:
                mtf_data = self.fetcher.fetch_multi_timeframe(symbol)

                if mtf_data is None:
                    symbols_failed += 1
                    continue

                symbols_scanned += 1

                for tf_key, df in mtf_data.items():
                    if df is None or len(df) < 20:
                        continue

                    setup = self.analyzer.analyze(df, symbol, tf_key)

                    if setup is None:
                        continue

                    if setup.score < SCORE_THRESHOLDS["A"]:
                        continue

                    sig = symbol + "_" + tf_key + "_" + setup.direction + "_" + str(setup.score) + "_" + setup.timestamp.strftime('%H%M')

                    if not self.alert_manager.can_alert(symbol, sig):
                        continue

                    if not blackout and self.news_filter.is_high_impact_time(symbol):
                        print("[SCAN] News blackout for " + symbol + " - alert suppressed")
                        continue

                    self.alert_manager.record_alert(symbol, sig)
                    self.signals_found += 1
                    new_signals.append(setup)

                    if not blackout:
                        await self.notifier.send_alert(setup)
                        print("[ALERT] " + setup.grade + " " + setup.direction.upper() + " " + symbol + " @ " + str(setup.score) + "pts")
                    else:
                        print("[FOUND] " + setup.grade + " " + setup.direction.upper() + " " + symbol + " @ " + str(setup.score) + "pts (blackout)")

                await asyncio.sleep(0.5)

            except Exception as e:
                print("[ERROR] Failed to scan " + symbol + ": " + str(e))
                symbols_failed += 1
                continue

        self.today_signals.extend(new_signals)

        current_date = now_wat().date()
        if current_date != self.last_summary_date:
            self.today_signals = []
            self.last_summary_date = current_date

        scan_duration = time.time() - scan_start
        print("[SCAN] Complete in " + str(round(scan_duration, 1)) + "s | Scanned: " + str(symbols_scanned) + "/" + str(len(ALL_SYMBOLS)) + " | Signals: " + str(len(new_signals)) + " | Total today: " + str(len(self.today_signals)))

    async def send_daily_summary(self):
        print("")
        print("[DAILY SUMMARY] Generating...")

        await self.notifier.send_daily_summary(self.today_signals)

        self.today_signals = []
        self.last_summary_date = now_wat().date()

        print("[DAILY SUMMARY] Sent and reset")

def setup_signal_handlers(bot: SMCTradingBot):
    def handle_signal(sig, frame):
        print("[SIGNAL] Received signal " + str(sig))
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(asyncio.create_task, bot.stop())
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

async def main():
    bot = SMCTradingBot()
    setup_signal_handlers(bot)
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
