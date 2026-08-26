# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import datetime
import plotly.express as px

st.set_page_config(
    page_title="Crypto Radar - 综合量化终端 & 模拟实盘交易系统",
    page_icon="🪙",
    layout="wide"
)

# 科技风 UI
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2638 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 14px;
        color: white;
    }
    .metric-title { font-size: 12px; color: #9CA3AF; margin-bottom: 4px; }
    .metric-val { font-size: 20px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ----------------- 数据库管理 (SQLite) -----------------
DB_FILE = "paper_trading.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 账户资金表
    c.execute('''CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY,
        balance REAL,
        init_capital REAL
    )''')
    # 持仓表
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        coin TEXT PRIMARY KEY,
        amount REAL,
        avg_cost REAL,
        updated_at TEXT
    )''')
    # 交易历史表
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        coin TEXT,
        side TEXT,
        price REAL,
        amount REAL,
        cost REAL,
        realized_pnl REAL
    )''')
    
    # 初始化账户（若不存在则给予 100,000 USDT 模拟金）
    c.execute("SELECT COUNT(*) FROM account")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO account (id, balance, init_capital) VALUES (1, 100000.0, 100000.0)")
    conn.commit()
    conn.close()

init_db()

def get_account_data():
    conn = sqlite3.connect(DB_FILE)
    acc = pd.read_sql("SELECT * FROM account WHERE id = 1", conn).iloc[0]
    pos = pd.read_sql("SELECT * FROM positions WHERE amount > 0.00001", conn)
    trades = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    return acc, pos, trades

