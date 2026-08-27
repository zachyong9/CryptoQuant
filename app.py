# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import requests
from datetime import datetime

st.set_page_config(
    page_title="Crypto Radar - Web3 智能量化交易终端",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入科技风暗黑 CSS
st.markdown("""
<style>
    .metric-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        color: white;
    }
    .metric-title { font-size: 13px; color: #94A3B8; margin-bottom: 4px; text-transform: uppercase; }
    .metric-value { font-size: 24px; font-weight: 700; color: #F8FAFC; }
    .status-running { color: #10B981; font-weight: bold; }
    .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-bull { background-color: rgba(16, 185, 129, 0.2); color: #10B981; }
    .badge-bear { background-color: rgba(239, 68, 68, 0.2); color: #EF4444; }
</style>
""", unsafe_allow_html=True)

DB_PATH = "paper_trading.db"

def init_and_get_data():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS account
                 (id INTEGER PRIMARY KEY, balance REAL, initial_balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS positions
                 (coin TEXT PRIMARY KEY, amount REAL, avg_cost REAL, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, coin TEXT, side TEXT, 
                  price REAL, amount REAL, cost REAL, realized_pnl REAL)''')
    conn.commit()

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
        pos = pd.DataFrame(columns=["coin", "amount", "avg_cost", "updated_at"])
        
    try:
        trades = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 20", conn)
    except Exception:
        trades = pd.DataFrame(columns=["id", "time", "coin", "side", "price", "amount", "cost", "realized_pnl"])
        
    conn.close()
    return {"balance": balance, "initial_balance": init_balance}, pos, trades

def get_realtime_tickers():
    """获取主要币种实时行情"""
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

acc, pos, trades = init_and_get_data()
tickers_df = get_realtime_tickers()

# 页面标题
st.title("⚡ Crypto Radar - Web3 智能量化交易终端")
st.caption("集全市场多因子监控、链上巨鲸雷达、智能合约安全审计与 24H 自动量化撮合于一体的全栈交易控制台")

# 顶栏核心数据卡片
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">账户可用资金 (USDT)</div>
        <div class="metric-value">${acc["balance"]:,.2f}</div>
        <div style="color:#10b981;font-size:12px;margin-top:4px;">初始本金: ${acc["initial_balance"]:,.2f}</div>
    </div>''', unsafe_allow_html=True)

with c2:
    active_pos = pos[pos['amount'] > 0.0001] if not pos.empty else pd.DataFrame()
    holdings_count = len(active_pos)
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">当前活跃持仓</div>
        <div class="metric-value">{holdings_count} <span style="font-size:14px;color:#94a3b8;">个币种</span></div>
        <div style="color:#38bdf8;font-size:12px;margin-top:4px;">实时多因子状态跟踪</div>
    </div>''', unsafe_allow_html=True)

with c3:
    total_trades = len(trades) if not trades.empty else 0
    st.markdown(f'''<div class="metric-box">
        <div class="metric-title">历史撮合总笔数</div>
        <div class="metric-value">{total_trades} <span style="font-size:14px;color:#94a3b8;">笔</span></div>
        <div style="color:#a855f7;font-size:12px;margin-top:4px;">策略自动与手动执行</div>
    </div>''', unsafe_allow_html=True)

with c4:
    st.markdown('''<div class="metric-box">
        <div class="metric-title">24H 策略托管状态</div>
        <div class="status-running" style="font-size:22px;margin-top:4px;">● RUNNING (在线)</div>
        <div style="color:#94a3b8;font-size:12px;margin-top:4px;">OKX 毫秒级信号驱动</div>
    </div>''', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# 全市场实时行情雷达矩阵
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

# 中部核心：持仓动态浮盈与资产净值走势
mid_l, mid_r = st.columns([1.1, 1.9])

with mid_l:
    st.subheader("💼 当前持仓动态监控")
    if not active_pos.empty:
        # 计算持仓浮动盈亏
        merged_pos = []
        for _, p in active_pos.iterrows():
            coin = p["coin"]
            amt = p["amount"]
            avg_cost = p["avg_cost"]
            cur_price = avg_cost
            if not tickers_df.empty and coin in tickers_df["coin"].values:
                cur_price = tickers_df[tickers_df["coin"] == coin]["price"].values[0]
            unrealized = (cur_price - avg_cost) * amt
            roi = ((cur_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0
            merged_pos.append({
                "标的": coin,
                "持仓量": f"{amt:.4f}",
                "开仓均价": f"${avg_cost:,.2f}",
                "当前市价": f"${cur_price:,.2f}",
                "浮动盈亏": f"${unrealized:+,.2f} ({roi:+.2f}%)"
            })
        st.dataframe(pd.DataFrame(merged_pos), use_container_width=True, hide_index=True)
    else:
        st.info("当前暂无持仓，策略引擎正在监听金叉建仓信号...")

    st.markdown("#### ⚙️ 策略执行配置")
    st.markdown("""
    * **主控模型**：MA17 / MA30 双均线金叉做多，死叉平仓
    * **仓位风控**：单笔最大动用 80% 可用资金，0.02% 滑点保护
    * **响应频率**：30 秒周期级 K 线扫描
    """)

with mid_r:
    st.subheader("📈 模拟账户资产净值走势")
    # 生成净值曲线
    if not trades.empty:
        trade_curve = trades.iloc[::-1].copy()
        trade_curve["cum_pnl"] = trade_curve["realized_pnl"].cumsum()
        trade_curve["equity"] = acc["initial_balance"] + trade_curve["cum_pnl"]
        fig_equity = px.line(trade_curve, x="time", y="equity", markers=True, title="Account Equity Growth")
        fig_equity.update_layout(
            template="plotly_dark",
            margin=dict(l=20, r=20, t=30, b=20),
            height=250,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_equity, use_container_width=True)
    else:
        # 空数据默认曲线
        dates = pd.date_range(end=datetime.now(), periods=5, freq='H')
        df_dummy = pd.DataFrame({"time": dates, "equity": [100000.0]*5})
        fig_equity = px.line(df_dummy, x="time", y="equity", title="Account Equity Growth (Initial: $100,000)")
        fig_equity.update_layout(template="plotly_dark", height=250, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_equity, use_container_width=True)

st.divider()

# 底部：流水与风控操作
bot_l, bot_r = st.columns([2, 1])

with bot_l:
    st.subheader("📜 最新自动化撮合交易流水 (最近 10 笔)")
    if not trades.empty:
        st.dataframe(trades[["time", "coin", "side", "price", "amount", "cost", "realized_pnl"]], use_container_width=True, hide_index=True)
    else:
        st.info("暂无历史成交记录。")

with bot_r:
    st.subheader("🛡️ 控制台与紧急风控")
    st.caption("手动介入或重置系统测试环境")
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
        st.success("账户状态已重置！")
        st.rerun()
