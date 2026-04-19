"""
agents/signal_confidence.py
Signal Confidence Agent — scores each strategy signal from 0-100.
Considers: multi-timeframe alignment, volume, sentiment, recent win rate.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .base import BaseAgent

logger = logging.getLogger(__name__)


class SignalConfidenceAgent(BaseAgent):
    max_tokens = 800
    system_prompt = """You are a trading signal evaluator for NSE India intraday trading.
Given a signal's details, score its conviction from 0 to 100.

Scoring guidelines:
- 80-100: Very strong setup, multiple confirmations
- 60-79:  Good setup, worth trading
- 40-59:  Borderline, marginal setup
- 0-39:   Weak signal, skip it

Consider: strategy type, risk-reward ratio, volume confirmation,
market sentiment, recent strategy performance.

Respond ONLY in JSON (no markdown):
{
  "confidence_score": <integer 0-100>,
  "timeframe_aligned": <true|false>,
  "volume_above_avg": <true|false>,
  "reasoning": "<one sentence>"
}"""

    def run(self, signal, market_analysis: dict, recent_win_rate: float) -> dict:
        """
        Score a signal.
        signal          — trading.models.Signal instance
        market_analysis — dict from MarketAnalystAgent.run()
        recent_win_rate — float 0-100, this strategy's win rate last 30 days
        """
        rr_ratio = 0
        try:
            entry = float(signal.entry_price)
            sl = float(signal.stop_loss)
            target = float(signal.target)
            risk = abs(entry - sl)
            reward = abs(target - entry)
            rr_ratio = round(reward / risk, 2) if risk > 0 else 0
        except Exception:
            pass

        prompt = f"""Evaluate this trading signal:

Symbol: {signal.symbol.symbol}
Strategy: {signal.strategy}
Signal type: {signal.signal_type}
Entry price: {signal.entry_price}
Stop loss: {signal.stop_loss}
Target: {signal.target}
Risk-reward ratio: {rr_ratio}

Market context:
- Sentiment: {market_analysis.get('sentiment', 'NEUTRAL')}
- Sentiment reason: {market_analysis.get('reason', 'N/A')}
- Risk level: {market_analysis.get('risk_level', 'MEDIUM')}

Strategy performance (last 30 days):
- Win rate: {recent_win_rate:.1f}%

Score this signal's conviction from 0 to 100."""

        result = self.call_llm_json(prompt)

        if not result:
            result = {
                "confidence_score": 50,
                "timeframe_aligned": False,
                "volume_above_avg": False,
                "reasoning": "Could not evaluate signal",
            }

        logger.info(
            "Signal confidence for %s %s: %s",
            signal.strategy, signal.symbol.symbol, result.get("confidence_score")
        )
        return result

    def get_recent_win_rate(self, strategy: str) -> float:
        """Calculate win rate for a strategy over the last 30 days."""
        from trading.models import Position
        cutoff = timezone.now() - timedelta(days=30)
        positions = Position.objects.filter(
            strategy=strategy,
            status__in=['TARGET_HIT', 'SL_HIT', 'CLOSED'],
            closed_at__gte=cutoff,
        )
        total = positions.count()
        if total == 0:
            return 50.0   # neutral default
        wins = positions.filter(status='TARGET_HIT').count()
        return round(wins / total * 100, 1)
