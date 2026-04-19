"""
Opening Range Breakout (ORB) Strategy

ORB window: 9:15 AM – 9:30 AM IST (first 15 minutes)
BUY:  First 5-min candle closing above ORB_HIGH after 9:30 AM
SELL: First 5-min candle closing below ORB_LOW after 9:30 AM
Volume filter: breakout candle volume > 1.5× 5-day average volume
Time cutoff: No new signals after 1:00 PM IST
Max: 1 BUY and 1 SELL per symbol per day
"""
import logging
from datetime import time, datetime, timedelta
from typing import Optional

import pandas as pd

from .base import BaseStrategy

logger = logging.getLogger(__name__)

ORB_END = time(9, 30)         # 9:30 AM IST
CUTOFF_TIME = time(13, 0)     # 1:00 PM IST
VOLUME_MULTIPLIER = 1.5


class ORBStrategy(BaseStrategy):
    name = 'ORB'

    def generate_signal(self, symbol, candles_df: pd.DataFrame):
        if candles_df.empty:
            return None

        df = candles_df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        now = df['timestamp'].iloc[-1]

        # Check time cutoff
        if now.time() > CUTOFF_TIME:
            return None

        # Extract ORB window candles (9:15–9:30)
        today = now.date()
        market_open = pd.Timestamp(datetime.combine(today, time(9, 15)), tz=now.tzinfo)
        orb_end_ts = pd.Timestamp(datetime.combine(today, ORB_END), tz=now.tzinfo)

        orb_candles = df[(df['timestamp'] >= market_open) & (df['timestamp'] < orb_end_ts)]
        if orb_candles.empty:
            return None

        orb_high = float(orb_candles['high'].max())
        orb_low = float(orb_candles['low'].min())
        orb_range = orb_high - orb_low

        if orb_range <= 0:
            return None

        # Only consider candles after ORB window
        post_orb = df[df['timestamp'] >= orb_end_ts]
        if post_orb.empty:
            return None

        # Volume filter: 5-day average volume of the symbol (use last 5 days' candles)
        five_days_ago = pd.Timestamp(datetime.combine(today - timedelta(days=5), time(9, 15)), tz=now.tzinfo)
        prev_candles = df[df['timestamp'] < market_open]
        avg_volume = prev_candles['volume'].mean() if not prev_candles.empty else 0

        # Check if today's signals have already been acted on
        from trading.models import Signal
        today_signals = Signal.objects.filter(
            symbol=symbol,
            strategy=self.name,
            candle_timestamp__date=today,
        )
        has_buy = today_signals.filter(signal_type='BUY').exists()
        has_sell = today_signals.filter(signal_type='SELL').exists()

        curr = post_orb.iloc[-1]
        curr_close = float(curr['close'])
        curr_volume = float(curr['volume'])
        candle_ts = curr['timestamp']

        # Volume check
        volume_ok = avg_volume == 0 or curr_volume > avg_volume * VOLUME_MULTIPLIER

        # BUY breakout
        if not has_buy and curr_close > orb_high and volume_ok:
            entry = curr_close
            sl = orb_low
            target = entry + 1.5 * orb_range
            return self._build_signal(
                symbol=symbol,
                signal_type='BUY',
                entry_price=entry,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=candle_ts,
            )

        # SELL breakdown
        if not has_sell and curr_close < orb_low and volume_ok:
            entry = curr_close
            sl = orb_high
            target = entry - 1.5 * orb_range
            return self._build_signal(
                symbol=symbol,
                signal_type='SELL',
                entry_price=entry,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=candle_ts,
            )

        return None
