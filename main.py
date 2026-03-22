import time
import threading
from roostoo import (
    get_ticker,
    get_balance,
    place_order,
    query_order,
    cancel_order,
)

# 多币种网格配置列表，可独立配置参数
GRID_CONFIGS = [
    {
        "symbol": "BTC/USD",
        "lower_bound": 63000.0,
        "upper_bound": 77000.0,
        "num_grids": 40,
        "q_per_grid": 0.0088,
    },
    {
        "symbol": "PAXG/USD",
        "lower_bound": 4000.0,
        "upper_bound": 5000.0,
        "num_grids": 40,
        "q_per_grid": 0.1375,
    },
]

MAKER_FEE = 0.0005  # 0.05% maker fee
TAKER_FEE = 0.001  # 0.1% taker fee


def init_grid(config):
    symbol = config["symbol"]
    lower_bound = config["lower_bound"]
    upper_bound = config["upper_bound"]
    num_grids = config["num_grids"]
    q_per_grid = config["q_per_grid"]

    spacing = (upper_bound - lower_bound) / num_grids
    base_currency = symbol.split("/")[0]

    # 1. 撤销当前所有的挂单
    print(f"[{symbol}] Canceling all existing pending orders...")
    cancel_order(pair=symbol)

    # 2. 获取当前价格以决定初始网格缺口(Gap)位置
    ticker = get_ticker(symbol)
    if not ticker or not ticker.get("Success"):
        raise Exception(
            f"[{symbol}] Failed to get ticker. Please check your network or API keys."
        )

    last_price = float(ticker["Data"][symbol]["LastPrice"])
    print(f"[{symbol}] Current price: {last_price}")

    # 计算初始空缺网格的索引 k
    # k 对应着正好在当前价格下方的那条网格线，这里不会挂任何单，从而保证最高买价和最低卖价之间相差 2 个间距
    k = int((last_price - lower_bound) / spacing)
    k = max(0, min(num_grids, k))

    print(
        f"[{symbol}] Initial gap index: {k} (Gap Price Level: {lower_bound + k * spacing})"
    )

    # 3. 检查是否有充足的基准货币以挂出所有的卖单
    num_sell_orders = num_grids - k
    # 卖出时手续费以基准货币扣除，所以我们需要准备本金 + 手续费的数量，增加精度以防各种币种位数不同
    required_base = round(num_sell_orders * q_per_grid * (1 + MAKER_FEE), 6) + 0.000001

    balance = get_balance()
    if not balance or not balance.get("Success"):
        raise Exception(f"[{symbol}] Failed to get balance.")

    # 使用更新后的现货钱包字段 'SpotWallet'
    currency_balance = balance["SpotWallet"].get(base_currency, {})
    free_base = float(currency_balance.get("Free", 0.0))
    print(
        f"[{symbol}] Current free {base_currency}: {free_base:.6f}, Required {base_currency}: {required_base:.6f}"
    )

    if free_base < required_base:
        base_to_buy = required_base - free_base
        base_to_buy = round(base_to_buy, 4)
        print(
            f"[{symbol}] Insufficient {base_currency}. Buying {base_to_buy:.4f} {base_currency} at market price..."
        )
        # 以市价买入所需的差额。买入的手续费以 USD 扣除，所以市价买入 base_to_buy 数量能得到确切数量的基准货币
        resp = place_order(symbol, "BUY", base_to_buy, order_type="MARKET")
        if not resp or not resp.get("Success"):
            raise Exception(f"[{symbol}] Failed to buy initial {base_currency}: {resp}")
        print(f"[{symbol}] Market buy successful.")
    elif free_base > required_base:
        # 持仓超量，需要卖出多余的基准货币
        # 考虑到市价卖出(Taker)时可能会以基准货币扣除手续费(0.1%)
        # 需确保卖出 base_to_sell 并扣除 TAKER_FEE 后，剩余余额等于 required_base
        # 公式: free_base - base_to_sell * (1 + TAKER_FEE) >= required_base
        base_to_sell = (free_base - required_base) / (1 + TAKER_FEE)
        base_to_sell = round(base_to_sell, 4)

        # 避免极小额度的灰尘交易（如小于万分之一）
        if base_to_sell >= 0.0001:
            print(
                f"[{symbol}] Excess {base_currency} found. Selling {base_to_sell:.4f} {base_currency} at market price to match required balance..."
            )
            resp = place_order(symbol, "SELL", base_to_sell, order_type="MARKET")
            if not resp or not resp.get("Success"):
                raise Exception(
                    f"[{symbol}] Failed to sell excess {base_currency}: {resp}"
                )
            print(f"[{symbol}] Market sell successful.")

    # 4. 初始化挂单
    active_orders = {}
    print(f"[{symbol}] Placing initial SELL limit orders...")
    for i in range(k + 1, num_grids + 1):
        price = lower_bound + i * spacing
        resp = place_order(symbol, "SELL", q_per_grid, price=price, order_type="LIMIT")
        if resp and resp.get("Success"):
            active_orders[i] = resp["OrderDetail"]["OrderID"]
            print(f"[{symbol}] Placed SELL order at {price}")
        else:
            print(f"[{symbol}] Failed to place SELL order at {price}: {resp}")

    print(f"[{symbol}] Placing initial BUY limit orders...")
    for i in range(0, k):
        price = lower_bound + i * spacing
        resp = place_order(symbol, "BUY", q_per_grid, price=price, order_type="LIMIT")
        if resp and resp.get("Success"):
            active_orders[i] = resp["OrderDetail"]["OrderID"]
            print(f"[{symbol}] Placed BUY order at {price}")
        else:
            print(f"[{symbol}] Failed to place BUY order at {price}: {resp}")

    return k, active_orders, spacing


