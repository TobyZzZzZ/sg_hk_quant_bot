from src.interfaces.strategy import BaseStrategy

class DualMAStrategy(BaseStrategy):
    def __init__(self, fast_window=10, slow_window=50):
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.initialize()

    def initialize(self, *args, **kwargs):
        self.price_history = []
        self.last_signal = 0

    def handle_data(self, current_price, *args, **kwargs):
        """
        Takes the current price, updates history, and returns a signal.
        Returns: 1 for BUY, -1 for SELL, 0 for HOLD.
        """
        self.price_history.append(current_price)
        if len(self.price_history) > self.slow_window:
            self.price_history.pop(0)

        if len(self.price_history) < self.slow_window:
            return 0

        fast_ma = sum(self.price_history[-self.fast_window:]) / self.fast_window
        slow_ma = sum(self.price_history[-self.slow_window:]) / self.slow_window

        # Check crossover
        prev_fast_ma = sum(self.price_history[-self.fast_window-1:-1]) / self.fast_window
        prev_slow_ma = sum(self.price_history[-self.slow_window-1:-1]) / self.slow_window

        signal = 0
        if fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma:
            signal = 1
        elif fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma:
            signal = -1

        return signal

    def analyze(self, *args, **kwargs):
        pass
