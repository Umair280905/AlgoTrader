"""Weekly P&L report generator."""
import logging
from datetime import date, timedelta

from django.db.models import Sum

logger = logging.getLogger(__name__)


def generate(week_ending: date = None):
    """
    Aggregate TradingDay records for the 5 trading days ending on week_ending.
    Returns a summary dict.
    """
    from trading.models import TradingDay, Position

    if week_ending is None:
        from django.utils import timezone
        week_ending = timezone.now().date()

    week_start = week_ending - timedelta(days=6)
    days = TradingDay.objects.filter(date__range=(week_start, week_ending))

    summary = {
        'week_start': week_start,
        'week_end': week_ending,
        'gross_pnl': float(days.aggregate(total=Sum('gross_pnl'))['total'] or 0),
        'net_pnl': float(days.aggregate(total=Sum('net_pnl'))['total'] or 0),
        'charges': float(days.aggregate(total=Sum('charges'))['total'] or 0),
        'total_trades': days.aggregate(total=Sum('total_trades'))['total'] or 0,
        'winning_trades': days.aggregate(total=Sum('winning_trades'))['total'] or 0,
        'losing_trades': days.aggregate(total=Sum('losing_trades'))['total'] or 0,
        'trading_days': days.count(),
    }
    win_rate = 0
    if summary['total_trades'] > 0:
        win_rate = round(summary['winning_trades'] / summary['total_trades'] * 100, 1)
    summary['win_rate'] = win_rate

    logger.info(
        "Weekly report %s to %s: Net P&L=%.2f, Trades=%d, Win Rate=%.1f%%",
        week_start, week_ending, summary['net_pnl'],
        summary['total_trades'], win_rate
    )
    return summary
