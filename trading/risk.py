"""
RiskController — safety gate before any order reaches the broker.

approve(signal) must return True for an order to be placed.
All rules are enforced here. The engine never places orders directly.
"""
import logging
from datetime import time, date
from typing import Tuple, Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import Signal, Position, TradingDay, Watchlist

logger = logging.getLogger(__name__)

IST = ZoneInfo('Asia/Kolkata')
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 0)

# NSE holidays — update each year
# TODO: maintain this list or fetch from a reliable source
NSE_HOLIDAYS_2025 = {
    date(2025, 2, 19),  # Chhatrapati Shivaji Maharaj Jayanti
    date(2025, 3, 14),  # Holi
    date(2025, 4, 14),  # Dr. Ambedkar Jayanti
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 1),   # Maharashtra Day
    date(2025, 8, 15),  # Independence Day
    date(2025, 10, 2),  # Gandhi Jayanti
    date(2025, 10, 24), # Dussehra
    date(2025, 11, 5),  # Diwali Laxmi Pujan
    date(2025, 11, 14), # Gurunanak Jayanti
    date(2025, 12, 25), # Christmas
}
NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26),  # Republic Day
    # TODO: update with full 2026 NSE holiday list
}
NSE_HOLIDAYS = NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026


class RiskController:
    def approve(self, signal: Signal) -> Tuple[bool, str]:
        """
        Returns (approved: bool, reason: str).
        Runs all risk checks in order. Fails fast on first rejection.
        """
        checks = [
            self._check_market_hours,
            self._check_trading_halted,
            self._check_daily_loss_limit,
            self._check_max_open_positions,
            self._check_max_per_strategy,
            self._check_no_reentry,
            self._check_strategy_enabled,
            self._check_minimum_funds,
        ]
        for check in checks:
            approved, reason = check(signal)
            if not approved:
                logger.warning("Risk rejected signal %s: %s", signal, reason)
                return False, reason
        return True, 'OK'

    def calculate_quantity(self, signal: Signal, available_cash: float) -> int:
        """Calculate position size based on current PHASE setting."""
        if settings.PHASE == 1:
            return 1

        risk_amount = available_cash * settings.RISK_PER_TRADE_PCT
        risk_per_share = abs(float(signal.entry_price) - float(signal.stop_loss))
        if risk_per_share <= 0:
            return 1
        qty = int(risk_amount / risk_per_share)
        qty = max(1, qty)
        qty = min(qty, signal.symbol.max_quantity)
        return qty

    # ── Individual checks ──────────────────────────────────────────────────────

    def _check_market_hours(self, signal: Signal) -> Tuple[bool, str]:
        now = timezone.now().astimezone(IST)
        if now.weekday() >= 5:
            return False, "Weekend — market closed"
        if now.date() in NSE_HOLIDAYS:
            return False, f"NSE holiday: {now.date()}"
        if not (MARKET_OPEN <= now.time() <= MARKET_CLOSE):
            return False, f"Outside market hours ({now.time()})"
        return True, ''

    def _check_trading_halted(self, signal: Signal) -> Tuple[bool, str]:
        today = timezone.now().date()
        td = TradingDay.objects.filter(date=today).first()
        if td and td.trading_halted:
            return False, "Trading halted — daily loss limit hit"
        return True, ''

    def _check_daily_loss_limit(self, signal: Signal) -> Tuple[bool, str]:
        today = timezone.now().date()
        td = TradingDay.objects.filter(date=today).first()
        if td and float(td.net_pnl) < -settings.MAX_DAILY_LOSS_INR:
            td.trading_halted = True
            td.save(update_fields=['trading_halted'])
            from notifications.telegram import send_message
            send_message(
                f"TRADING HALTED — Daily loss limit ₹{settings.MAX_DAILY_LOSS_INR} reached. "
                "No new orders today."
            )
            return False, "Daily loss limit exceeded"
        return True, ''

    def _check_max_open_positions(self, signal: Signal) -> Tuple[bool, str]:
        # Exit signals are always allowed through
        if signal.signal_type in ('EXIT_LONG', 'EXIT_SHORT'):
            return True, ''
        open_count = Position.objects.filter(status='OPEN').count()
        if open_count >= settings.MAX_OPEN_POSITIONS:
            return False, f"Max open positions ({settings.MAX_OPEN_POSITIONS}) reached"
        return True, ''

    def _check_max_per_strategy(self, signal: Signal) -> Tuple[bool, str]:
        if signal.signal_type in ('EXIT_LONG', 'EXIT_SHORT'):
            return True, ''
        strategy_open = Position.objects.filter(
            status='OPEN', strategy=signal.strategy
        ).count()
        if strategy_open >= settings.MAX_PER_STRATEGY:
            return False, f"Max positions for {signal.strategy} reached"
        return True, ''

    def _check_no_reentry(self, signal: Signal) -> Tuple[bool, str]:
        if signal.signal_type in ('EXIT_LONG', 'EXIT_SHORT'):
            return True, ''
        existing = Position.objects.filter(
            symbol=signal.symbol, status='OPEN'
        ).exists()
        if existing:
            return False, f"Already have open position in {signal.symbol.symbol}"
        return True, ''

    def _check_strategy_enabled(self, signal: Signal) -> Tuple[bool, str]:
        # Strategy enable/disable is controlled by Watchlist.is_active for now
        # TODO: add a StrategyConfig model if per-strategy toggle is needed
        if not signal.symbol.is_active:
            return False, f"{signal.symbol.symbol} is not active in watchlist"
        return True, ''

    def _check_minimum_funds(self, signal: Signal) -> Tuple[bool, str]:
        if signal.signal_type in ('EXIT_LONG', 'EXIT_SHORT'):
            return True, ''
        try:
            from trading.engine import get_broker_client
            client = get_broker_client()
            funds = client.get_funds()
            if funds['available_cash'] < settings.MINIMUM_CASH_BUFFER:
                return False, f"Available cash below minimum buffer (₹{settings.MINIMUM_CASH_BUFFER})"
        except Exception as exc:
            logger.warning("Could not check funds: %s", exc)
            # Fail open — don't block trading due to funds check error
        return True, ''
