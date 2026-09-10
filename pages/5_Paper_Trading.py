# -*- coding: utf-8 -*-
"""
Market Deep Dive - 多资产深度行情与多空博弈 (仅保留数据分析与技术指标)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="Apex Intel | 市场深度看板",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #d1d5db; }
    .metric-card {
        background: #151a23;
        border: 1px solid #232936;
        border-radius: 8px;
        padding: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 **多资产深度行情与多空持仓博弈**")
st.caption("展示主流加密货币与美股核心指数的实时动量与技术指标分析")

# 标的定义
ASSETS = {
    "BTC/USDT": {"type": "Crypto", "base": 78610.0},
    "ETH/USDT": {"type": "Crypto", "base": 2488.0},
    "SOL/USDT": {"type": "Crypto", "base": 102.9},
    "NVDA (英伟达)": {"type": "US_Stock", "base": 128.5},
    "TSLA (特斯拉)": {"type": "US_Stock", "base": 235.4},
    "QQQ (纳指ETF)": {"type": "US_Stock", "base": 478.6},
}

selected = st.selectbox("选择分析标的", list(ASSETS.keys()), index=0)

# 生成模拟深度走势图
np.random.seed(42)
periods = 60
base_px = ASSETS[selected]["base"]
changes = np.random.normal(0, base_px * 0.003, periods)
prices = base_px + np.cumsum(changes)
times = pd.date_range(end=pd.Timestamp.now(), periods=periods, freq='5min')

fig = go.Figure()
fig.add_trace(go.Scatter(x=times, y=prices, mode='lines', line=dict(color='#2962ff', width=2), name="价格走势"))
fig.update_layout(
    template="plotly_dark",
    plot_bgcolor="#11151c",
    paper_bgcolor="#11151c",
    height=380,
    margin=dict(l=20, r=20, t=20, b=20),
    xaxis=dict(gridcolor="#1f2633"),
    yaxis=dict(gridcolor="#1f2633")
)
st.plotly_chart(fig, use_container_width=True)

# 指标分析
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:12px; color:#848e9c;">24H 波动率</div>
        <div style="font-size:22px; font-weight:700; color:#0ecb81; margin-top:4px;">3.42%</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:12px; color:#848e9c;">RSI (14)</div>
        <div style="font-size:22px; font-weight:700; color:#2962ff; margin-top:4px;">54.8 (中性)</div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size:12px; color:#848e9c;">主力资金流向</div>
        <div style="font-size:22px; font-weight:700; color:#0ecb81; margin-top:4px;">+$18.4M 净流入</div>
    </div>
    """, unsafe_allow_html=True)