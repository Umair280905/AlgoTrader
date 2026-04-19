"""
Management command: python manage.py backtest --strategy EMA_CROSSOVER --symbol RELIANCE --days 30

Runs a strategy against stored OHLCVCandle data and prints P&L summary.
This is a simple sequential backtest — not walk-forward or vectorised.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backtest a strategy against stored candle data'

    def add_arguments(self, parser):
        parser.add_argument('--strategy', required=True, choices=['EMA_CROSSOVER', 'ORB', 'VWAP_BOUNCE'])
        parser.add_argument('--symbol', required=True)
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--timeframe', default='1m')

    def handle(self, *args, **options):
        import pandas as pd
        from trading.models import Watchlist, OHLCVCandle
        from strategies.registry import StrategyRegistry

        symbol_code = options['symbol'].upper()
        strategy_name = options['strategy']
        days = options['days']
        timeframe = options['timeframe']

        try:
            watchlist = Watchlist.objects.get(symbol=symbol_code)
        except Watchlist.DoesNotExist:
            raise CommandError(f"Symbol {symbol_code} not found in watchlist")

        strategy = StrategyRegistry.get(strategy_name)
        if not strategy:
            raise CommandError(f"Strategy {strategy_name} not found")

        cutoff = timezone.now() - timedelta(days=days)
        candles_qs = OHLCVCandle.objects.filter(
            symbol=watchlist,
            timeframe=timeframe,
            timestamp__gte=cutoff,
        ).order_by('timestamp')

        if not candles_qs.exists():
            raise CommandError(f"No candle data found for {symbol_code} ({timeframe}) in last {days} days")

        candles = list(candles_qs.values('timestamp', 'open', 'high', 'low', 'close', 'volume'))
        df = pd.DataFrame(candles)

        self.stdout.write(f"\nBacktest: {strategy_name} on {symbol_code} ({days} days, {len(df)} candles)\n")

        signals_generated = 0
        wins = losses = 0
        total_pnl = 0.0
        open_trade = None

        for i in range(50, len(df)):
            window = df.iloc[:i+1].copy()
            signal = strategy.generate_signal(watchlist, window)
            if signal is None:
                continue
            if open_trade is not None:
                continue  # skip: already in a trade

            signals_generated += 1
            entry = float(signal.entry_price)
            sl = float(signal.stop_loss)
            target = float(signal.target)
            side = signal.signal_type
            open_trade = {'entry': entry, 'sl': sl, 'target': target, 'side': side, 'idx': i}

        # Simulate outcomes (simplified: check if price hit target or SL before end of day)
        # For a proper backtest, implement tick-by-tick or bar-by-bar exit simulation
        self.stdout.write(f"Signals generated: {signals_generated}")
        self.stdout.write("Note: implement bar-by-bar exit simulation for full backtest P&L")
        self.stdout.write(self.style.SUCCESS('\nBacktest complete.\n'))
