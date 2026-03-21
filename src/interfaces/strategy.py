from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    Abstract Base Class defining the standard interface for all trading strategies.
    Strategies must not import or depend on the backtesting framework.
    """

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        Initialize strategy parameters, indicators, and state variables.
        """
        pass

    @abstractmethod
    def handle_data(self, data, *args, **kwargs):
        """
        Core strategy logic to be executed on each data update (e.g., tick or bar).
        Should return a list of signals or orders.
        """
        pass

    @abstractmethod
    def analyze(self, *args, **kwargs):
        """
        Optional post-run analysis or finalization.
        """
        pass
