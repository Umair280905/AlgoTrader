# """
# agents/base.py
# Base class for all AI agents. Every agent calls the Anthropic API
# through this common interface.
# """
# import json
# import logging
# import os

# import httpx

# logger = logging.getLogger(__name__)

# ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
# MODEL = "claude-sonnet-4-20250514"


# class BaseAgent:
#     """
#     All agents inherit from this.
#     Subclasses define:
#         - system_prompt (str)
#         - run(*args) -> dict
#     """
#     system_prompt = "You are a helpful trading assistant."
#     max_tokens = 1000

#     def call_llm(self, user_message: str, history: list = None) -> str:
    
#     # Send a message to Claude and return the text response.
#     # history = list of {"role": "user"/"assistant", "content": "..."} dicts
    
#         from django.conf import settings as django_settings
#     api_key = (
#         getattr(django_settings, 'ANTHROPIC_API_KEY', '')
#         or os.environ.get("ANTHROPIC_API_KEY", "")
#     )

#     if not api_key:
#         logger.warning("ANTHROPIC_API_KEY not set — returning mock response")
#         return self._mock_response(user_message)

#         messages = []
#         if history:
#             messages.extend(history)
#         messages.append({"role": "user", "content": user_message})

#         payload = {
#             "model": MODEL,
#             "max_tokens": self.max_tokens,
#             "system": self.system_prompt,
#             "messages": messages,
#         }

#         try:
#             response = httpx.post(
#                 ANTHROPIC_API_URL,
#                 headers={
#                     "x-api-key": api_key,
#                     "anthropic-version": "2023-06-01",
#                     "content-type": "application/json",
#                 },
#                 json=payload,
#                 timeout=30,
#             )
#             response.raise_for_status()
#             data = response.json()
#             return data["content"][0]["text"]
#         except Exception as exc:
#             logger.error("LLM call failed: %s", exc)
#             return ""

#     def call_llm_json(self, user_message: str) -> dict:
#         """
#         Like call_llm but expects and parses a JSON response.
#         Returns empty dict on failure.
#         """
#         raw = self.call_llm(user_message)
#         if not raw:
#             return {}
#         try:
#             # Strip markdown code fences if present
#             clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
#             return json.loads(clean)
#         except json.JSONDecodeError as exc:
#             logger.error("JSON parse failed: %s | raw: %s", exc, raw[:200])
#             return {}

#     # def _mock_response(self, message: str) -> str:
#     #     """Fallback when no API key is set — useful for local dev/testing."""
#     #     return json.dumps({
#     #         "confidence_score": 50,
#     #         "sentiment": "NEUTRAL",
#     #         "reason": "Mock response — set ANTHROPIC_API_KEY in .env to enable real AI",
#     #         "avoid": False,
#     #     })



# def _mock_response(self, message: str) -> str:
#     """Smart mock response based on the question asked — no API key needed."""
#     message_lower = message.lower()

#     if any(word in message_lower for word in ['pnl', 'p&l', 'profit', 'loss', 'money']):
#         return "Based on your trading data, check the Dashboard for today's live P&L. The Reports page shows your full equity curve and daily breakdown."

#     if any(word in message_lower for word in ['strategy', 'best', 'performing', 'ema', 'orb', 'vwap']):
#         return "Go to the Reports page → Strategy Comparison chart to see which strategy is generating the most P&L. EMA Crossover, ORB, and VWAP Bounce are all tracked separately."

#     if any(word in message_lower for word in ['trade', 'trades', 'how many']):
#         return "Check the Trades page for a full history of all trades with filters by date, strategy, and symbol."

#     if any(word in message_lower for word in ['loss', 'losing', 'sl', 'stop']):
#         return "Your losing trades are listed on the Trades page — filter by SL_HIT status to see all stop-loss hits."

#     if any(word in message_lower for word in ['position', 'open', 'current']):
#         return "Your open positions are shown live on the Dashboard. They refresh every 10 seconds automatically."

#     if any(word in message_lower for word in ['week', 'weekly', 'this week']):
#         return "The Journal page shows a day-by-day breakdown for the week. Reports page shows the weekly equity curve."

#     return (
#         "I'm running in demo mode — add your ANTHROPIC_API_KEY to .env to enable "
#         "full AI responses. For now, use the Dashboard, Trades, Reports, and Journal "
#         "pages to explore your trading data."
#     )























# code 2: 
"""
agents/base.py
Base class for all AI agents. Every agent calls the Anthropic API
through this common interface.
"""
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
# MODEL = "claude-sonnet-4-20250514"
MODEL = "claude-sonnet-4-5"

class BaseAgent:
    """
    All agents inherit from this.
    Subclasses define:
        - system_prompt (str)
        - run(*args) -> dict
    """
    system_prompt = "You are a helpful trading assistant."
    max_tokens = 1000

    def call_llm(self, user_message: str, history: list = None) -> str:
        """
        Send a message to Claude and return the text response.
        history = list of {"role": "user"/"assistant", "content": "..."} dicts
        """
        from django.conf import settings as django_settings
        api_key = (
            getattr(django_settings, 'ANTHROPIC_API_KEY', '')
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — returning mock response")
            return self._mock_response(user_message)

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": MODEL,
            "max_tokens": self.max_tokens,
            "system": self.system_prompt,
            "messages": messages,
        }

        try:
            response = httpx.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            print("STATUS:", response.status_code)
            print("RESPONSE:", response.text)
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ""

    def call_llm_json(self, user_message: str) -> dict:
        """
        Like call_llm but expects and parses a JSON response.
        Returns empty dict on failure.
        """
        raw = self.call_llm(user_message)
        if not raw:
            return {}
        try:
            # Strip markdown code fences if present
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed: %s | raw: %s", exc, raw[:200])
            return {}

    def _mock_response(self, message: str) -> str:
        """Smart mock response based on the question asked — no API key needed."""
        message_lower = message.lower()

        if any(word in message_lower for word in ['pnl', 'p&l', 'profit', 'loss', 'money']):
            return "Based on your trading data, check the Dashboard for today's live P&L. The Reports page shows your full equity curve and daily breakdown."

        if any(word in message_lower for word in ['strategy', 'best', 'performing', 'ema', 'orb', 'vwap']):
            return "Go to the Reports page → Strategy Comparison chart to see which strategy is generating the most P&L. EMA Crossover, ORB, and VWAP Bounce are all tracked separately."

        if any(word in message_lower for word in ['trade', 'trades', 'how many']):
            return "Check the Trades page for a full history of all trades with filters by date, strategy, and symbol."

        if any(word in message_lower for word in ['losing', 'sl', 'stop']):
            return "Your losing trades are listed on the Trades page — filter by SL_HIT status to see all stop-loss hits."

        if any(word in message_lower for word in ['position', 'open', 'current']):
            return "Your open positions are shown live on the Dashboard. They refresh every 10 seconds automatically."

        if any(word in message_lower for word in ['week', 'weekly', 'this week']):
            return "The Journal page shows a day-by-day breakdown for the week. Reports page shows the weekly equity curve."

        return (
            "I'm running in demo mode — add your ANTHROPIC_API_KEY to .env to enable "
            "full AI responses. For now, use the Dashboard, Trades, Reports, and Journal "
            "pages to explore your trading data."
        )