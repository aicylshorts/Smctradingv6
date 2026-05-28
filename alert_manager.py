"""
SMC Trading Bot - Alert Manager
Manages alert cooldowns, deduplication, and spam protection.
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Set
from collections import defaultdict

from settings import MAX_ALERTS_PER_HOUR, ALERT_COOLDOWN_MINUTES

WAT = timezone(timedelta(hours=1))

def now_wat():
    return datetime.now(WAT)

class AlertManager:
    def __init__(self):
        self.last_alert_time: Dict[str, float] = {}
        self.hourly_counts: Dict[str, int] = defaultdict(int)
        self.hourly_reset: Dict[str, datetime] = {}
        self.sent_signatures: Set[str] = set()
        self.signature_expiry: Dict[str, float] = {}

    def can_alert(self, symbol: str, setup_signature: str) -> bool:
        now = time.time()
        now_dt = now_wat()

        if setup_signature in self.sent_signatures:
            return False

        last_time = self.last_alert_time.get(symbol, 0)
        cooldown_seconds = ALERT_COOLDOWN_MINUTES * 60
        if (now - last_time) < cooldown_seconds:
            return False

        hour_key = f"{symbol}_{now_dt.hour}"
        if hour_key not in self.hourly_reset:
            self.hourly_counts[hour_key] = 0
            self.hourly_reset[hour_key] = now_dt

        if self.hourly_counts[hour_key] >= MAX_ALERTS_PER_HOUR:
            return False

        return True

    def record_alert(self, symbol: str, setup_signature: str):
        now = time.time()
        now_dt = now_wat()
        hour_key = f"{symbol}_{now_dt.hour}"

        self.last_alert_time[symbol] = now
        self.sent_signatures.add(setup_signature)
        self.signature_expiry[setup_signature] = now + 3600

        if hour_key not in self.hourly_counts:
            self.hourly_counts[hour_key] = 0
        self.hourly_counts[hour_key] += 1

        self._cleanup_old_signatures(now)

    def _cleanup_old_signatures(self, now: float):
        expired = [sig for sig, expiry in self.signature_expiry.items() if expiry < now]
        for sig in expired:
            self.sent_signatures.discard(sig)
            del self.signature_expiry[sig]

    def get_stats(self) -> Dict:
        now_dt = now_wat()
        hour_key = f"GLOBAL_{now_dt.hour}"
        total_alerts = sum(count for key, count in self.hourly_counts.items() if key.endswith(f"_{now_dt.hour}"))
        return {
            "active_cooldowns": len(self.last_alert_time),
            "signatures_tracked": len(self.sent_signatures),
            "alerts_this_hour": total_alerts,
        }

_manager = None

def get_alert_manager():
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager
