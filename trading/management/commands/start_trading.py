"""
Management command: python manage.py start_trading

Verifies all prerequisites and prints a startup summary.
The actual trading runs through Celery tasks — this command just validates config.
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Verify trading configuration and print startup summary'

    def handle(self, *args, **options):
        from trading.models import Watchlist, TradingDay
        from django.utils import timezone

        self.stdout.write(self.style.SUCCESS('\n=== AlgoTrader Startup Check ===\n'))

        # Mode
        mode = 'PAPER TRADING' if settings.PAPER_TRADING else '** LIVE TRADING **'
        self.stdout.write(f"Mode:              {mode}")
        self.stdout.write(f"Phase:             {settings.PHASE}")
        self.stdout.write(f"Max daily loss:    ₹{settings.MAX_DAILY_LOSS_INR}")
        self.stdout.write(f"Max open pos:      {settings.MAX_OPEN_POSITIONS}")
        self.stdout.write(f"Max per strategy:  {settings.MAX_PER_STRATEGY}")
        self.stdout.write(f"Min cash buffer:   ₹{settings.MINIMUM_CASH_BUFFER}")

        # Watchlist
        active = Watchlist.objects.filter(is_active=True)
        self.stdout.write(f"\nActive symbols ({active.count()}):")
        for w in active:
            self.stdout.write(f"  - {w.symbol} ({w.instrument_type})")

        # Broker connectivity
        self.stdout.write('\nChecking broker connectivity...')
        try:
            from trading.engine import get_broker_client
            broker = get_broker_client()
            funds = broker.get_funds()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Broker OK — Available cash: ₹{funds['available_cash']:,.2f}"
                )
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Broker check failed: {exc}"))

        # Redis / Celery
        self.stdout.write('\nChecking Redis...')
        try:
            import redis
            r = redis.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            self.stdout.write(self.style.SUCCESS('Redis OK'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Redis check failed: {exc}"))

        self.stdout.write(self.style.SUCCESS(
            '\nAll checks complete. Start Celery worker + beat to begin trading.\n'
        ))
