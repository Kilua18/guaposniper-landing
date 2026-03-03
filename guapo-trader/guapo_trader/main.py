#!/usr/bin/env python3
"""
GuapoTrader - Bot de scalping crypto pour Raspberry Pi
Combine Binance (CEX) + Solana/Phantom (DEX)
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from .config import Config
from .exchanges.binance_client import BinanceClient
from .exchanges.solana_client import SolanaClient
from .strategies.scalper import ScalpingStrategy
from .strategies.base import Signal
from .risk.manager import RiskManager
from .notifications.telegram import TelegramNotifier
from .database.trades import TradeDatabase
from .utils.logger import setup_logger

BANNER = """
╔══════════════════════════════════════╗
║         GUAPO TRADER v1.0           ║
║   Scalping Bot - Raspberry Pi       ║
║   Binance + Solana/Phantom          ║
╚══════════════════════════════════════╝
"""


class GuapoTrader:
    """Bot de trading principal."""

    def __init__(self, config_path: str = None):
        self.config = Config(config_path)
        self._running = False

        # Setup logging
        setup_logger(
            level=self.config.log_level,
            log_file=self.config.log_file,
            max_size=self.config.log_max_size,
            retention=self.config.log_retention,
        )

        # Composants
        self.binance = BinanceClient(
            api_key=self.config.binance_api_key,
            api_secret=self.config.binance_api_secret,
            testnet=self.config.binance_testnet,
        )
        self.solana = SolanaClient(
            rpc_url=self.config.solana_rpc_url,
            private_key=self.config.solana_private_key,
            slippage_bps=self.config.solana_slippage_bps,
        )
        self.strategy = ScalpingStrategy(
            rsi_period=self.config.rsi_period,
            rsi_oversold=self.config.rsi_oversold,
            rsi_overbought=self.config.rsi_overbought,
            ema_fast=self.config.ema_fast,
            ema_slow=self.config.ema_slow,
            bb_period=self.config.bb_period,
            bb_std=self.config.bb_std,
        )
        self.risk = RiskManager(
            max_position_usdt=self.config.max_position_usdt,
            max_open_trades=self.config.max_open_trades,
            max_daily_loss_usdt=self.config.max_daily_loss_usdt,
            max_daily_trades=self.config.max_daily_trades,
            cooldown_after_loss=self.config.cooldown_after_loss,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=self.config.stop_loss_pct,
        )
        self.telegram = TelegramNotifier(
            bot_token=self.config.telegram_bot_token,
            chat_id=self.config.telegram_chat_id,
            enabled=self.config.telegram_enabled,
        )
        self.db = TradeDatabase(db_path=self.config.db_path)

    async def start(self):
        """Démarre le bot."""
        print(BANNER)
        logger.info("Démarrage de GuapoTrader...")

        # Connexions
        await self.db.connect()
        await self.binance.connect()
        await self.solana.connect()

        balance = await self.binance.get_balance("USDT")
        await self.telegram.notify_startup(self.config.binance_pairs, balance)

        self._running = True
        logger.info(
            f"Bot prêt | Paires: {self.config.binance_pairs} | "
            f"Balance: {balance:.2f} USDT | "
            f"Stratégie: {self.strategy.name}"
        )

        # Boucle principale
        try:
            # Lancer les tâches en parallèle
            tasks = [
                asyncio.create_task(self._scalping_loop()),
                asyncio.create_task(self._monitor_exits()),
                asyncio.create_task(self._daily_report_loop()),
            ]
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tâches annulées")
        finally:
            await self.stop()

    async def stop(self, reason: str = "Manuel"):
        """Arrête le bot proprement."""
        self._running = False
        logger.info(f"Arrêt de GuapoTrader ({reason})")

        # Notifier
        await self.telegram.notify_shutdown(reason)

        # Afficher les stats
        stats = await self.db.get_total_stats()
        logger.info(
            f"Stats totales: {stats['total_trades']} trades | "
            f"PnL: {stats['total_pnl']:+.4f} USDT | "
            f"Win rate: {stats['win_rate']}%"
        )

        # Fermer les connexions
        await self.telegram.close()
        await self.binance.close()
        await self.solana.close()
        await self.db.close()

    async def _scalping_loop(self):
        """Boucle principale de scalping: scan les paires et exécute les trades."""
        while self._running:
            try:
                for symbol in self.config.binance_pairs:
                    await self._process_pair(symbol)
                    await asyncio.sleep(1)  # Pause entre les paires

                await asyncio.sleep(self.config.scan_interval)
            except Exception as e:
                logger.error(f"Erreur scalping loop: {e}")
                await self.telegram.notify_error(str(e))
                await asyncio.sleep(10)

    async def _process_pair(self, symbol: str):
        """Analyse une paire et exécute un trade si signal."""
        try:
            # Récupérer les bougies
            df = await self.binance.get_klines(symbol, self.config.timeframe, limit=100)
            if df.empty:
                return

            # Analyser avec la stratégie
            sig = self.strategy.analyze(df)

            if sig == Signal.BUY:
                await self._execute_buy(symbol)
            elif sig == Signal.SELL and symbol in self.risk.open_trades:
                await self._execute_sell(symbol, reason="signal")

        except Exception as e:
            logger.error(f"Erreur traitement {symbol}: {e}")

    async def _execute_buy(self, symbol: str):
        """Exécute un achat."""
        # Vérifier les risques
        can_trade, reason = self.risk.can_open_trade(symbol)
        if not can_trade:
            logger.debug(f"Achat {symbol} bloqué: {reason}")
            return

        # Calculer la taille de position
        balance = await self.binance.get_balance("USDT")
        position_size = self.risk.get_position_size(balance)

        if position_size < 5:  # Minimum 5 USDT
            logger.debug(f"Balance insuffisante: {balance:.2f} USDT")
            return

        # Exécuter l'achat
        order = await self.binance.buy_market(symbol, position_size)
        if order is None:
            return

        # Enregistrer
        self.risk.register_open(
            symbol=symbol,
            entry_price=order["price"],
            quantity=order["quantity"],
            cost=order["cost"],
            order_id=order["id"],
        )
        await self.db.record_open(
            symbol=symbol,
            entry_price=order["price"],
            quantity=order["quantity"],
            cost=order["cost"],
        )

        # Notifier
        if self.config.telegram_notify_trades:
            await self.telegram.notify_trade(
                action="BUY",
                symbol=symbol,
                price=order["price"],
                quantity=order["quantity"],
                cost=order["cost"],
            )

        indicators = self.strategy.get_indicators(
            await self.binance.get_klines(symbol, self.config.timeframe, limit=100)
        )
        logger.info(f"Indicateurs {symbol}: {indicators}")

    async def _execute_sell(self, symbol: str, reason: str = "signal"):
        """Exécute une vente."""
        trade = self.risk.open_trades.get(symbol)
        if trade is None:
            return

        # Exécuter la vente
        order = await self.binance.sell_market(symbol, trade.quantity)
        if order is None:
            return

        # Calculer PnL et enregistrer
        pnl = self.risk.register_close(symbol, order["price"], order["cost"])
        await self.db.record_close(
            symbol=symbol,
            exit_price=order["price"],
            revenue=order["cost"],
            pnl=pnl,
            reason=reason,
        )

        # Notifier
        if self.config.telegram_notify_trades:
            await self.telegram.notify_trade(
                action="SELL",
                symbol=symbol,
                price=order["price"],
                quantity=order["quantity"],
                cost=order["cost"],
                pnl=pnl,
            )

    async def _monitor_exits(self):
        """Surveille les trades ouverts pour TP/SL."""
        while self._running:
            try:
                for symbol in list(self.risk.open_trades.keys()):
                    price = await self.binance.get_price(symbol)
                    exit_reason = self.risk.check_exit_conditions(symbol, price)

                    if exit_reason:
                        logger.info(
                            f"{exit_reason.upper()} déclenché sur {symbol} "
                            f"@ {price:.6f}"
                        )
                        await self._execute_sell(symbol, reason=exit_reason)

                await asyncio.sleep(5)  # Vérifier toutes les 5 secondes
            except Exception as e:
                logger.error(f"Erreur monitor exits: {e}")
                await asyncio.sleep(10)

    async def _daily_report_loop(self):
        """Envoie un rapport quotidien via Telegram."""
        if not self.config.telegram_daily_report:
            return

        while self._running:
            try:
                from datetime import datetime
                now = datetime.now()
                if now.hour == self.config.telegram_report_hour and now.minute == 0:
                    balance = await self.binance.get_balance("USDT")
                    status = self.risk.status
                    await self.telegram.notify_daily_report(
                        daily_pnl=status["daily_pnl"],
                        trade_count=status["daily_trades"],
                        open_trades=status["open_trades"],
                        balance=balance,
                    )
                    await asyncio.sleep(61)  # Éviter double envoi
                else:
                    await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Erreur daily report: {e}")
                await asyncio.sleep(60)


def main():
    """Point d'entrée CLI."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    bot = GuapoTrader(config_path)

    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        logger.info(f"Signal {sig} reçu, arrêt...")
        bot._running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        logger.info("Arrêt par Ctrl+C")
    finally:
        loop.run_until_complete(bot.stop("Arrêt système"))
        loop.close()


if __name__ == "__main__":
    main()
