# main.py
import argparse
import sys
from src.strategies.multi_factor import run_strategy as run_multi_factor
from src.strategies.toy import run_strategy as run_toy_strategy


def main():
    parser = argparse.ArgumentParser(description="Roostoo 量化交易机器人")
    parser.add_argument(
        "--strategy",
        type=str,
        default="multi_factor",
        choices=["multi_factor", "toy"],
        help="选择运行的策略 (默认: multi_factor)",
    )

    # 允许传递额外参数给策略
    args, unknown = parser.parse_known_args()

    if args.strategy == "multi_factor":
        print("🚀 正在启动多因子策略...")
        # 传递 unknown 参数给策略
        run_multi_factor(unknown)
    elif args.strategy == "toy":
        print("🚀 正在启动双均线入门策略...")
        run_toy_strategy(unknown)


if __name__ == "__main__":
    main()
