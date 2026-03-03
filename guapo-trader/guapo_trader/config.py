import os
from pathlib import Path

import yaml
from loguru import logger


class Config:
    """Charge et valide la configuration depuis config.yaml."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        self.path = Path(config_path)

        if not self.path.exists():
            raise FileNotFoundError(
                f"Config introuvable: {self.path}\n"
                "Copie config.example.yaml -> config.yaml et remplis tes clés API."
            )

        with open(self.path) as f:
            self._data = yaml.safe_load(f)

        self._validate()
        logger.info(f"Config chargée depuis {self.path}")

    def _validate(self):
        required_sections = ["binance", "strategy", "risk"]
        for section in required_sections:
            if section not in self._data:
                raise ValueError(f"Section '{section}' manquante dans config.yaml")

        if self.binance_api_key == "TA_CLE_API_BINANCE":
            logger.warning("Clé API Binance non configurée ! Mode lecture seule.")

    # --- Binance ---
    @property
    def binance_api_key(self) -> str:
        return self._data["binance"]["api_key"]

    @property
    def binance_api_secret(self) -> str:
        return self._data["binance"]["api_secret"]

    @property
    def binance_testnet(self) -> bool:
        return self._data["binance"].get("testnet", True)

    # --- Solana ---
    @property
    def solana_rpc_url(self) -> str:
        return self._data.get("solana", {}).get(
            "rpc_url", "https://api.mainnet-beta.solana.com"
        )

    @property
    def solana_private_key(self) -> str:
        return self._data.get("solana", {}).get("private_key", "")

    @property
    def solana_slippage_bps(self) -> int:
        return self._data.get("solana", {}).get("slippage_bps", 100)

    # --- Strategy ---
    @property
    def binance_pairs(self) -> list:
        return self._data["strategy"]["binance_pairs"]

    @property
    def solana_tokens(self) -> list:
        return self._data["strategy"].get("solana_tokens", [])

    @property
    def timeframe(self) -> str:
        return self._data["strategy"].get("timeframe", "5m")

    @property
    def rsi_period(self) -> int:
        return self._data["strategy"].get("rsi_period", 14)

    @property
    def rsi_oversold(self) -> float:
        return self._data["strategy"].get("rsi_oversold", 30)

    @property
    def rsi_overbought(self) -> float:
        return self._data["strategy"].get("rsi_overbought", 70)

    @property
    def ema_fast(self) -> int:
        return self._data["strategy"].get("ema_fast", 9)

    @property
    def ema_slow(self) -> int:
        return self._data["strategy"].get("ema_slow", 21)

    @property
    def bb_period(self) -> int:
        return self._data["strategy"].get("bb_period", 20)

    @property
    def bb_std(self) -> float:
        return self._data["strategy"].get("bb_std", 2.0)

    @property
    def take_profit_pct(self) -> float:
        return self._data["strategy"].get("take_profit_pct", 0.5)

    @property
    def stop_loss_pct(self) -> float:
        return self._data["strategy"].get("stop_loss_pct", 0.3)

    @property
    def scan_interval(self) -> int:
        return self._data["strategy"].get("scan_interval", 30)

    # --- Risk ---
    @property
    def max_position_usdt(self) -> float:
        return self._data["risk"].get("max_position_usdt", 20.0)

    @property
    def max_open_trades(self) -> int:
        return self._data["risk"].get("max_open_trades", 3)

    @property
    def max_daily_loss_usdt(self) -> float:
        return self._data["risk"].get("max_daily_loss_usdt", 10.0)

    @property
    def max_daily_trades(self) -> int:
        return self._data["risk"].get("max_daily_trades", 50)

    @property
    def cooldown_after_loss(self) -> int:
        return self._data["risk"].get("cooldown_after_loss", 120)

    # --- Telegram ---
    @property
    def telegram_enabled(self) -> bool:
        return self._data.get("telegram", {}).get("enabled", False)

    @property
    def telegram_bot_token(self) -> str:
        return self._data.get("telegram", {}).get("bot_token", "")

    @property
    def telegram_chat_id(self) -> str:
        return self._data.get("telegram", {}).get("chat_id", "")

    @property
    def telegram_notify_trades(self) -> bool:
        return self._data.get("telegram", {}).get("notify_trades", True)

    @property
    def telegram_daily_report(self) -> bool:
        return self._data.get("telegram", {}).get("notify_daily_report", True)

    @property
    def telegram_report_hour(self) -> int:
        return self._data.get("telegram", {}).get("daily_report_hour", 22)

    # --- Database ---
    @property
    def db_path(self) -> str:
        return self._data.get("database", {}).get("path", "data/trades.db")

    # --- Logging ---
    @property
    def log_level(self) -> str:
        return self._data.get("logging", {}).get("level", "INFO")

    @property
    def log_file(self) -> str:
        return self._data.get("logging", {}).get("file", "logs/guapo-trader.log")

    @property
    def log_max_size(self) -> str:
        return self._data.get("logging", {}).get("max_size", "10 MB")

    @property
    def log_retention(self) -> str:
        return self._data.get("logging", {}).get("retention", "7 days")
