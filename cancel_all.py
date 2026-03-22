from roostoo import cancel_order
import time


print("=== Canceling all existing orders for configured pairs ===")
for symbol in ["BTC/USD", "ETH/USD", "TAO/USD", "PAXG/USD"]:
    print(f"[{symbol}] Canceling pending orders...")
    cancel_order(pair=symbol)
    time.sleep(0.5)
