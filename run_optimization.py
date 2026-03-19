# run_optimization.py
import pandas as pd
import numpy as np
import glob
import os
import itertools
from tqdm import tqdm

# ================= 调参范围配置 =================
# 在这里修改你想测试的参数范围
PARAM_GRID = {
    "fast_window": [5, 10, 15],
    "slow_window": [30, 50, 80],
    "min_score": [0.50, 0.55, 0.60],
    "cooldown_periods": [2, 3, 5]
}

# 固定参数
FIXED_PARAMS = {
    "momentum_window": 20,
    "volatility_window": 20,
    "volume_ma_window": 20,
    "weights": {"trend": 0.4, "momentum": 0.4, "volatility": 0.1, "volume": 0.1},
    "thresholds": {
        "sell_score": 0.35,
        "max_volatility": 0.05,
        "min_volume_ratio": 1.2
    },
    "trade": {
        "max_positions": 1,
        "trade_percent": 0.95,
        "fee": 0.001,
        "slippage": 0.0005
    },
    "data_interval": "1h" # 确保你下载了 1h 数据
}
# ================================================

def load_market_data(data_dir="data", interval="1h"):
    pattern = os.path.join(data_dir, f"*-{interval}-*.csv")
    files = glob.glob(pattern)
    if not files:
        print(f"❌ 未找到 {interval} 数据。请先运行下载脚本。")
        return None, None
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, index_col='open_time')
            df.index = pd.to_datetime(df.index)
            fname = os.path.basename(f)
            parts = fname.replace('.csv', '').split('-')
            if len(parts) >= 3:
                df['symbol'] = parts[0]
                dfs.append(df)
        except: continue
    
    if not dfs: return None, None
    full = pd.concat(dfs).sort_index()
    close_pivot = full.pivot_table(index=full.index, columns='symbol', values='close')
    vol_pivot = full.pivot_table(index=full.index, columns='symbol', values='volume') if 'volume' in full.columns else None
    if vol_pivot is None: vol_pivot = pd.DataFrame(1.0, index=close_pivot.index, columns=close_pivot.columns)
    
    return close_pivot, vol_pivot

def calculate_scores(close_df, vol_df, params):
    # 复制自 backtest_m_a_fixed.py 的逻辑
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
    vol_score = np.where(vol_ratio > p["thresholds"]["max_volatility"], 0, np.clip(1 - (vol_ratio / p["thresholds"]["max_volatility"]), 0, 1))
    
    vol_score_factor = 0.5 # 简化
    
    w = p["weights"]
    total = (trend_score * w["trend"] + momentum_score * w["momentum"] + vol_score * w["volatility"] + vol_score_factor * w["volume"])
    return total

def run_single_backtest(params, close_df, vol_df):
    capital = 1000000
    holdings = {}
    cooldowns = {}
    
    scores = calculate_scores(close_df, vol_df, params)
    windows = [params["fast_window"], params["slow_window"], params["momentum_window"], params["volatility_window"]]
    start_idx = max(windows) + max(params["trade"].get("cooldown_periods", 0), 5)
    
    if start_idx >= len(close_df): return -999, 0
    
    for t in range(start_idx, len(close_df)):
        curr_scores = scores.iloc[t]
        curr_prices = close_df.iloc[t]
        
        # Cooldown
        for sym in list(cooldowns.keys()):
            cooldowns[sym] -= 1
            if cooldowns[sym] <= 0: del cooldowns[sym]
        
        # Sell
        to_sell = [sym for sym, qty in list(holdings.items()) if sym in curr_scores.index and curr_scores[sym] < params["thresholds"]["sell_score"]]
        for sym in to_sell:
            qty = holdings.pop(sym)
            capital += qty * curr_prices[sym] * (1 - params["trade"]["fee"] - params["trade"]["slippage"])
            cooldowns[sym] = params["trade"].get("cooldown_periods", 3)
        
        # Buy
        if len(holdings) < params["trade"]["max_positions"]:
            valid = curr_scores[curr_scores >= params["thresholds"]["min_score"]]
            valid = valid.drop(labels=list(holdings.keys()), errors='ignore').drop(labels=list(cooldowns.keys()), errors='ignore')
            if not valid.empty:
                best_sym = valid.idxmax()
                price = curr_prices[best_sym]
                qty = (capital * params["trade"]["trade_percent"]) / price
                cost = qty * price * (1 + params["trade"]["fee"] + params["trade"]["slippage"])
                if cost <= capital and qty * price > 10:
                    capital -= cost
                    holdings[best_sym] = qty
        
        # Calc Value (简化：只记录最后一步)
        if t == len(close_df) - 1:
            total_val = capital
            for sym, qty in holdings.items():
                if sym in curr_prices.index: total_val += qty * curr_prices[sym]
            return (total_val - 1000000) / 1000000, len(holdings) # 返回回报率
            
    return 0, 0

def main():
    print("🔍 开始参数优化搜索...")
    close_df, vol_df = load_market_data(interval=FIXED_PARAMS["data_interval"])
    if close_df is None: return
    
    keys, values = zip(*PARAM_GRID.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"共需测试 {len(combinations)} 种参数组合。")
    
    best_ret = -999
    best_params = None
    results = []
    
    for combo in tqdm(combinations, desc="Optimizing"):
        p = FIXED_PARAMS.copy()
        p.update(combo)
        # 处理嵌套字典更新
        if "min_score" in combo:
            p["thresholds"]["min_score"] = combo["min_score"]
        
        ret, _ = run_single_backtest(p, close_df, vol_df)
        results.append((ret, p))
        
        if ret > best_ret:
            best_ret = ret
            best_params = p
    
    print("\n" + "="*50)
    print("🏆 最佳参数结果")
    print("="*50)
    print(f"最大回报率: {best_ret:.2%}")
    print(f"最佳参数配置:")
    for k, v in best_params.items():
        if isinstance(v, dict):
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v}")
    print("="*50)
    
    # 保存结果到 CSV
    res_df = []
    for r, p in results:
        row = {"return": r}
        row.update(p)
        # 展平 nested dict
        if "thresholds" in row:
            for kk, vv in row["thresholds"].items():
                row[f"thresh_{kk}"] = vv
            del row["thresholds"]
        res_df.append(row)
    
    pd.DataFrame(res_df).to_csv("optimization_results.csv", index=False)
    print("📄 详细结果已保存至 optimization_results.csv")

if __name__ == "__main__":
    main()