import time
import threading
from roostoo import (
    get_ticker,
    get_balance,
    place_order,
    query_order,
    cancel_order,
)

# Multi-currency grid configuration list, parameters can be configured independently
GRID_CONFIGS = [
    {
        "symbol": "BTC/USD",
        "lower_bound": 63000.0,
        "upper_bound": 77000.0,
        "num_grids": 40,
        "q_per_grid": 0.0882,
    },
    {
        "symbol": "ETH/USD",
        "lower_bound": 1850.0,
        "upper_bound": 2500.0,
        "num_grids": 52,
        "q_per_grid": 2.1882,
    },
    {
        "symbol": "TAO/USD",
        "lower_bound": 220.0,
        "upper_bound": 330.0,
        "num_grids": 55,
        "q_per_grid": 16.3635,
    },
    {
        "symbol": "PAXG/USD",
        "lower_bound": 4000.0,
        "upper_bound": 5000.0,
        "num_grids": 40,
        "q_per_grid": 1.3750,
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

    # 1. Cancel all current pending orders
    print(f"[{symbol}] Canceling all existing pending orders...")
    cancel_order(pair=symbol)

    # 2. Get current price to determine the initial grid gap position
    ticker = get_ticker(symbol)
    if not ticker or not ticker.get("Success"):
        raise Exception(
            f"[{symbol}] Failed to get ticker. Please check your network or API keys."
        )

    last_price = float(ticker["Data"][symbol]["LastPrice"])
    print(f"[{symbol}] Current price: {last_price}")

    # Calculate initial gap index k
    # k corresponds to the grid line just below the current price. No orders will be placed here,
    # ensuring a 2-spacing distance between the highest buy price and the lowest sell price.
    k = int((last_price - lower_bound) / spacing)
    k = max(0, min(num_grids, k))

    print(
        f"[{symbol}] Initial gap index: {k} (Gap Price Level: {lower_bound + k * spacing})"
    )

    # 3. Check if there is enough base currency to place all sell orders
    num_sell_orders = num_grids - k
    # Fees are deducted in base currency for sells, so we need to prepare principal + fees.
    # Increase precision to handle different currency decimal places.
    required_base = round(num_sell_orders * q_per_grid * (1 + MAKER_FEE), 6) + 0.000001

    balance = get_balance()
    if not balance or not balance.get("Success"):
        raise Exception(f"[{symbol}] Failed to get balance.")

    # Use the updated spot wallet field 'SpotWallet'
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
        # Buy the required difference at market price. Fees for buying are deducted in USD,
        # so buying base_to_buy amount will result in the exact amount of base currency.
        resp = place_order(symbol, "BUY", base_to_buy, order_type="MARKET")
        if not resp or not resp.get("Success"):
            raise Exception(f"[{symbol}] Failed to buy initial {base_currency}: {resp}")
        print(f"[{symbol}] Market buy successful.")
    elif free_base > required_base:
        # Excess holdings, need to sell extra base currency
        # Considering fees (0.1%) might be deducted in base currency for market sells (Taker)
        # Ensure that after selling base_to_sell and deducting TAKER_FEE, the remaining balance equals required_base
        # Formula: free_base - base_to_sell * (1 + TAKER_FEE) >= required_base
        base_to_sell = (free_base - required_base) / (1 + TAKER_FEE)
        base_to_sell = round(base_to_sell, 4)

        # Avoid dust trades (e.g., less than 0.0001)
        if base_to_sell >= 0.0001:
            print(
                f"[{symbol}] Excess {base_currency} found. Selling {base_to_sell:.4f} {base_currency} at market price to match required balance..."
            )
            resp = place_order(symbol, "SELL", base_to_sell, order_type="MARKET")
            if not resp or not resp.get("Success"):
                raise Exception(
                    f"[{symbol}] Failed to sell excess {base_currency}: {resp}"
                )
            print(f"[{symbol}] Market buy successful.")

    # 4. Initialize pending orders
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

        # Fetch all currently pending orders
        pending_resp = query_order(pair=symbol, pending_only=True)

        if not pending_resp or not pending_resp.get("Success"):
            if pending_resp and pending_resp.get("ErrMsg") == "no order matched":
                pending_ids = set()
            else:
                # Skip this loop iteration on temporary network error or Rate Limit
                continue
        else:
            pending_orders = pending_resp.get("OrderMatched", [])
            pending_ids = set(order["OrderID"] for order in pending_orders)

        # Find orders in active_orders that are no longer in the pending list, meaning they are FILLED
        filled_indices = []
        for idx, order_id in active_orders.items():
            if order_id not in pending_ids:
                filled_indices.append(idx)

        if not filled_indices:
            continue

        # Split filled orders by direction and sort them to handle sharp fluctuations (multiple fills at once)
        # When price rises, sell orders are filled, replenished from bottom to top
        sells_filled = sorted([i for i in filled_indices if i > current_gap])
        # When price falls, buy orders are filled, replenished from top to bottom
        buys_filled = sorted(
            [i for i in filled_indices if i < current_gap], reverse=True
        )

        # Handle triggered sell orders (price increase)
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

        # Handle triggered buy orders (price decrease)
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

    # Start an independent thread for each configuration
    for config in GRID_CONFIGS:
        t = threading.Thread(
            target=run_grid, args=(config,), name=config["symbol"], daemon=True
        )
        t.start()
        threads.append(t)
        # Start interval to prevent too many requests at once hitting API limits
        time.sleep(1)

    try:
        # Main thread waits for all child threads
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all grid bots...")


if __name__ == "__main__":
    main()
