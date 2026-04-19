from django.contrib import admin
from .models import Watchlist, Signal, Order, Position, TradingDay, OHLCVCandle


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'instrument_type', 'is_active', 'lot_size', 'max_quantity', 'exchange')
    list_filter = ('is_active', 'instrument_type')
    search_fields = ('symbol',)
    list_editable = ('is_active',)


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'strategy', 'signal_type', 'entry_price', 'stop_loss', 'target', 'acted_on', 'created_at')
    list_filter = ('strategy', 'signal_type', 'acted_on')
    search_fields = ('symbol__symbol',)
    readonly_fields = ('created_at', 'candle_timestamp')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('get_symbol', 'side', 'order_type', 'quantity', 'status', 'filled_price', 'is_paper', 'created_at')
    list_filter = ('status', 'side', 'is_paper', 'order_type')
    search_fields = ('signal__symbol__symbol', 'broker_order_id')
    readonly_fields = ('created_at',)

    @admin.display(description='Symbol')
    def get_symbol(self, obj):
        return obj.signal.symbol.symbol


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'strategy', 'side', 'entry_price', 'quantity', 'stop_loss', 'target', 'pnl', 'status', 'opened_at')
    list_filter = ('status', 'strategy', 'side')
    search_fields = ('symbol__symbol',)
    readonly_fields = ('opened_at', 'closed_at')


@admin.register(TradingDay)
class TradingDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'net_pnl', 'gross_pnl', 'charges', 'total_trades', 'winning_trades', 'losing_trades', 'trading_halted')
    list_filter = ('trading_halted',)
    search_fields = ('date',)


@admin.register(OHLCVCandle)
class OHLCVCandleAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'timeframe', 'timestamp', 'open', 'high', 'low', 'close', 'volume')
    list_filter = ('timeframe', 'symbol')
    search_fields = ('symbol__symbol',)
    readonly_fields = ('timestamp',)






"""
Add these registrations to trading/admin.py
Paste at the bottom of the file.
"""
from trading.models import (
    AISignalScore, AIRiskSuggestion,
    AIJournalEntry, AITunerSuggestion, AIChatMessage
)

@admin.register(AISignalScore)
class AISignalScoreAdmin(admin.ModelAdmin):
    list_display = ['signal', 'confidence_score', 'market_sentiment', 'passed_gate', 'created_at']
    list_filter = ['passed_gate', 'market_sentiment', 'avoid_symbol']
    readonly_fields = ['created_at']

@admin.register(AIRiskSuggestion)
class AIRiskSuggestionAdmin(admin.ModelAdmin):
    list_display = ['date', 'suggested_size_multiplier', 'recent_win_rate', 'applied', 'created_at']
    list_filter = ['applied']
    readonly_fields = ['created_at']

@admin.register(AIJournalEntry)
class AIJournalEntryAdmin(admin.ModelAdmin):
    list_display = ['position', 'created_at']
    readonly_fields = ['created_at']

@admin.register(AITunerSuggestion)
class AITunerSuggestionAdmin(admin.ModelAdmin):
    list_display = ['week_ending', 'strategy', 'suggestion_text', 'win_rate_this_week', 'applied']
    list_filter = ['strategy', 'applied']

@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'role', 'content', 'created_at']
    list_filter = ['role']
    readonly_fields = ['created_at']
