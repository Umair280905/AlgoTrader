"""
agents/journal_agent.py
Journal Agent — auto-writes a trade rationale after every position closes.
Saves to AIJournalEntry and updates TradingDay.notes.
"""
import logging
from turtle import position

from trading.models import AIJournalEntry

from .base import BaseAgent

logger = logging.getLogger(__name__)


class JournalAgent(BaseAgent):
    max_tokens = 1000
    system_prompt = """You are a trading journal writer for an intraday trader.
Given a closed trade's details, write a concise journal entry.
Be specific, factual, and educational.

Respond ONLY in JSON (no markdown):
{
  "rationale": "<why this trade was taken — 2 sentences>",
  "what_worked": "<what went right, or empty string if loss>",
  "what_failed": "<what went wrong, or empty string if win>",
  "lesson": "<one actionable lesson for next time>",
  "market_context": "<brief market context at time of trade>"
}"""

    def run(self, position) -> dict:
        """
        Write a journal entry for a closed position.
        position — trading.models.Position instance (must be closed)
        """
        from trading.models import AIJournalEntry

        # Don't re-write if entry already exists
        # if hasattr(position, 'ai_journal'):
        #     return {}
        from trading.models import AIJournalEntry
        if AIJournalEntry.objects.filter(position=position).exists():
            AIJournalEntry.objects.filter(position=position).delete()

        pnl = float(position.pnl) if position.pnl else 0
        outcome = "WIN" if pnl > 0 else "LOSS"
        duration_min = 0
        if position.closed_at and position.opened_at:
            duration_min = int((position.closed_at - position.opened_at).seconds / 60)

        prompt = f"""Write a journal entry for this closed trade:

Symbol: {position.symbol.symbol}
Strategy: {position.strategy}
Direction: {position.side}
Entry price: ₹{position.entry_price}
Exit price: ₹{position.exit_price}
Stop loss was: ₹{position.stop_loss}
Target was: ₹{position.target}
Exit reason: {position.status}
P&L: ₹{pnl:.2f} ({outcome})
Duration: {duration_min} minutes"""

        result = self.call_llm_json(prompt)

        if not result:
            result = {
                "rationale": f"{position.strategy} signal on {position.symbol.symbol}.",
                "what_worked": "Target hit." if outcome == "WIN" else "",
                "what_failed": "" if outcome == "WIN" else "Stop loss hit.",
                "lesson": "Review setup conditions.",
                "market_context": "N/A",
            }

        # Save to DB
        AIJournalEntry.objects.create(
            position=position,
            rationale=result.get("rationale", ""),
            what_worked=result.get("what_worked", ""),
            what_failed=result.get("what_failed", ""),
            lesson=result.get("lesson", ""),
            market_context=result.get("market_context", ""),
        )

        # Also append to TradingDay notes
        if position.closed_at:
            from trading.models import TradingDay
            td, _ = TradingDay.objects.get_or_create(date=position.closed_at.date())
            new_note = (
                f"\n[{position.symbol.symbol} {outcome} ₹{pnl:.0f}] "
                f"{result.get('lesson', '')}"
            )
            td.notes += new_note
            td.save(update_fields=['notes'])

        logger.info("Journal written for position %d", position.id)
        return result
