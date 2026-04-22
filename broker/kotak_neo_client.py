"""
Kotak Neo API adapter — drop-in replacement for MirageClient.

Authentication: Kotak Neo requires an OTP-based login once per trading day.
Run the management command to authenticate and save the token:

    python manage.py kotak_login

Then set KOTAK_ACCESS_TOKEN in your .env file (or the command does it for you).

Install dependency:
    pip install neo-api-client
"""
import logging

from django.conf import settings

from .exceptions import BrokerAPIError

logger = logging.getLogger(__name__)

_TIMEFRAME_MAP = {
    '1m': '1', '3m': '3', '5m': '5', '10m': '10',
    '15m': '15', '30m': '30', '60m': '60', '1h': '60',
}
_SIDE_MAP = {'BUY': 'B', 'SELL': 'S'}
_ORDER_TYPE_MAP = {
    'MARKET': 'MKT', 'LIMIT': 'L', 'SL_MARKET': 'SL-M', 'SL_LIMIT': 'SL',
}
_STATUS_MAP = {
    'complete': 'FILLED', 'completed': 'FILLED',
    'open': 'OPEN', 'pending': 'PENDING',
    'rejected': 'REJECTED', 'cancelled': 'CANCELLED', 'canceled': 'CANCELLED',
}


class KotakNeoClient:
    def __init__(self):
        try:
            from neo_api_client import NeoAPI
        except ImportError as exc:
            raise ImportError(
                "neo-api-client is not installed. Run: pip install neo-api-client"
            ) from exc

        if not settings.KOTAK_ACCESS_TOKEN:
            raise BrokerAPIError(
                "KOTAK_ACCESS_TOKEN is not set. "
                "Run 'python manage.py kotak_login' to authenticate."
            )

        self._neo = NeoAPI(
            consumer_key=settings.KOTAK_CONSUMER_KEY,
            consumer_secret=settings.KOTAK_CONSUMER_SECRET,
            environment='prod',
            access_token=settings.KOTAK_ACCESS_TOKEN,
            neo_fin_key=settings.KOTAK_NEO_FIN_KEY,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _unwrap(self, response, key: str = 'data'):
        """Extract data from a Kotak Neo response; raise BrokerAPIError on failure."""
        if isinstance(response, dict):
            error = response.get('error') or response.get('errMsg')
            st = response.get('stCode') or response.get('stat')
            if error or (st not in (None, 200, '200', 'Ok')):
                raise BrokerAPIError(str(error or response.get('message') or response))
            return response.get(key, response)
        return response

    def _get_instrument_token(self, symbol: str) -> tuple[str, str]:
        """
        Resolve a plain symbol to (instrument_token, exchange_segment).
        Tries NSE equity first, then NSE F&O.

        TODO: For production replace with a pre-loaded scrip master lookup
              to avoid an extra API round-trip on every quote/candle call.
        """
        for exchange in ('nse_cm', 'nse_fo'):
            try:
                resp = self._neo.search_scrip(exchange_segment=exchange, symbol=symbol)
                data = self._unwrap(resp)
                if data:
                    entry = data[0] if isinstance(data, list) else data
                    token = (
                        entry.get('pSymbol')
                        or entry.get('token')
                        or entry.get('instrument_token')
                    )
                    if token:
                        return str(token), exchange
            except Exception:
                continue
        raise BrokerAPIError(f"Could not resolve instrument token for symbol: {symbol}")

    def _trading_symbol(self, symbol: str, exchange: str) -> str:
        """Convert plain symbol to Kotak trading_symbol (e.g. 'SBIN-EQ')."""
        suffix = '-EQ' if exchange == 'nse_cm' else ''
        return symbol if symbol.endswith(suffix) else f"{symbol}{suffix}"

    # ── Market data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Returns: {'ltp', 'open', 'high', 'low', 'close', 'volume'}"""
        token, exchange = self._get_instrument_token(symbol)
        resp = self._neo.quotes(
            instrument_tokens=[{"instrument_token": token, "exchange_segment": exchange}],
            quote_type="",
            isIndex=False,
        )
        data = self._unwrap(resp)
        q = data[0] if isinstance(data, list) else data
        return {
            'ltp':    float(q.get('ltp') or q.get('lastTradedPrice') or 0),
            'open':   float(q.get('open') or q.get('openPrice') or 0),
            'high':   float(q.get('high') or q.get('highPrice') or 0),
            'low':    float(q.get('low') or q.get('lowPrice') or 0),
            'close':  float(q.get('cls') or q.get('close') or q.get('previousClose') or 0),
            'volume': int(q.get('vol') or q.get('volume') or 0),
        }

    def get_candles(self, symbol: str, timeframe: str, from_dt, to_dt) -> list:
        """Returns list of OHLCV dicts sorted by timestamp ascending."""
        token, exchange = self._get_instrument_token(symbol)
        kotak_exchange = 'NSE' if exchange == 'nse_cm' else 'NFO'
        candle_type = _TIMEFRAME_MAP.get(timeframe, '1')

        resp = self._neo.intradaycandles(
            exchange=kotak_exchange,
            token=token,
            to_date=to_dt.strftime('%Y-%m-%d %H:%M:%S'),
            from_date=from_dt.strftime('%Y-%m-%d %H:%M:%S'),
            type=candle_type,
        )
        raw = self._unwrap(resp)
        candles_raw = raw if isinstance(raw, list) else (raw.get('candles') or raw.get('data') or [])

        candles = []
        for c in candles_raw:
            if isinstance(c, list):
                # [timestamp, open, high, low, close, volume]
                candles.append({
                    'timestamp': c[0],
                    'open': float(c[1]), 'high': float(c[2]),
                    'low': float(c[3]), 'close': float(c[4]),
                    'volume': int(c[5]) if len(c) > 5 else 0,
                })
            else:
                candles.append({
                    'timestamp': c.get('timestamp') or c.get('time'),
                    'open': float(c.get('open', 0)), 'high': float(c.get('high', 0)),
                    'low': float(c.get('low', 0)),   'close': float(c.get('close', 0)),
                    'volume': int(c.get('volume', 0)),
                })
        return sorted(candles, key=lambda x: x['timestamp'])

    # ── Account ────────────────────────────────────────────────────────────────

    def get_funds(self) -> dict:
        """Returns: {'available_cash', 'used_margin', 'total_balance'}"""
        resp = self._neo.limits(segment='', exchange='', product='')
        data = self._unwrap(resp)
        if isinstance(data, list):
            data = data[0] if data else {}
        return {
            'available_cash': float(data.get('cashMargin') or data.get('net') or 0),
            'used_margin':    float(data.get('marginUsed') or data.get('utilisedAmount') or 0),
            'total_balance':  float(data.get('gross') or data.get('grossAvailableMargin') or 0),
        }

    # ── Orders ─────────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        order_type: str,
        price: float = 0,
        sl: float = 0,
    ) -> str:
        """Places an order and returns the broker_order_id string."""
        token, exchange = self._get_instrument_token(symbol)
        trading_sym = self._trading_symbol(symbol, exchange)
        kotak_order_type = _ORDER_TYPE_MAP.get(order_type.upper(), 'MKT')
        transaction_type = _SIDE_MAP.get(side.upper(), 'B')

        resp = self._neo.place_order(
            exchange_segment=exchange,
            product='MIS',
            price=str(price),
            order_type=kotak_order_type,
            quantity=str(qty),
            validity='DAY',
            trading_symbol=trading_sym,
            transaction_type=transaction_type,
            amo='NO',
            disclosed_quantity='0',
            market_protection='0',
            pf='N',
            trigger_price=str(sl) if sl else '0',
            tag=None,
        )
        data = self._unwrap(resp)
        if isinstance(data, list):
            data = data[0] if data else {}
        order_id = data.get('nOrdNo') or data.get('orderId') or data.get('order_id')
        if not order_id:
            raise BrokerAPIError(f"No order_id in response: {data}")
        return str(order_id)

    def get_order_status(self, broker_order_id: str) -> dict:
        """Returns: {'status', 'filled_qty', 'avg_price', 'message'}"""
        resp = self._neo.order_history(order_id=broker_order_id)
        data = self._unwrap(resp)
        entry = data[0] if isinstance(data, list) and data else (data or {})
        raw_status = (entry.get('ordSt') or entry.get('status') or '').lower()
        return {
            'status':     _STATUS_MAP.get(raw_status, raw_status.upper()),
            'filled_qty': int(entry.get('fldQty') or entry.get('filledQty') or 0),
            'avg_price':  float(entry.get('avgPrc') or entry.get('avgPrice') or 0),
            'message':    entry.get('rejRsn') or entry.get('message') or '',
        }

    def cancel_order(self, broker_order_id: str) -> bool:
        """Cancels an open order. Returns True on success."""
        try:
            self._unwrap(self._neo.cancel_order(order_id=broker_order_id, isVerify=False))
            return True
        except BrokerAPIError as exc:
            logger.error("Failed to cancel order %s: %s", broker_order_id, exc)
            return False

    def get_positions(self) -> list:
        """Returns all open intraday positions (non-zero net quantity)."""
        resp = self._neo.positions()
        data = self._unwrap(resp)
        positions_raw = data if isinstance(data, list) else (data.get('positions') or [])
        result = []
        for p in positions_raw:
            net_qty = int(p.get('netQty') or p.get('net_quantity') or 0)
            if net_qty == 0:
                continue
            result.append({
                'symbol':    p.get('trdSym') or p.get('sym') or p.get('tradingSymbol') or '',
                'side':      'LONG' if net_qty > 0 else 'SHORT',
                'quantity':  abs(net_qty),
                'avg_price': float(p.get('avgBuyPrc') or p.get('avgSellPrc') or p.get('avgPrice') or 0),
                'ltp':       float(p.get('ltp') or 0),
                'pnl':       float(p.get('npnl') or p.get('unrealPnl') or 0),
            })
        return result

    def get_holdings(self) -> list:
        """Returns CNC equity holdings (for reference only)."""
        resp = self._neo.holdings()
        data = self._unwrap(resp)
        return data if isinstance(data, list) else (data.get('holdings') or [])
