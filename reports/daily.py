"""Daily P&L report generator."""
import logging
from datetime import date

from django.utils import timezone

logger = logging.getLogger(__name__)


def generate(report_date: date = None):
    """
    Compute and return the TradingDay record for the given date.
    Creates the record if it doesn't exist.
    """
    from trading.models import TradingDay, Position

    if report_date is None:
        report_date = timezone.now().date()

    td, created = TradingDay.objects.get_or_create(date=report_date)

    # Recompute from closed positions
    closed_positions = Position.objects.filter(
        status__in=['CLOSED', 'SL_HIT', 'TARGET_HIT'],
        closed_at__date=report_date,
    )

    gross_pnl = sum(float(p.pnl or 0) for p in closed_positions)
    total_trades = closed_positions.count()
    winning_trades = closed_positions.filter(pnl__gt=0).count()
    losing_trades = closed_positions.filter(pnl__lte=0).count()
    charges = total_trades * 40.0  # ₹40 flat per trade (20 × 2 orders)

    td.gross_pnl = gross_pnl
    td.charges = charges
    td.net_pnl = gross_pnl - charges
    td.total_trades = total_trades
    td.winning_trades = winning_trades
    td.losing_trades = losing_trades
    td.save(update_fields=[
        'gross_pnl', 'charges', 'net_pnl',
        'total_trades', 'winning_trades', 'losing_trades'
    ])

    logger.info("Daily report generated for %s: Net P&L=%.2f, Trades=%d",
                report_date, float(td.net_pnl), total_trades)
    return td
