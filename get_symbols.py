# get_symbols.py
import requests
import json
import time
from roostoo_api import _get_timestamp, check_server_time

BASE_URL = "https://mock-api.roostoo.com"

def fetch_all_symbols():
    print("🔍 正在连接 Roostoo 服务器获取交易对列表...")
    
    # 1. 先检查连通性
    if not check_server_time():
        print("❌ 无法连接服务器，请检查网络或 API 状态。")
        return []

    # 2. 调用 Ticker 接口 (通常返回所有交易对)
    # 注意：Roostoo 文档中 get_ticker 如果不传 pair 参数，可能返回所有
    url = f"{BASE_URL}/v3/ticker"
    params = {"timestamp": _get_timestamp()}
    
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()
        
        if not data.get("Success"):
            print(f"❌ API 返回失败: {data}")
            return []
            
        # 解析数据
        # 假设返回结构是 {"Data": {"BTC/USD": {...}, "ETH/USD": {...}}, "Success": true}
        raw_data = data.get("Data", {})
        symbols = list(raw_data.keys())
        
        if not symbols:
            print("⚠️ 未找到任何交易对，可能是 API 返回格式有变。")
            return []

        print(f"✅ 成功获取 {len(symbols)} 个交易对！")
        for s in symbols[:5]:
            print(f"   - {s}")
        if len(symbols) > 5:
            print(f"   ... 还有 {len(symbols)-5} 个")

        # 保存到本地文件
        with open("symbols.json", "w") as f:
            json.dump(symbols, f, indent=2)
        print("💾 已保存至 symbols.json")
        
        return symbols

    except Exception as e:
        print(f"❌ 获取过程中出错: {e}")
        return []

if __name__ == "__main__":
    fetch_all_symbols()