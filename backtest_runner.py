import argparse
import sys
import os
import pandas as pd

from src.backtest.engine import StrategyRunner
from src.backtest.portfolio import Portfolio
from src.backtest.datafeed import DataFeed
from src.backtest.execution import Execution
from src.backtest.performance import PerformanceAnalyzer

# Dynamic Strategy Loading
STRATEGIES = {
    "grid": ("src.strategies.spot_grid", "ArithmeticGridStrategy"),
    "multifactor": ("src.strategies.multi_factor", "MultiFactorStrategy"),
    "dualma": ("src.strategies.dual_ma", "DualMAStrategy"),
}


def load_strategy(strategy_name, params):
    if strategy_name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    module_name, class_name = STRATEGIES[strategy_name]
    module = __import__(module_name, fromlist=[class_name])
    strategy_class = getattr(module, class_name)

    if params:
        return strategy_class(**params)
    return strategy_class()


def main():
    parser = argparse.ArgumentParser(description="Unified Backtest Runner")
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=STRATEGIES.keys(),
        help="Strategy to run",
    )
    parser.add_argument("--data", type=str, required=True, help="Path to CSV data file")
    parser.add_argument(
        "--params", type=str, default="{}", help="Strategy parameters in JSON format"
    )
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Parse params
    import json

    try:
        strategy_params = json.loads(args.params)
    except json.JSONDecodeError:
        print("Error: Invalid JSON for strategy parameters.")
        sys.exit(1)

    # Load data
    print(f"Loading data from {args.data}...")
    df = pd.read_csv(args.data)
    if "open_time" in df.columns:
        df["open_time"] = pd.to_datetime(df["open_time"])
        df.set_index("open_time", inplace=True)
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

    # Filter by date
    if args.start:
        df = df[df.index >= args.start]
    if args.end:
        df = df[df.index <= args.end]

    if df.empty:
        print("Error: No data available for the specified date range.")
        sys.exit(1)

    datafeed = DataFeed(df)

    # Load strategy
    strategy = load_strategy(args.strategy, strategy_params)

    # Initialize components
    portfolio = Portfolio(initial_capital=100000)
    execution = Execution(maker_fee=0.0005, taker_fee=0.001)

    # Run Engine
    runner = StrategyRunner(strategy, datafeed, portfolio, execution)
    equity_curve, trades = runner.run()

    # Analyze
    analyzer = PerformanceAnalyzer(equity_curve, trades)
    analyzer.calculate_metrics()
    analyzer.export_results(output_dir="reports")


if __name__ == "__main__":
    main()
