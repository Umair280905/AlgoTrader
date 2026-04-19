"""
agents/risk_advisor.py
Risk Advisor Agent — suggests dynamic position size multiplier
based on recent portfolio performance and exposure.
Writes suggestions to AIRiskSuggestion table for human review.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .base import BaseAgent

logger = logging.getLogger(__name__)


class RiskAdvisorAgent(BaseAgent):
    max_tokens = 600
    system_prompt = """You are a risk management advisor for an intraday trading system.
Given portfolio stats, suggest a position size multiplier.

Rules:
- Normal conditions: multiplier = 1.0
- Recent losses / high drawdown: multiplier = 0.5 (trade half size)
- Excellent recent performance: multiplier = 1.0 (never exceed 1.0 — preserve capital)
- High correlation between open positions: multiplier = 0.5

Respond ONLY in JSON (no markdown):
{
  "suggested_multiplier": <float 0.5 or 1.0>,
  "reason": "<one sentence explanation>"
}"""

    def run(self) -> dict:
        """
        Analyze current portfolio state and suggest a size multiplier.
        Saves the suggestion to AIRiskSuggestion table.
        """
        from trading.models import Position, TradingDay, AIRiskSuggestion

        today = timezone.now().date()
        cutoff_7d = today - timedelta(days=7)

        # Gather stats
        open_positions = Position.objects.filter(status='OPEN')
        open_count = open_positions.count()

        # Exposure: sum of (entry_price * qty) for open positions
        exposure = sum(
            float(p.entry_price) * p.quantity for p in open_positions
        )

        # Check correlation — are multiple positions in same direction?
        long_count = open_positions.filter(side='LONG').count()
        short_count = open_positions.filter(side='SHORT').count()
        high_correlation = (long_count >= 2 or short_count >= 2)

        # Recent drawdown
        recent_days = TradingDay.objects.filter(date__gte=cutoff_7d)
        recent_pnl = sum(float(d.net_pnl) for d in recent_days)
        recent_wins = sum(d.winning_trades for d in recent_days)
        recent_total = sum(d.total_trades for d in recent_days)
        recent_win_rate = (recent_wins / recent_total * 100) if recent_total > 0 else 50.0

        prompt = f"""Portfolio status:
- Open positions: {open_count}
- Total exposure: ₹{exposure:.0f}
- Long positions: {long_count}, Short positions: {short_count}
- High correlation risk: {high_correlation}
- Last 7 days net P&L: ₹{recent_pnl:.2f}
- Last 7 days win rate: {recent_win_rate:.1f}%
- Last 7 days trades: {recent_total}

Suggest a position size multiplier."""

        result = self.call_llm_json(prompt)

        if not result:
            result = {"suggested_multiplier": 1.0, "reason": "Could not evaluate portfolio"}

        multiplier = float(result.get("suggested_multiplier", 1.0))
        multiplier = max(0.5, min(1.0, multiplier))   # clamp between 0.5 and 1.0

        # Save suggestion to DB
        AIRiskSuggestion.objects.create(
            date=today,
            suggested_size_multiplier=multiplier,
            reason=result.get("reason", ""),
            portfolio_exposure_pct=round(exposure / 100000 * 100, 2),  # vs 1L baseline
            recent_win_rate=recent_win_rate,
            recent_drawdown=abs(min(0, recent_pnl)),
        )

        logger.info("Risk suggestion: multiplier=%.1f | %s", multiplier, result.get("reason"))
        return result