def run_grid(config):
    symbol = config["symbol"]
    lower_bound = config["lower_bound"]
    upper_bound = config["upper_bound"]
    num_grids = config["num_grids"]
    q_per_grid = config["q_per_grid"]

    print(f"=== Starting {symbol} Grid Bot ===")
    try:
        current_gap, active_orders, spacing = init_grid(config)
    except Exception as e:
        print(f"[{symbol}] Initialization failed: {e}")
        return

    print(f"[{symbol}] Grid initialization complete. Starting monitor loop...")

    while True:
        time.sleep(1)

        # 抓取目前所有处于 pending 状态的订单
        pending_resp = query_order(pair=symbol, pending_only=True)

        if not pending_resp or not pending_resp.get("Success"):
            if pending_resp and pending_resp.get("ErrMsg") == "no order matched":
                pending_ids = set()
            else:
                # 遇到临时的网络错误或 Rate Limit 则跳过本次循环
                continue
        else:
            pending_orders = pending_resp.get("OrderMatched", [])
            pending_ids = set(order["OrderID"] for order in pending_orders)

        # 找出当前活动订单中已经不在 pending 列表里的订单，这意味着它们已成交（FILLED）
        filled_indices = []
        for idx, order_id in active_orders.items():
            if order_id not in pending_ids:
                filled_indices.append(idx)

        if not filled_indices:
            continue

        # 将已成交订单按方向拆分并排序，以便妥善处理剧烈波动（一次成交多单）的情况
        # 价格上涨时，卖单被吃掉，从下往上依次填补
        sells_filled = sorted([i for i in filled_indices if i > current_gap])
        # 价格下跌时，买单被吃掉，从上往下依次填补
        buys_filled = sorted(
            [i for i in filled_indices if i < current_gap], reverse=True
        )

        # 处理被触发的卖单（币价上涨）
        for idx in sells_filled:
            print(
                f"[{symbol}] [FILLED] SELL order at index {idx} (Price: {lower_bound + idx * spacing}) filled."
            )
            del active_orders[idx]
            current_gap += 1
            new_buy_idx = current_gap - 1
            if new_buy_idx >= 0:
                price = lower_bound + new_buy_idx * spacing
                resp = place_order(
                    symbol, "BUY", q_per_grid, price=price, order_type="LIMIT"
                )
                if resp and resp.get("Success"):
                    active_orders[new_buy_idx] = resp["OrderDetail"]["OrderID"]
                    print(f"[{symbol}] [PLACED] New BUY order at {price}")

        # 处理被触发的买单（币价下跌）
        for idx in buys_filled:
            print(
                f"[{symbol}] [FILLED] BUY order at index {idx} (Price: {lower_bound + idx * spacing}) filled."
            )
            del active_orders[idx]
            current_gap -= 1
            new_sell_idx = current_gap + 1
            if new_sell_idx <= num_grids:
                price = lower_bound + new_sell_idx * spacing
                resp = place_order(
                    symbol, "SELL", q_per_grid, price=price, order_type="LIMIT"
                )
                if resp and resp.get("Success"):
                    active_orders[new_sell_idx] = resp["OrderDetail"]["OrderID"]
                    print(f"[{symbol}] [PLACED] New SELL order at {price}")


def main():
    print("=== Starting Multi-Pair Grid Bots ===")
    threads = []

    # 为每个配置启动一个独立的线程
    for config in GRID_CONFIGS:
        t = threading.Thread(
            target=run_grid, args=(config,), name=config["symbol"], daemon=True
        )
        t.start()
        threads.append(t)
        # 启动间隔，防止瞬间请求太多导致被 API 限制
        time.sleep(1)

    try:
        # 主线程等待所有子线程
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all grid bots...")


if __name__ == "__main__":
    main()
