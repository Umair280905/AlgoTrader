"""
create_positions.py  (FIXED VERSION)
=====================================
Creates 5 clean OPEN positions for demo.
Run:  python create_positions.py
"""
import os, sys, django, uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from trading.models import Watchlist, Signal, Order, Position
from django.utils import timezone
from decimal import Decimal

print("="*50)
print("  Creating demo open positions")
print("="*50)

# Clean exit signals from previous run
exit_sigs = Signal.objects.filter(signal_type__in=['EXIT_LONG','EXIT_SHORT'])
n = exit_sigs.count()
if n:
    Order.objects.filter(signal__in=exit_sigs).delete()
    exit_sigs.delete()
    print(f"Cleaned {n} exit signals")

# Clean old open positions
old = Position.objects.filter(status='OPEN').count()
if old:
    Position.objects.filter(status='OPEN').delete()
    print(f"Cleared {old} old open positions")

trades = [
    ("RELIANCE",  "EMA_CROSSOVER", "BUY",  "2905.50","2876.00","2963.00", 3),
    ("TCS",       "ORB",           "BUY",  "3985.00","3940.00","4075.00", 2),
    ("HDFCBANK",  "VWAP_BOUNCE",   "BUY",  "1712.00","1690.00","1756.00", 4),
    ("INFY",      "EMA_CROSSOVER", "SELL", "1823.00","1848.00","1775.00", 5),
    ("SBIN",      "VWAP_BOUNCE",   "BUY",  "842.50", "831.00", "865.00",  8),
]

created = 0
for sym_name, strategy, sig_type, entry, sl, target, qty in trades:
    sym, _ = Watchlist.objects.get_or_create(
        symbol=sym_name,
        defaults={'instrument_type':'EQUITY','exchange':'NSE',
                  'lot_size':1,'max_quantity':10,'is_active':True}
    )
    sym.is_active = True
    sym.save()

    e = Decimal(entry); s = Decimal(sl); t = Decimal(target)
    now = timezone.now()

    sig = Signal.objects.create(
        symbol=sym, strategy=strategy, signal_type=sig_type,
        entry_price=e, stop_loss=s, target=t,
        quantity=qty, candle_timestamp=now, acted_on=True,
    )
    order = Order.objects.create(
        signal=sig,
        broker_order_id="DEMO" + uuid.uuid4().hex[:8].upper(),
        order_type='MARKET',
        side='BUY' if sig_type=='BUY' else 'SELL',
        quantity=qty, price=e, status='FILLED',
        filled_price=e, filled_at=now, is_paper=True,
    )
    side = 'LONG' if sig_type=='BUY' else 'SHORT'
    Position.objects.create(
        symbol=sym, strategy=strategy, side=side,
        entry_price=e, quantity=qty, stop_loss=s, target=t,
        status='OPEN', entry_order=order, opened_at=now,
    )
    created += 1
    print(f"  OPEN  {sym_name:12} {strategy:15} {side:5} Rs{entry} qty={qty}")

print()
print(f"Created  : {created} positions")
print(f"In DB    : {Position.objects.filter(status='OPEN').count()} open")
print()
print("Refresh http://localhost:8000 now!")