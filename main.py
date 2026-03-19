# main.py
import time
from roostoo_api import check_server_time, get_balance, get_ticker, place_order

SYMBOL = "BTC/USD"
TRADE_QTY = 0.01  # 每次交易数量


def run_strategy():
    print("🤖 量化机器人启动中...")

    # 1. 首先测试连接和 API 权限
    print("--> 正在测试服务器连接...")
    if not check_server_time():
        print("❌ 无法连接到 Roostoo 服务器，请检查网络。")
        return

    print("--> 正在获取账户余额...")
    balance = get_balance()
    if not balance or not balance.get("Success"):
        print("❌ API Key 或 Secret 错误，或者无权访问余额！请检查 config.py。")
        return

    # 打印当前可用资金 (假设你需要看 USD 余额)
    usd_free = balance.get("SpotWallet", {}).get("USD", {}).get("Free", "未知")
    print(f"✅ 连接成功！当前账户可用资金: ${usd_free}")
    print("-" * 30)

    # 2. 进入主循环
    while True:
        try:
            # 获取最新价格
            price = get_ticker(SYMBOL)

            if price is None:
                print(f"[{time.strftime('%H:%M:%S')}] 获取价格失败，稍后重试...")
                time.sleep(5)
                continue

            print(f"[{time.strftime('%H:%M:%S')}] 当前 {SYMBOL} 价格: ${price}")

            # ----------------------------------------------------
            # ⬇️ 这里写你的交易逻辑 ⬇️
            # 这只是一个极其简单的测试逻辑，实盘前一定要换成你自己的策略！

            if price < 60000:
                print(f"📉 价格低于 60000，触发买入 {TRADE_QTY} {SYMBOL}！")
                # 发送市价买单 (MARKET)
                result = place_order(SYMBOL, "BUY", TRADE_QTY, order_type="MARKET")
                print(f"订单结果: {result}")
                time.sleep(60)  # 买完冷却 60 秒

            elif price > 65000:
                print(f"📈 价格高于 65000，触发卖出 {TRADE_QTY} {SYMBOL}！")
                # 发送市价卖单 (MARKET)
                result = place_order(SYMBOL, "SELL", TRADE_QTY, order_type="MARKET")
                print(f"订单结果: {result}")
                time.sleep(60)  # 卖完冷却 60 秒

            # ⬆️ 你的交易逻辑结束 ⬆️
            # ----------------------------------------------------

            # 休息 30 秒，防止请求过频被封
            time.sleep(30)

        except Exception as e:
            print(f"策略运行异常: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_strategy()
