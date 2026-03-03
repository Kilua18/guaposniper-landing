import pandas as pd
import ta
from loguru import logger

from .base import BaseStrategy, Signal


class ScalpingStrategy(BaseStrategy):
    """
    Stratégie de scalping combinant RSI + Bollinger Bands + EMA crossover.

    Signal d'ACHAT quand au moins 2 conditions sur 3 sont remplies:
    1. RSI < oversold (survente)
    2. Prix touche/sous la bande Bollinger basse
    3. EMA rapide croise au-dessus de EMA lente

    Signal de VENTE quand au moins 2 conditions sur 3 sont remplies:
    1. RSI > overbought (surachat)
    2. Prix touche/au-dessus de la bande Bollinger haute
    3. EMA rapide croise en-dessous de EMA lente
    """

    def __init__(self, rsi_period: int = 14, rsi_oversold: float = 30,
                 rsi_overbought: float = 70, ema_fast: int = 9,
                 ema_slow: int = 21, bb_period: int = 20, bb_std: float = 2.0):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.bb_period = bb_period
        self.bb_std = bb_std

    @property
    def name(self) -> str:
        return "Scalper RSI+BB+EMA"

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajoute tous les indicateurs au DataFrame."""
        df = df.copy()

        # RSI
        df["rsi"] = ta.momentum.rsi(df["close"], window=self.rsi_period)

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            df["close"], window=self.bb_period, window_dev=self.bb_std
        )
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_mid"] = bb.bollinger_mavg()

        # EMA
        df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=self.ema_fast)
        df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=self.ema_slow)

        # Crossover EMA: 1 = bullish cross, -1 = bearish cross
        df["ema_diff"] = df["ema_fast"] - df["ema_slow"]
        df["ema_cross"] = 0
        df.loc[
            (df["ema_diff"] > 0) & (df["ema_diff"].shift(1) <= 0), "ema_cross"
        ] = 1  # Bullish
        df.loc[
            (df["ema_diff"] < 0) & (df["ema_diff"].shift(1) >= 0), "ema_cross"
        ] = -1  # Bearish

        return df

    def analyze(self, df: pd.DataFrame, **kwargs) -> Signal:
        """Analyse le DataFrame et retourne un signal."""
        if len(df) < max(self.rsi_period, self.bb_period, self.ema_slow) + 5:
            return Signal.HOLD

        df = self._compute_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Score d'achat (0 à 3)
        buy_score = 0
        sell_score = 0

        # 1. RSI
        rsi = last["rsi"]
        if pd.notna(rsi):
            if rsi < self.rsi_oversold:
                buy_score += 1
            elif rsi > self.rsi_overbought:
                sell_score += 1

        # 2. Bollinger Bands
        price = last["close"]
        bb_lower = last["bb_lower"]
        bb_upper = last["bb_upper"]
        if pd.notna(bb_lower) and pd.notna(bb_upper):
            if price <= bb_lower:
                buy_score += 1
            elif price >= bb_upper:
                sell_score += 1

        # 3. EMA Crossover (sur les 3 dernières bougies)
        recent_crosses = df["ema_cross"].iloc[-3:]
        if (recent_crosses == 1).any():
            buy_score += 1
        elif (recent_crosses == -1).any():
            sell_score += 1

        # Décision: au moins 2 signaux concordants
        if buy_score >= 2:
            logger.debug(
                f"Signal ACHAT | RSI={rsi:.1f} | "
                f"Prix={price:.6f} | BB_low={bb_lower:.6f} | "
                f"Score={buy_score}/3"
            )
            return Signal.BUY
        elif sell_score >= 2:
            logger.debug(
                f"Signal VENTE | RSI={rsi:.1f} | "
                f"Prix={price:.6f} | BB_high={bb_upper:.6f} | "
                f"Score={sell_score}/3"
            )
            return Signal.SELL

        return Signal.HOLD

    def get_indicators(self, df: pd.DataFrame) -> dict:
        """Retourne les indicateurs actuels."""
        if len(df) < max(self.rsi_period, self.bb_period, self.ema_slow) + 5:
            return {}

        df = self._compute_indicators(df)
        last = df.iloc[-1]

        return {
            "rsi": round(float(last["rsi"]), 2) if pd.notna(last["rsi"]) else None,
            "bb_upper": round(float(last["bb_upper"]), 6) if pd.notna(last["bb_upper"]) else None,
            "bb_lower": round(float(last["bb_lower"]), 6) if pd.notna(last["bb_lower"]) else None,
            "bb_mid": round(float(last["bb_mid"]), 6) if pd.notna(last["bb_mid"]) else None,
            "ema_fast": round(float(last["ema_fast"]), 6) if pd.notna(last["ema_fast"]) else None,
            "ema_slow": round(float(last["ema_slow"]), 6) if pd.notna(last["ema_slow"]) else None,
            "price": round(float(last["close"]), 6),
        }
