import unittest
import pandas as pd
from src.backtest.engine import StrategyRunner
from src.backtest.portfolio import Portfolio
from src.backtest.datafeed import DataFeed
from src.backtest.execution import Execution
from src.backtest.performance import PerformanceAnalyzer


class MockStrategy:
    def handle_data(self, row, *args, **kwargs):
        # Buy 1 at first step
        return [{"type": "BUY", "amount_usd": 1000}]

    def analyze(self):
        pass


class TestBacktestEngine(unittest.TestCase):
    def test_engine_run(self):
        df = pd.DataFrame(
            {
                "open_time": pd.date_range(start="2026-01-01", periods=5),
                "close": [100, 105, 110, 108, 115],
            }
        ).set_index("open_time")

        datafeed = DataFeed(df)
        portfolio = Portfolio(initial_capital=10000)
        execution = Execution()
        strategy = MockStrategy()

        runner = StrategyRunner(strategy, datafeed, portfolio, execution)
        equity_curve, trades = runner.run()

        self.assertGreater(len(equity_curve), 0)
        self.assertGreater(len(trades), 0)

        analyzer = PerformanceAnalyzer(equity_curve, trades)
        metrics = analyzer.calculate_metrics()
        self.assertIn("Total Return", metrics)


if __name__ == "__main__":
    unittest.main()
