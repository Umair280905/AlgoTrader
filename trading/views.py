import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Position, Signal, Order, TradingDay, Watchlist
from .serializers import PositionSerializer, TradingDaySerializer, SignalSerializer


# ── Dashboard ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    open_positions = Position.objects.filter(status='OPEN').select_related('symbol')
    recent_signals = Signal.objects.order_by('-created_at')[:20]
    today = timezone.now().date()
    trading_day, _ = TradingDay.objects.get_or_create(date=today)
    from django.conf import settings
    context = {
        'open_positions': open_positions,
        'recent_signals': recent_signals,
        'trading_day': trading_day,
        'paper_trading': settings.PAPER_TRADING,
        'phase': settings.PHASE,
    }
    return render(request, 'dashboard.html', context)


# ── Trades ─────────────────────────────────────────────────────────────────────

@login_required
def trades(request):
    qs = Position.objects.all().select_related('symbol', 'entry_order', 'exit_order')

    # Filters
    symbol_filter = request.GET.get('symbol', '')
    strategy_filter = request.GET.get('strategy', '')
    side_filter = request.GET.get('side', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if symbol_filter:
        qs = qs.filter(symbol__symbol__icontains=symbol_filter)
    if strategy_filter:
        qs = qs.filter(strategy=strategy_filter)
    if side_filter:
        qs = qs.filter(side=side_filter)
    if date_from:
        qs = qs.filter(opened_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(opened_at__date__lte=date_to)

    context = {
        'positions': qs[:200],
        'strategy_choices': Position.STRATEGY_CHOICES,
        'side_choices': Position.SIDE_CHOICES,
        'filters': {
            'symbol': symbol_filter,
            'strategy': strategy_filter,
            'side': side_filter,
            'date_from': date_from,
            'date_to': date_to,
        },
    }
    return render(request, 'trades.html', context)


# ── Reports ────────────────────────────────────────────────────────────────────

@login_required
def reports(request):
    trading_days = TradingDay.objects.order_by('date')

    # Equity curve data
    cumulative = 0
    equity_labels = []
    equity_data = []
    for td in trading_days:
        cumulative += float(td.net_pnl)
        equity_labels.append(str(td.date))
        equity_data.append(round(cumulative, 2))

    # Daily P&L bars
    daily_labels = [str(td.date) for td in trading_days]
    daily_pnl = [float(td.net_pnl) for td in trading_days]

    # Win/loss totals
    total_wins = sum(td.winning_trades for td in trading_days)
    total_losses = sum(td.losing_trades for td in trading_days)

    # Strategy comparison (last 30 days)
    from django.db.models import Sum
    cutoff = timezone.now().date() - timedelta(days=30)
    strategy_data = {}
    for strategy_code, strategy_label in Position.STRATEGY_CHOICES:
        pnl = Position.objects.filter(
            strategy=strategy_code,
            status__in=['CLOSED', 'SL_HIT', 'TARGET_HIT'],
            closed_at__date__gte=cutoff,
        ).aggregate(total=Sum('pnl'))['total'] or 0
        strategy_data[strategy_label] = float(pnl)

    context = {
        'equity_labels': json.dumps(equity_labels),
        'equity_data': json.dumps(equity_data),
        'daily_labels': json.dumps(daily_labels),
        'daily_pnl': json.dumps(daily_pnl),
        'total_wins': total_wins,
        'total_losses': total_losses,
        'strategy_labels': json.dumps(list(strategy_data.keys())),
        'strategy_pnl': json.dumps(list(strategy_data.values())),
    }
    return render(request, 'reports.html', context)


# ── Journal ────────────────────────────────────────────────────────────────────

@login_required
def journal(request):
    if request.method == 'POST':
        date_str = request.POST.get('date')
        notes = request.POST.get('notes', '')
        if date_str:
            td, _ = TradingDay.objects.get_or_create(date=date_str)
            td.notes = notes
            td.save(update_fields=['notes'])
            messages.success(request, 'Journal saved.')
        return redirect('journal')

    trading_days = TradingDay.objects.order_by('-date')
    return render(request, 'journal.html', {'trading_days': trading_days})


# ── Settings ───────────────────────────────────────────────────────────────────

@login_required
def settings_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_symbol':
            symbol_id = request.POST.get('symbol_id')
            wl = get_object_or_404(Watchlist, id=symbol_id)
            wl.is_active = not wl.is_active
            wl.save(update_fields=['is_active'])
            messages.success(request, f"{wl.symbol} {'activated' if wl.is_active else 'deactivated'}.")
        elif action == 'add_symbol':
            symbol = request.POST.get('symbol', '').upper().strip()
            instrument_type = request.POST.get('instrument_type', 'EQUITY')
            lot_size = int(request.POST.get('lot_size', 1))
            if symbol:
                Watchlist.objects.get_or_create(
                    symbol=symbol,
                    defaults={'instrument_type': instrument_type, 'lot_size': lot_size}
                )
                messages.success(request, f"{symbol} added to watchlist.")
        return redirect('settings')

    from django.conf import settings as django_settings
    watchlist = Watchlist.objects.all()
    context = {
        'watchlist': watchlist,
        'settings': {
            'PAPER_TRADING': django_settings.PAPER_TRADING,
            'PHASE': django_settings.PHASE,
            'MAX_DAILY_LOSS_INR': django_settings.MAX_DAILY_LOSS_INR,
            'MAX_OPEN_POSITIONS': django_settings.MAX_OPEN_POSITIONS,
            'MAX_PER_STRATEGY': django_settings.MAX_PER_STRATEGY,
            'RISK_PER_TRADE_PCT': django_settings.RISK_PER_TRADE_PCT,
            'MINIMUM_CASH_BUFFER': django_settings.MINIMUM_CASH_BUFFER,
        },
    }
    return render(request, 'settings.html', context)


# ── REST API endpoints for dashboard polling ───────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_positions(request):
    positions = Position.objects.filter(status='OPEN').select_related('symbol')
    serializer = PositionSerializer(positions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_pnl(request):
    today = timezone.now().date()
    td = TradingDay.objects.filter(date=today).first()
    return Response({
        'net_pnl': float(td.net_pnl) if td else 0.0,
        'gross_pnl': float(td.gross_pnl) if td else 0.0,
        'total_trades': td.total_trades if td else 0,
        'winning_trades': td.winning_trades if td else 0,
        'losing_trades': td.losing_trades if td else 0,
        'trading_halted': td.trading_halted if td else False,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_signals(request):
    signals = Signal.objects.order_by('-created_at')[:30]
    serializer = SignalSerializer(signals, many=True)
    return Response(serializer.data)







"""
Add these to trading/views.py
Paste at the bottom of the file.
"""

# ── AI Chat endpoint ──────────────────────────────────────────────────────────

@login_required
def ai_chat(request):
    """Render the chat page."""
    from trading.models import AIChatMessage
    session_id = str(request.user.id)
    messages = AIChatMessage.objects.filter(session_id=session_id).order_by('created_at')
    return render(request, 'ai_chat.html', {'messages': messages})


@login_required
def ai_chat_send(request):
    """Handle a chat message POST and return the reply."""
    if request.method == 'POST':
        import json as _json
        body = _json.loads(request.body)
        user_message = body.get('message', '').strip()
        if not user_message:
            from django.http import JsonResponse
            return JsonResponse({'reply': 'Please enter a message.'})

        from agents.chat_agent import TraderChatAgent
        agent = TraderChatAgent()
        session_id = str(request.user.id)
        reply = agent.run(user_message, session_id)
        from django.http import JsonResponse
        return JsonResponse({'reply': reply})

    from django.http import JsonResponse
    return JsonResponse({'reply': 'Invalid request.'}, status=400)


# ── AI Dashboard data endpoints ───────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_ai_scores(request):
    """Return latest AI signal scores for dashboard display."""
    from trading.models import AISignalScore
    from trading.serializers import AISignalScoreSerializer
    scores = AISignalScore.objects.order_by('-created_at')[:20]
    data = [
        {
            'signal_id': s.signal_id,
            'symbol': s.signal.symbol.symbol,
            'strategy': s.signal.strategy,
            'confidence_score': s.confidence_score,
            'market_sentiment': s.market_sentiment,
            'passed_gate': s.passed_gate,
            'created_at': s.created_at.isoformat(),
        }
        for s in scores
    ]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_tuner_suggestions(request):
    """Return latest tuner suggestions."""
    from trading.models import AITunerSuggestion
    suggestions = AITunerSuggestion.objects.filter(applied=False).order_by('-week_ending')[:10]
    data = [
        {
            'id': s.id,
            'strategy': s.strategy,
            'suggestion_text': s.suggestion_text,
            'current_param': s.current_param,
            'suggested_param': s.suggested_param,
            'win_rate_this_week': s.win_rate_this_week,
            'net_pnl_this_week': s.net_pnl_this_week,
            'week_ending': str(s.week_ending),
        }
        for s in suggestions
    ]
    return Response(data)