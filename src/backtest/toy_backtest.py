#https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{YEAR}-{MONTH}.zip
import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt

# ================= 配置区域 =================
DATA_FOLDER = 'data'             # 数据文件夹名称
SYMBOL_PREFIX = 'BTCUSDT-1m'     # 文件名前缀匹配
FAST_WINDOW = 10                 # 快线周期
SLOW_WINDOW = 50                 # 慢线周期
INITIAL_CAPITAL = 50000          # 初始资金 (USD)
TRADE_SIZE_USD = 1000            # 每次交易金额 (USD)，或者你可以改为固定数量 BTC
# ===========================================

def load_data():
    """加载 data 文件夹下所有匹配的 CSV 文件并合并"""
    path_pattern = os.path.join(DATA_FOLDER, f"{SYMBOL_PREFIX}*.csv")
    files = glob.glob(path_pattern)
    
    if not files:
        print(f"❌ 错误：在 '{DATA_FOLDER}' 文件夹下未找到匹配 '{SYMBOL_PREFIX}*.csv' 的文件。")
        print("请确保你已经下载了数据并放对了位置。")
        return None

    print(f"🔍 找到 {len(files)} 个数据文件：{[os.path.basename(f) for f in files]}")
    
    df_list = []
    for file in sorted(files): # 排序确保时间顺序
        # 读取 CSV，币安数据没有表头，需要手动指定列名
        cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
                'taker_buy_quote', 'ignore']
        
        temp_df = pd.read_csv(file, header=None, names=cols)
        df_list.append(temp_df)
        print(f"  ✅ 已加载: {os.path.basename(file)} ({len(temp_df)} 行)")

    # 合并所有数据
    full_df = pd.concat(df_list, ignore_index=True)
    
    # 数据清洗：转换时间戳，设置索引
    full_df['open_time'] = pd.to_datetime(full_df['open_time'], unit='ms')
    full_df.set_index('open_time', inplace=True)
    
    # 确保价格是数字类型
    full_df['close'] = pd.to_numeric(full_df['close'])
    
    # 按时间排序并去重（防止月度数据交接处有重复）
    full_df = full_df.sort_index()
    full_df = full_df[~full_df.index.duplicated(keep='first')]
    
    print(f"✅ 数据准备完成！总行数：{len(full_df)}, 时间范围：{full_df.index[0]} 到 {full_df.index[-1]}")
    return full_df

