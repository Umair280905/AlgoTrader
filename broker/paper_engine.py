"""
Paper trading engine — simulates order fills without touching the live broker.

Implements the same interface as MirageClient so TradingEngine can swap
between real and paper mode by changing a single settings flag.
"""
import uuid
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

SLIPPAGE_PCT = 0.0005  # 0.05% default slippage


class PaperEngine:
    """Simulated broker that fills orders at LTP + slippage."""

    # In-memory store of paper orders {order_id: order_dict}
    _orders: dict = {}

    def get_quote(self, symbol: str) -> dict:
        """
        Returns a simulated quote.  The engine tries to fetch the last stored
        OHLCVCandle for the symbol as a realistic price proxy.
        """
        try:
            from trading.models import OHLCVCandle, Watchlist
            wl = Watchlist.objects.get(symbol=symbol, is_active=True)
            candle = OHLCVCandle.objects.filter(symbol=wl).order_by('-timestamp').first()
            if candle:
                return {
                    'ltp': float(candle.close),
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': candle.volume,
                }
        except Exception:
            pass
        # Fallback — return zero quote (signals won't fire on empty data anyway)
        return {'ltp': 0, 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0}

    def get_candles(self, symbol: str, timeframe: str, from_dt, to_dt) -> list:
        """Returns stored candles from DB — no live feed needed for paper mode."""
        from trading.models import OHLCVCandle, Watchlist
        try:
            wl = Watchlist.objects.get(symbol=symbol)
            qs = OHLCVCandle.objects.filter(
                symbol=wl,
                timeframe=timeframe,
                timestamp__gte=from_dt,
                timestamp__lte=to_dt,
            ).order_by('timestamp')
            return [
                {
                    'timestamp': c.timestamp,
                    'open': float(c.open),
                    'high': float(c.high),
                    'low': float(c.low),
                    'close': float(c.close),
                    'volume': c.volume,
                }
                for c in qs
            ]
        except Exception:
            return []

    def get_funds(self) -> dict:
        return {
            'available_cash': 100000.0,
            'used_margin': 0.0,
            'total_balance': 100000.0,
        }

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str,
        price: float = 0,
        sl: float = 0,
    ) -> str:
        """Simulate immediate fill at LTP ± slippage."""
        quote = self.get_quote(symbol)
        ltp = quote['ltp'] or price or 100.0  # fallback for empty data

        if order_type == 'MARKET':
            if side == 'BUY':
                fill_price = round(ltp * (1 + SLIPPAGE_PCT), 2)
            else:
                fill_price = round(ltp * (1 - SLIPPAGE_PCT), 2)
        else:
            fill_price = price or ltp

        order_id = f"PAPER-{uuid.uuid4().hex[:10].upper()}"
        self._orders[order_id] = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': qty,
            'order_type': order_type,
            'status': 'FILLED',
            'filled_qty': qty,
            'avg_price': fill_price,
            'message': 'Paper fill',
        }
        logger.info(
            "[PAPER] %s %d %s @ %.2f (order_id=%s)",
            side, qty, symbol, fill_price, order_id
        )
        return order_id

    def get_order_status(self, broker_order_id: str) -> dict:
        order = self._orders.get(broker_order_id)
        if order:
            return {
                'status': order['status'],
                'filled_qty': order['filled_qty'],
                'avg_price': order['avg_price'],
                'message': order['message'],
            }
        return {'status': 'UNKNOWN', 'filled_qty': 0, 'avg_price': 0, 'message': 'Not found'}

    def cancel_order(self, broker_order_id: str) -> bool:
        if broker_order_id in self._orders:
            self._orders[broker_order_id]['status'] = 'CANCELLED'
            return True
        return False

    def get_positions(self) -> list:
        """Return open paper positions derived from the DB."""
        from trading.models import Position
        positions = Position.objects.filter(status='OPEN', entry_order__is_paper=True)
        return [
            {
                'symbol': p.symbol.symbol,
                'side': p.side,
                'quantity': p.quantity,
                'avg_price': float(p.entry_price),
                'ltp': float(p.entry_price),
                'pnl': 0.0,
            }
            for p in positions
        ]

    def get_holdings(self) -> list:
        return []
