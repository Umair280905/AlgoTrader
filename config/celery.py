import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('algo_trader')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run-strategies': {
        'task': 'trading.tasks.run_strategies',
        'schedule': 60.0,
    },
    'sync-orders': {
        'task': 'trading.tasks.sync_order_status',
        'schedule': 30.0,
    },
    'check-positions': {
        'task': 'trading.tasks.check_positions',
        'schedule': 60.0,
    },
    'square-off': {
        'task': 'trading.tasks.square_off_all',
        # 3:15 PM IST = 09:45 UTC
        'schedule': crontab(hour=9, minute=45, day_of_week='1-5'),
    },
    'daily-report': {
        'task': 'trading.tasks.generate_daily_report',
        # 3:45 PM IST = 10:15 UTC
        'schedule': crontab(hour=10, minute=15, day_of_week='1-5'),
    },
    'purge-candles': {
        'task': 'trading.tasks.purge_old_candles',
        # 4:00 PM IST = 10:30 UTC
        'schedule': crontab(hour=10, minute=30, day_of_week='1-5'),
    },
    'morning-brief': {
        'task': 'trading.tasks.send_morning_brief',
        # 9:00 AM IST = 03:30 UTC
        'schedule': crontab(hour=3, minute=30, day_of_week='1-5'),
    },
    'run-risk-advisor': {
    'task': 'trading.tasks.run_risk_advisor',
    'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),
},
'run-strategy-tuner': {
    'task': 'trading.tasks.run_strategy_tuner',
    'schedule': crontab(hour=20, minute=0, day_of_week='0'),  # Sunday 8 PM
},
}
