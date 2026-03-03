import aiosqlite
from pathlib import Path
from datetime import datetime, date

from loguru import logger


class TradeDatabase:
    """Base de données SQLite pour l'historique des trades."""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        """Ouvre la connexion et crée les tables."""
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        logger.info(f"Base de données initialisée: {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL DEFAULT 'binance',
                side TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                cost REAL,
                revenue REAL,
                pnl REAL,
                reason TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_opened ON trades(opened_at);

            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_pnl REAL DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                best_trade REAL DEFAULT 0,
                worst_trade REAL DEFAULT 0
            );
        """)
        await self._db.commit()

    async def record_open(self, symbol: str, entry_price: float, quantity: float,
                          cost: float, exchange: str = "binance") -> int:
        """Enregistre l'ouverture d'un trade. Retourne l'ID."""
        cursor = await self._db.execute(
            """INSERT INTO trades (symbol, exchange, side, entry_price, quantity,
               cost, opened_at)
               VALUES (?, ?, 'buy', ?, ?, ?, ?)""",
            (symbol, exchange, entry_price, quantity, cost,
             datetime.now().isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def record_close(self, symbol: str, exit_price: float, revenue: float,
                           pnl: float, reason: str = "signal"):
        """Enregistre la fermeture d'un trade."""
        await self._db.execute(
            """UPDATE trades SET exit_price=?, revenue=?, pnl=?, reason=?,
               closed_at=?, side='sell'
               WHERE symbol=? AND closed_at IS NULL
               ORDER BY id DESC LIMIT 1""",
            (exit_price, revenue, pnl, reason,
             datetime.now().isoformat(), symbol),
        )
        await self._db.commit()

        # Mettre à jour les stats quotidiennes
        await self._update_daily_stats(pnl)

    async def _update_daily_stats(self, pnl: float):
        """Met à jour les statistiques du jour."""
        today = date.today().isoformat()

        await self._db.execute(
            """INSERT INTO daily_stats (date, total_pnl, trade_count, wins, losses,
               best_trade, worst_trade)
               VALUES (?, ?, 1, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
               total_pnl = total_pnl + ?,
               trade_count = trade_count + 1,
               wins = wins + ?,
               losses = losses + ?,
               best_trade = MAX(best_trade, ?),
               worst_trade = MIN(worst_trade, ?)""",
            (today, pnl,
             1 if pnl > 0 else 0, 1 if pnl < 0 else 0,
             pnl if pnl > 0 else 0, pnl if pnl < 0 else 0,
             pnl, 1 if pnl > 0 else 0, 1 if pnl < 0 else 0,
             pnl, pnl),
        )
        await self._db.commit()

    async def get_daily_stats(self, target_date: str = None) -> dict | None:
        """Retourne les stats d'un jour."""
        if target_date is None:
            target_date = date.today().isoformat()

        async with self._db.execute(
            "SELECT * FROM daily_stats WHERE date=?", (target_date,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "date": row[0],
                    "total_pnl": row[1],
                    "trade_count": row[2],
                    "wins": row[3],
                    "losses": row[4],
                    "best_trade": row[5],
                    "worst_trade": row[6],
                    "win_rate": (row[3] / row[2] * 100) if row[2] > 0 else 0,
                }
        return None

    async def get_total_stats(self) -> dict:
        """Retourne les statistiques globales."""
        async with self._db.execute(
            """SELECT COUNT(*), SUM(pnl), AVG(pnl),
               SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END),
               MAX(pnl), MIN(pnl)
               FROM trades WHERE closed_at IS NOT NULL"""
        ) as cursor:
            row = await cursor.fetchone()
            total = row[0] or 0
            return {
                "total_trades": total,
                "total_pnl": round(row[1] or 0, 4),
                "avg_pnl": round(row[2] or 0, 4),
                "wins": row[3] or 0,
                "losses": row[4] or 0,
                "best_trade": round(row[5] or 0, 4),
                "worst_trade": round(row[6] or 0, 4),
                "win_rate": round((row[3] or 0) / total * 100, 1) if total > 0 else 0,
            }

    async def get_open_trades(self) -> list:
        """Retourne les trades ouverts."""
        async with self._db.execute(
            "SELECT symbol, entry_price, quantity, cost, opened_at FROM trades WHERE closed_at IS NULL"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "symbol": r[0],
                    "entry_price": r[1],
                    "quantity": r[2],
                    "cost": r[3],
                    "opened_at": r[4],
                }
                for r in rows
            ]

    async def get_recent_trades(self, limit: int = 20) -> list:
        """Retourne les derniers trades fermés."""
        async with self._db.execute(
            """SELECT symbol, entry_price, exit_price, quantity, cost, revenue,
               pnl, reason, opened_at, closed_at
               FROM trades WHERE closed_at IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "symbol": r[0],
                    "entry_price": r[1],
                    "exit_price": r[2],
                    "quantity": r[3],
                    "cost": r[4],
                    "revenue": r[5],
                    "pnl": r[6],
                    "reason": r[7],
                    "opened_at": r[8],
                    "closed_at": r[9],
                }
                for r in rows
            ]
