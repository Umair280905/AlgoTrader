from django.db import models


class Watchlist(models.Model):
    INSTRUMENT_CHOICES = [
        ('EQUITY', 'Equity'),
        ('INDEX_FUTURES', 'Index Futures'),
    ]
    symbol = models.CharField(max_length=20, unique=True)
    instrument_type = models.CharField(max_length=20, choices=INSTRUMENT_CHOICES, default='EQUITY')
    exchange = models.CharField(max_length=10, default='NSE')
    lot_size = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    max_quantity = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.symbol} ({self.instrument_type})"

    class Meta:
        ordering = ['symbol']


class Signal(models.Model):
    STRATEGY_CHOICES = [
        ('EMA_CROSSOVER', 'EMA Crossover'),
        ('ORB', 'Opening Range Breakout'),
        ('VWAP_BOUNCE', 'VWAP Bounce'),
    ]
    SIGNAL_TYPE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('EXIT_LONG', 'Exit Long'),
        ('EXIT_SHORT', 'Exit Short'),
    ]

    symbol = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name='signals')
    strategy = models.CharField(max_length=30, choices=STRATEGY_CHOICES)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPE_CHOICES)
    entry_price = models.DecimalField(max_digits=12, decimal_places=2)
    stop_loss = models.DecimalField(max_digits=12, decimal_places=2)
    target = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField(default=1)
    candle_timestamp = models.DateTimeField()
    acted_on = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.strategy}] {self.signal_type} {self.symbol.symbol} @ {self.entry_price}"

    class Meta:
        ordering = ['-created_at']


class Order(models.Model):
    ORDER_TYPE_CHOICES = [
        ('MARKET', 'Market'),
        ('LIMIT', 'Limit'),
        ('SL_MARKET', 'SL Market'),
    ]
    SIDE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('OPEN', 'Open'),
        ('FILLED', 'Filled'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, related_name='orders')
    broker_order_id = models.CharField(max_length=50, unique=True)
    order_type = models.CharField(max_length=15, choices=ORDER_TYPE_CHOICES)
    side = models.CharField(max_length=5, choices=SIDE_CHOICES)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    filled_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    filled_at = models.DateTimeField(null=True, blank=True)
    is_paper = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} {self.signal.symbol.symbol} [{self.status}]"

    class Meta:
        ordering = ['-created_at']


class Position(models.Model):
    SIDE_CHOICES = [
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('SL_HIT', 'Stop Loss Hit'),
        ('TARGET_HIT', 'Target Hit'),
    ]
    STRATEGY_CHOICES = [
        ('EMA_CROSSOVER', 'EMA Crossover'),
        ('ORB', 'Opening Range Breakout'),
        ('VWAP_BOUNCE', 'VWAP Bounce'),
    ]

    symbol = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name='positions')
    strategy = models.CharField(max_length=30, choices=STRATEGY_CHOICES)
    side = models.CharField(max_length=5, choices=SIDE_CHOICES)
    entry_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField()
    stop_loss = models.DecimalField(max_digits=12, decimal_places=2)
    target = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    exit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pnl = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    entry_order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='entry_positions'
    )
    exit_order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='exit_positions'
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.side} {self.symbol.symbol} [{self.status}] P&L: {self.pnl}"

    class Meta:
        ordering = ['-opened_at']


class TradingDay(models.Model):
    date = models.DateField(unique=True)
    gross_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    trading_halted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.date} | Net P&L: {self.net_pnl} | Trades: {self.total_trades}"

    class Meta:
        ordering = ['-date']


