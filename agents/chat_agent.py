"""
agents/chat_agent.py
Trader Chat Agent — answers natural language questions about
trading history, performance, and decisions.
"""
import logging

from django.utils import timezone

from .base import BaseAgent

logger = logging.getLogger(__name__)


class TraderChatAgent(BaseAgent):
    max_tokens = 1000
    system_prompt = """You are a trading assistant for an NSE intraday trader using AlgoTrader.
You have access to the trader's complete trade history, signals, and performance data.
Answer questions clearly, concisely, and factually based only on the data provided.
If you don't have enough data to answer, say so honestly.
Use ₹ for Indian rupees. Keep responses under 150 words."""

    def run(self, user_message: str, session_id: str) -> str:
        """
        Answer a trader's question using trade data as context.
        Saves the conversation to AIChatMessage.
        Returns the assistant's reply as a string.
        """
        from trading.models import (
            AIChatMessage, Position, Signal, TradingDay
        )

        # Save user message
        AIChatMessage.objects.create(
            session_id=session_id,
            role='user',
            content=user_message,
        )

        # Build data context to inject into the prompt
        context = self._build_context()

        # Get last 10 messages for conversation history
        history_qs = AIChatMessage.objects.filter(
            session_id=session_id
        ).order_by('-created_at')[:10]
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(history_qs)
        ]

        full_message = f"""Current trading data context:
{context}

Trader's question: {user_message}"""

        reply = self.call_llm(full_message, history=history[:-1])  # exclude current msg

        if not reply:
            reply = "I couldn't process your question. Please try again."

        # Save assistant reply
        AIChatMessage.objects.create(
            session_id=session_id,
            role='assistant',
            content=reply,
        )

        return reply

    def _build_context(self) -> str:
        """Build a concise data summary to inject as context."""
        from trading.models import Position, TradingDay, Signal

        today = timezone.now().date()

        # Today's stats
        td = TradingDay.objects.filter(date=today).first()
        today_str = (
            f"Today ({today}): Net P&L ₹{td.net_pnl}, "
            f"{td.total_trades} trades, {td.winning_trades}W/{td.losing_trades}L"
            if td else "No trading data for today yet."
        )

        # Open positions
        open_pos = Position.objects.filter(status='OPEN').select_related('symbol')
        if open_pos.exists():
            pos_str = " | ".join(
                f"{p.symbol.symbol} {p.side} @ ₹{p.entry_price} [{p.strategy}]"
                for p in open_pos
            )
        else:
            pos_str = "No open positions"

        # Last 5 closed trades
        recent = Position.objects.filter(
            status__in=['TARGET_HIT', 'SL_HIT', 'CLOSED']
        ).order_by('-closed_at')[:5].select_related('symbol')
        recent_str = " | ".join(
            f"{p.symbol.symbol} {p.status} ₹{p.pnl}"
            for p in recent
        ) or "No recent closed trades"

        # Last 7 days summary
        from datetime import timedelta
        week_days = TradingDay.objects.filter(
            date__gte=today - timedelta(days=7)
        ).order_by('date')
        week_str = " | ".join(
            f"{d.date}: ₹{d.net_pnl} ({d.winning_trades}W/{d.losing_trades}L)"
            for d in week_days
        ) or "No weekly data"

        return f"""--- Today ---
{today_str}

--- Open Positions ---
{pos_str}

--- Last 5 Closed Trades ---
{recent_str}

--- Last 7 Days ---
{week_str}"""
