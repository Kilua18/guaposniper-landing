import asyncio
from decimal import Decimal, ROUND_DOWN

import ccxt.async_support as ccxt
import pandas as pd
from loguru import logger


class BinanceClient:
    """Client Binance pour le scalping spot."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        options = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        if testnet:
            options["sandbox"] = True
            logger.warning("BINANCE TESTNET ACTIVÉ - pas d'argent réel")

        self.exchange = ccxt.binance(options)
        self.testnet = testnet
        self._markets_loaded = False

    async def connect(self):
        """Charge les marchés et vérifie la connexion."""
        await self.exchange.load_markets()
        self._markets_loaded = True
        balance = await self.get_balance("USDT")
        logger.info(f"Binance connecté | USDT disponible: {balance:.2f}")
        return True

    async def close(self):
        await self.exchange.close()

    async def get_balance(self, asset: str = "USDT") -> float:
        """Retourne le solde disponible d'un asset."""
        balance = await self.exchange.fetch_balance()
        return float(balance.get(asset, {}).get("free", 0))

    async def get_klines(self, symbol: str, timeframe: str = "5m",
                         limit: int = 100) -> pd.DataFrame:
        """Récupère les bougies OHLCV et retourne un DataFrame."""
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.astype({
            "open": float, "high": float, "low": float,
            "close": float, "volume": float,
        })
        return df

    async def get_price(self, symbol: str) -> float:
        """Retourne le prix actuel d'une paire."""
        ticker = await self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])

    async def get_order_book(self, symbol: str, limit: int = 5) -> dict:
        """Retourne le carnet d'ordres."""
        return await self.exchange.fetch_order_book(symbol, limit)

    def _calculate_quantity(self, symbol: str, usdt_amount: float, price: float) -> float:
        """Calcule la quantité à acheter en respectant les règles du marché."""
        market = self.exchange.market(symbol)
        raw_qty = usdt_amount / price

        # Respecter la précision du marché
        precision = market.get("precision", {}).get("amount", 8)
        qty = float(Decimal(str(raw_qty)).quantize(
            Decimal(10) ** -precision, rounding=ROUND_DOWN
        ))

        # Vérifier la quantité minimum
        min_qty = market.get("limits", {}).get("amount", {}).get("min", 0)
        if min_qty and qty < min_qty:
            logger.warning(f"{symbol}: quantité {qty} < minimum {min_qty}")
            return 0.0

        return qty

    async def buy_market(self, symbol: str, usdt_amount: float) -> dict | None:
        """Achat au marché. Retourne l'ordre exécuté ou None."""
        try:
            price = await self.get_price(symbol)
            qty = self._calculate_quantity(symbol, usdt_amount, price)
            if qty <= 0:
                return None

            order = await self.exchange.create_market_buy_order(symbol, qty)
            filled_price = float(order.get("average", price))
            filled_qty = float(order.get("filled", qty))
            cost = float(order.get("cost", filled_price * filled_qty))

            logger.info(
                f"ACHAT {symbol} | "
                f"Qté: {filled_qty} | "
                f"Prix: {filled_price:.6f} | "
                f"Coût: {cost:.2f} USDT"
            )
            return {
                "id": order["id"],
                "symbol": symbol,
                "side": "buy",
                "price": filled_price,
                "quantity": filled_qty,
                "cost": cost,
                "timestamp": order.get("timestamp"),
            }
        except Exception as e:
            logger.error(f"Erreur achat {symbol}: {e}")
            return None

    async def sell_market(self, symbol: str, quantity: float) -> dict | None:
        """Vente au marché. Retourne l'ordre exécuté ou None."""
        try:
            order = await self.exchange.create_market_sell_order(symbol, quantity)
            filled_price = float(order.get("average", 0))
            filled_qty = float(order.get("filled", quantity))
            revenue = float(order.get("cost", filled_price * filled_qty))

            logger.info(
                f"VENTE {symbol} | "
                f"Qté: {filled_qty} | "
                f"Prix: {filled_price:.6f} | "
                f"Revenu: {revenue:.2f} USDT"
            )
            return {
                "id": order["id"],
                "symbol": symbol,
                "side": "sell",
                "price": filled_price,
                "quantity": filled_qty,
                "cost": revenue,
                "timestamp": order.get("timestamp"),
            }
        except Exception as e:
            logger.error(f"Erreur vente {symbol}: {e}")
            return None

    async def get_open_orders(self, symbol: str = None) -> list:
        """Retourne les ordres ouverts."""
        return await self.exchange.fetch_open_orders(symbol)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Annule un ordre."""
        try:
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Ordre {order_id} annulé ({symbol})")
            return True
        except Exception as e:
            logger.error(f"Erreur annulation {order_id}: {e}")
            return False
