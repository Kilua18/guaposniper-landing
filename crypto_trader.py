#!/usr/bin/env python3
"""
CryptoTrader IA - Script de trading crypto intelligent pour Termux
Utilise des indicateurs techniques + un modele de decision IA (ML)
Compatible Termux / Android (Z Fold, etc.)

AVERTISSEMENT : Ce script est a but educatif.
Le trading de cryptomonnaies comporte des risques importants.
N'investissez que ce que vous pouvez vous permettre de perdre.
"""

import os
import sys
import json
import time
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG = {
    # Paire de trading (symbole CoinGecko)
    "coin_id": "bitcoin",
    "vs_currency": "usd",
    "symbol": "BTC/USD",

    # Parametres du modele IA
    "lookback_days": 90,        # Jours d'historique pour l'entrainement
    "prediction_threshold": 0.6, # Seuil de confiance pour agir (0.5-1.0)
    "retrain_interval_hours": 6, # Re-entrainer le modele toutes les X heures

    # Parametres de trading (paper trading par defaut)
    "initial_balance_usd": 1000.0,
    "trade_size_pct": 0.1,       # 10% du portefeuille par trade
    "stop_loss_pct": 0.03,       # Stop-loss a 3%
    "take_profit_pct": 0.06,     # Take-profit a 6%

    # Intervalles
    "check_interval_seconds": 300,  # Verifier toutes les 5 minutes

    # Fichiers de donnees
    "data_dir": "trader_data",
    "portfolio_file": "portfolio.json",
    "trades_file": "trades.json",
    "model_file": "model_state.json",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(CONFIG["data_dir"], "trader.log")
            if os.path.isdir(CONFIG["data_dir"])
            else "trader.log"
        ),
    ],
)
log = logging.getLogger("CryptoTrader")

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def ensure_data_dir():
    Path(CONFIG["data_dir"]).mkdir(parents=True, exist_ok=True)


def load_json(filename):
    filepath = os.path.join(CONFIG["data_dir"], filename)
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return None


