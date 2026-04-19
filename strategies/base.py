"""Abstract base class for all trading strategies."""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseStrategy(ABC):
    """
    All strategies must inherit from this class and implement generate_signal().
    The engine calls generate_signal(symbol_obj, candles_df) on every tick.
    """

    name: str = ''  # Must be set in subclass — matches Signal.strategy choices

    @abstractmethod
    def generate_signal(self, symbol, candles_df: pd.DataFrame):
        """
        Evaluate latest candles and return a Signal model instance (unsaved)
        or None if no signal is triggered.

        Args:
            symbol: Watchlist model instance
            candles_df: DataFrame with columns [timestamp, open, high, low, close, volume]
                        sorted ascending, already fetched by the engine.

        Returns:
            trading.models.Signal (unsaved) or None
        """
        ...

    def _build_signal(self, symbol, signal_type, entry_price, stop_loss, target,
                      quantity, candle_timestamp):
        """Helper to build an unsaved Signal instance."""
        from trading.models import Signal
        return Signal(
            symbol=symbol,
            strategy=self.name,
            signal_type=signal_type,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target=round(target, 2),
            quantity=quantity,
            candle_timestamp=candle_timestamp,
            acted_on=False,
        )
