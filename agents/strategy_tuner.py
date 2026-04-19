"""
agents/strategy_tuner.py
Strategy Tuner Agent — weekly performance review.
Runs every Sunday and writes AITunerSuggestion records.
"""
import logging
from datetime import timedelta, date

from django.utils import timezone

from .base import BaseAgent

logger = logging.getLogger(__name__)


class StrategyTunerAgent(BaseAgent):
    max_tokens = 1200
    system_prompt = """You are a quantitative trading strategy analyst.
Given weekly performance data for intraday trading strategies on NSE India,
suggest specific, actionable parameter improvements.

Be concrete — mention actual values to change, not vague advice.
Examples: "Raise ORB volume filter from 1.5x to 2.0x",
          "Move VWAP time cutoff from 2:30 PM to 1:30 PM".

Respond ONLY in JSON (no markdown):
{
  "suggestions": [
    {
      "strategy": "<EMA_CROSSOVER|ORB|VWAP_BOUNCE|ALL>",
      "suggestion_text": "<plain English suggestion>",
      "current_param": "<current setting>",
      "suggested_param": "<new suggested setting>"
    }
  ]
}"""

    def run(self) -> list:
        """
        Analyze last 7 days performance and generate suggestions.
        Returns list of created AITunerSuggestion objects.
        """
        from trading.models import Position, TradingDay, AITunerSuggestion

        week_ending = timezone.now().date()
        cutoff = week_ending - timedelta(days=7)

        # Build performance summary per strategy
        strategy_stats = []
        for strategy_code in ['EMA_CROSSOVER', 'ORB', 'VWAP_BOUNCE']:
            positions = Position.objects.filter(
                strategy=strategy_code,
                closed_at__date__gte=cutoff,
                status__in=['TARGET_HIT', 'SL_HIT', 'CLOSED'],
            )
            total = positions.count()
            wins = positions.filter(status='TARGET_HIT').count()
            pnl = sum(float(p.pnl or 0) for p in positions)
            win_rate = (wins / total * 100) if total > 0 else 0

            strategy_stats.append({
                "strategy": strategy_code,
                "total_trades": total,
                "wins": wins,
                "win_rate": round(win_rate, 1),
                "net_pnl": round(pnl, 2),
            })

        # Weekly totals
        week_days = TradingDay.objects.filter(date__gte=cutoff)
        total_net = sum(float(d.net_pnl) for d in week_days)

        prompt = f"""Weekly performance review (last 7 days ending {week_ending}):

Total net P&L: ₹{total_net:.2f}

Strategy breakdown:
{chr(10).join(
    f"- {s['strategy']}: {s['total_trades']} trades | "
    f"Win rate: {s['win_rate']}% | Net P&L: ₹{s['net_pnl']}"
    for s in strategy_stats
)}

Current strategy parameters:
- EMA Crossover: EMA 9/21 on 15m, SL=signal candle low, Target=2x risk
- ORB: 9:15-9:30 range, volume filter=1.5x avg, cutoff=1PM
- VWAP Bounce: 0.1% proximity, trend filter=3 candles, cutoff=2:30PM

Suggest improvements for any underperforming strategies."""

        result = self.call_llm_json(prompt)
        suggestions_data = result.get("suggestions", []) if result else []

        created = []
        for s in suggestions_data:
            strategy_code = s.get("strategy", "ALL")
            # Get this week's stats for that strategy
            stats = next((x for x in strategy_stats if x["strategy"] == strategy_code), {})
            obj = AITunerSuggestion.objects.create(
                week_ending=week_ending,
                strategy=strategy_code,
                suggestion_text=s.get("suggestion_text", ""),
                current_param=s.get("current_param", ""),
                suggested_param=s.get("suggested_param", ""),
                win_rate_this_week=stats.get("win_rate", 0),
                net_pnl_this_week=stats.get("net_pnl", 0),
            )
            created.append(obj)
            logger.info("Tuner suggestion: %s", s.get("suggestion_text"))

        return created