def run_backtest(df):
    """执行双均线策略回测"""
    print("\n🚀 开始回测...")
    print(f"策略：MA{FAST_WINDOW} (快) vs MA{SLOW_WINDOW} (慢)")
    
    # 1. 计算均线
    df['ma_fast'] = df['close'].rolling(window=FAST_WINDOW).mean()
    df['ma_slow'] = df['close'].rolling(window=SLOW_WINDOW).mean()
    
    # 2. 生成信号
    # 初始化列
    df['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
    
    # 逻辑：当快线上穿慢线 -> 买入 (1)；当快线下穿慢线 -> 卖出 (-1)
    # shift(1) 表示上一根 K 线的状态，用来判断交叉
    df['prev_fast'] = df['ma_fast'].shift(1)
    df['prev_slow'] = df['ma_slow'].shift(1)
    
    # 金叉：当前快>慢 且 之前快<=慢
    df.loc[(df['ma_fast'] > df['ma_slow']) & (df['prev_fast'] <= df['prev_slow']), 'signal'] = 1
    
    # 死叉：当前快<慢 且 之前快>=慢
    df.loc[(df['ma_fast'] < df['ma_slow']) & (df['prev_fast'] >= df['prev_slow']), 'signal'] = -1
    
    # 3. 模拟交易循环
    capital = INITIAL_CAPITAL
    btc_holdings = 0.0
    trades = []
    
    # 记录资金曲线
    portfolio_value = []
    
    print(f"💰 初始资金: ${capital:,.2f}")
    
    # 跳过前 SLOW_WINDOW 行，因为那里均线是 NaN
    for i in range(SLOW_WINDOW, len(df)):
        row = df.iloc[i]
        current_price = row['close']
        signal = row['signal']
        timestamp = row.name
        
        # 执行交易
        if signal == 1 and capital > 0:
            # 买入：用全部可用资金买入 (或者固定金额，这里简化为全仓)
            # 为了更真实，我们可以限制每次只买固定金额，防止一次梭哈
            buy_amount = min(capital, TRADE_SIZE_USD) 
            if buy_amount > 10: # 最小交易额限制
                qty = buy_amount / current_price
                btc_holdings += qty
                capital -= buy_amount
                trades.append({'time': timestamp, 'type': 'BUY', 'price': current_price, 'qty': qty})
                # print(f"[{timestamp}] 🟢 买入: ${buy_amount:.2f} @ ${current_price:.2f}")

        elif signal == -1 and btc_holdings > 0:
            # 卖出：卖出所有持仓
            sell_value = btc_holdings * current_price
            capital += sell_value
            trades.append({'time': timestamp, 'type': 'SELL', 'price': current_price, 'qty': btc_holdings})
            # print(f"[{timestamp}] 🔴 卖出: {btc_holdings:.6f} BTC @ ${current_price:.2f} (得 ${sell_value:.2f})")
            btc_holdings = 0.0
            
        # 记录当前总资产 (现金 + 持仓市值)
        total_value = capital + (btc_holdings * current_price)
        portfolio_value.append({'time': timestamp, 'value': total_value})

    # 最终结算：假设最后如果还持有币，按最后一个价格卖出
    final_price = df.iloc[-1]['close']
    final_capital = capital + (btc_holdings * final_price)
    
    print("\n" + "="*30)
    print("📊 回测结果报告")
    print("="*30)
    print(f"初始资金: ${INITIAL_CAPITAL:,.2f}")
    print(f"最终资产: ${final_capital:,.2f}")
    profit = final_capital - INITIAL_CAPITAL
    profit_pct = (profit / INITIAL_CAPITAL) * 100
    print(f"净利润: ${profit:,.2f} ({profit_pct:.2f}%)")
    print(f"交易次数: {len(trades)}")
    print(f"数据结束时间: {df.index[-1]}")
    print("="*30)

    # 4. 绘图
    plot_results(df, portfolio_value, trades)

def plot_results(df, portfolio_value, trades):
    """绘制价格和资金曲线"""
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # 绘制价格走势 (只画一部分以免太密，或者画全程)
    color = 'tab:blue'
    ax1.set_xlabel('Time')
    ax1.set_ylabel('BTC Price (USD)', color=color)
    ax1.plot(df.index, df['close'], color=color, alpha=0.3, label='BTC Price')
    ax1.plot(df.index, df['ma_fast'], color='orange', linewidth=1, label=f'MA{FAST_WINDOW}')
    ax1.plot(df.index, df['ma_slow'], color='purple', linewidth=1, label=f'MA{SLOW_WINDOW}')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # 标记买卖点
    for trade in trades:
        if trade['type'] == 'BUY':
            ax1.scatter(trade['time'], trade['price'], color='green', marker='^', s=100, zorder=5)
        else:
            ax1.scatter(trade['time'], trade['price'], color='red', marker='v', s=100, zorder=5)

    # 绘制资金曲线 (右轴)
    ax2 = ax1.twinx()
    pv_df = pd.DataFrame(portfolio_value)
    color = 'tab:green'
    ax2.set_ylabel('Portfolio Value (USD)', color=color)
    ax2.plot(pv_df['time'], pv_df['value'], color=color, linewidth=2, label='Portfolio Value')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title(f'Dual MA Strategy Backtest ({FAST_WINDOW}/{SLOW_WINDOW})')
    fig.tight_layout()
    
    # 保存图表
    chart_name = f"backtest_result_{SYMBOL_PREFIX}.png"
    plt.savefig(chart_name)
    print(f"📈 图表已保存为: {chart_name}")
    plt.show()

if __name__ == "__main__":
    # 检查数据文件夹是否存在
    if not os.path.exists(DATA_FOLDER):
        print(f"❌ 错误：找不到 '{DATA_FOLDER}' 文件夹。请先创建它并放入 CSV 文件。")
    else:
        data = load_data()
        if data is not None:
            run_backtest(data)
