import time
from dataclasses import dataclass, field
from datetime import datetime, date

from loguru import logger


@dataclass
class OpenTrade:
    """Représente un trade ouvert."""
    symbol: str
    side: str
    entry_price: float
    quantity: float
    cost: float
    timestamp: float
    order_id: str = ""


class RiskManager:
    """Gère les risques: position sizing, limites, stop loss / take profit."""

    def __init__(self, max_position_usdt: float = 20.0, max_open_trades: int = 3,
                 max_daily_loss_usdt: float = 10.0, max_daily_trades: int = 50,
                 cooldown_after_loss: int = 120,
                 take_profit_pct: float = 0.5, stop_loss_pct: float = 0.3):
        self.max_position_usdt = max_position_usdt
        self.max_open_trades = max_open_trades
        self.max_daily_loss_usdt = max_daily_loss_usdt
        self.max_daily_trades = max_daily_trades
        self.cooldown_after_loss = cooldown_after_loss
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

        # État
        self.open_trades: dict[str, OpenTrade] = {}  # symbol -> trade
        self.daily_pnl: float = 0.0
        self.daily_trade_count: int = 0
        self._current_date: date = date.today()
        self._last_loss_time: float = 0
        self._halted = False

    def _reset_daily_if_needed(self):
        """Reset les compteurs quotidiens si nouveau jour."""
        today = date.today()
        if today != self._current_date:
            logger.info(
                f"Nouveau jour | PnL hier: {self.daily_pnl:+.2f} USDT | "
                f"Trades: {self.daily_trade_count}"
            )
            self.daily_pnl = 0.0
            self.daily_trade_count = 0
            self._current_date = today
            self._halted = False

    def can_open_trade(self, symbol: str) -> tuple[bool, str]:
        """Vérifie si on peut ouvrir un nouveau trade."""
        self._reset_daily_if_needed()

        if self._halted:
            return False, "Trading arrêté (perte max journalière atteinte)"

        # Déjà un trade ouvert sur ce symbol
        if symbol in self.open_trades:
            return False, f"Trade déjà ouvert sur {symbol}"

        # Max trades ouverts
        if len(self.open_trades) >= self.max_open_trades:
            return False, f"Max {self.max_open_trades} trades ouverts atteint"

        # Max trades quotidiens
        if self.daily_trade_count >= self.max_daily_trades:
            return False, f"Max {self.max_daily_trades} trades/jour atteint"

        # Perte max quotidienne
        if self.daily_pnl <= -self.max_daily_loss_usdt:
            self._halted = True
            return False, f"Perte max journalière ({self.max_daily_loss_usdt} USDT) atteinte"

        # Cooldown après perte
        if self._last_loss_time > 0:
            elapsed = time.time() - self._last_loss_time
            if elapsed < self.cooldown_after_loss:
                remaining = int(self.cooldown_after_loss - elapsed)
                return False, f"Cooldown après perte: {remaining}s restantes"

        return True, "OK"

    def register_open(self, symbol: str, entry_price: float, quantity: float,
                      cost: float, order_id: str = ""):
        """Enregistre un trade ouvert."""
        self.open_trades[symbol] = OpenTrade(
            symbol=symbol,
            side="buy",
            entry_price=entry_price,
            quantity=quantity,
            cost=cost,
            timestamp=time.time(),
            order_id=order_id,
        )
        self.daily_trade_count += 1
        logger.info(f"Trade ouvert: {symbol} @ {entry_price:.6f} ({cost:.2f} USDT)")

    def register_close(self, symbol: str, exit_price: float, revenue: float) -> float:
        """Enregistre la fermeture d'un trade. Retourne le PnL."""
        trade = self.open_trades.pop(symbol, None)
        if trade is None:
            logger.warning(f"Pas de trade ouvert pour {symbol}")
            return 0.0

        pnl = revenue - trade.cost
        self.daily_pnl += pnl

        if pnl < 0:
            self._last_loss_time = time.time()

        emoji = "+" if pnl >= 0 else ""
        logger.info(
            f"Trade fermé: {symbol} | "
            f"Entrée: {trade.entry_price:.6f} -> Sortie: {exit_price:.6f} | "
            f"PnL: {emoji}{pnl:.4f} USDT | "
            f"PnL jour: {self.daily_pnl:+.2f} USDT"
        )
        return pnl

    def check_exit_conditions(self, symbol: str, current_price: float) -> str | None:
        """Vérifie si un trade ouvert doit être fermé (TP/SL)."""
        trade = self.open_trades.get(symbol)
        if trade is None:
            return None

        pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100

        if pnl_pct >= self.take_profit_pct:
            return "take_profit"
        elif pnl_pct <= -self.stop_loss_pct:
            return "stop_loss"
        return None

    def get_position_size(self, balance: float) -> float:
        """Retourne la taille de position en USDT."""
        return min(self.max_position_usdt, balance * 0.95)

    @property
    def status(self) -> dict:
        """Retourne l'état actuel du risk manager."""
        self._reset_daily_if_needed()
        return {
            "open_trades": len(self.open_trades),
            "open_symbols": list(self.open_trades.keys()),
            "daily_pnl": round(self.daily_pnl, 4),
            "daily_trades": self.daily_trade_count,
            "halted": self._halted,
        }
