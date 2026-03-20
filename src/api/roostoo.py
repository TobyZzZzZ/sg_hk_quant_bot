# roostoo_api.py
import requests
import time
import hmac
import hashlib
try:
    import config
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    import config

BASE_URL = "https://mock-api.roostoo.com"


def _get_timestamp():
    """返回 13 位毫秒时间戳的字符串形式"""
    return str(int(time.time() * 1000))


def _get_signed_headers(payload: dict = {}):
    """
    生成 RCL_TopLevelCheck 接口所需的签名请求头和参数字符串。
    核心逻辑：按照 Key 排序 -> 拼接成字符串 -> HMAC SHA256 加密
    """
    payload["timestamp"] = _get_timestamp()
    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)

    # 使用 config.py 中的 SECRET_KEY 进行签名
    signature = hmac.new(
        config.API_SECRET.encode("utf-8"), total_params.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers = {
        "RST-API-KEY": config.API_KEY,  # 使用 config.py 中的 API_KEY
        "MSG-SIGNATURE": signature,
    }

    return headers, payload, total_params


# ------------------------------
# 公开接口 (不需要签名)
# ------------------------------


def check_server_time():
    """检查服务器时间并测试连接"""
    url = f"{BASE_URL}/v3/serverTime"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"获取服务器时间出错: {e}")
        return None


def get_ticker(pair=None):
    """
    获取指定交易对的最新行情，例如: 'BTC/USD'
    这个接口在文档中标记为 RCL_TSCheck，需要 timestamp 但不需要签名
    """
    url = f"{BASE_URL}/v3/ticker"
    params = {"timestamp": _get_timestamp()}
    if pair:
        params["pair"] = pair

    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()

        # 为了方便策略调用，直接提取并返回当前最新价格 (LastPrice)
        if data and data.get("Success") and pair in data.get("Data", {}):
            return float(data["Data"][pair]["LastPrice"])
        return None
    except Exception as e:
        print(f"获取行情出错: {e}")
        return None


# ------------------------------
# 加密接口 (需要签名)
# ------------------------------


def get_balance():
    """获取账户余额"""
    url = f"{BASE_URL}/v3/balance"
    headers, payload, _ = _get_signed_headers({})
    try:
        # GET 请求，参数放在 URL 中 (params)
        res = requests.get(url, headers=headers, params=payload)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"获取余额出错: {e}")
        return None


def place_order(pair_or_coin, side, quantity, price=None, order_type=None):
    """
    下达交易订单 (LIMIT 限价单 或 MARKET 市价单)
    side: 'BUY' 或 'SELL'
    """
    url = f"{BASE_URL}/v3/place_order"
    # 确保格式是 "BTC/USD"
    pair = f"{pair_or_coin}/USD" if "/" not in pair_or_coin else pair_or_coin

    # 如果没传 type，根据是否有 price 自动判断
    if order_type is None:
        order_type = "LIMIT" if price is not None else "MARKET"

    payload = {
        "pair": pair,
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": str(quantity),
    }

    if order_type == "LIMIT":
        if price is None:
            print("错误：限价单 (LIMIT) 必须提供价格 (price)。")
            return None
        payload["price"] = str(price)

    headers, _, total_params = _get_signed_headers(payload)
    # 官方要求：所有 POST 请求必须设置此 Content-Type
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    try:
        # POST 请求，按照官方要求把签名后的字符串作为 data 发送
        res = requests.post(url, headers=headers, data=total_params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"下单出错: {e}")
        return None
