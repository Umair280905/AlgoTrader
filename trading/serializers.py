from rest_framework import serializers
from .models import Position, Signal, Order, TradingDay, Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Watchlist
        fields = '__all__'


class SignalSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source='symbol.symbol', read_only=True)

    class Meta:
        model = Signal
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source='signal.symbol.symbol', read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


class PositionSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source='symbol.symbol', read_only=True)
    unrealised_pnl = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = '__all__'

    def get_unrealised_pnl(self, obj):
        # Real-time P&L would require a live LTP fetch; return entry-based estimate
        return None


class TradingDaySerializer(serializers.ModelSerializer):
    win_rate = serializers.SerializerMethodField()

    class Meta:
        model = TradingDay
        fields = '__all__'

    def get_win_rate(self, obj):
        if obj.total_trades == 0:
            return 0
        return round(obj.winning_trades / obj.total_trades * 100, 1)
