"""
Celery periodic tasks — all market-data and order-management automation.

Each task checks IST market hours at the top and exits early if outside session.
"""
import logging
from datetime import time, datetime, timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

IST = ZoneInfo('Asia/Kolkata')
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 0)


def _ist_now():
    return timezone.now().astimezone(IST)


def _is_market_hours():
    now = _ist_now()
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


# ── Strategy execution ────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.run_strategies')
def run_strategies():
    """
    1. Fetch latest candles for all active watchlist symbols
    2. Run all three strategies
    3. Apply risk checks
    4. Place orders for approved signals
    """
    if not _is_market_hours():
        return

    from django.utils.timezone import now as utcnow
    from trading.models import Watchlist, OHLCVCandle
    from trading.engine import TradingEngine, get_broker_client
    from trading.risk import RiskController
    from strategies.registry import StrategyRegistry
    import pandas as pd

    broker = get_broker_client()
    engine = TradingEngine()
    risk = RiskController()
    registry = StrategyRegistry()

    active_symbols = Watchlist.objects.filter(is_active=True)
    today_open = datetime.combine(_ist_now().date(), time(9, 15)).replace(tzinfo=IST)
    now_ist = _ist_now()

    for watchlist in active_symbols:
        try:
            candles_raw = broker.get_candles(
                symbol=watchlist.symbol,
                timeframe='1m',
                from_dt=today_open,
                to_dt=now_ist,
            )
        except Exception as exc:
            logger.error("Failed to fetch candles for %s: %s", watchlist.symbol, exc)
            continue

        if not candles_raw:
            continue

        # Upsert candles to DB cache
        for c in candles_raw:
            OHLCVCandle.objects.update_or_create(
                symbol=watchlist,
                timeframe='1m',
                timestamp=c['timestamp'],
                defaults={
                    'open': c['open'],
                    'high': c['high'],
                    'low': c['low'],
                    'close': c['close'],
                    'volume': c['volume'],
                },
            )

        df = pd.DataFrame(candles_raw)
        if df.empty:
            continue

        # Run each strategy
        for strategy in registry.all():
            try:
                signal = strategy.generate_signal(watchlist, df)
            except Exception as exc:
                logger.error(
                    "Strategy %s error on %s: %s",
                    strategy.name, watchlist.symbol, exc
                )
                continue

            if signal is None:
                continue

            # Save signal regardless of risk outcome
            signal.save()
            logger.info("Signal generated: %s", signal)

            from notifications.telegram import send_message
            send_message(
                f"SIGNAL [{strategy.name}] {signal.signal_type} {watchlist.symbol} "
                f"@ {signal.entry_price} | SL: {signal.stop_loss} | "
                f"TGT: {signal.target} | Qty: {signal.quantity}"
            )

            approved, reason = risk.approve(signal)
            if not approved:
                logger.info("Signal rejected by risk: %s — %s", signal, reason)
                continue

            # AI Decision Gate
            from django.conf import settings as django_settings
            if django_settings.AI_ENABLED:
                from agents.orchestrator import AIOrchestrator
                orchestrator = AIOrchestrator()
                ai_passed, ai_score = orchestrator.evaluate_signal(signal)
                if not ai_passed:
                    logger.info(
                        "Signal blocked by AI gate: %s score=%d threshold=%d",
                        signal, ai_score, django_settings.AI_MIN_CONFIDENCE
                    )
                    continue

            engine.place_entry_order(signal)


# ── Order sync ────────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.sync_order_status')
def sync_order_status():
    """Poll broker for PENDING/OPEN order status updates."""
    if not _is_market_hours():
        return

    from trading.models import Order
    from trading.engine import TradingEngine

    engine = TradingEngine()
    pending_orders = Order.objects.filter(status__in=['PENDING', 'OPEN'])
    for order in pending_orders:
        try:
            engine.sync_order(order)
        except Exception as exc:
            logger.error("Failed to sync order %s: %s", order.broker_order_id, exc)


# ── Position monitoring ───────────────────────────────────────────────────────

@shared_task(name='trading.tasks.check_positions')
def check_positions():
    """Check if any open position has hit its SL or target."""
    if not _is_market_hours():
        return

    from trading.models import Position
    from trading.engine import TradingEngine, get_broker_client

    broker = get_broker_client()
    engine = TradingEngine()

    open_positions = Position.objects.filter(status='OPEN').select_related('symbol')
    for position in open_positions:
        try:
            quote = broker.get_quote(position.symbol.symbol)
            ltp = float(quote.get('ltp', 0))
            if ltp <= 0:
                continue

            hit_sl = hit_target = False

            if position.side == 'LONG':
                hit_sl = ltp <= float(position.stop_loss)
                hit_target = ltp >= float(position.target)
            else:
                hit_sl = ltp >= float(position.stop_loss)
                hit_target = ltp <= float(position.target)

            if hit_sl:
                logger.info("SL hit for position %d at LTP %s", position.id, ltp)
                from notifications.telegram import send_message
                send_message(
                    f"SL HIT {position.symbol.symbol} | "
                    f"Loss: ₹{float((ltp - float(position.entry_price)) * position.quantity):.2f} | "
                    "Exiting at market"
                )
                exit_order = engine.place_exit_order(position, reason='sl_hit')
                if exit_order:
                    position.status = 'SL_HIT'
                    position.save(update_fields=['status'])

            elif hit_target:
                logger.info("Target hit for position %d at LTP %s", position.id, ltp)
                exit_order = engine.place_exit_order(position, reason='target_hit')
                if exit_order:
                    position.status = 'TARGET_HIT'
                    position.save(update_fields=['status'])

        except Exception as exc:
            logger.error("Error checking position %d: %s", position.id, exc)


