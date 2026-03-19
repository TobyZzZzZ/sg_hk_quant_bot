# download_data_lite.py
import requests
import pandas as pd
import os
import time
from tqdm import tqdm
from datetime import datetime, timedelta

# ================= 配置区域 =================
DATA_DIR = "data"
# Top 20 主流币种
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "TRXUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "SHIBUSDT", "BCHUSDT", "UNIUSDT",
    "ATOMUSDT", "LINKUSDT", "ETCUSDT", "XLMUSDT", "NEARUSDT"
]

# 精简计划：(间隔, 回溯月数)
# 15m: 半年, 1h: 2年, 4h/1d: 5年
DOWNLOAD_PLAN = [
    ("15m", 6),
    ("1h", 24),
    ("4h", 60),
    ("1d", 60)
]

BASE_URL = "https://api.binance.com/api/v3/klines"
TIMEOUT_PER_FILE = 30
# ===========================================

def get_month_ranges(months_back):
    ranges = []
    now = datetime.now()
    for i in range(months_back):
        if now.month - i <= 0:
            target_year = now.year - 1 + (now.month - i) // 12
            target_month = (now.month - i) % 12
            if target_month == 0: target_month = 12
        else:
            target_year = now.year
            target_month = now.month - i
        
        start_date = datetime(target_year, target_month, 1)
        end_date = datetime(target_year, target_month, 1) + timedelta(days=32)
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
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return False, "Exists"

    params = {
        "symbol": symbol, "interval": interval,
        "startTime": start_time, "endTime": end_time, "limit": 1000
    }
    
    all_data = []
    try:
        while True:
            resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT_PER_FILE)
            if resp.status_code != 200: return False, f"Error {resp.status_code}"
            data = resp.json()
            if not data: break
            all_data.extend(data)
            params["startTime"] = data[-1][0] + 1
            if len(data) < 1000: break
            time.sleep(0.1)
        
        if not all_data: return False, "No Data"

        columns = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        df = pd.DataFrame(all_data, columns=columns)
        # 只保留需要的列并转换时间
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(filepath)
        return True, f"Saved ({len(df)} rows)"

    except Exception as e:
        return False, str(e)

def main():
    print("🚀 启动 Lite 下载器 (精简版)...")
    print(f"💾 目标: Top 20 币种, 15m/1h/4h/1d")
    print("⚠️ 预计总量: ~10-15 GB")
    print("-" * 50)
    
    total_tasks = []
    for interval, months in DOWNLOAD_PLAN:
        ranges = get_month_ranges(months)
        for symbol in SYMBOLS:
            for r in ranges:
                total_tasks.append({
                    "symbol": symbol, "interval": interval,
                    "start": r["start"], "end": r["end"], "label": r["label"]
                })
    
    print(f"📋 共 {len(total_tasks)} 个任务。自动跳过已存在文件。")
    
    success_count = skip_count = fail_count = 0
    
    for task in tqdm(total_tasks, desc="Downloading"):
        status, msg = fetch_and_save(
            task["symbol"], task["interval"], 
            task["start"], task["end"], task["label"]
        )
        if status: success_count += 1
        elif msg == "Exists": skip_count += 1
        else: fail_count += 1
        time.sleep(0.2)

    print("\n" + "="*50)
    print(f"✅ 新增: {success_count} | ⏭️ 跳过: {skip_count} | ❌ 失败: {fail_count}")
    print("="*50)

if __name__ == "__main__":
    main()