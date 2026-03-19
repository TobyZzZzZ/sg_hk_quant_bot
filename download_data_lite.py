# download_data_lite.py
import requests
import pandas as pd
import os
import time
from tqdm import tqdm
from datetime import datetime, timedelta

# ================= 配置区域 =================
DATA_DIR = "data"
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "TRXUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "SHIBUSDT", "BCHUSDT", "UNIUSDT",
    "ATOMUSDT", "LINKUSDT", "ETCUSDT", "XLMUSDT", "NEARUSDT"
]

# 【5年计划】所有周期统一回溯 60 个月 (5年)
DOWNLOAD_PLAN = [
    ("15m", "month", 60),   
    ("1h", "month", 60),    
    ("4h", "month", 60),    
    ("1d", "month", 60)     
]

BASE_URL = "https://api.binance.com/api/v3/klines"
TIMEOUT_PER_FILE = 30
MAX_RETRIES = 3

# Binance API 返回的完整 12 列定义
# 0: Open Time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume,
# 6: Close Time, 7: Quote Asset Volume, 8: Number of Trades,
# 9: Taker Buy Base Asset Volume, 10: Taker Buy Quote Asset Volume, 11: Ignore
BINANCE_COLUMNS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
]

# 我们最终只需要保存的 6 列
TARGET_COLUMNS = ['open_time', 'open', 'high', 'low', 'close', 'volume']
# ===========================================

def get_month_ranges(count_back):
    """生成最近 N 个月的列表"""
    ranges = []
    now = datetime.now()
    
    for i in range(count_back):
        if now.month - i <= 0:
            target_year = now.year - 1 + (now.month - i) // 12
            target_month = (now.month - i) % 12
            if target_month == 0: target_month = 12
        else:
            target_year = now.year
            target_month = now.month - i
        
        start_date = datetime(target_year, target_month, 1)
        end_date = start_date + timedelta(days=32)
        end_date = end_date.replace(day=1)
        
        ranges.append({
            "start": int(start_date.timestamp() * 1000),
            "end": int(end_date.timestamp() * 1000),
            "label": start_date.strftime("%Y-%m")
        })
    return ranges

def fetch_and_save(symbol, interval, start_time, end_time, label):
    filename = f"{symbol}-{interval}-{label}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    
    # 增量检查
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return "skip", "Exists"

    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }
    
    all_data = []
    retry_count = 0
    last_error = ""
    
    while retry_count < MAX_RETRIES:
        try:
            resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT_PER_FILE)
            
            if resp.status_code == 400:
                return "skip", "Invalid params"
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            
            data = resp.json()
            
            if not data:
                return "skip", "No data"
            
            all_data.extend(data)
            
            # 分页逻辑
            if len(data) == 1000:
                params["startTime"] = data[-1][0] + 1
                time.sleep(0.2)
                continue
            else:
                break
                
        except Exception as e:
            last_error = str(e)
            retry_count += 1
            if retry_count == MAX_RETRIES:
                return "fail", last_error
            time.sleep(2)

    if not all_data:
        return "skip", "Empty"

    # 【修复核心】先按 12 列解析，再筛选出需要的 6 列
    df = pd.DataFrame(all_data, columns=BINANCE_COLUMNS)
    
    # 类型转换
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    
    # 只保留目标列
    df = df[TARGET_COLUMNS]
    
    # 设置索引并去重
    df.set_index('open_time', inplace=True)
    df = df[~df.index.duplicated(keep='first')]
    
    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 保存
    df.to_csv(filepath)
    
    return "success", f"{len(df)} rows"

def main():
    print("🚀 启动 5年数据下载器 (修复版)...")
    print(f"💾 目标: Top 20 币种 | 全周期 5 年 (60 个月)")
    print(f"📅 跨度: 15m/1h/4h/1d 均回溯至 2021-03 (约)")
    print(f"⏳ 预计耗时: 3.5 - 5.0 小时")
    print("-" * 70)
    
    total_tasks = []
    for interval, unit, months in DOWNLOAD_PLAN:
        ranges = get_month_ranges(months)
        for symbol in SYMBOLS:
            for r in ranges:
                total_tasks.append({
                    "symbol": symbol, "interval": interval,
                    "start": r["start"], "end": r["end"], 
                    "label": r["label"]
                })
    
    print(f"📋 任务总数: {len(total_tasks)} 个文件")
    print("开始下载... (观察上方实时统计)\n")
    
    stats = {"success": 0, "skip": 0, "fail": 0}
    
    with tqdm(total=len(total_tasks), desc="Init", unit="file") as pbar:
        for task in total_tasks:
            status, msg = fetch_and_save(
                task["symbol"], task["interval"], 
                task["start"], task["end"], 
                task["label"]
            )
            
            if status == "success":
                stats["success"] += 1
            elif status == "skip":
                stats["skip"] += 1
            else:
                stats["fail"] += 1
                print(f"\n❌ [FAIL] {task['symbol']}-{task['interval']}-{task['label']}: {msg}")
            
            # 实时更新进度条描述
            pbar.set_description(f"✅{stats['success']} | ⏭️{stats['skip']} | ❌{stats['fail']}")
            pbar.update(1)
            
            # 延时控制
            time.sleep(0.15) 

    print("\n" + "="*70)
    print("🎉 5年数据下载完成")
    print("="*70)
    print(f"✅ 成功下载 : {stats['success']} 个新文件")
    print(f"⏭️  智能跳过 : {stats['skip']} 个 (已存在)")
    print(f"❌ 真实失败 : {stats['fail']} 个")
    print("="*70)
    
    if stats['fail'] == 0:
        print("🌟 完美！数据准备就绪，可以开始回测了！")
    else:
        print("💡 少量失败属正常现象（如币种早期无数据）。")

if __name__ == "__main__":
    main()
