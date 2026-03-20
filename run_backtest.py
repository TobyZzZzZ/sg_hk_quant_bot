# run_backtest.py
import argparse
import sys
import os

# 确保 src 目录在路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.backtest.engine import STRATEGY_PARAMS, load_market_data, run_backtest
from src.backtest.optimizer import run_optimization


def main():
    parser = argparse.ArgumentParser(description="Roostoo 回测引擎")
    parser.add_argument(
        "--mode",
        type=str,
        default="run",
        choices=["run", "optimize"],
        help="选择运行模式: run (单次回测) 或 optimize (参数优化)",
    )
    parser.add_argument(
        "--interval", type=str, default="1h", help="回测数据的时间间隔 (e.g., 1h, 15m)"
    )

    args, _ = parser.parse_known_args()

    if args.mode == "run":
        print(f"📈 正在启动单次回测 (间隔: {args.interval})...")
        # 修改参数中的间隔
        params = STRATEGY_PARAMS.copy()
        params["data_interval"] = args.interval

        data = load_market_data(interval=args.interval)
        if data is not None:
            close_df, vol_df = data
            run_backtest(params, close_df, vol_df)
    elif args.mode == "optimize":
        print(f"🔍 正在启动参数优化...")
        run_optimization()


if __name__ == "__main__":
    main()
