# main_strategy.py
import time
import json
import os
import argparse
import numpy as np
from roostoo_api import check_server_time, get_balance, get_ticker, place_order

# ================= 默认参数 =================
DEFAULT_PARAMS = {
    "fast_window": 10,
    "slow_window": 50,
    "momentum_window": 20,
    "volatility_window": 20,
    "volume_ma_window": 20,
    "weights": {"trend": 0.4, "momentum": 0.4, "volatility": 0.1, "volume": 0.1},
    "thresholds": {
        "min_score": 0.55,      # 买入最低分
        "sell_score": 0.35,     # 卖出最高分
        "max_volatility": 0.05,
        "min_volume_ratio": 1.2
    },
    "trade": {
        "max_positions": 1,
        "trade_percent": 0.95,
        "cooldown_periods": 3,  # 卖出后冷却几轮
        "check_interval": 60    # 默认 60 秒检查一次 (可根据需要调整)
    }
}

SYMBOLS_FILE = "symbols.json"
DEFAULT_SYMBOLS = [
    "BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD",
    "ADA/USD", "DOGE/USD", "AVAX/USD", "TRX/USD", "DOT/USD",
    "MATIC/USD", "LTC/USD", "SHIB/USD", "BCH/USD", "UNI/USD",
    "ATOM/USD", "LINK/USD", "ETC/USD", "XLM/USD", "NEAR/USD"
]

# 全局状态
price_history = {}
volume_history = {} # 占位，若 API 无 volume 则忽略该因子
current_holdings = {}
cooldowns = {} # {symbol: remaining_count}

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-Factor Trading Bot")
    # 简单参数
    parser.add_argument("--fast_window", type=int, default=DEFAULT_PARAMS["fast_window"])
    parser.add_argument("--slow_window", type=int, default=DEFAULT_PARAMS["slow_window"])
    parser.add_argument("--momentum_window", type=int, default=DEFAULT_PARAMS["momentum_window"])
    parser.add_argument("--min_score", type=float, default=DEFAULT_PARAMS["thresholds"]["min_score"])
    parser.add_argument("--max_positions", type=int, default=DEFAULT_PARAMS["trade"]["max_positions"])
    parser.add_argument("--interval", type=int, default=DEFAULT_PARAMS["trade"]["check_interval"], help="Check interval in seconds")
    parser.add_argument("--cooldown", type=int, default=DEFAULT_PARAMS["trade"]["cooldown_periods"])
    
    # 权重参数 (简化为字符串解析或固定，这里为了脚本简单暂不开放所有权重命令行，可在代码改)
    args = parser.parse_args()
    
    # 合并参数
    params = DEFAULT_PARAMS.copy()
    params["fast_window"] = args.fast_window
    params["slow_window"] = args.slow_window
    params["momentum_window"] = args.momentum_window
    params["thresholds"]["min_score"] = args.min_score
    params["trade"]["max_positions"] = args.max_positions
    params["trade"]["check_interval"] = args.interval
    params["trade"]["cooldown_periods"] = args.cooldown
    
    return params

def load_symbols():
    if os.path.exists(SYMBOLS_FILE):
        try:
            with open(SYMBOLS_FILE, "r") as f:
                symbols = json.load(f)
            return symbols[:20]
        except:
            pass
    return DEFAULT_SYMBOLS[:20]

def calculate_ma(data, window):
    if len(data) < window: return None
    return sum(data[-window:]) / window

def calculate_std(data, window):
    if len(data) < window: return 0
    return np.std(data[-window:])

def get_factor_scores(symbol, prices, params):
    p = params
    
    # 1. Trend
    fast_ma = calculate_ma(prices, p["fast_window"])
    slow_ma = calculate_ma(prices, p["slow_window"])
    if not fast_ma or not slow_ma or slow_ma == 0:
        trend_score = 0.5
    else:
        bias = (fast_ma - slow_ma) / slow_ma
        trend_score = max(0, min(1, bias * 20 + 0.5))
    
    # 2. Momentum
    if len(prices) < p["momentum_window"]:
        momentum_score = 0.5
    else:
        mom = (prices[-1] - prices[-p["momentum_window"]]) / prices[-p["momentum_window"]]
        momentum_score = max(0, min(1, mom * 10 + 0.5))
    
    # 3. Volatility
    if len(prices) < p["volatility_window"]:
        vol_score = 0.5
    else:
        std_dev = calculate_std(prices, p["volatility_window"])
        avg_p = calculate_ma(prices, p["volatility_window"])
        vol_ratio = std_dev / avg_p if avg_p else 0
        if vol_ratio > p["thresholds"]["max_volatility"]:
            vol_score = 0
        else:
            vol_score = max(0, 1 - (vol_ratio / p["thresholds"]["max_volatility"]))
    
    # 4. Volume (简化：若无真实 volume 数据，此项恒定为 0.5，不影响大局)
    volume_score = 0.5 
    
    # Weighted Sum
    w = p["weights"]
    total = (trend_score * w["trend"] + momentum_score * w["momentum"] + 
             vol_score * w["volatility"] + volume_score * w["volume"])
    
    return max(0, min(1, total))

