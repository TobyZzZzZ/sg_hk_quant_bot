# backtest_m_a_fixed.py
import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
from tqdm import tqdm

# ================= 策略参数 (可调优) =================
STRATEGY_PARAMS = {
    "data_interval": "1h",          # 【关键】使用 1小时 数据，避开 1m 噪音
    "fast_window": 10,
    "slow_window": 50,
    "momentum_window": 20,
    "volatility_window": 20,
    "volume_ma_window": 20,
    
    "weights": {"trend": 0.4, "momentum": 0.4, "volatility": 0.1, "volume": 0.1},
    
    "thresholds": {
        "min_score": 0.55,          # 提高阈值，宁缺毋滥
        "max_volatility": 0.05,     
        "min_volume_ratio": 1.2
    },
    
    "trade": {
        "max_positions": 1,
        "trade_percent": 0.95,
        "fee": 0.001,               # 0.1% Taker
        "slippage": 0.0005,         # 【新增】0.05% 滑点模拟
        "cooldown_periods": 3       # 【新增】卖出后冷却 3 个周期 (3小时) 才能重买该币
    }
}
# ============================================================

def load_market_data(data_dir="data", interval="1h"):
    """加载指定周期的数据"""
    pattern = os.path.join(data_dir, f"*-{interval}-*.csv")
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ 未找到 {interval} 数据文件。请运行下载脚本。")
        print(f"   查找模式: {pattern}")
        return None
    
    print(f"🔍 找到 {len(files)} 个 {interval} 数据文件...")
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, index_col='open_time')
            df.index = pd.to_datetime(df.index)
            fname = os.path.basename(f)
            parts = fname.replace('.csv', '').split('-')
            if len(parts) >= 3:
                symbol = parts[0]
                df['symbol'] = symbol
                dfs.append(df)
        except Exception as e:
            continue
    
    if not dfs: return None
    full = pd.concat(dfs).sort_index()
    
    close_pivot = full.pivot_table(index=full.index, columns='symbol', values='close')
    if 'volume' in full.columns:
        vol_pivot = full.pivot_table(index=full.index, columns='symbol', values='volume')
    else:
        vol_pivot = pd.DataFrame(1.0, index=close_pivot.index, columns=close_pivot.columns)
        
    print(f"✅ 数据加载完成。范围: {close_pivot.index[0]} 到 {close_pivot.index[-1]}")
    print(f"   币种数: {len(close_pivot.columns)}")
    return close_pivot, vol_pivot

def calculate_scores(close_df, vol_df, params):
    p = params
    scores = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
    
    ma_fast = close_df.rolling(p["fast_window"]).mean()
    ma_slow = close_df.rolling(p["slow_window"]).mean()
    bias = (ma_fast - ma_slow) / ma_slow
    trend_score = np.clip(bias * 20 + 0.5, 0, 1)
    
    mom = close_df.pct_change(periods=p["momentum_window"])
    momentum_score = np.clip(mom * 10 + 0.5, 0, 1)
    
    std_dev = close_df.rolling(p["volatility_window"]).std()
    avg_p = close_df.rolling(p["volatility_window"]).mean()
    vol_ratio = std_dev / avg_p
    vol_score = np.where(vol_ratio > p["thresholds"]["max_volatility"], 
                         0, 
                         np.clip(1 - (vol_ratio / p["thresholds"]["max_volatility"]), 0, 1))
    
    avg_vol = vol_df.rolling(p["volume_ma_window"]).mean()
    vol_rat_val = vol_df / avg_vol
    vol_score_factor = np.where(vol_rat_val < p["thresholds"]["min_volume_ratio"],
                                0.3,
                                np.clip(0.5 + (vol_rat_val - 1) * 0.2, 0, 1))
    
    w = p["weights"]
    total = (trend_score * w["trend"] + 
             momentum_score * w["momentum"] + 
             vol_score * w["volatility"] + 
             vol_score_factor * w["volume"])
    
    return total

