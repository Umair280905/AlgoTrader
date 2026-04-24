"""
Yahoo Finance broker client — real market data via yfinance + paper order simulation.

No account or API key required. Data is 15-minute delayed for NSE/BSE.

Install dependency:
    pip install yfinance

Symbol format: pass plain NSE symbols (e.g. 'RELIANCE', 'INFY', 'NIFTY50').
This client automatically appends '.NS' for NSE lookup.
"""
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SLIPPAGE_PCT = 0.0005  # 0.05%

_YF_INTERVAL_MAP = {
    '1m': '1m', '2m': '2m', '3m': '5m',
    '5m': '5m', '10m': '15m', '15m': '15m',
    '30m': '30m', '60m': '60m', '1h': '60m',
}

# Indices use a different Yahoo ticker format
_INDEX_MAP = {
    'NIFTY': '^NSEI',
    'NIFTY50': '^NSEI',
    'BANKNIFTY': '^NSEBANK',
    'SENSEX': '^BSESN',
}


def _yf_symbol(symbol: str) -> str:
    """Convert plain symbol to Yahoo Finance ticker."""
    upper = symbol.upper()
    if upper in _INDEX_MAP:
        return _INDEX_MAP[upper]
    if '.' in upper:  # already has exchange suffix
        return upper
    return f"{upper}.NS"


class YahooFinanceClient:
    """
    Drop-in broker replacement using Yahoo Finance for market data
    and in-memory simulation for order management.
    """

    _orders: dict = {}

    # ── Market data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Returns latest available quote (15-min delayed for NSE)."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(_yf_symbol(symbol))
            info = ticker.fast_info
            ltp = float(info.get('lastPrice') or info.get('last_price') or 0)
            if ltp <= 0:
                # fallback: last 1m candle
                hist = ticker.history(period='1d', interval='1m')
                if not hist.empty:
                    row = hist.iloc[-1]
                    return {
                        'ltp':    float(row['Close']),
                        'open':   float(row['Open']),
                        'high':   float(row['High']),
                        'low':    float(row['Low']),
                        'close':  float(row['Close']),
                        'volume': int(row['Volume']),
                    }
            return {
                'ltp':    ltp,
                'open':   float(info.get('open') or 0),
                'high':   float(info.get('dayHigh') or info.get('day_high') or 0),
                'low':    float(info.get('dayLow') or info.get('day_low') or 0),
                'close':  float(info.get('previousClose') or info.get('previous_close') or ltp),
                'volume': int(info.get('threeMonthAverageVolume') or 0),
            }
        except Exception as exc:
            logger.error("get_quote failed for %s: %s", symbol, exc)
            return {'ltp': 0, 'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0}

    def get_candles(self, symbol: str, timeframe: str, from_dt, to_dt) -> list:
        """
        Returns OHLCV candles from Yahoo Finance sorted by timestamp ascending.

        Note: yfinance provides 1m data for the last 7 days only.
        Intraday intervals (< 1d) are limited to 60 days max.
        """
        try:
            import yfinance as yf
            yf_interval = _YF_INTERVAL_MAP.get(timeframe, '1m')

            # yfinance needs end > start even for same-day intraday requests
            if isinstance(from_dt, datetime):
                from_date = from_dt.date() if hasattr(from_dt, 'date') else from_dt
                to_date   = to_dt.date()   if hasattr(to_dt,   'date') else to_dt
            else:
                from_date = from_dt
                to_date   = to_dt
            start_str = str(from_date)
            # Always request at least the next calendar day so same-day intraday works
            from datetime import date, timedelta as _td
            end_date = to_date if isinstance(to_date, date) else date.fromisoformat(str(to_date))
            end_str  = str(end_date + _td(days=1))

            hist = yf.download(
                _yf_symbol(symbol),
                start=start_str,
                end=end_str,
                interval=yf_interval,
                progress=False,
                auto_adjust=True,
            )

            if hist.empty:
                return []

            # yfinance >= 0.2 may return multi-level columns; flatten them
            if isinstance(hist.columns, __import__('pandas').MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            candles = []
            for ts, row in hist.iterrows():
                if hasattr(ts, 'to_pydatetime'):
                    ts = ts.to_pydatetime()
                candles.append({
                    'timestamp': ts,
                    'open':   float(row['Open']),
                    'high':   float(row['High']),
                    'low':    float(row['Low']),
                    'close':  float(row['Close']),
                    'volume': int(row['Volume']),
                })
            return candles
        except Exception as exc:
            logger.error("get_candles failed for %s: %s", symbol, exc)
            return []

    # ── Account (paper) ────────────────────────────────────────────────────────

    def get_funds(self) -> dict:
        return {
            'available_cash': 100_000.0,
            'used_margin':    0.0,
            'total_balance':  100_000.0,
        }

    # ── Orders (paper simulation) ──────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str,
        price: float = 0,
        sl: float = 0,
    ) -> str:
        """Simulate immediate fill at latest quote ± slippage."""
        quote = self.get_quote(symbol)
        ltp = quote['ltp'] or price or 100.0

        if order_type == 'MARKET':
            fill_price = round(ltp * (1 + SLIPPAGE_PCT), 2) if side == 'BUY' \
                         else round(ltp * (1 - SLIPPAGE_PCT), 2)
        else:
            fill_price = price or ltp

        order_id = f"YF-{uuid.uuid4().hex[:10].upper()}"
        self._orders[order_id] = {
            'order_id':   order_id,
            'symbol':     symbol,
            'side':       side,
            'quantity':   qty,
            'order_type': order_type,
            'status':     'FILLED',
            'filled_qty': qty,
            'avg_price':  fill_price,
            'message':    'Yahoo Finance paper fill',
        }
        logger.info("[YF-PAPER] %s %d %s @ %.2f (order_id=%s)",
                    side, qty, symbol, fill_price, order_id)
        return order_id

    def get_order_status(self, broker_order_id: str) -> dict:
        order = self._orders.get(broker_order_id)
        if order:
            return {
                'status':     order['status'],
                'filled_qty': order['filled_qty'],
                'avg_price':  order['avg_price'],
                'message':    order['message'],
            }
        return {'status': 'UNKNOWN', 'filled_qty': 0, 'avg_price': 0, 'message': 'Not found'}

    def cancel_order(self, broker_order_id: str) -> bool:
        if broker_order_id in self._orders:
            self._orders[broker_order_id]['status'] = 'CANCELLED'
            return True
        return False

    def get_positions(self) -> list:
        """Return open paper positions from the DB."""
        try:
            from trading.models import Position
            positions = Position.objects.filter(status='OPEN', entry_order__is_paper=True)
            return [
                {
                    'symbol':    p.symbol.symbol,
                    'side':      p.side,
                    'quantity':  p.quantity,
                    'avg_price': float(p.entry_price),
                    'ltp':       float(p.entry_price),
                    'pnl':       0.0,
                }
                for p in positions
            ]
        except Exception:
            return []

    def get_holdings(self) -> list:
        return []