def execute_trade(coin, side, price, amount):
    """撮合模拟交易并更新数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    acc = pd.read_sql("SELECT * FROM account WHERE id = 1", conn).iloc[0]
    balance = acc['balance']
    cost = price * amount
    fee = cost * 0.0005 # 0.05% 真实手续费
    total_cost = cost + fee

    now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if side == "BUY":
        if total_cost > balance:
            conn.close()
            return False, f"余额不足！需要 ${total_cost:,.2f} USDT，当前余额 ${balance:,.2f} USDT"
        
        # 扣减资金
        new_balance = balance - total_cost
        c.execute("UPDATE account SET balance = ? WHERE id = 1", (new_balance,))

        # 更新持仓
        c.execute("SELECT amount, avg_cost FROM positions WHERE coin = ?", (coin,))
        row = c.fetchone()
        if row:
            curr_amt, curr_cost = row
            new_amt = curr_amt + amount
            new_avg = ((curr_amt * curr_cost) + cost) / new_amt
            c.execute("UPDATE positions SET amount = ?, avg_cost = ?, updated_at = ? WHERE coin = ?", (new_amt, new_avg, now_time, coin))
        else:
            c.execute("INSERT INTO positions VALUES (?, ?, ?, ?)", (coin, amount, price, now_time))

        # 记录交易流水
        c.execute("INSERT INTO trades (time, coin, side, price, amount, cost, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (now_time, coin, "BUY", price, amount, total_cost, 0.0))
        conn.commit()
        conn.close()
        return True, f"✅ 模拟买入成功！以 ${price:,.2f} 购入 {amount} {coin.replace('-USDT','')}"

    elif side == "SELL":
        c.execute("SELECT amount, avg_cost FROM positions WHERE coin = ?", (coin,))
        row = c.fetchone()
        if not row or row[0] < amount:
            conn.close()
            curr_have = row[0] if row else 0
            return False, f"持仓不足！当前仅持有 {curr_have} {coin.replace('-USDT','')}"
        
        curr_amt, curr_cost = row
        proceeds = cost - fee
        new_balance = balance + proceeds
        c.execute("UPDATE account SET balance = ? WHERE id = 1", (new_balance,))

        realized_pnl = (price - curr_cost) * amount - fee

        new_amt = curr_amt - amount
        if new_amt < 0.00001:
            c.execute("DELETE FROM positions WHERE coin = ?", (coin,))
        else:
            c.execute("UPDATE positions SET amount = ?, updated_at = ? WHERE coin = ?", (new_amt, now_time, coin))

        c.execute("INSERT INTO trades (time, coin, side, price, amount, cost, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (now_time, coin, "SELL", price, amount, proceeds, realized_pnl))
        conn.commit()
        conn.close()
        return True, f"✅ 模拟卖出成功！以 ${price:,.2f} 卖出 {amount} {coin.replace('-USDT','')}，实现盈亏: ${realized_pnl:+,.2f} USDT"

def reset_account():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE account SET balance = 100000.0, init_capital = 100000.0 WHERE id = 1")
    c.execute("DELETE FROM positions")
    c.execute("DELETE FROM trades")
    conn.commit()
    conn.close()

@st.cache_data(ttl=10)
def get_live_prices(coins):
    prices = {}
    for c in coins:
        try:
            res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={c}", timeout=3).json()
            if res.get("code") == "0" and res.get("data"):
                prices[c] = float(res["data"][0]["last"])
        except Exception:
            prices[c] = 0.0
    return prices

# ----------------- 界面主逻辑 -----------------
st.title("🪙 Crypto Radar - 综合量化终端 & 实盘模拟交易中心")
st.caption("左侧导航已聚合所有独立看板 · 本地 SQLite 驱动无本金真实模拟账户 · 支持 10 万 USDT 模拟交易")

COIN_LIST = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "DOGE-USDT", "XRP-USDT"]
live_prices = get_live_prices(COIN_LIST)

acc, pos_df, trades_df = get_account_data()

# 计算持仓市值与账户总资产
holdings_val = 0.0
pos_records = []
if not pos_df.empty:
    for idx, r in pos_df.iterrows():
        c_coin = r['coin']
        c_amt = r['amount']
        c_cost = r['avg_cost']
        c_price = live_prices.get(c_coin, c_cost)
        val = c_amt * c_price
        holdings_val += val
        unrealized = (c_price - c_cost) * c_amt
        unrealized_pct = ((c_price - c_cost) / c_cost) * 100 if c_cost > 0 else 0.0
        pos_records.append({
            "资产代号": c_coin,
            "持仓数量": f"{c_amt:,.4f}",
            "持仓均价": f"${c_cost:,.2f}",
            "当前市价": f"${c_price:,.2f}",
            "当前持仓市值": f"${val:,.2f}",
            "浮动盈亏 ($)": f"{unrealized:+,.2f}",
            "浮动收益率": f"{unrealized_pct:+.2f}%"
        })

total_equity = acc['balance'] + holdings_val
total_pnl = total_equity - acc['init_capital']
total_pnl_pct = (total_pnl / acc['init_capital']) * 100

# 顶栏核心资产卡片
c1, c2, c3, c4 = st.columns(4)
pnl_color = "#10B981" if total_pnl >= 0 else "#EF4444"

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">账户总净值 (USDT)</div>
        <div class="metric-val">${total_equity:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">可用现金余额 (USDT)</div>
        <div class="metric-val">${acc['balance']:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">当前持仓总市值</div>
        <div class="metric-val">${holdings_val:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">累计模拟盈亏</div>
        <div class="metric-val" style="color:{pnl_color};">{total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# 交易下单面板与持仓表格
left_trade, right_pos = st.columns([1, 1.6])

with left_trade:
    st.subheader("⚡ 快速模拟下单交易")
    t_coin = st.selectbox("选择交易标的", COIN_LIST)
    curr_t_price = live_prices.get(t_coin, 0.0)
    st.info(f"当前 {t_coin} 实时行情价格: **${curr_t_price:,.2f} USDT**")

    t_side = st.radio("交易方向", ["买入 (BUY)", "卖出 (SELL)"], horizontal=True)
    t_amount = st.number_input("交易数量 (Token Amount)", min_value=0.0001, value=0.1, step=0.1, format="%.4f")
    
    est_cost = t_amount * curr_t_price
    st.caption(f"预计成交金额: ~${est_cost:,.2f} USDT (已含 0.05% 手续费)")

    if st.button("🚀 提交模拟订单", use_container_width=True):
        if curr_t_price <= 0:
            st.error("无法获取当前标的价格，请稍后重试！")
        else:
            side_str = "BUY" if "买入" in t_side else "SELL"
            ok, msg = execute_trade(t_coin, side_str, curr_t_price, t_amount)
            if ok:
                st.success(msg)
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)

    st.markdown("---")
    if st.button("⚠️ 重置账户资金为 100,000 USDT", use_container_width=True):
        reset_account()
        st.success("账户已重置！")
        time.sleep(1)
        st.rerun()

with right_pos:
    st.subheader(f"💼 当前真实模拟持仓 ({len(pos_records)} 个资产)")
    if pos_records:
        df_p_show = pd.DataFrame(pos_records)
        st.dataframe(df_p_show, hide_index=True, use_container_width=True)
    else:
        st.info("目前为空仓状态，可在左侧进行买入建仓。")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    st.subheader("📜 最近模拟交易流水记录")
    if not trades_df.empty:
        t_show = trades_df[["time", "coin", "side", "price", "amount", "realized_pnl"]].copy()
        t_show.columns = ["成交时间", "币种", "方向", "成交均价", "成交数量", "已实现盈亏 ($)"]
        t_show["成交均价"] = t_show["成交均价"].apply(lambda x: f"${x:,.2f}")
        t_show["已实现盈亏 ($)"] = t_show["已实现盈亏 ($)"].apply(lambda x: f"{x:+,.2f}")
        st.dataframe(t_show, hide_index=True, use_container_width=True)
    else:
        st.caption("暂无交易历史流水。")