class OHLCVCandle(models.Model):
    symbol = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name='candles')
    timeframe = models.CharField(max_length=5)  # 1m, 5m, 15m
    timestamp = models.DateTimeField()
    open = models.DecimalField(max_digits=12, decimal_places=2)
    high = models.DecimalField(max_digits=12, decimal_places=2)
    low = models.DecimalField(max_digits=12, decimal_places=2)
    close = models.DecimalField(max_digits=12, decimal_places=2)
    volume = models.BigIntegerField()
    vwap = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.symbol.symbol} {self.timeframe} @ {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
        unique_together = ('symbol', 'timeframe', 'timestamp')
        indexes = [
            models.Index(fields=['symbol', 'timeframe', 'timestamp']),
        ]







# ─────────────────────────────────────────────────────────────────────────────
# ADD THESE MODELS at the bottom of trading/models.py
# Open trading/models.py and paste everything below the OHLCVCandle class
# ─────────────────────────────────────────────────────────────────────────────


class AISignalScore(models.Model):
    """
    Stores the Signal Confidence Agent's conviction score for every signal.
    Linked 1-to-1 with Signal.
    """
    signal = models.OneToOneField(
        Signal, on_delete=models.CASCADE, related_name='ai_score'
    )
    confidence_score = models.IntegerField(default=0)          # 0–100
    market_sentiment = models.CharField(max_length=20, default='NEUTRAL',
        choices=[('POSITIVE','Positive'),('NEUTRAL','Neutral'),('NEGATIVE','Negative')])
    sentiment_reason = models.TextField(blank=True)            # e.g. "RBI rate hike today"
    avoid_symbol = models.BooleanField(default=False)          # Market Analyst flag
    timeframe_aligned = models.BooleanField(default=False)     # multi-TF confirmation
    volume_above_avg = models.BooleanField(default=False)
    strategy_recent_winrate = models.FloatField(default=0.0)   # last 30 days %
    passed_gate = models.BooleanField(default=False)           # crossed threshold?
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Score {self.confidence_score} | {self.signal}"

    class Meta:
        ordering = ['-created_at']


class AIRiskSuggestion(models.Model):
    """
    Risk Advisor Agent writes dynamic position sizing suggestions here.
    Human reviews and applies manually.
    """
    date = models.DateField()
    suggested_size_multiplier = models.FloatField(default=1.0)  # e.g. 0.5 = half size
    reason = models.TextField()                                  # agent's explanation
    portfolio_exposure_pct = models.FloatField(default=0.0)     # % capital at risk
    recent_win_rate = models.FloatField(default=0.0)
    recent_drawdown = models.FloatField(default=0.0)            # ₹ drawdown last 7 days
    applied = models.BooleanField(default=False)                # did you apply it?
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} | Multiplier: {self.suggested_size_multiplier}x | Applied: {self.applied}"

    class Meta:
        ordering = ['-date']


class AIJournalEntry(models.Model):
    """
    Journal Agent auto-writes one entry per closed trade.
    Linked to Position.
    """
    position = models.OneToOneField(
        Position, on_delete=models.CASCADE, related_name='ai_journal'
    )
    rationale = models.TextField()       # why the trade was taken
    what_worked = models.TextField(blank=True)
    what_failed = models.TextField(blank=True)
    lesson = models.TextField(blank=True)
    market_context = models.TextField(blank=True)   # what was happening in market
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Journal: {self.position.symbol.symbol} | {self.created_at.date()}"

    class Meta:
        ordering = ['-created_at']


class AITunerSuggestion(models.Model):
    """
    Strategy Tuner Agent writes weekly parameter suggestions here.
    Human reviews every Monday.
    """
    STRATEGY_CHOICES = [
        ('EMA_CROSSOVER', 'EMA Crossover'),
        ('ORB', 'Opening Range Breakout'),
        ('VWAP_BOUNCE', 'VWAP Bounce'),
        ('ALL', 'All Strategies'),
    ]

    week_ending = models.DateField()
    strategy = models.CharField(max_length=30, choices=STRATEGY_CHOICES)
    suggestion_text = models.TextField()            # plain English suggestion
    current_param = models.CharField(max_length=100, blank=True)   # e.g. "volume_filter=1.5x"
    suggested_param = models.CharField(max_length=100, blank=True) # e.g. "volume_filter=2.0x"
    win_rate_this_week = models.FloatField(default=0.0)
    net_pnl_this_week = models.FloatField(default=0.0)
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.week_ending} | {self.strategy} | Applied: {self.applied}"

    class Meta:
        ordering = ['-week_ending']


class AIChatMessage(models.Model):
    """
    Stores conversation history for the Trader Chat Agent.
    Each user question and agent answer is stored here.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    session_id = models.CharField(max_length=100)    # browser session or user ID
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"

    class Meta:
        ordering = ['created_at']


     