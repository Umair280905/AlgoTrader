"""Strategy registry — loads all active strategy instances."""
from .ema_crossover import EMACrossoverStrategy
from .orb import ORBStrategy
from .vwap_bounce import VWAPBounceStrategy


class StrategyRegistry:
    _strategies = [
        EMACrossoverStrategy(),
        ORBStrategy(),
        VWAPBounceStrategy(),
    ]

    @classmethod
    def all(cls):
        """Return all registered strategy instances."""
        return cls._strategies

    @classmethod
    def get(cls, name: str):
        """Return a strategy by its name attribute."""
        for s in cls._strategies:
            if s.name == name:
                return s
        return None
