"""
VWAP Bounce Strategy

Timeframe: 5-minute candles
VWAP: Cumulative daily VWAP (reset at 9:15 AM IST)
BUY:  Price dips within 0.1% of VWAP then closes above — bullish candle
SELL: Price rises within 0.1% of VWAP then closes below — bearish candle
Trend filter: last 3 candles above VWAP for BUY
SL: Low of bounce candle - 0.2% (BUY) | inverse (SELL)
TGT: VWAP + (VWAP - SL)
Time cutoff: No new signals after 2:30 PM IST
Max: 3 per symbol per day
"""
import logging
from datetime import time, datetime
from typing import Optional

import pandas as pd
import numpy as np

from .base import BaseStrategy

logger = logging.getLogger(__name__)

CUTOFF_TIME = time(14, 30)      # 2:30 PM IST
VWAP_PROXIMITY_PCT = 0.001      # 0.1%
SL_BUFFER_PCT = 0.002           # 0.2%
MAX_SIGNALS_PER_DAY = 3


class VWAPBounceStrategy(BaseStrategy):
    name = 'VWAP_BOUNCE'

    def generate_signal(self, symbol, candles_df: pd.DataFrame):
        if len(candles_df) < 5:
            return None

        df = candles_df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        now = df['timestamp'].iloc[-1]
        if now.time() > CUTOFF_TIME:
            return None

        today = now.date()

        # Check daily signal count
        from trading.models import Signal
        today_count = Signal.objects.filter(
            symbol=symbol,
            strategy=self.name,
            candle_timestamp__date=today,
        ).count()
        if today_count >= MAX_SIGNALS_PER_DAY:
            return None

        # Filter today's candles for cumulative VWAP calculation
        today_start_str = str(datetime.combine(today, time(9, 15)))
        today_candles = df[df['timestamp'].dt.date == today].copy()
        if today_candles.empty:
            return None

        # Cumulative VWAP = sum(typical_price * volume) / sum(volume)
        today_candles['typical_price'] = (
            today_candles['high'] + today_candles['low'] + today_candles['close']
        ) / 3
        today_candles['tp_vol'] = today_candles['typical_price'] * today_candles['volume']
        today_candles['cum_tp_vol'] = today_candles['tp_vol'].cumsum()
        today_candles['cum_vol'] = today_candles['volume'].cumsum()
        today_candles['vwap'] = today_candles['cum_tp_vol'] / today_candles['cum_vol']

        if today_candles['vwap'].isna().iloc[-1] or today_candles['cum_vol'].iloc[-1] == 0:
            return None

        curr = today_candles.iloc[-1]
        vwap = float(curr['vwap'])
        close = float(curr['close'])
        high = float(curr['high'])
        low = float(curr['low'])
        candle_ts = curr['timestamp']

        proximity_band = vwap * VWAP_PROXIMITY_PCT

        # BUY: price dipped within 0.1% of VWAP (low near vwap) then closed above
        # Trend filter: last 3 candles were above VWAP
        if len(today_candles) >= 4:
            last_3 = today_candles.iloc[-4:-1]
            above_vwap_trend = all(
                float(r['close']) > float(r['vwap']) for _, r in last_3.iterrows()
            )
        else:
            above_vwap_trend = False

        # Bullish candle: close > open
        is_bullish = close > float(curr['open'])

        if (
            above_vwap_trend
            and abs(low - vwap) <= proximity_band
            and close > vwap
            and is_bullish
        ):
            sl = low * (1 - SL_BUFFER_PCT)
            target = vwap + (vwap - sl)
            return self._build_signal(
                symbol=symbol,
                signal_type='BUY',
                entry_price=close,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=candle_ts,
            )

        # SELL: price rose within 0.1% of VWAP (high near vwap) then closed below
        below_vwap_trend = False
        if len(today_candles) >= 4:
            last_3 = today_candles.iloc[-4:-1]
            below_vwap_trend = all(
                float(r['close']) < float(r['vwap']) for _, r in last_3.iterrows()
            )

        is_bearish = close < float(curr['open'])

        if (
            below_vwap_trend
            and abs(high - vwap) <= proximity_band
            and close < vwap
            and is_bearish
        ):
            sl = high * (1 + SL_BUFFER_PCT)
            target = vwap - (sl - vwap)
            return self._build_signal(
                symbol=symbol,
                signal_type='SELL',
                entry_price=close,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=candle_ts,
            )

        return None
