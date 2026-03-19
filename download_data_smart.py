# download_data_smart.py
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

# 下载计划：(间隔, 回溯月数)
# 15m: 1年 (12个月), 1h: 3年 (36个月)
DOWNLOAD_PLAN = [
    ("15m", 12),
    ("1h", 36)
]

BASE_URL = "https://api.binance.com/api/v3/klines"
TIMEOUT_PER_FILE = 30 # 秒
# ===========================================

def get_month_ranges(months_back):
    """生成过去 N 个月的 (start_time, end_time) 列表"""
    ranges = []
    now = datetime.now()
    # 从当前月份往前推
    for i in range(months_back):
        # 计算目标月份的第一天
        if now.month - i <= 0:
            target_year = now.year - 1 + (now.month - i) // 12
            target_month = (now.month - i) % 12
            if target_month == 0: target_month = 12
        else:
            target_year = now.year
            target_month = now.month - i
        
        start_date = datetime(target_year, target_month, 1)
        end_date = datetime(target_year, target_month, 1) + timedelta(days=32)
        end_date = end_date.replace(day=1) # 下个月1号
        
        ranges.append({
            "start": int(start_date.timestamp() * 1000),
            "end": int(end_date.timestamp() * 1000),
            "label": start_date.strftime("%Y-%m")
        })
    return ranges

def fetch_and_save(symbol, interval, start_time, end_time, label):
    filename = f"{symbol}-{interval}-{label}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    
    # 增量检查：如果文件存在且大于1KB，跳过
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return False, "Exists"

    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }
    
    all_data = []
    try:
        while True:
            resp = requests.get(BASE_URL, params=params, timeout=TIMEOUT_PER_FILE)
            if resp.status_code != 200:
                return False, f"Error {resp.status_code}"
            
            data = resp.json()
            if not data:
                break
            
            all_data.extend(data)
            # 更新起始时间
            params["startTime"] = data[-1][0] + 1
            
            if len(data) < 1000:
                break
            
            # 防止请求过快
            time.sleep(0.2) 
            
        if not all_data:
            return False, "No Data"

        # 处理数据
        columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 
                   'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
                   'taker_buy_quote', 'ignore']
        df = pd.DataFrame(all_data, columns=columns)
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        
        # 确保目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(filepath)
        return True, f"Saved ({len(df)} rows)"

    except Exception as e:
        return False, str(e)

def main():
    print("🚀 启动智能增量下载器...")
    print(f"💾 数据保存目录: {DATA_DIR}/")
    print("⏳ 预计运行时间：约 6 小时 (取决于网络)")
    print("-" * 50)
    
    total_tasks = []
    
    # 生成任务队列
    for interval, months in DOWNLOAD_PLAN:
        ranges = get_month_ranges(months)
        for symbol in SYMBOLS:
            for r in ranges:
                total_tasks.append({
                    "symbol": symbol,
                    "interval": interval,
                    "start": r["start"],
                    "end": r["end"],
                    "label": r["label"]
                })
    
    print(f"📋 共生成 {len(total_tasks)} 个下载任务。")
    print("   策略: 15m (1年), 1h (3年) for Top 20 Coins.")
    print("   机制: 自动跳过已存在的文件。")
    print("-" * 50)
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    # 使用 tqdm 显示进度
    for task in tqdm(total_tasks, desc="Downloading"):
        status, msg = fetch_and_save(
            task["symbol"], 
            task["interval"], 
            task["start"], 
            task["end"], 
            task["label"]
        )
        
        if status:
            success_count += 1
        elif msg == "Exists":
            skip_count += 1
        else:
            fail_count += 1
            # 失败不重试，避免卡死，睡醒再手动跑或改进
            
        # 礼貌延时，避免被封IP
        time.sleep(0.5) 

    print("\n" + "="*50)
    print("🎉 下载任务结束！")
    print(f"✅ 成功下载: {success_count} 个文件")
    print(f"⏭️  自动跳过: {skip_count} 个文件 (已存在)")
    print(f"❌ 失败: {fail_count} 个文件")
    print("="*50)
    print("💡 提示：如果有失败的文件，可以再次运行此脚本，它们会被重新尝试。")

if __name__ == "__main__":
    main()