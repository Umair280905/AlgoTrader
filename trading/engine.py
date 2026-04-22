"""
TradingEngine — orchestrates signal → risk check → order placement → position tracking.

get_broker_client() returns PaperEngine or MirageClient based on settings.PAPER_TRADING.
"""
import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .models import Signal, Order, Position, Watchlist
from .risk import RiskController

logger = logging.getLogger(__name__)

risk_controller = RiskController()


def get_broker_client():
    """Factory: returns PaperEngine or KotakNeoClient based on settings."""
    if settings.PAPER_TRADING:
        from broker.paper_engine import PaperEngine
        return PaperEngine()
    from broker.kotak_neo_client import KotakNeoClient
    return KotakNeoClient()


class TradingEngine:
    def __init__(self):
        self.broker = get_broker_client()

    def place_entry_order(self, signal: Signal) -> Optional[Order]:
        """
        Place an entry order for a given (already saved) Signal.
        Returns the Order object or None if placement failed.
        """
        # Determine quantity
        try:
            funds = self.broker.get_funds()
            available_cash = funds['available_cash']
        except Exception as exc:
            logger.error("Failed to fetch funds: %s", exc)
            available_cash = 0.0

        qty = risk_controller.calculate_quantity(signal, available_cash)
        signal.quantity = qty
        signal.save(update_fields=['quantity'])

        side = 'BUY' if signal.signal_type in ('BUY',) else 'SELL'

        try:
            broker_order_id = self.broker.place_order(
                symbol=signal.symbol.symbol,
                side=side,
                qty=qty,
                order_type='MARKET',
                price=0,
                sl=float(signal.stop_loss),
            )
        except Exception as exc:
            logger.error("Failed to place order for signal %d: %s", signal.id, exc)
            return None

        order = Order.objects.create(
            signal=signal,
            broker_order_id=broker_order_id,
            order_type='MARKET',
            side=side,
            quantity=qty,
            price=Decimal('0'),
            status='PENDING',
            is_paper=settings.PAPER_TRADING,
        )

        signal.acted_on = True
        signal.save(update_fields=['acted_on'])

        from notifications.telegram import send_message
        send_message(
            f"ORDER PLACED broker_id:{broker_order_id} | {side} {qty} "
            f"{signal.symbol.symbol} @ MARKET"
        )
        logger.info("Order placed: %s", order)
        return order

    def place_exit_order(self, position: Position, reason: str = 'manual') -> Optional[Order]:
        """Place a market exit order for an open position."""
        exit_side = 'SELL' if position.side == 'LONG' else 'BUY'

        try:
            broker_order_id = self.broker.place_order(
                symbol=position.symbol.symbol,
                side=exit_side,
                qty=position.quantity,
                order_type='MARKET',
            )
        except Exception as exc:
            logger.error("Failed to place exit order for position %d: %s", position.id, exc)
            return None

        # Create a synthetic exit signal for the Order FK
        exit_signal = Signal.objects.create(
            symbol=position.symbol,
            strategy=position.strategy,
            signal_type='EXIT_LONG' if position.side == 'LONG' else 'EXIT_SHORT',
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            target=position.target,
            quantity=position.quantity,
            candle_timestamp=timezone.now(),
            acted_on=True,
        )

        order = Order.objects.create(
            signal=exit_signal,
            broker_order_id=broker_order_id,
            order_type='MARKET',
            side=exit_side,
            quantity=position.quantity,
            price=Decimal('0'),
            status='PENDING',
            is_paper=settings.PAPER_TRADING,
        )

        position.exit_order = order
        position.save(update_fields=['exit_order'])
        logger.info("Exit order placed for position %d (%s)", position.id, reason)
        return order

    def sync_order(self, order: Order) -> None:
        """Poll broker for latest order status and update DB."""
        try:
            status_data = self.broker.get_order_status(order.broker_order_id)
        except Exception as exc:
            logger.error("Failed to sync order %s: %s", order.broker_order_id, exc)
            return

        # Map broker status to our choices
        # TODO: CONFIRM — broker may return different status strings
        broker_status = (status_data.get('status') or '').upper()
        status_map = {
            'FILLED': 'FILLED',
            'COMPLETE': 'FILLED',
            'COMPLETED': 'FILLED',
            'REJECTED': 'REJECTED',
            'CANCELLED': 'CANCELLED',
            'OPEN': 'OPEN',
            'PENDING': 'PENDING',
        }
        mapped_status = status_map.get(broker_status, order.status)

        update_fields = ['status']
        order.status = mapped_status

        if mapped_status == 'FILLED':
            order.filled_price = Decimal(str(status_data.get('avg_price', 0)))
            order.filled_at = timezone.now()
            update_fields += ['filled_price', 'filled_at']
            self._handle_fill(order, status_data)

        order.save(update_fields=update_fields)

    def _handle_fill(self, order: Order, status_data: dict) -> None:
        """Create or close a Position when an order fills."""
        signal = order.signal
        fill_price = Decimal(str(status_data.get('avg_price', 0)))

        if signal.signal_type in ('BUY', 'SELL'):
            # Entry fill — create Position
            side = 'LONG' if order.side == 'BUY' else 'SHORT'
            Position.objects.create(
                symbol=signal.symbol,
                strategy=signal.strategy,
                side=side,
                entry_price=fill_price,
                quantity=order.quantity,
                stop_loss=signal.stop_loss,
                target=signal.target,
                status='OPEN',
                entry_order=order,
            )
            from notifications.telegram import send_message
            send_message(
                f"FILLED {order.side} {order.quantity} {signal.symbol.symbol} @ {fill_price}"
            )

        elif signal.signal_type in ('EXIT_LONG', 'EXIT_SHORT'):
            # Exit fill — close the Position
            position = Position.objects.filter(
                symbol=signal.symbol,
                strategy=signal.strategy,
                status='OPEN',
            ).first()
            if position:
                self._close_position(position, fill_price, order)

    def _close_position(self, position: Position, exit_price: Decimal, exit_order: Order) -> None:
        """Calculate P&L and mark position as closed."""
        if position.side == 'LONG':
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity

        # Rough brokerage estimate: ₹20 flat per trade (2 orders)
        charges = Decimal('40.00')

        position.exit_price = exit_price
        position.exit_order = exit_order
        position.pnl = pnl
        position.status = 'CLOSED'
        position.closed_at = timezone.now()
        position.save(update_fields=['exit_price', 'exit_order', 'pnl', 'status', 'closed_at'])

        # Update TradingDay
        self._update_trading_day(pnl, charges)

        duration = (position.closed_at - position.opened_at).seconds // 60
        from notifications.telegram import send_message
        send_message(
            f"CLOSED {position.symbol.symbol} | P&L: {'+'if pnl>=0 else ''}₹{float(pnl):.2f} | "
            f"Strategy: {position.strategy} | Duration: {duration} min"
        )
        # Trigger Journal Agent asynchronously
        from trading.tasks import run_journal_agent
        run_journal_agent.delay(position.id)

        # # Trigger Journal Agent asynchronously
        # from trading.tasks import run_journal_agent
        # run_journal_agent.delay(position.id)

    def _update_trading_day(self, pnl: Decimal, charges: Decimal) -> None:
        """Upsert TradingDay record with latest P&L."""
        today = timezone.now().date()
        td, _ = TradingDay.objects.get_or_create(date=today)
        td.gross_pnl += pnl
        td.charges += charges
        td.net_pnl = td.gross_pnl - td.charges
        td.total_trades += 1
        if pnl > 0:
            td.winning_trades += 1
        else:
            td.losing_trades += 1
        td.save(update_fields=['gross_pnl', 'charges', 'net_pnl', 'total_trades',
                               'winning_trades', 'losing_trades'])
