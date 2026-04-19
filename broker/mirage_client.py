"""
Mirage Trading REST API adapter.

This is the ONLY file that makes HTTP calls to Mirage.
All other project code calls MirageClient methods.

TODO: Review every endpoint path and response key against your Mirage API docs.
      Annotated with # TODO: CONFIRM comments wherever broker docs are needed.
"""
import time
import logging
from typing import Optional

import httpx
from django.conf import settings

from .exceptions import BrokerAPIError, OrderRejectedError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 2, 4]  # seconds between retries


class MirageClient:
    def __init__(self):
        self.base_url = settings.MIRAGE_BASE_URL.rstrip('/')
        self.headers = {
            # TODO: CONFIRM — verify exact header names with Mirage API docs
            'X-API-KEY': settings.MIRAGE_API_KEY,
            'X-API-SECRET': settings.MIRAGE_API_SECRET,
            'Content-Type': 'application/json',
        }
        self.client = httpx.Client(headers=self.headers, timeout=10)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt, backoff in enumerate(_RETRY_BACKOFF):
            try:
                resp = self.client.request(method, url, **kwargs)
                if resp.status_code in (500, 502, 503, 504):
                    logger.warning(
                        "Mirage API %s %s returned %d (attempt %d)",
                        method, path, resp.status_code, attempt + 1
                    )
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException as exc:
                logger.warning("Mirage API timeout on %s (attempt %d)", path, attempt + 1)
                last_exc = exc
                time.sleep(backoff)
            except httpx.HTTPStatusError as exc:
                raise BrokerAPIError(
                    str(exc), status_code=exc.response.status_code,
                    response_body=exc.response.text
                ) from exc
        raise BrokerAPIError(f"Max retries exceeded for {path}") from last_exc

    # ── Market data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """
        Returns: {'ltp', 'open', 'high', 'low', 'close', 'volume'}

        TODO: CONFIRM endpoint path and response keys from Mirage docs
        """
        # TODO: CONFIRM — endpoint may be /quotes/{symbol} or /market/quote?symbol=
        data = self._request('GET', f'/quotes/{symbol}')
        return {
            # TODO: CONFIRM — verify these response key names
            'ltp': data.get('ltp') or data.get('last_price') or data.get('lastPrice'),
            'open': data.get('open'),
            'high': data.get('high'),
            'low': data.get('low'),
            'close': data.get('close') or data.get('prev_close'),
            'volume': data.get('volume'),
        }

    def get_candles(self, symbol: str, timeframe: str, from_dt, to_dt) -> list:
        """
        Returns list of OHLCV dicts sorted by timestamp ascending.
        Each dict: {'timestamp', 'open', 'high', 'low', 'close', 'volume'}

        TODO: CONFIRM endpoint path, query param names, and response structure
        """
        # TODO: CONFIRM — endpoint and param names (from/to may be epoch or ISO string)
        params = {
            'symbol': symbol,
            'interval': timeframe,  # TODO: CONFIRM — '1m' or '1' or 'ONE_MINUTE'?
            'from': int(from_dt.timestamp()),
            'to': int(to_dt.timestamp()),
        }
        data = self._request('GET', '/candles', params=params)
        # TODO: CONFIRM — response may be data['candles'] or data['data'] or just a list
        candles_raw = data.get('candles') or data.get('data') or data
        candles = []
        for c in candles_raw:
            # TODO: CONFIRM — key names in each candle dict
            candles.append({
                'timestamp': c.get('timestamp') or c.get('time'),
                'open': float(c.get('open', 0)),
                'high': float(c.get('high', 0)),
                'low': float(c.get('low', 0)),
                'close': float(c.get('close', 0)),
                'volume': int(c.get('volume', 0)),
            })
        return sorted(candles, key=lambda x: x['timestamp'])

    # ── Account ────────────────────────────────────────────────────────────────

    def get_funds(self) -> dict:
        """
        Returns: {'available_cash', 'used_margin', 'total_balance'}

        TODO: CONFIRM endpoint path and response keys
        """
        # TODO: CONFIRM — endpoint may be /funds or /account/balance
        data = self._request('GET', '/funds')
        return {
            # TODO: CONFIRM — key names
            'available_cash': float(data.get('available_cash') or data.get('availableCash') or 0),
            'used_margin': float(data.get('used_margin') or data.get('usedMargin') or 0),
            'total_balance': float(data.get('total_balance') or data.get('totalBalance') or 0),
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
        """
        Places an order and returns the broker_order_id string.

        TODO: CONFIRM endpoint path, payload keys, and response key for order ID
        """
        payload = {
            # TODO: CONFIRM — exact payload field names expected by Mirage
            'symbol': symbol,
            'side': side,              # TODO: CONFIRM — 'BUY'/'SELL' or 'B'/'S'?
            'quantity': qty,
            'order_type': order_type,  # TODO: CONFIRM — 'MARKET'/'LIMIT'/'SL_MARKET'?
            'price': price,
            'stop_loss': sl,
            'exchange': 'NSE',         # TODO: CONFIRM — required field?
            'product': 'MIS',          # TODO: CONFIRM — intraday product type name
        }
        # TODO: CONFIRM — endpoint may be /orders or /order/place
        data = self._request('POST', '/orders', json=payload)
        # TODO: CONFIRM — response key: 'order_id', 'orderId', or 'id'?
        order_id = data.get('order_id') or data.get('orderId') or data.get('id')
        if not order_id:
            raise BrokerAPIError(f"No order_id in response: {data}")
        return str(order_id)

    def get_order_status(self, broker_order_id: str) -> dict:
        """
        Returns: {'status', 'filled_qty', 'avg_price', 'message'}

        TODO: CONFIRM endpoint path and response keys
        """
        # TODO: CONFIRM — endpoint may be /orders/{id} or /order/status?order_id=
        data = self._request('GET', f'/orders/{broker_order_id}')
        return {
            # TODO: CONFIRM — status values: 'FILLED'/'REJECTED'/'OPEN'/'PENDING'/'CANCELLED'?
            'status': data.get('status') or data.get('order_status'),
            'filled_qty': int(data.get('filled_qty') or data.get('filledQty') or 0),
            'avg_price': float(data.get('avg_price') or data.get('avgPrice') or 0),
            'message': data.get('message') or data.get('reason') or '',
        }

    def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancels an open order. Returns True on success.

        TODO: CONFIRM endpoint path and HTTP method (DELETE or POST?)
        """
        try:
            # TODO: CONFIRM — may be DELETE /orders/{id} or POST /orders/{id}/cancel
            self._request('DELETE', f'/orders/{broker_order_id}')
            return True
        except BrokerAPIError as exc:
            logger.error("Failed to cancel order %s: %s", broker_order_id, exc)
            return False

    def get_positions(self) -> list:
        """
        Returns all open intraday positions from the broker.

        TODO: CONFIRM endpoint path and response structure
        """
        # TODO: CONFIRM — endpoint may be /positions or /portfolio/positions
        data = self._request('GET', '/positions')
        positions_raw = data.get('positions') or data.get('data') or data
        result = []
        for p in positions_raw:
            result.append({
                # TODO: CONFIRM — key names in each position dict
                'symbol': p.get('symbol') or p.get('tradingsymbol'),
                'side': p.get('side') or ('LONG' if int(p.get('quantity', 0)) > 0 else 'SHORT'),
                'quantity': abs(int(p.get('quantity') or p.get('net_quantity') or 0)),
                'avg_price': float(p.get('avg_price') or p.get('average_price') or 0),
                'ltp': float(p.get('ltp') or p.get('last_price') or 0),
                'pnl': float(p.get('pnl') or p.get('unrealised_pnl') or 0),
            })
        return result

    def get_holdings(self) -> list:
        """
        Returns CNC equity holdings (for reference only).

        TODO: CONFIRM endpoint path and response structure
        """
        # TODO: CONFIRM — endpoint may be /holdings or /portfolio/holdings
        data = self._request('GET', '/holdings')
        holdings_raw = data.get('holdings') or data.get('data') or data
        return holdings_raw
