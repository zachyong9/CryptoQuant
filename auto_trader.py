# -*- coding: utf-8 -*-
import time
import requests
import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "paper_trading.db"
FAST_MA = 17
SLOW_MA = 30
FEE_RATE = 0.0005  # 0.05% 手续费
SLIPPAGE = 0.0002  # 0.02% 滑点

def get_kline_signal(inst_id="BTC-USDT", bar="15m", limit=100):
    """获取最新 K 线并计算当前均线交叉信号"""
    url = "https://www.okx.com/api/v5/market/candles"
    try:
        res = requests.get(url, params={"instId": inst_id, "bar": bar, "limit": limit}, timeout=5)
        data = res.json()
        if data.get("code") != "0" or not data.get("data"):
            return None, 0.0
        
        df = pd.DataFrame(data["data"], columns=[
            "ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"
        ]).iloc[::-1].reset_index(drop=True)
        
        df["close"] = df["close"].astype(float)
        df["MA_Fast"] = df["close"].rolling(FAST_MA).mean()
        df["MA_Slow"] = df["close"].rolling(SLOW_MA).mean()

        latest_close = df["close"].iloc[-1]
        
        # 判断前一根柱子与当前柱子的交叉
        prev_fast, prev_slow = df["MA_Fast"].iloc[-2], df["MA_Slow"].iloc[-2]
        curr_fast, curr_slow = df["MA_Fast"].iloc[-1], df["MA_Slow"].iloc[-1]

        signal = "HOLD"
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            signal = "BUY"
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            signal = "SELL"

        return signal, latest_close
    except Exception as e:
        print(f"获取行情失败: {e}")
        return None, 0.0

def execute_auto_trade(coin, side, price):
    """自动化撮合入库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    acc = pd.read_sql("SELECT * FROM account WHERE id = 1", conn).iloc[0]
    balance = acc['balance']
    now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if side == "BUY":
        c.execute("SELECT amount FROM positions WHERE coin = ?", (coin,))
        row = c.fetchone()
        if row and row[0] > 0.0001:
            conn.close()
            return  # 已有持仓，不重复买入
        
        # 使用 80% 的可用资金建仓
        invest_amount = balance * 0.8
        if invest_amount < 10:
            conn.close()
            return
        
        actual_buy = price * (1 + SLIPPAGE)
        fee = invest_amount * FEE_RATE
        buy_tokens = (invest_amount - fee) / actual_buy

        new_balance = balance - invest_amount
        c.execute("UPDATE account SET balance = ? WHERE id = 1", (new_balance,))
        c.execute("INSERT OR REPLACE INTO positions (coin, amount, avg_cost, updated_at) VALUES (?, ?, ?, ?)",
                  (coin, buy_tokens, actual_buy, now_time))
        c.execute("INSERT INTO trades (time, coin, side, price, amount, cost, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (now_time, coin, "AUTO_BUY", actual_buy, buy_tokens, invest_amount, 0.0))
        conn.commit()
        print(f"[{now_time}] 🤖 自动执行买入: {coin} @ ${actual_buy:,.2f}，数量: {buy_tokens:.4f}")

    elif side == "SELL":
        c.execute("SELECT amount, avg_cost FROM positions WHERE coin = ?", (coin,))
        row = c.fetchone()
        if not row or row[0] <= 0.0001:
            conn.close()
            return  # 无持仓，无需平仓
        
        amount, avg_cost = row
        actual_sell = price * (1 - SLIPPAGE)
        proceeds = amount * actual_sell
        fee = proceeds * FEE_RATE
        net_proceeds = proceeds - fee
        realized_pnl = (actual_sell - avg_cost) * amount - fee

        new_balance = balance + net_proceeds
        c.execute("UPDATE account SET balance = ? WHERE id = 1", (new_balance,))
        c.execute("DELETE FROM positions WHERE coin = ?", (coin,))
        c.execute("INSERT INTO trades (time, coin, side, price, amount, cost, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (now_time, coin, "AUTO_SELL", actual_sell, amount, net_proceeds, realized_pnl))
        conn.commit()
        print(f"[{now_time}] 🤖 自动执行平仓: {coin} @ ${actual_sell:,.2f}，实现盈亏: ${realized_pnl:+,.2f}")

    conn.close()

def run_auto_trader():
    print("=" * 60)
    print("🤖 Crypto Radar - 24H 自动化量化策略托管引擎已启动")
    print(f"策略模型: MA{FAST_MA}/MA{SLOW_MA} 趋势追踪 | 标的: BTC-USDT, ETH-USDT, SOL-USDT")
    print("=" * 60)

    target_coins = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    
    while True:
        try:
            for coin in target_coins:
                signal, price = get_kline_signal(coin, bar="15m")
                if price > 0:
                    curr_t = datetime.now().strftime('%H:%M:%S')
                    print(f"[{curr_t}] 扫描 {coin}: 现价 ${price:,.2f} | 信号: {signal}")
                    if signal in ["BUY", "SELL"]:
                        execute_auto_trade(coin, signal, price)
            time.sleep(30)  # 每 30 秒轮询一次
        except KeyboardInterrupt:
            print("\n机器人已手动停止。")
            break
        except Exception as e:
            print(f"运行异常: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_auto_trader()