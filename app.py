# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sqlite3
import requests
from datetime import datetime

st.set_page_config(
    page_title="Crypto Radar - Web3 智能量化交易终端",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 科技风暗黑 CSS
st.markdown("""
<style>
    .metric-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        color: white;
    }
    .metric-title { font-size: 13px; color: #94A3B8; margin-bottom: 4px; text-transform: uppercase; }
    .metric-value { font-size: 24px; font-weight: 700; color: #F8FAFC; }
    .status-running { color: #10B981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

DB_PATH = "paper_trading.db"
FEE_RATE = 0.0005  # 0.05%

def init_and_get_data():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    
    # 建表
    c.execute('''CREATE TABLE IF NOT EXISTS account
                 (id INTEGER PRIMARY KEY, balance REAL, initial_balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS positions
                 (coin TEXT PRIMARY KEY, side TEXT, leverage INTEGER, margin REAL, 
                  amount REAL, avg_cost REAL, liq_price REAL, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, coin TEXT, side TEXT, 
                  leverage INTEGER, price REAL, amount REAL, cost REAL, realized_pnl REAL)''')
    conn.commit()

    # 数据库结构兼容性自动迁移（防止老数据库缺少列报错）
    c.execute("PRAGMA table_info(positions)")
    pos_cols = [row[1] for row in c.fetchall()]
    if "side" not in pos_cols:
        c.execute("ALTER TABLE positions ADD COLUMN side TEXT DEFAULT 'LONG'")
    if "leverage" not in pos_cols:
        c.execute("ALTER TABLE positions ADD COLUMN leverage INTEGER DEFAULT 1")
    if "margin" not in pos_cols:
        c.execute("ALTER TABLE positions ADD COLUMN margin REAL DEFAULT 0.0")
    if "liq_price" not in pos_cols:
        c.execute("ALTER TABLE positions ADD COLUMN liq_price REAL DEFAULT 0.0")

    c.execute("PRAGMA table_info(trades)")
    trade_cols = [row[1] for row in c.fetchall()]
    if "leverage" not in trade_cols:
        c.execute("ALTER TABLE trades ADD COLUMN leverage INTEGER DEFAULT 1")
    conn.commit()

    # 初始化账户资产
    try:
        c.execute("SELECT balance, initial_balance FROM account WHERE id = 1")
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO account (id, balance, initial_balance) VALUES (1, 100000.0, 100000.0)")
            conn.commit()
            balance, init_balance = 100000.0, 100000.0
        else:
            balance, init_balance = row[0], row[1]
    except Exception:
        balance, init_balance = 100000.0, 100000.0
        
    try:
        pos = pd.read_sql("SELECT * FROM positions", conn)
    except Exception:
        pos = pd.DataFrame(columns=["coin", "side", "leverage", "margin", "amount", "avg_cost", "liq_price", "updated_at"])
        
    try:
        trades = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 20", conn)
    except Exception:
        trades = pd.DataFrame(columns=["id", "time", "coin", "side", "leverage", "price", "amount", "cost", "realized_pnl"])
        
    conn.close()
    return {"balance": balance, "initial_balance": init_balance}, pos, trades

def get_realtime_tickers():
    symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "DOGE-USDT", "XRP-USDT"]
    res_list = []
    for s in symbols:
        try:
            url = f"https://www.okx.com/api/v5/market/ticker?instId={s}"
            r = requests.get(url, timeout=2).json()
            if r.get("code") == "0" and r.get("data"):
                d = r["data"][0]
                price = float(d["last"])
                open_24h = float(d["open24h"])
                chg = ((price - open_24h) / open_24h) * 100
                res_list.append({"coin": s, "price": price, "chg_24h": chg})
        except Exception:
            pass
    return pd.DataFrame(res_list)

def execute_open_position(coin, side, leverage, margin, cur_price):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT balance FROM account WHERE id = 1")
    balance = c.fetchone()[0]
    
    notional = margin * leverage
    fee = notional * FEE_RATE
    total_deduct = margin + fee
    
    if total_deduct > balance:
        conn.close()
        return False, "账户可用保证金不足以支付开仓与手续费！"
    
    amount = notional / cur_price
    if side == "LONG":
        liq_price = cur_price * (1 - (1 / leverage) + 0.005)
    else:
        liq_price = cur_price * (1 + (1 / leverage) - 0.005)
    
    now_t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE account SET balance = ? WHERE id = 1", (balance - total_deduct,))
    c.execute("""INSERT OR REPLACE INTO positions 
                 (coin, side, leverage, margin, amount, avg_cost, liq_price, updated_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (coin, side, leverage, margin, amount, cur_price, liq_price, now_t))
    c.execute("""INSERT INTO trades (time, coin, side, leverage, price, amount, cost, realized_pnl) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (now_t, coin, f"OPEN_{side}", leverage, cur_price, amount, margin, -fee))
    conn.commit()
    conn.close()
    return True, "开仓成功！"

def execute_close_position(coin, cur_price):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT side, leverage, margin, amount, avg_cost FROM positions WHERE coin = ?", (coin,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "持仓不存在！"
    
    side = row[0] or "LONG"
    leverage = row[1] or 1
    margin = row[2] or 0.0
    amount = row[3]
    avg_cost = row[4]
    
    notional = amount * cur_price
    close_fee = notional * FEE_RATE
    
    if side == "LONG":
        pnl = (cur_price - avg_cost) * amount
    else:
        pnl = (avg_cost - cur_price) * amount
    
    net_return = margin + pnl - close_fee
    c.execute("SELECT balance FROM account WHERE id = 1")
    balance = c.fetchone()[0]
    
    now_t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE account SET balance = ? WHERE id = 1", (balance + net_return,))
    c.execute("DELETE FROM positions WHERE coin = ?", (coin,))
    c.execute("""INSERT INTO trades (time, coin, side, leverage, price, amount, cost, realized_pnl) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (now_t, coin, f"CLOSE_{side}", leverage, cur_price, amount, margin, pnl - close_fee))
    conn.commit()
    conn.close()
    return True, "平仓成功！"

acc, pos, trades = init_and_get_data()
tickers_df = get_realtime_tickers()

# 页面主标题
st.title("⚡ Crypto Radar - Web3 智能合约与量化交易终端")
st.caption("集 20x 杠杆合约撮合、全市场多因子监控、链上巨鲸雷达与智能合约安全审计于一体的全栈交易控制台")

# 顶栏核心数据卡片
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">账户可用保证金 (USDT)</div>
        <div class="metric-value">${acc["balance"]:,.2f}</div>
        <div style="color:#10b981;font-size:12px;margin-top:4px;">初始本金: ${acc["initial_balance"]:,.2f}</div>
    </div>''', unsafe_allow_html=True)

with c2:
    active_pos = pos[pos['amount'] > 0.00001] if not pos.empty else pd.DataFrame()
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">当前活跃持仓</div>
        <div class="metric-value">{len(active_pos)} <span style="font-size:14px;color:#94a3b8;">个头寸</span></div>
        <div style="color:#38bdf8;font-size:12px;margin-top:4px;">支持最高 20x 杠杆多空</div>
    </div>''', unsafe_allow_html=True)

with c3:
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">撮合成交总笔数</div>
        <div class="metric-value">{len(trades)} <span style="font-size:14px;color:#94a3b8;">笔</span></div>
        <div style="color:#a855f7;font-size:12px;margin-top:4px;">双向开平仓流水</div>
    </div>''', unsafe_allow_html=True)

with c4:
    st.markdown('''<div class="metric-box">
        <div class="metric-title">24H 策略托管引擎</div>
        <div class="status-running" style="font-size:22px;margin-top:4px;">● RUNNING (在线)</div>
        <div style="color:#94a3b8;font-size:12px;margin-top:4px;">MA17/MA30 趋势捕捉</div>
    </div>''', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# 全市场实时行情热力矩阵
st.subheader("🌐 全市场实时行情与信号热力矩阵")
if not tickers_df.empty:
    cols = st.columns(len(tickers_df))
    for idx, row in tickers_df.iterrows():
        with cols[idx]:
            chg_color = "#10B981" if row["chg_24h"] >= 0 else "#EF4444"
            sign = "+" if row["chg_24h"] >= 0 else ""
            st.markdown(f'''
            <div style="background:#131b2e;border:1px solid #1e293b;border-radius:8px;padding:12px;text-align:center;">
                <div style="font-size:13px;color:#94A3B8;font-weight:600;">{row["coin"]}</div>
                <div style="font-size:18px;font-weight:700;color:white;margin:4px 0;">${row["price"]:,.2f}</div>
                <div style="font-size:12px;color:{chg_color};font-weight:600;">{sign}{row["chg_24h"]:.2f}%</div>
            </div>
            ''', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# 核心交易区：下单柜台 + 动态合约持仓
trade_col, pos_col = st.columns([1.1, 1.9])

with trade_col:
    st.subheader("🎯 杠杆合约模拟交易下单柜台")
    t_coin = st.selectbox("选择交易标的", ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "DOGE-USDT", "XRP-USDT"])
    
    cur_p = 0.0
    if not tickers_df.empty and t_coin in tickers_df["coin"].values:
        cur_p = tickers_df[tickers_df["coin"] == t_coin]["price"].values[0]
    
    st.caption(f"当前市场最新成交价: **${cur_p:,.2f}**")
    
    t_side = st.radio("交易方向", ["🟢 做多 (LONG)", "🔴 做空 (SHORT)"], horizontal=True)
    t_lev = st.slider("杠杆倍数 (Leverage)", min_value=1, max_value=20, value=10, step=1)
    
    max_margin = max(10.0, float(acc["balance"]))
    t_margin = st.number_input("投入保证金 (USDT)", min_value=10.0, max_value=max_margin, value=min(1000.0, max_margin), step=100.0)
    
    notional_val = t_margin * t_lev
    st.markdown(f"**名义持仓价值**：`${notional_val:,.2f}` | **预估手续费**：`${notional_val * FEE_RATE:,.2f}`")
    
    if st.button("🚀 立即确认下单开仓", use_container_width=True):
        if cur_p <= 0:
            st.error("无法获取当前最新市价，请刷新重试！")
        else:
            side_code = "LONG" if "做多" in t_side else "SHORT"
            succ, msg = execute_open_position(t_coin, side_code, t_lev, t_margin, cur_p)
            if succ:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

with pos_col:
    st.subheader("💼 当前活跃合约持仓")
    if not active_pos.empty:
        for idx, p in active_pos.iterrows():
            coin = p["coin"]
            side = p["side"] if "side" in p and pd.notna(p["side"]) else "LONG"
            lev = int(p["leverage"]) if "leverage" in p and pd.notna(p["leverage"]) else 1
            margin = float(p["margin"]) if "margin" in p and pd.notna(p["margin"]) else (p["amount"] * p["avg_cost"] / max(1, lev))
            amt = float(p["amount"])
            avg_cost = float(p["avg_cost"])
            liq_p = float(p["liq_price"]) if "liq_price" in p and pd.notna(p["liq_price"]) else (avg_cost * 0.9)
            
            p_cur = avg_cost
            if not tickers_df.empty and coin in tickers_df["coin"].values:
                p_cur = tickers_df[tickers_df["coin"] == coin]["price"].values[0]
            
            pnl = (p_cur - avg_cost) * amt if side == "LONG" else (avg_cost - p_cur) * amt
            roe = (pnl / margin) * 100 if margin > 0 else 0
            pnl_color = "#10B981" if pnl >= 0 else "#EF4444"
            side_badge = "🟢 多头 LONG" if side == "LONG" else "🔴 空头 SHORT"
            
            st.markdown(f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:16px;font-weight:700;color:white;">{coin} <span style="background:#F59E0B;color:black;padding:2px 6px;border-radius:4px;font-size:12px;font-weight:700;">{lev}X</span> <span style="font-size:13px;color:#94A3B8;margin-left:8px;">{side_badge}</span></span>
                    <span style="font-size:16px;font-weight:700;color:{pnl_color};">浮动盈亏: ${pnl:+,.2f} ({roe:+.2f}%)</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:13px;color:#94A3B8;margin-top:8px;">
                    <span>持仓数量: {amt:.4f} | 保证金: ${margin:,.2f}</span>
                    <span>开仓均价: ${avg_cost:,.2f} | 现价: ${p_cur:,.2f} | 强平价: <span style="color:#EF4444;font-weight:600;">${liq_p:,.2f}</span></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"⚡ 一键市价平仓 [{coin}]", key=f"close_{coin}_{idx}", use_container_width=True):
                succ, msg = execute_close_position(coin, p_cur)
                if succ:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.info("当前暂无活跃合约持仓，可在左侧下单柜台进行 1~20x 模拟开仓。")

st.divider()

# 下半部：资产净值曲线 + 策略与风控配置
mid_l, mid_r = st.columns([1.5, 1])

with mid_l:
    st.subheader("📈 模拟账户资产净值增长曲线")
    if not trades.empty:
        trade_curve = trades.iloc[::-1].copy()
        trade_curve["cum_pnl"] = trade_curve["realized_pnl"].cumsum()
        trade_curve["equity"] = acc["initial_balance"] + trade_curve["cum_pnl"]
        fig_equity = px.line(trade_curve, x="time", y="equity", markers=True)
        fig_equity.update_layout(
            template="plotly_dark",
            height=260,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_equity, use_container_width=True)
    else:
        st.caption("暂无交易曲线")

with mid_r:
    st.subheader("⚙️ 策略与系统控制台")
    st.markdown("""
    * **主控模型**：MA17 / MA30 双均线金叉做多，死叉平仓
    * **杠杆风控**：支持最高 20x 独立保证金隔离仓位
    * **滑点与费率**：固定 0.05% 手续费与动态滑点保护
    """)
    if st.button("🔄 立即刷新最新行情与持仓", use_container_width=True):
        st.rerun()
    if st.button("⚠️ 重置账户资金为 $100,000", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE account SET balance = 100000.0 WHERE id = 1")
        c.execute("DELETE FROM positions")
        c.execute("DELETE FROM trades")
        conn.commit()
        conn.close()
        st.success("账户状态与持仓已重置！")
        st.rerun()

st.divider()

# 底部交易流水
st.subheader("📜 最新交易与平仓撮合流水 (最近 20 笔)")
if not trades.empty:
    st.dataframe(trades[["time", "coin", "side", "leverage", "price", "amount", "cost", "realized_pnl"]], use_container_width=True, hide_index=True)
else:
    st.info("暂无历史成交记录。")
