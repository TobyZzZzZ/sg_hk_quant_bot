import time
from src.api.roostoo import (
    get_ticker,
    get_balance,
    place_order,
    query_order,
    cancel_order,
)

SYMBOL = "BTC/USD"
LOWER_BOUND = 63000.0
UPPER_BOUND = 77000.0
NUM_GRIDS = 40
SPACING = (UPPER_BOUND - LOWER_BOUND) / NUM_GRIDS
Q_PER_GRID = 0.3537  # 固定的每格基准货币(BTC)交易数量
MAKER_FEE = 0.0005  # 0.05% maker fee


def init_grid():
    # 1. 撤销当前所有的挂单
    print(f"Canceling all existing pending orders for {SYMBOL}...")
    cancel_order(pair=SYMBOL)

    # 2. 获取当前价格以决定初始网格缺口(Gap)位置
    ticker = get_ticker(SYMBOL)
    if not ticker or not ticker.get("Success"):
        raise Exception("Failed to get ticker. Please check your network or API keys.")

    last_price = float(ticker["Data"][SYMBOL]["LastPrice"])
    print(f"Current price: {last_price}")

    # 计算初始空缺网格的索引 k
    # k 对应着正好在当前价格下方的那条网格线，这里不会挂任何单，从而保证最高买价和最低卖价之间相差 2 个间距
    k = int((last_price - LOWER_BOUND) / SPACING)
    k = max(0, min(NUM_GRIDS, k))

    print(f"Initial gap index: {k} (Gap Price Level: {LOWER_BOUND + k * SPACING})")

    # 3. 检查是否有充足的 BTC 以挂出所有的卖单
    num_sell_orders = NUM_GRIDS - k
    # 卖出时手续费以 BTC 扣除，所以我们需要准备本金 + 手续费的 BTC 数量
    required_btc = round(num_sell_orders * Q_PER_GRID * (1 + MAKER_FEE), 4) + 0.0001

    balance = get_balance()
    if not balance or not balance.get("Success"):
        raise Exception("Failed to get balance.")

    # 使用更新后的现货钱包字段 'SpotWallet'
    free_btc = float(balance["SpotWallet"]["BTC"]["Free"])
    print(f"Current free BTC: {free_btc:.6f}, Required BTC: {required_btc:.4f}")

    if free_btc < required_btc:
        btc_to_buy = required_btc - free_btc
        print(f"Insufficient BTC. Buying {btc_to_buy:.6f} BTC at market price...")
        # 以市价买入所需的差额 BTC。买入的手续费以 USD 扣除，所以市价买入 btc_to_buy 数量能得到确切数量的 BTC
        resp = place_order(SYMBOL, "BUY", btc_to_buy, order_type="MARKET")
        if not resp or not resp.get("Success"):
            raise Exception(f"Failed to buy initial BTC: {resp}")
        print("Market buy successful.")

    # 4. 初始化挂单
    active_orders = {}
    print("Placing initial SELL limit orders...")
    for i in range(k + 1, NUM_GRIDS + 1):
        price = LOWER_BOUND + i * SPACING
        resp = place_order(SYMBOL, "SELL", Q_PER_GRID, price=price, order_type="LIMIT")
        if resp and resp.get("Success"):
            active_orders[i] = resp["OrderDetail"]["OrderID"]
            print(f"Placed SELL order at {price}")
        else:
            print(f"Failed to place SELL order at {price}: {resp}")

    print("Placing initial BUY limit orders...")
    for i in range(0, k):
        price = LOWER_BOUND + i * SPACING
        resp = place_order(SYMBOL, "BUY", Q_PER_GRID, price=price, order_type="LIMIT")
        if resp and resp.get("Success"):
            active_orders[i] = resp["OrderDetail"]["OrderID"]
            print(f"Placed BUY order at {price}")
        else:
            print(f"Failed to place BUY order at {price}: {resp}")

    return k, active_orders


def main():
    print("=== Starting BTC/USD Grid Bot ===")
    current_gap, active_orders = init_grid()
    print(f"Grid initialization complete. Starting monitor loop...")

    while True:
        time.sleep(1)

        # 抓取目前所有处于 pending 状态的订单
        pending_resp = query_order(pair=SYMBOL, pending_only=True)

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
                f"[FILLED] SELL order at index {idx} (Price: {LOWER_BOUND + idx * SPACING}) filled."
            )
            del active_orders[idx]
            current_gap += 1
            new_buy_idx = current_gap - 1
            if new_buy_idx >= 0:
                price = LOWER_BOUND + new_buy_idx * SPACING
                resp = place_order(
                    SYMBOL, "BUY", Q_PER_GRID, price=price, order_type="LIMIT"
                )
                if resp and resp.get("Success"):
                    active_orders[new_buy_idx] = resp["OrderDetail"]["OrderID"]
                    print(f"[PLACED] New BUY order at {price}")

        # 处理被触发的买单（币价下跌）
        for idx in buys_filled:
            print(
                f"[FILLED] BUY order at index {idx} (Price: {LOWER_BOUND + idx * SPACING}) filled."
            )
            del active_orders[idx]
            current_gap -= 1
            new_sell_idx = current_gap + 1
            if new_sell_idx <= NUM_GRIDS:
                price = LOWER_BOUND + new_sell_idx * SPACING
                resp = place_order(
                    SYMBOL, "SELL", Q_PER_GRID, price=price, order_type="LIMIT"
                )
                if resp and resp.get("Success"):
                    active_orders[new_sell_idx] = resp["OrderDetail"]["OrderID"]
                    print(f"[PLACED] New SELL order at {price}")


if __name__ == "__main__":
    main()
