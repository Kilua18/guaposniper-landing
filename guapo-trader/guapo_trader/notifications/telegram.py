import asyncio

import httpx
from loguru import logger


class TelegramNotifier:
    """Envoie des notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._http = httpx.AsyncClient(timeout=10)

    async def close(self):
        await self._http.aclose()

    async def send(self, message: str, parse_mode: str = "HTML"):
        """Envoie un message Telegram."""
        if not self.enabled:
            return

        try:
            resp = await self._http.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Telegram erreur: {resp.text}")
        except Exception as e:
            logger.warning(f"Telegram erreur: {e}")

    async def notify_trade(self, action: str, symbol: str, price: float,
                           quantity: float, cost: float, pnl: float = None):
        """Notifie un trade."""
        if action == "BUY":
            icon = "🟢"
            msg = (
                f"{icon} <b>ACHAT {symbol}</b>\n"
                f"Prix: <code>{price:.6f}</code>\n"
                f"Quantité: <code>{quantity}</code>\n"
                f"Coût: <code>{cost:.2f} USDT</code>"
            )
        else:
            icon = "🔴" if pnl and pnl < 0 else "💰"
            pnl_str = f"{pnl:+.4f} USDT" if pnl is not None else "N/A"
            msg = (
                f"{icon} <b>VENTE {symbol}</b>\n"
                f"Prix: <code>{price:.6f}</code>\n"
                f"Quantité: <code>{quantity}</code>\n"
                f"Revenu: <code>{cost:.2f} USDT</code>\n"
                f"PnL: <code>{pnl_str}</code>"
            )

        await self.send(msg)

    async def notify_daily_report(self, daily_pnl: float, trade_count: int,
                                  open_trades: int, balance: float):
        """Envoie le rapport quotidien."""
        icon = "📈" if daily_pnl >= 0 else "📉"
        msg = (
            f"📊 <b>RAPPORT QUOTIDIEN GuapoTrader</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{icon} PnL: <code>{daily_pnl:+.4f} USDT</code>\n"
            f"📋 Trades: <code>{trade_count}</code>\n"
            f"📂 Positions ouvertes: <code>{open_trades}</code>\n"
            f"💰 Balance USDT: <code>{balance:.2f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await self.send(msg)

    async def notify_error(self, error_msg: str):
        """Notifie une erreur."""
        msg = f"⚠️ <b>ERREUR GuapoTrader</b>\n<code>{error_msg}</code>"
        await self.send(msg)

    async def notify_startup(self, pairs: list, balance: float):
        """Notifie le démarrage du bot."""
        pairs_str = ", ".join(pairs)
        msg = (
            f"🚀 <b>GuapoTrader démarré !</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Paires: <code>{pairs_str}</code>\n"
            f"Balance: <code>{balance:.2f} USDT</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await self.send(msg)

    async def notify_shutdown(self, reason: str = "Manuel"):
        """Notifie l'arrêt du bot."""
        msg = f"🛑 <b>GuapoTrader arrêté</b>\nRaison: {reason}"
        await self.send(msg)
