import argparse
import time

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
    parser = argparse.ArgumentParser(description="Live Trading Runner")
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        choices=STRATEGIES.keys(),
        help="Strategy to run",
    )
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Trading symbol")
    parser.add_argument(
        "--interval", type=int, default=60, help="Check interval in seconds"
    )
    args = parser.parse_args()

    print(f"🤖 Starting Live Trading for {args.strategy} on {args.symbol}...")

    strategy = load_strategy(args.strategy, {})

    # Simple Mock Event Loop
    try:
        while True:
            print(f"[{time.strftime('%H:%M:%S')}] Fetching market data...")
            # Mock data fetch from roostoo or other API
            mock_price = 65000.0  # dummy

            # Use Strategy Interface
            signals = strategy.handle_data(mock_price)
            if signals:
                print(f"--> Strategy emitted signal: {signals}")
                # Mock execute

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Live trading stopped.")
        strategy.analyze()


if __name__ == "__main__":
    main()
