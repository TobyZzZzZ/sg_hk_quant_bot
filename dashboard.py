import os
import time
import hmac
import hashlib
import threading
from datetime import datetime
import requests
from flask import Flask, jsonify, send_file
from flask_cors import CORS

# 硬编码的 API 密钥配置
API_KEY = "VhVGQKB2AQyV9iT3Zv0hQlZT7pVFTzvDq3vUQZ2KfOIBpuNsRg09JrJ0vTgbdY2u"
API_SECRET = "s9D4xhzE5puvvzfdwDo6DM4u66rIIbkyc0yYJa2fAlWyYxUcsrB1gfdFcrjsdvsm"
BASE_URL = "https://mock-api.roostoo.com"

app = Flask(__name__)
CORS(app)

# --- 内存状态（用于保存图表历史和当前信息） ---
state = {
    "history": [],  # 记录 BTC 价格和账户净值走势
    "assets": {},  # 各币种的持仓量和市值
    "pending_buy": [],  # 未成交买单
    "pending_sell": [],  # 未成交卖单
    "last_update": "",
}


# --- 核心 API 请求方法 ---
def _get_timestamp():
    return str(int(time.time() * 1000))


def _get_signed_headers(payload):
    payload["timestamp"] = _get_timestamp()
    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)
    signature = hmac.new(
        API_SECRET.encode("utf-8"), total_params.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {"RST-API-KEY": API_KEY, "MSG-SIGNATURE": signature}, payload, total_params


def get_ticker():
    res = requests.get(f"{BASE_URL}/v3/ticker", params={"timestamp": _get_timestamp()})
    return res.json()


def get_balance():
    headers, payload, _ = _get_signed_headers({})
    res = requests.get(f"{BASE_URL}/v3/balance", headers=headers, params=payload)
    return res.json()


def query_order(pair="BTC/USD", pending_only=True):
    payload = {"pair": pair, "pending_only": "TRUE" if pending_only else "FALSE"}
    headers, _, total_params = _get_signed_headers(payload)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    res = requests.post(
        f"{BASE_URL}/v3/query_order", headers=headers, data=total_params
    )
    return res.json()


# --- 后台定时抓取数据的线程 ---
def update_data():
    global state
    try:
        # 1. 获取所有行情
        tickers_res = get_ticker()
        if not tickers_res or not tickers_res.get("Success"):
            return
        tickers = tickers_res.get("Data", {})
        btc_price = float(tickers.get("BTC/USD", {}).get("LastPrice", 0))

        # 2. 获取余额与计算净值
        balance_res = get_balance()
        if not balance_res or not balance_res.get("Success"):
            return
        spot_wallet = balance_res.get(
            "SpotWallet", {}
        )  # 适配最新的 API 文档 SpotWallet

        total_net_worth = 0.0
        assets = {}
        for coin, amt in spot_wallet.items():
            total_coin = float(amt["Free"]) + float(amt["Lock"])
            if total_coin <= 0:
                continue

            # 计价逻辑：USD 自身价值即为数量，其它币种取 LastPrice 换算
            if coin == "USD":
                val = total_coin
            else:
                pair = f"{coin}/USD"
                price = float(tickers.get(pair, {}).get("LastPrice", 0))
                val = total_coin * price

            total_net_worth += val
            assets[coin] = {"amount": total_coin, "value": val}

        # 3. 获取挂单情况
        orders_res = query_order(pair="BTC/USD", pending_only=True)
        orders = (
            orders_res.get("OrderMatched", [])
            if orders_res and orders_res.get("Success")
            else []
        )

        buys = [
            {"price": float(o["Price"]), "qty": float(o["Quantity"])}
            for o in orders
            if o["Side"] == "BUY"
        ]
        sells = [
            {"price": float(o["Price"]), "qty": float(o["Quantity"])}
            for o in orders
            if o["Side"] == "SELL"
        ]

        # 按照题目要求：买单按价格降序，卖单按价格升序
        buys = sorted(buys, key=lambda x: x["price"], reverse=True)
        sells = sorted(sells, key=lambda x: x["price"])

        # 4. 更新内存状态
        now_str = datetime.now().strftime("%H:%M:%S")
        state["history"].append(
            {"time": now_str, "btc_price": btc_price, "net_worth": total_net_worth}
        )
        # 限制历史记录条数以防内存泄漏 (360条 = 1小时数据)
        if len(state["history"]) > 360:
            state["history"].pop(0)

        state["assets"] = assets
        state["pending_buy"] = buys
        state["pending_sell"] = sells
        state["last_update"] = now_str

        print(
            f"[{now_str}] Snapshot Captured: BTC={btc_price}, NetWorth=${total_net_worth:.2f}"
        )
    except Exception as e:
        print(f"Error updating dashboard data: {e}")


def worker_thread():
    while True:
        # 计算距离下一个整 10 秒还需要 sleep 多久
        now = time.time()
        sleep_sec = 10 - (now % 10)
        time.sleep(sleep_sec)
        update_data()


# --- 路由 ---
@app.route("/api/data")
def api_data():
    return jsonify(state)


@app.route("/")
def index():
    # 当访问根目录时，直接返回同目录下的 HTML 文件
    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dashboard.html"
    )
    if not os.path.exists(html_path):
        return "Error: dashboard.html not found in the same directory.", 404
    return send_file(html_path)


if __name__ == "__main__":
    print("Initializing first data fetch...")
    update_data()
    # 开启后台守护线程
    t = threading.Thread(target=worker_thread, daemon=True)
    t.start()

    print("\n" + "=" * 50)
    print(" Dashboard Server is RUNNING!")
    print(" Please open this link in your browser:")
    print(" http://127.0.0.1:8888")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=8888)