def save_json(filename, data):
    filepath = os.path.join(CONFIG["data_dir"], filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Recuperation des donnees de marche (API CoinGecko gratuite)
# ---------------------------------------------------------------------------

def fetch_market_data(coin_id, vs_currency, days):
    """Recupere l'historique des prix via CoinGecko (gratuit, sans cle API)."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        f"/market_chart?vs_currency={vs_currency}&days={days}&interval=daily"
    )
    log.info(f"Recuperation des donnees: {coin_id} ({days} jours)...")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        prices = data["prices"]            # [[timestamp_ms, price], ...]
        volumes = data["total_volumes"]     # [[timestamp_ms, volume], ...]

        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["volume"] = [v[1] for v in volumes[: len(df)]]
        df.set_index("timestamp", inplace=True)
        log.info(f"  -> {len(df)} points de donnees recus")
        return df
    except Exception as e:
        log.error(f"Erreur API CoinGecko: {e}")
        return None


def fetch_current_price(coin_id, vs_currency):
    """Recupere le prix actuel."""
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_id}&vs_currencies={vs_currency}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()[coin_id][vs_currency]
    except Exception as e:
        log.error(f"Erreur prix actuel: {e}")
        return None


# ---------------------------------------------------------------------------
# Indicateurs techniques
# ---------------------------------------------------------------------------

def compute_indicators(df):
    """Calcule les indicateurs techniques sur le DataFrame."""
    df = df.copy()

    # Moyennes mobiles
    df["sma_7"] = df["price"].rolling(window=7).mean()
    df["sma_21"] = df["price"].rolling(window=21).mean()
    df["ema_12"] = df["price"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["price"].ewm(span=26, adjust=False).mean()

    # MACD
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # RSI (14 periodes)
    delta = df["price"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger Bands (20 periodes, 2 ecarts-types)
    df["bb_mid"] = df["price"].rolling(window=20).mean()
    bb_std = df["price"].rolling(window=20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    # Variation de prix (rendement journalier)
    df["return_1d"] = df["price"].pct_change(1)
    df["return_3d"] = df["price"].pct_change(3)
    df["return_7d"] = df["price"].pct_change(7)

    # Variation de volume
    df["vol_change"] = df["volume"].pct_change(1)
    df["vol_sma_7"] = df["volume"].rolling(window=7).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma_7"]

    # Momentum
    df["momentum_10"] = df["price"] - df["price"].shift(10)

    # Label : le prix monte-t-il le lendemain ? (1 = oui, 0 = non)
    df["target"] = (df["price"].shift(-1) > df["price"]).astype(int)

    df.dropna(inplace=True)
    return df


# ---------------------------------------------------------------------------
# Modele IA (Random Forest)
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "sma_7", "sma_21", "ema_12", "ema_26",
    "macd", "macd_signal", "macd_hist",
    "rsi",
    "bb_upper", "bb_lower", "bb_width",
    "return_1d", "return_3d", "return_7d",
    "vol_change", "vol_ratio",
    "momentum_10",
]


class TradingAI:
    """Modele de prediction base sur Random Forest."""

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.accuracy = 0.0
        self.last_trained = None

    def train(self, df):
        """Entraine le modele sur les donnees historiques."""
        X = df[FEATURE_COLS].values
        y = df["target"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model.fit(X_train_scaled, y_train)
        self.accuracy = self.model.score(X_test_scaled, y_test)
        self.is_trained = True
        self.last_trained = datetime.now()

        log.info(f"Modele entraine - Precision: {self.accuracy:.2%}")
        self._log_feature_importance(df)
        return self.accuracy

    def predict(self, df):
        """Predit la direction du prix (hausse/baisse) avec probabilite."""
        if not self.is_trained:
            return None, 0.0

        latest = df[FEATURE_COLS].iloc[-1:].values
        latest_scaled = self.scaler.transform(latest)

        prediction = self.model.predict(latest_scaled)[0]
        probabilities = self.model.predict_proba(latest_scaled)[0]
        confidence = max(probabilities)

        direction = "HAUSSE" if prediction == 1 else "BAISSE"
        log.info(f"Prediction: {direction} (confiance: {confidence:.2%})")
        return prediction, confidence

    def needs_retrain(self):
        if self.last_trained is None:
            return True
        hours_since = (datetime.now() - self.last_trained).total_seconds() / 3600
        return hours_since >= CONFIG["retrain_interval_hours"]

    def _log_feature_importance(self, df):
        importances = self.model.feature_importances_
        feat_imp = sorted(
            zip(FEATURE_COLS, importances), key=lambda x: x[1], reverse=True
        )
        log.info("Top 5 indicateurs les plus importants:")
        for name, imp in feat_imp[:5]:
            log.info(f"  {name}: {imp:.4f}")


# ---------------------------------------------------------------------------
# Gestionnaire de portefeuille (Paper Trading)
# ---------------------------------------------------------------------------

class Portfolio:
    """Simule un portefeuille de trading (paper trading)."""

    def __init__(self):
        saved = load_json(CONFIG["portfolio_file"])
        if saved:
            self.balance_usd = saved["balance_usd"]
            self.holdings = saved["holdings"]
            self.total_trades = saved["total_trades"]
            self.winning_trades = saved["winning_trades"]
            self.initial_balance = saved.get(
                "initial_balance", CONFIG["initial_balance_usd"]
            )
            log.info(f"Portefeuille charge: ${self.balance_usd:.2f} USD, "
                     f"{self.holdings:.8f} crypto")
        else:
            self.balance_usd = CONFIG["initial_balance_usd"]
            self.holdings = 0.0
            self.total_trades = 0
            self.winning_trades = 0
            self.initial_balance = CONFIG["initial_balance_usd"]

        self.trades = load_json(CONFIG["trades_file"]) or []
        self.entry_price = None

    def save(self):
        save_json(CONFIG["portfolio_file"], {
            "balance_usd": self.balance_usd,
            "holdings": self.holdings,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "initial_balance": self.initial_balance,
        })
        save_json(CONFIG["trades_file"], self.trades)

    def buy(self, price):
        """Achete de la crypto."""
        trade_amount = self.balance_usd * CONFIG["trade_size_pct"]
        if trade_amount < 1.0:
            log.warning("Solde insuffisant pour acheter")
            return False

        qty = trade_amount / price
        self.balance_usd -= trade_amount
        self.holdings += qty
        self.entry_price = price

        trade = {
            "type": "BUY",
            "price": price,
            "qty": qty,
            "amount_usd": trade_amount,
            "timestamp": datetime.now().isoformat(),
        }
        self.trades.append(trade)
        self.save()

        log.info(
            f"ACHAT: {qty:.8f} @ ${price:,.2f} "
            f"(${trade_amount:.2f})"
        )
        return True

    def sell(self, price, reason="signal"):
        """Vend toute la position."""
        if self.holdings <= 0:
            return False

        amount_usd = self.holdings * price
        profit = amount_usd - (self.holdings * (self.entry_price or price))
        profit_pct = (profit / (self.holdings * (self.entry_price or price))) * 100

        self.balance_usd += amount_usd
        self.total_trades += 1
        if profit > 0:
            self.winning_trades += 1

        trade = {
            "type": "SELL",
            "price": price,
            "qty": self.holdings,
            "amount_usd": amount_usd,
            "profit": profit,
            "profit_pct": profit_pct,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        self.trades.append(trade)

        log.info(
            f"VENTE ({reason}): {self.holdings:.8f} @ ${price:,.2f} "
            f"-> {'+'if profit>=0 else ''}{profit:.2f}$ ({profit_pct:+.2f}%)"
        )

        self.holdings = 0.0
        self.entry_price = None
        self.save()
        return True

    def get_total_value(self, current_price):
        return self.balance_usd + (self.holdings * current_price)

    def get_pnl(self, current_price):
        total = self.get_total_value(current_price)
        return total - self.initial_balance

    def get_win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    def print_status(self, current_price):
        total = self.get_total_value(current_price)
        pnl = self.get_pnl(current_price)
        pnl_pct = (pnl / self.initial_balance) * 100

        print("\n" + "=" * 50)
        print(f"  PORTEFEUILLE - {CONFIG['symbol']}")
        print("=" * 50)
        print(f"  Prix actuel:     ${current_price:,.2f}")
        print(f"  Solde USD:       ${self.balance_usd:,.2f}")
        print(f"  Holdings:        {self.holdings:.8f}")
        print(f"  Valeur totale:   ${total:,.2f}")
        print(f"  PnL:             {'+'if pnl>=0 else ''}{pnl:.2f}$ ({pnl_pct:+.2f}%)")
        print(f"  Trades:          {self.total_trades}")
        print(f"  Win rate:        {self.get_win_rate():.0%}")
        print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# Boucle principale de trading
# ---------------------------------------------------------------------------

class CryptoTrader:
    """Boucle principale du bot de trading."""

    def __init__(self):
        ensure_data_dir()
        self.ai = TradingAI()
        self.portfolio = Portfolio()
        self.running = True

        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        log.info("\nArret du bot...")
        self.running = False

    def _check_stop_loss_take_profit(self, current_price):
        """Verifie les seuils de stop-loss et take-profit."""
        if self.portfolio.holdings <= 0 or self.portfolio.entry_price is None:
            return

        change_pct = (current_price - self.portfolio.entry_price) / self.portfolio.entry_price

        if change_pct <= -CONFIG["stop_loss_pct"]:
            log.warning(f"STOP-LOSS declenche ({change_pct:.2%})")
            self.portfolio.sell(current_price, reason="stop-loss")
        elif change_pct >= CONFIG["take_profit_pct"]:
            log.info(f"TAKE-PROFIT declenche ({change_pct:.2%})")
            self.portfolio.sell(current_price, reason="take-profit")

    def run(self):
        print(r"""
   ____                  _        _____              _
  / ___|_ __ _   _ _ __ | |_ ___ |_   _| __ __ _  __| | ___ _ __
 | |   | '__| | | | '_ \| __/ _ \  | || '__/ _` |/ _` |/ _ \ '__|
 | |___| |  | |_| | |_) | || (_) | | || | | (_| | (_| |  __/ |
  \____|_|   \__, | .__/ \__\___/  |_||_|  \__,_|\__,_|\___|_|
             |___/|_|             IA Trading Bot v1.0
        """)
        print("  Mode: PAPER TRADING (simulation)")
        print(f"  Paire: {CONFIG['symbol']}")
        print(f"  Solde initial: ${CONFIG['initial_balance_usd']:,.2f}")
        print(f"  Intervalle: {CONFIG['check_interval_seconds']}s")
        print("-" * 50)

        while self.running:
            try:
                # 1. Recuperer le prix actuel
                current_price = fetch_current_price(
                    CONFIG["coin_id"], CONFIG["vs_currency"]
                )
                if current_price is None:
                    log.warning("Impossible de recuperer le prix, nouvel essai...")
                    time.sleep(30)
                    continue

                # 2. Verifier stop-loss / take-profit
                self._check_stop_loss_take_profit(current_price)

                # 3. Entrainer / re-entrainer le modele si necessaire
                if self.ai.needs_retrain():
                    df = fetch_market_data(
                        CONFIG["coin_id"],
                        CONFIG["vs_currency"],
                        CONFIG["lookback_days"],
                    )
                    if df is not None:
                        df = compute_indicators(df)
                        if len(df) > 30:
                            self.ai.train(df)

                # 4. Obtenir la prediction IA
                if self.ai.is_trained:
                    df = fetch_market_data(
                        CONFIG["coin_id"],
                        CONFIG["vs_currency"],
                        CONFIG["lookback_days"],
                    )
                    if df is not None:
                        df = compute_indicators(df)
                        prediction, confidence = self.ai.predict(df)

                        if confidence >= CONFIG["prediction_threshold"]:
                            if prediction == 1 and self.portfolio.holdings == 0:
                                # Signal d'achat
                                log.info(
                                    f"Signal ACHAT (confiance: {confidence:.2%})"
                                )
                                self.portfolio.buy(current_price)
                            elif prediction == 0 and self.portfolio.holdings > 0:
                                # Signal de vente
                                log.info(
                                    f"Signal VENTE (confiance: {confidence:.2%})"
                                )
                                self.portfolio.sell(current_price, reason="signal-ia")
                        else:
                            log.info(
                                f"Confiance trop faible ({confidence:.2%}), "
                                f"pas d'action"
                            )

                # 5. Afficher le statut
                self.portfolio.print_status(current_price)

                # 6. Attendre le prochain cycle
                log.info(
                    f"Prochain check dans "
                    f"{CONFIG['check_interval_seconds']}s... "
                    f"(Ctrl+C pour quitter)"
                )
                time.sleep(CONFIG["check_interval_seconds"])

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                log.error(f"Erreur dans la boucle principale: {e}")
                time.sleep(60)

        # Sauvegarde finale
        log.info("Sauvegarde du portefeuille...")
        self.portfolio.save()
        log.info("Bot arrete. A bientot!")


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    trader = CryptoTrader()
    trader.run()
