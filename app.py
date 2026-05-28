"""
SMC Trading Bot - Render.com Entry Point
All times in WAT (West African Time, UTC+1).
"""
import sys
import os
import asyncio
import threading
import time
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify

from main import SMCTradingBot

WAT = timezone(timedelta(hours=1))

def now_wat():
    return datetime.now(WAT)

def now_utc():
    return datetime.now(timezone.utc)

app = Flask(__name__)
bot_instance = None
bot_thread = None

@app.route('/')
def home():
    if bot_instance:
        return jsonify({
            "status": "running",
            "bot": "SMC Trading Bot",
            "scans_completed": getattr(bot_instance, 'scans_completed', 0),
            "signals_found_today": len(getattr(bot_instance, 'today_signals', [])),
            "last_scan_time": getattr(bot_instance, 'last_scan_time', None),
            "wat_time": now_wat().strftime("%Y-%m-%d %H:%M:%S WAT"),
            "utc_time": now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
        })
    return jsonify({
        "status": "starting",
        "bot": "SMC Trading Bot",
        "wat_time": now_wat().strftime("%Y-%m-%d %H:%M:%S WAT"),
        "utc_time": now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/stats')
def stats():
    if bot_instance:
        return jsonify({
            "scans_completed": getattr(bot_instance, 'scans_completed', 0),
            "total_signals_found": getattr(bot_instance, 'signals_found', 0),
            "today_signals": len(getattr(bot_instance, 'today_signals', [])),
            "last_scan_time": getattr(bot_instance, 'last_scan_time', None),
            "wat_time": now_wat().strftime("%Y-%m-%d %H:%M:%S WAT"),
            "utc_time": now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")
        })
    return jsonify({"error": "Bot not initialized"}), 503

def run_bot():
    global bot_instance
    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_instance = SMCTradingBot()
        try:
            print("[RENDER] Bot thread starting...")
            loop.run_until_complete(bot_instance.start())
        except Exception as e:
            print(f"[BOT THREAD] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                loop.close()
            except Exception:
                pass
        print("[BOT THREAD] Restarting in 10 seconds...")
        time.sleep(10)

if __name__ == "__main__":
    print("[RENDER] Starting SMC Trading Bot...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    time.sleep(2)
    port = int(os.environ.get("PORT", 10000))
    print(f"[RENDER] Web server starting on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)