def run_backtest(params, close_df, vol_df):
    capital = 1000000
    holdings = {} # {sym: qty}
    cooldowns = {} # {sym: remaining_periods}
    portfolio_values = []
    trade_count = 0
    
    scores = calculate_scores(close_df, vol_df, params)
    
    # 确定起始点 (取最大窗口)
    windows = [params["fast_window"], params["slow_window"], params["momentum_window"], params["volatility_window"]]
    start_idx = max(windows) + params["trade"]["cooldown_periods"]
    
    print(f"⏳ 开始回测 ({len(close_df) - start_idx} 步)...")
    
    for t in tqdm(range(start_idx, len(close_df)), disable=False):
        idx = close_df.index[t]
        curr_scores = scores.iloc[t]
        curr_prices = close_df.iloc[t]
        
        # 1. 处理冷却期
        for sym in list(cooldowns.keys()):
            cooldowns[sym] -= 1
            if cooldowns[sym] <= 0:
                del cooldowns[sym]
        
        # 2. 检查卖出 (得分低于阈值 或 趋势反转)
        to_sell = []
        for sym, qty in list(holdings.items()):
            if sym in curr_scores.index:
                # 简单的卖出逻辑：分数低于 0.3 或者 死叉 (fast < slow)
                # 这里简化为分数过低
                if curr_scores[sym] < 0.35: 
                    to_sell.append(sym)
        
        for sym in to_sell:
            qty = holdings.pop(sym)
            price = curr_prices[sym]
            # 卖出费用 + 滑点
            sell_value = qty * price * (1 - params["trade"]["fee"] - params["trade"]["slippage"])
            capital += sell_value
            cooldowns[sym] = params["trade"]["cooldown_periods"] # 进入冷却
            trade_count += 1
        
        # 3. 检查买入
        if len(holdings) < params["trade"]["max_positions"]:
            # 筛选：分数够高 + 不在冷却期 + 不在持仓
            valid = curr_scores[curr_scores >= params["thresholds"]["min_score"]]
            valid = valid.drop(labels=list(holdings.keys()), errors='ignore')
            valid = valid.drop(labels=list(cooldowns.keys()), errors='ignore')
            
            if not valid.empty:
                best_sym = valid.idxmax()
                best_price = curr_prices[best_sym]
                
                alloc = capital * params["trade"]["trade_percent"]
                qty = alloc / best_price
                
                # 买入费用 + 滑点
                cost = qty * best_price * (1 + params["trade"]["fee"] + params["trade"]["slippage"])
                
                if cost <= capital and qty * best_price > 10: # 最小交易额
                    capital -= cost
                    holdings[best_sym] = qty
                    trade_count += 1
        
        # 计算总值
        total_val = capital
        for sym, qty in holdings.items():
            if sym in curr_prices.index:
                total_val += qty * curr_prices[sym]
        portfolio_values.append(total_val)
    
    final = portfolio_values[-1]
    ret = (final - 1000000) / 1000000
    
    print("\n" + "="*40)
    print("📊 回测结果 (含手续费 + 滑点 + 冷却)")
    print("="*40)
    print(f"初始: $1,000,000 | 最终: ${final:,.2f}")
    print(f"回报率: {ret:.2%}")
    print(f"总交易次数: {trade_count}")
    print(f"平均每次交易成本估算: ${(1000000-final)/max(trade_count, 1):.2f}")
    print("="*40)
    
    # 绘图
    plt.figure(figsize=(14, 7))
    plt.plot(portfolio_values, label='Portfolio Value', color='green')
    plt.title(f"Multi-Factor Strategy ({params['data_interval']}) - Return: {ret:.2%}")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig("backtest_result_fixed.png")
    print("📈 图表保存为 backtest_result_fixed.png")
    plt.show()
    
    return ret

if __name__ == "__main__":
    interval = STRATEGY_PARAMS["data_interval"]
    data = load_market_data(interval=interval)
    if data:
        close_df, vol_df = data
        run_backtest(STRATEGY_PARAMS, close_df, vol_df)