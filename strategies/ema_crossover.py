"""
EMA 9/21 Crossover Strategy

Timeframe: 15-minute candles
BUY:  EMA9 crosses above EMA21 (uptrend context: price > EMA21)
SELL: EMA9 crosses below EMA21
SL:   Low of signal candle (BUY) / High of signal candle (SELL)
TGT:  Entry + 2 × (Entry - SL)  — 2:1 risk-reward
"""
import logging
from typing import Optional

import pandas as pd

from .base import BaseStrategy

logger = logging.getLogger(__name__)

MIN_CANDLES = 50


class EMACrossoverStrategy(BaseStrategy):
    name = 'EMA_CROSSOVER'

    def generate_signal(self, symbol, candles_df: pd.DataFrame):
        if len(candles_df) < MIN_CANDLES:
            return None

        df = candles_df.copy()
        df['ema9']  = df['close'].ewm(span=9,  adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

        if df['ema9'].isna().iloc[-1] or df['ema21'].isna().iloc[-1]:
            return None

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        ema9_curr = curr['ema9']
        ema21_curr = curr['ema21']
        ema9_prev = prev['ema9']
        ema21_prev = prev['ema21']

        # BUY signal: EMA9 crosses above EMA21, price > EMA21 (uptrend)
        if ema9_prev <= ema21_prev and ema9_curr > ema21_curr and curr['close'] > ema21_curr:
            entry = float(curr['close'])
            sl = float(curr['low'])
            risk = entry - sl
            if risk <= 0:
                return None
            target = entry + 2 * risk
            return self._build_signal(
                symbol=symbol,
                signal_type='BUY',
                entry_price=entry,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=curr['timestamp'],
            )

        # SELL signal: EMA9 crosses below EMA21
        if ema9_prev >= ema21_prev and ema9_curr < ema21_curr:
            entry = float(curr['close'])
            sl = float(curr['high'])
            risk = sl - entry
            if risk <= 0:
                return None
            target = entry - 2 * risk
            return self._build_signal(
                symbol=symbol,
                signal_type='SELL',
                entry_price=entry,
                stop_loss=sl,
                target=target,
                quantity=1,
                candle_timestamp=curr['timestamp'],
            )

        return None
