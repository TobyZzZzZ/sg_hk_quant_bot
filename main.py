# main.py
import asyncio
import sqlite3
import time
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.api.roostoo import (
    get_ticker,
    get_balance,
    place_order,
    cancel_order,
    query_order,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "trading.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            timestamp INTEGER PRIMARY KEY,
            price REAL,
            total_equity REAL,
            usd_balance REAL,
            btc_balance REAL
        )
    """)
    conn.commit()
    conn.close()


init_db()


class StrategyState:
    def __init__(self):
        self.running = False
        self.symbol = "BTC/USD"
        self.lower_price = 65000.0
        self.upper_price = 75000.0
        self.grid_count = 40
        self.total_investment = 1000000.0
        self.qty_per_grid = 0.0

        # 【新增】缓存最新资产，防止 API 频率限制或偶发网络错误导致权益瞬间归零
        self.last_usd_free = 0.0
        self.last_usd_lock = 0.0
        self.last_btc_free = 0.0
        self.last_btc_lock = 0.0

    @property
    def last_usd_total(self):
        return self.last_usd_free + self.last_usd_lock

    @property
    def last_btc_total(self):
        return self.last_btc_free + self.last_btc_lock


state = StrategyState()


def update_balance_from_api():
    """带缓存机制和全兼容解析的余额更新"""
    bal_data = get_balance()

    if not bal_data or not isinstance(bal_data, dict):
        # API 报错时不更新资产（保留上次的缓存），但会在终端打印
        print(f"[警告] 余额API未返回有效字典: {bal_data}")
        return

    # 兼容各种大小写变体
    success = bal_data.get("Success", bal_data.get("success", False))
    if not success:
        print(
            f"[警告] 交易所拒绝了余额请求 (可能被限流): {bal_data.get('ErrMsg', bal_data)}"
        )
        return

    wallet_data = bal_data.get(
        "SpotWallet",
        bal_data.get("Wallet", bal_data.get("wallet", bal_data.get("data", {}))),
    )

    if isinstance(wallet_data, dict):
        usd_info = wallet_data.get("USD", wallet_data.get("usd", {}))
        btc_info = wallet_data.get("BTC", wallet_data.get("btc", {}))

        if usd_info:
            state.last_usd_free = float(usd_info.get("Free", usd_info.get("free", 0)))
            state.last_usd_lock = float(
                usd_info.get("Lock", usd_info.get("lock", usd_info.get("locked", 0)))
            )
        if btc_info:
            state.last_btc_free = float(btc_info.get("Free", btc_info.get("free", 0)))
            state.last_btc_lock = float(
                btc_info.get("Lock", btc_info.get("lock", btc_info.get("locked", 0)))
            )


def get_current_price():
    ticker = get_ticker(state.symbol)
    if ticker and isinstance(ticker, dict):
        data_dict = ticker.get("Data", ticker.get("data", {}))
        pair_data = data_dict.get(state.symbol, data_dict)
        last_price = pair_data.get(
            "LastPrice", pair_data.get("lastPrice", pair_data.get("price", 0))
        )
        if last_price:
            return float(last_price)
    return 0.0


def setup_initial_position():
    print(">>> 正在初始化网格策略...")
    cancel_order(pair=state.symbol)
    time.sleep(1)

    current_price = get_current_price()
    if current_price == 0.0:
        raise Exception("无法获取当前价格，初始化失败")

    state.qty_per_grid = round(
        state.total_investment / (current_price * state.grid_count), 4
    )
    if state.qty_per_grid <= 0:
        state.qty_per_grid = 0.0001

    step = (state.upper_price - state.lower_price) / state.grid_count
    sell_grids_count = sum(
        1
        for i in range(state.grid_count + 1)
        if (state.lower_price + i * step) > current_price
    )
    target_btc = sell_grids_count * state.qty_per_grid

    update_balance_from_api()
    btc = state.last_btc_total
    diff = target_btc - btc

    if diff > 0.001:
        print(f"初始建仓: 市价买入 {round(diff, 4)} BTC")
        place_order(
            state.symbol, side="BUY", quantity=round(diff, 4), order_type="MARKET"
        )
    elif diff < -0.001:
        print(f"初始建仓: 市价卖出 {round(abs(diff), 4)} BTC")
        place_order(
            state.symbol, side="SELL", quantity=round(abs(diff), 4), order_type="MARKET"
        )

    time.sleep(1)


async def strategy_loop():
    while True:
        try:
            current_price = get_current_price()
            if current_price == 0.0:
                # 遇到错误时，也等待到下一个 10 秒整点
                sleep_time = 10.0 - (time.time() % 10.0)
                await asyncio.sleep(sleep_time)
                continue

            # 更新资金（如果失败会自动使用上次成功的缓存值）
            update_balance_from_api()

            total_equity = state.last_usd_total + (state.last_btc_total * current_price)

            # 【关键修复】只有算出真实权益才写入数据库，严防 0 污染
            if total_equity > 0:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO history (timestamp, price, total_equity, usd_balance, btc_balance) VALUES (?, ?, ?, ?, ?)",
                    (
                        int(time.time() * 1000),
                        current_price,
                        total_equity,
                        state.last_usd_total,
                        state.last_btc_total,
                    ),
                )
                conn.commit()
                conn.close()

            # 如果策略未运行，只记录数据，不执行挂单逻辑
            if not state.running:
                sleep_time = 10.0 - (time.time() % 10.0)
                await asyncio.sleep(sleep_time)
                continue

            pending_res = query_order(pair=state.symbol, pending_only=True)
            pending_orders = []
            if pending_res and isinstance(pending_res, dict):
                pending_orders = pending_res.get(
                    "OrderMatched", pending_res.get("data", [])
                )

            pending_prices = [
                float(o.get("Price", o.get("price", 0)))
                for o in pending_orders
                if str(o.get("Type", o.get("type", ""))).upper() == "LIMIT"
            ]

            step = (state.upper_price - state.lower_price) / state.grid_count
            buffer = step * 0.1

            for i in range(state.grid_count + 1):
                grid_price = round(state.lower_price + i * step, 2)
                has_order = any(abs(p - grid_price) < 1.0 for p in pending_prices)

                if not has_order:
                    if grid_price < current_price - buffer:
                        place_order(
                            state.symbol,
                            side="BUY",
                            quantity=state.qty_per_grid,
                            price=grid_price,
                            order_type="LIMIT",
                        )
                        await asyncio.sleep(0.1)
                    elif grid_price > current_price + buffer:
                        place_order(
                            state.symbol,
                            side="SELL",
                            quantity=state.qty_per_grid,
                            price=grid_price,
                            order_type="LIMIT",
                        )
                        await asyncio.sleep(0.1)

        except Exception as e:
            import traceback

            print(f"策略循环异常: {e}")
            traceback.print_exc()

        # 【核心修改】动态计算睡眠时间，精准对齐到下一个 10 秒整点
        sleep_time = 10.0 - (time.time() % 10.0)
        await asyncio.sleep(sleep_time)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(strategy_loop())


class StartConfig(BaseModel):
    lower_price: float
    upper_price: float
    grid_count: int
    total_investment: float


@app.post("/api/start")
def api_start(config: StartConfig):
    if state.running:
        return {"status": "error", "msg": "Strategy running"}
    state.lower_price, state.upper_price, state.grid_count, state.total_investment = (
        config.lower_price,
        config.upper_price,
        config.grid_count,
        config.total_investment,
    )
    try:
        setup_initial_position()
        state.running = True
        return {"status": "success", "msg": "Started"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


@app.post("/api/stop")
def api_stop():
    state.running = False
    cancel_order(pair=state.symbol)
    return {"status": "success", "msg": "Stopped"}


@app.get("/api/status")
def api_status():
    return {
        "running": state.running,
        "config": {
            "lower_price": state.lower_price,
            "upper_price": state.upper_price,
            "grid_count": state.grid_count,
            "investment": state.total_investment,
        },
    }


@app.get("/api/chart_data")
def api_chart_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, price, total_equity FROM history ORDER BY timestamp DESC LIMIT 500"
    )
    rows = c.fetchall()
    conn.close()
    rows.reverse()
    return {
        "times": [r[0] for r in rows],
        "prices": [r[1] for r in rows],
        "equities": [r[2] for r in rows],
    }


@app.get("/api/account")
def api_account():
    update_balance_from_api()
    wallets = []
    # 从缓存中读取，确保 UI 始终有数据展示
    if state.last_usd_total > 0 or state.last_usd_free > 0:
        wallets.append(
            {
                "coin": "USD",
                "free": state.last_usd_free,
                "lock": state.last_usd_lock,
                "total": state.last_usd_total,
            }
        )
    if state.last_btc_total > 0 or state.last_btc_free > 0:
        wallets.append(
            {
                "coin": "BTC",
                "free": state.last_btc_free,
                "lock": state.last_btc_lock,
                "total": state.last_btc_total,
            }
        )

    return {"wallets": wallets, "current_price": get_current_price()}


@app.get("/api/orders")
def api_orders():
    res = query_order(pair=state.symbol, pending_only=True)
    orders = []
    if res and isinstance(res, dict) and res.get("Success", res.get("success")):
        orders = res.get("OrderMatched", res.get("data", []))
        orders = sorted(
            orders, key=lambda x: float(x.get("Price", x.get("price", 0))), reverse=True
        )
    return {"orders": orders}


@app.post("/api/cancel_all")
def api_cancel_all():
    cancel_order()
    return {"status": "success", "msg": "已撤销所有挂单"}


@app.post("/api/close_all")
def api_close_all():
    # 1. 撤销所有挂单
    cancel_order()
    time.sleep(1)

    # 2. 获取最新余额，市价卖出所有非 USD 币种
    bal_data = get_balance()
    sold_coins = []
    if (
        bal_data
        and isinstance(bal_data, dict)
        and bal_data.get("Success", bal_data.get("success"))
    ):
        wallet_data = bal_data.get(
            "SpotWallet",
            bal_data.get("Wallet", bal_data.get("wallet", bal_data.get("data", {}))),
        )
        if isinstance(wallet_data, dict):
            for coin, info in wallet_data.items():
                if coin.upper() == "USD":
                    continue
                free = float(info.get("Free", info.get("free", 0)))
                lock = float(info.get("Lock", info.get("lock", 0)))
                total = free + lock
                if total > 0.0001:
                    # 市价卖出
                    place_order(
                        f"{coin}/USD",
                        side="SELL",
                        quantity=round(total, 4),
                        order_type="MARKET",
                    )
                    sold_coins.append(coin)

        msg = (
            f"已一键平仓 (出售了 {', '.join(sold_coins)})"
            if sold_coins
            else "当前没有可平仓的资产"
        )
        return {"status": "success", "msg": msg}

    return {"status": "error", "msg": "无法获取余额信息，平仓失败"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
