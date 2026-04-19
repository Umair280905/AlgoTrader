"""
Telegram notification sender.

Create a bot via @BotFather and store credentials in .env:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...

send_message(text) is the only public API — all other modules call this.
"""
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


def send_message(text: str) -> None:
    """
    Send a Telegram message asynchronously (fire-and-forget).
    Never raises — logs errors silently so trading is never blocked by notification failure.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured — skipping message: %s", text[:80])
        return

    thread = threading.Thread(target=_send_sync, args=(text,), daemon=True)
    thread.start()


def _send_sync(text: str) -> None:
    """Synchronous send — runs in background thread."""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': settings.TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML',
        }
        resp = httpx.post(url, json=payload, timeout=10)
        if not resp.is_success:
            logger.warning("Telegram send failed: %s %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Telegram send error: %s", exc)
