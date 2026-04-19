"""
agents/orchestrator.py
AI Orchestrator — coordinates all agents for each trading signal.
Called from trading/tasks.py after a signal is generated.
"""
import logging

from django.conf import settings

from .market_analyst import MarketAnalystAgent
from .signal_confidence import SignalConfidenceAgent
from .risk_advisor import RiskAdvisorAgent

logger = logging.getLogger(__name__)

# Minimum confidence score to pass the AI Decision Gate
MIN_CONFIDENCE = getattr(settings, 'AI_MIN_CONFIDENCE', 60)


class AIOrchestrator:
    """
    Coordinates Market Analyst + Signal Confidence agents.
    Called once per signal. Returns (passed: bool, score: int).
    """

    def __init__(self):
        self.analyst = MarketAnalystAgent()
        self.confidence_agent = SignalConfidenceAgent()
        self.risk_advisor = RiskAdvisorAgent()

    def evaluate_signal(self, signal) -> tuple:
        """
        Full AI evaluation pipeline for a signal.

        Returns:
            (passed: bool, confidence_score: int)

        Side effects:
            - Creates AISignalScore record
            - Logs decision
        """
        from trading.models import AISignalScore

        try:
            # Step 1: Market Analyst — check sentiment & news
            market_analysis = self.analyst.run(signal.symbol.symbol)

            # If analyst says avoid, short-circuit with score 0
            if market_analysis.get('avoid', False):
                logger.info(
                    "Market Analyst flagged %s as avoid: %s",
                    signal.symbol.symbol,
                    market_analysis.get('reason')
                )
                AISignalScore.objects.create(
                    signal=signal,
                    confidence_score=0,
                    market_sentiment=market_analysis.get('sentiment', 'NEGATIVE'),
                    sentiment_reason=market_analysis.get('reason', ''),
                    avoid_symbol=True,
                    passed_gate=False,
                )
                return False, 0

            # Step 2: Signal Confidence — score the setup
            recent_win_rate = self.confidence_agent.get_recent_win_rate(signal.strategy)
            score_data = self.confidence_agent.run(signal, market_analysis, recent_win_rate)

            confidence_score = int(score_data.get('confidence_score', 50))
            passed = confidence_score >= MIN_CONFIDENCE

            # Step 3: Save the score to DB
            AISignalScore.objects.create(
                signal=signal,
                confidence_score=confidence_score,
                market_sentiment=market_analysis.get('sentiment', 'NEUTRAL'),
                sentiment_reason=market_analysis.get('reason', ''),
                avoid_symbol=False,
                timeframe_aligned=score_data.get('timeframe_aligned', False),
                volume_above_avg=score_data.get('volume_above_avg', False),
                strategy_recent_winrate=recent_win_rate,
                passed_gate=passed,
            )

            logger.info(
                "AI Gate: %s %s score=%d threshold=%d → %s",
                signal.strategy,
                signal.symbol.symbol,
                confidence_score,
                MIN_CONFIDENCE,
                "PASS" if passed else "BLOCK",
            )

            return passed, confidence_score

        except Exception as exc:
            logger.error("Orchestrator error for signal %d: %s", signal.id, exc)
            # Fail open — if AI crashes, let existing RiskController decide
            return True, 50

    def run_risk_advisor(self):
        """Run the Risk Advisor Agent — call once per day at market open."""
        try:
            return self.risk_advisor.run()
        except Exception as exc:
            logger.error("Risk advisor error: %s", exc)
            return {"suggested_multiplier": 1.0, "reason": "Error in risk advisor"}
