"""
agents/market_analyst.py
Market Analyst Agent — checks news sentiment and macro context
before any signal is evaluated. Uses web search tool via Claude.
"""
import logging

from .base import BaseAgent

logger = logging.getLogger(__name__)


class MarketAnalystAgent(BaseAgent):
    system_prompt = """You are a market analyst for NSE India.
Given a stock symbol, analyze:
1. Recent news sentiment (positive/negative/neutral)
2. Any earnings announcements, results, or corporate actions today
3. Macro events (RBI policy, FII/DII data, global cues like SGX Nifty)
4. Whether the stock should be avoided for trading today

Respond ONLY in JSON with this exact structure (no markdown, no explanation):
{
  "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
  "reason": "brief one-line reason",
  "avoid": true | false,
  "risk_level": "LOW" | "MEDIUM" | "HIGH"
}"""

    def run(self, symbol: str) -> dict:
        """
        Analyze market sentiment for a symbol.
        Returns dict with sentiment, reason, avoid flag, risk_level.
        """
        prompt = (
            f"Analyze NSE stock symbol: {symbol}\n"
            f"Today's date context: check for any news, earnings, "
            f"or macro events that would affect trading this symbol today."
        )

        result = self.call_llm_json(prompt)

        # Defaults if LLM fails
        if not result:
            result = {
                "sentiment": "NEUTRAL",
                "reason": "Could not fetch analysis",
                "avoid": False,
                "risk_level": "MEDIUM",
            }

        logger.info("Market analysis for %s: %s", symbol, result)
        return result
