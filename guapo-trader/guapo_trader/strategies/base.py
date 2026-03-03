from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class BaseStrategy(ABC):
    """Classe de base pour toutes les stratégies de trading."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def analyze(self, df: pd.DataFrame, **kwargs) -> Signal:
        """Analyse les données et retourne un signal BUY, SELL ou HOLD."""
        ...

    @abstractmethod
    def get_indicators(self, df: pd.DataFrame) -> dict:
        """Retourne les valeurs actuelles des indicateurs."""
        ...