def run_strategy():
    global price_history, current_holdings, cooldowns
    
    params = parse_args()
    print("🚀 [多因子策略] 启动...")
    print(f"   参数: MA{params['fast_window']}/{params['slow_window']} | MinScore: {params['thresholds']['min_score']}")
    print(f"   冷却期: {params['trade']['cooldown_periods']} 轮 | 检查间隔: {params['trade']['check_interval']}s")
    
    if not check_server_time():
        print("❌ 服务器连接失败")
        return
    
    balance_data = get_balance()
    if not balance_data or not balance_data.get("Success"):
        print("❌ 获取余额失败")
        return
    
    usd_free = float(balance_data.get("SpotWallet", {}).get("USD", {}).get("Free", 0))
    print(f"💰 初始资金: ${usd_free:,.2f}")
    
    symbols = load_symbols()
    print(f"📋 监控 {len(symbols)} 个币种")
    
    # 预热
    max_win = max(params["fast_window"], params["slow_window"], params["momentum_window"])
    print(f"⏳ 预热数据 ({max_win} 点)...")
    for sym in symbols:
        price_history[sym] = []
    
    for i in range(max_win):
        for sym in symbols:
            p = get_ticker(sym)
            if p: price_history[sym].append(p)
        time.sleep(params["trade"]["check_interval"])
        if i % 10 == 0: print(f"   {i}/{max_win}")
    
    print("✅ 预热完成，开始交易循环...\n")
    
    while True:
        try:
            # 刷新余额
            bal = get_balance()
            if bal and bal.get("Success"):
                usd_free = float(bal.get("SpotWallet", {}).get("USD", {}).get("Free", 0))
            
            candidates = []
            
            # 更新冷却计数
            for sym in list(cooldowns.keys()):
                cooldowns[sym] -= 1
                if cooldowns[sym] <= 0:
                    del cooldowns[sym]
            
            for sym in symbols:
                price = get_ticker(sym)
                if not price: continue
                
                history = price_history[sym]
                history.append(price)
                if len(history) > max_win + 10: # 留一点缓冲
                    history.pop(0)
                
                if len(history) < max_win:
                    continue
                
                score = get_factor_scores(sym, history, params)
                
                # --- 卖出逻辑 ---
                if sym in current_holdings:
                    if score < params["thresholds"]["sell_score"]:
                        qty = current_holdings[sym]['qty']
                        print(f"📉 [{sym}] 分数({score:.2f})低于卖出阈值，执行卖出")
                        res = place_order(sym, "SELL", qty, order_type="MARKET")
                        if res and res.get("Success"):
                            del current_holdings[sym]
                            cooldowns[sym] = params["trade"]["cooldown_periods"]
                            print(f"  ✅ 卖出成功，进入冷却期")
                        else:
                            print(f"  ❌ 卖出失败: {res}")
                    continue
                
                # --- 买入候选 ---
                if sym not in cooldowns and score >= params["thresholds"]["min_score"]:
                    candidates.append({'symbol': sym, 'score': score, 'price': price})
            
            # --- 执行买入 ---
            if candidates and usd_free > 50 and len(current_holdings) < params["trade"]["max_positions"]:
                candidates.sort(key=lambda x: x['score'], reverse=True)
                best = candidates[0]
                
                # 简单的单仓位逻辑：如果有多个位置，可以扩展此处逻辑
                # 这里假设 MAX_POSITIONS=1，直接全仓买入最强的
                alloc = usd_free * params["trade"]["trade_percent"]
                qty = alloc / best['price']
                
                if qty * best['price'] > 10:
                    print(f"📈 [{best['symbol']}] 最高分({best['score']:.2f})，执行买入")
                    res = place_order(best['symbol'], "BUY", qty, order_type="MARKET")
                    if res and res.get("Success"):
                        current_holdings[best['symbol']] = {'qty': qty, 'entry': best['price']}
                        print(f"  ✅ 买入成功")
                    else:
                        print(f"  ❌ 买入失败: {res}")
            
            # 状态打印
            if int(time.time()) % (params["trade"]["check_interval"] * 5) < params["trade"]["check_interval"]:
                hold_list = list(current_holdings.keys())
                cool_list = list(cooldowns.keys())
                print(f"[{time.strftime('%H:%M:%S')}] 持仓: {hold_list} | 冷却: {cool_list} | 资金: ${usd_free:.1f}")
            
            time.sleep(params["trade"]["check_interval"])
            
        except Exception as e:
            print(f"⚠️ 异常: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_strategy()