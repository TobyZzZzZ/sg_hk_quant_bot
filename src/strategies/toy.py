# main.py
import argparse
import time
from src.api.roostoo import check_server_time, get_balance, get_ticker, place_order

# --- 默认参数 ---
DEFAULT_SYMBOL = "BTC/USD"
DEFAULT_TRADE_QTY = 0.01
DEFAULT_FAST_WINDOW = 10
DEFAULT_SLOW_WINDOW = 50
DEFAULT_CHECK_INTERVAL = 30

# --- 状态维护 ---
price_history = []      # 存储历史价格
current_position = None # 当前持仓状态: 'BUY' (持有), 'SELL' (空仓), None (初始)

def calculate_ma(data, window):
    """计算移动平均线"""
    if len(data) < window:
        return None
    return sum(data[-window:]) / window

def parse_args(args_list=None):
    parser = argparse.ArgumentParser(description="Toy Strategy", add_help=False)
    parser.add_argument("--symbol", type=str, default=DEFAULT_SYMBOL)
    parser.add_argument("--qty", type=float, default=DEFAULT_TRADE_QTY)
    parser.add_argument("--fast_window", type=int, default=DEFAULT_FAST_WINDOW)
    parser.add_argument("--slow_window", type=int, default=DEFAULT_SLOW_WINDOW)
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL)
    
    args, _ = parser.parse_known_args(args_list)
    return args

def run_strategy(args_list=None):
    global price_history, current_position
    
    args = parse_args(args_list)
    SYMBOL = args.symbol
    TRADE_QTY = args.qty
    FAST_WINDOW = args.fast_window
    SLOW_WINDOW = args.slow_window
    CHECK_INTERVAL = args.interval

    print("🤖 双均线策略机器人启动中...")
    print(f"--> 交易对: {SYMBOL}, 数量: {TRADE_QTY}")
    print(f"--> 快线周期: {FAST_WINDOW}, 慢线周期: {SLOW_WINDOW}")

    # 1. 初始化检查
    if not check_server_time():
        print("❌ 无法连接到服务器。")
        return

    balance = get_balance()
    if not balance or not balance.get("Success"):
        print("❌ API 密钥错误或无权限。")
        return
    
    usd_free = balance.get("SpotWallet", {}).get("USD", {}).get("Free", 0)
    print(f"✅ 连接成功！可用资金: ${usd_free}")
    print("-" * 30)

    # 2. 预热数据 (为了不让一启动就乱交易，先收集 enough 数据)
    print(f"⏳ 正在收集初始数据 ({SLOW_WINDOW} 个点)...")
    while len(price_history) < SLOW_WINDOW:
        price = get_ticker(SYMBOL)
        if price:
            price_history.append(price)
            print(f"已收集: {len(price_history)}/{SLOW_WINDOW} (当前价: {price})")
        else:
            print("获取价格失败，重试...")
        time.sleep(CHECK_INTERVAL)
    
    print("✅ 数据收集完成，策略正式运行！\n")

    # 3. 主循环
    while True:
        try:
            # 获取最新价格
            current_price = get_ticker(SYMBOL)
            
            if current_price is None:
                print(f"[{time.strftime('%H:%M:%S')}] 获取价格失败，跳过本轮。")
                time.sleep(CHECK_INTERVAL)
                continue

            # 更新历史数据
            price_history.append(current_price)
            # 保持列表长度不超过慢线周期，节省内存
            if len(price_history) > SLOW_WINDOW:
                price_history.pop(0)

            # 计算均线
            fast_ma = calculate_ma(price_history, FAST_WINDOW)
            slow_ma = calculate_ma(price_history, SLOW_WINDOW)

            if fast_ma is None or slow_ma is None:
                time.sleep(CHECK_INTERVAL)
                continue

            print(f"[{time.strftime('%H:%M:%S')}] 价格: ${current_price:.2f} | 快线: ${fast_ma:.2f} | 慢线: ${slow_ma:.2f}")

            # --- 核心交易逻辑 ---
            
            # 情况 A: 金叉 (快线 > 慢线) -> 应该买入
            if fast_ma > slow_ma:
                if current_position != 'BUY':
                    print(f"📈 触发金叉！快线({fast_ma:.2f}) 上穿 慢线({slow_ma:.2f}) -> 执行买入")
                    result = place_order(SYMBOL, "BUY", TRADE_QTY, order_type="MARKET")
                    if result and result.get("Success"):
                        current_position = 'BUY'
                        print("✅ 买入成功，当前持仓: BTC")
                    else:
                        print(f"❌ 买入失败: {result}")
                else:
                    print("💤 已持有 BTC，继续观察...")

            # 情况 B: 死叉 (快线 < 慢线) -> 应该卖出
            elif fast_ma < slow_ma:
                if current_position != 'SELL': # 注意：这里逻辑简化，假设空仓就是 SELL 状态
                    # 实际上我们需要知道是否持有币。
                    # 简单处理：如果上次操作是买入，现在就要卖出。
                    # 为了严谨，我们可以检查余额，但这里用状态机模拟
                    if current_position == 'BUY': 
                        print(f"📉 触发死叉！快线({fast_ma:.2f}) 下穿 慢线({slow_ma:.2f}) -> 执行卖出")
                        result = place_order(SYMBOL, "SELL", TRADE_QTY, order_type="MARKET")
                        if result and result.get("Success"):
                            current_position = 'SELL' # 代表空仓
                            print("✅ 卖出成功，当前持仓: USD")
                        else:
                            print(f"❌ 卖出失败: {result}")
                    # 如果本来就是 SELL (空仓)，则什么都不做
                else:
                    print("💤 已空仓，继续观察...")
            
            # 分隔线
            print("-" * 30)
            
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"⚠️ 策略运行异常: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_strategy()
