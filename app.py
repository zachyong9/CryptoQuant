# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

st.set_page_config(
    page_title="Crypto Radar - Web3 智能量化交易终端",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 样式美化
st.markdown("""
<style>
    .metric-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        color: white;
    }
    .status-running {
        color: #10B981;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = "paper_trading.db"

# 数据库安全初始化与读取
def init_and_get_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS account
                 (id INTEGER PRIMARY KEY, balance REAL, initial_balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS positions
                 (coin TEXT PRIMARY KEY, amount REAL, avg_cost REAL, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, coin TEXT, side TEXT, 
                  price REAL, amount REAL, cost REAL, realized_pnl REAL)''')
    
    # 检查 account 是否有记录
    c.execute("SELECT balance, initial_balance FROM account WHERE id = 1")
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO account (id, balance, initial_balance) VALUES (1, 100000.0, 100000.0)")
        conn.commit()
        balance, init_balance = 100000.0, 100000.0
    else:
        balance, init_balance = row[0], row[1]
        
    pos = pd.read_sql("SELECT * FROM positions", conn)
    trades = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    
    return {"balance": balance, "initial_balance": init_balance}, pos, trades

acc, pos, trades = init_and_get_data()

st.title("⚡ Crypto Radar - Web3 智能量化交易终端")
st.caption("集行情多因子监控、链上巨鲸雷达、智能合约安全审计与 24H 自动量化撮合于一体的全栈交易控制台")

# 顶栏核心数据卡片
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'''<div class="metric-box">
        <div style="color:#94a3b8;font-size:13px;">账户可用资金 (USDT)</div>
        <div style="font-size:24px;font-weight:700;">${acc["balance"]:,.2f}</div>
        <div style="color:#10b981;font-size:12px;">初始本金: ${acc["initial_balance"]:,.2f}</div>
    </div>''', unsafe_allow_html=True)

with c2:
    holdings_count = len(pos[pos['amount'] > 0]) if not pos.empty else 0
    st.markdown(f'''<div class="metric-box">
        <div style="color:#94a3b8;font-size:13px;">当前活跃持仓</div>
        <div style="font-size:24px;font-weight:700;">{holdings_count} <span style="font-size:14px;color:#94a3b8;">个币种</span></div>
        <div style="color:#38bdf8;font-size:12px;">实时动态跟踪</div>
    </div>''', unsafe_allow_html=True)

with c3:
    total_trades = len(trades) if not trades.empty else 0
    st.markdown(f'''<div class="metric-box">
        <div style="color:#94a3b8;font-size:13px;">历史撮合总笔数</div>
        <div style="font-size:24px;font-weight:700;">{total_trades} <span style="font-size:14px;color:#94a3b8;">笔</span></div>
        <div style="color:#a855f7;font-size:12px;">包含自动与手动策略</div>
    </div>''', unsafe_allow_html=True)

with c4:
    st.markdown('''<div class="metric-box">
        <div style="color:#94a3b8;font-size:13px;">24H 策略托管状态</div>
        <div class="status-running" style="font-size:22px;margin-top:2px;">● RUNNING (在线)</div>
        <div style="color:#94a3b8;font-size:12px;">MA17/MA30 趋势捕捉</div>
    </div>''', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# 左右分栏
left_col, right_col = st.columns([1.2, 1.8])

with left_col:
    st.subheader("💼 当前持仓明细")
    if not pos.empty and pos['amount'].sum() > 0:
        st.dataframe(pos, use_container_width=True, hide_index=True)
    else:
        st.info("当前暂无持仓，策略机器人正在等待最佳开仓信号...")

    st.divider()
    st.subheader("🤖 自动化策略运行配置")
    st.markdown("""
    * **监听标的**：`BTC-USDT`、`ETH-USDT`、`SOL-USDT`
    * **主控模型**：双均线金叉做多 / 死叉平仓
    * **风控规则**：单笔投入 80% 可用仓位，固定滑点保护 (0.02%)
    * **调度间隔**：30 秒自动轮询一次 OKX 市场深度
    """)

with right_col:
    st.subheader("📜 最新交易流水与撮合记录")
    if not trades.empty:
        st.dataframe(trades, use_container_width=True, hide_index=True)
    else:
        st.info("暂无历史成交记录。")

st.divider()
st.markdown("👈 **请在左侧侧边栏切换子页面**：\n* **`Market Quant`**：全市场主流币多因子指标分析与策略绩效回测\n* **`Onchain Radar`**：EVM 巨鲸大额追踪与智能合约防貔貅安全审计")