# ── EOD square-off ────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.square_off_all')
def square_off_all():
    """Force-close all open positions at 3:15 PM IST."""
    from trading.models import Position
    from trading.engine import TradingEngine

    now = _ist_now()
    if now.weekday() >= 5:
        return

    engine = TradingEngine()
    open_positions = Position.objects.filter(status='OPEN')
    count = open_positions.count()
    logger.info("EOD square-off: closing %d positions", count)

    for position in open_positions:
        try:
            engine.place_exit_order(position, reason='eod_squareoff')
        except Exception as exc:
            logger.error("Failed to square off position %d: %s", position.id, exc)

    if count > 0:
        from notifications.telegram import send_message
        send_message(f"EOD SQUARE-OFF: Closed {count} open position(s) at market.")


# ── Daily report ──────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.generate_daily_report')
def generate_daily_report():
    """Compute TradingDay aggregates and send Telegram EOD summary."""
    from trading.models import TradingDay, Position

    now = _ist_now()
    if now.weekday() >= 5:
        return

    today = now.date()
    td, _ = TradingDay.objects.get_or_create(date=today)

    from notifications.telegram import send_message
    win_rate = 0
    if td.total_trades > 0:
        win_rate = round(td.winning_trades / td.total_trades * 100)

    pnl_str = f"+₹{float(td.net_pnl):.2f}" if td.net_pnl >= 0 else f"-₹{abs(float(td.net_pnl)):.2f}"
    send_message(
        f"EOD REPORT {today.strftime('%d-%b')} | Net P&L: {pnl_str} | "
        f"Trades: {td.total_trades} | Win: {td.winning_trades} | "
        f"Loss: {td.losing_trades} | Win Rate: {win_rate}%"
    )
    logger.info("Daily report sent for %s", today)


# ── Candle purge ──────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.purge_old_candles')
def purge_old_candles():
    """Delete OHLCVCandle records older than 5 days."""
    from trading.models import OHLCVCandle

    cutoff = timezone.now() - timedelta(days=5)
    deleted, _ = OHLCVCandle.objects.filter(timestamp__lt=cutoff).delete()
    logger.info("Purged %d old candle records", deleted)


# ── Morning brief ─────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.send_morning_brief')
def send_morning_brief():
    """Send a Telegram morning brief at 9:00 AM IST with today's watchlist."""
    from trading.models import Watchlist

    now = _ist_now()
    if now.weekday() >= 5:
        return

    active = Watchlist.objects.filter(is_active=True).values_list('symbol', flat=True)
    symbols_str = ', '.join(active) if active else 'None'

    from notifications.telegram import send_message
    send_message(
        f"MORNING BRIEF {now.strftime('%d-%b-%Y')} | "
        f"Active watchlist: {symbols_str} | "
        f"Paper trading: {'ON' if __import__('django.conf', fromlist=['settings']).settings.PAPER_TRADING else 'OFF'}"
    )










"""
Add these tasks to trading/tasks.py
Paste at the bottom of the file.
"""

# ── AI Agent tasks ────────────────────────────────────────────────────────────

@shared_task(name='trading.tasks.run_risk_advisor')
def run_risk_advisor():
    """Run Risk Advisor Agent at 9:00 AM IST daily."""
    now = _ist_now()
    if now.weekday() >= 5:
        return
    try:
        from agents.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator()
        result = orchestrator.run_risk_advisor()
        logger.info("Risk advisor completed: %s", result)
    except Exception as exc:
        logger.error("Risk advisor task failed: %s", exc)


@shared_task(name='trading.tasks.run_strategy_tuner')
def run_strategy_tuner():
    """Run Strategy Tuner Agent every Sunday evening."""
    now = _ist_now()
    if now.weekday() != 6:   # 6 = Sunday
        return
    try:
        from agents.strategy_tuner import StrategyTunerAgent
        tuner = StrategyTunerAgent()
        suggestions = tuner.run()
        logger.info("Strategy tuner created %d suggestions", len(suggestions))

        if suggestions:
            from notifications.telegram import send_message
            send_message(
                f"WEEKLY TUNER: {len(suggestions)} strategy suggestion(s) ready. "
                "Review at /admin → AI Tuner Suggestions."
            )
    except Exception as exc:
        logger.error("Strategy tuner task failed: %s", exc)


@shared_task(name='trading.tasks.run_journal_agent')
def run_journal_agent(position_id: int):
    """
    Write a journal entry for a just-closed position.
    Called by TradingEngine._close_position() after each trade closes.
    """
    try:
        from trading.models import Position
        from agents.journal_agent import JournalAgent
        position = Position.objects.get(id=position_id)
        agent = JournalAgent()
        agent.run(position)
        logger.info("Journal written for position %d", position_id)
    except Exception as exc:
        logger.error("Journal agent task failed for position %d: %s", position_id, exc)
