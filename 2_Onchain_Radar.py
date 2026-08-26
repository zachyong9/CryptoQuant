# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from web3 import Web3
from hexbytes import HexBytes
from datetime import datetime
import requests
import time

st.set_page_config(
    page_title="Web3 链上情报与合约安全审计中心",
    page_icon="⚡",
    layout="wide"
)

# 注入科技风 CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e2638 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 16px 20px;
        color: white;
    }
    .metric-title { font-size: 13px; color: #9CA3AF; margin-bottom: 6px; text-transform: uppercase; }
    .metric-value { font-size: 24px; font-weight: 700; color: #F3F4F6; }
    .metric-sub { font-size: 12px; color: #10B981; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

NETWORKS = {
    "Ethereum (以太坊主网)": {
        "chain_id": 1,
        "rpc": "https://ethereum-rpc.publicnode.com",
        "symbol": "ETH",
        "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "explorer": "https://etherscan.io/tx/",
        "tokensniffer": "https://tokensniffer.com/token/eth/"
    },
    "BSC (币安智能链)": {
        "chain_id": 56,
        "rpc": "https://bsc-rpc.publicnode.com",
        "symbol": "BNB",
        "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "usdt": "0x55d398326f99059fF775485246999027B3197955",
        "explorer": "https://bscscan.com/tx/",
        "tokensniffer": "https://tokensniffer.com/token/bsc/"
    }
}

PAIR_CREATED_TOPIC = Web3.keccak(text="PairCreated(address,address,address,uint256)")
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)")

ERC20_MINI_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
]

BASE_TOKENS = {
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "WETH",
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c": "WBNB",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
    "0x55d398326f99059fF775485246999027B3197955": "USDT",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC"
}

# 侧边栏控制
st.sidebar.title("⚙️ 链上情报与审计配置")
selected_net = st.sidebar.selectbox("选择监听主网", list(NETWORKS.keys()))
net_info = NETWORKS[selected_net]

scan_depth = st.sidebar.slider("区块扫描深度", min_value=1, max_value=6, value=3, step=1)
native_threshold = st.sidebar.number_input(f"{net_info['symbol']} 巨鲸阈值", min_value=1.0, value=20.0, step=5.0)
usdt_threshold = st.sidebar.number_input("USDT 巨鲸阈值 ($)", min_value=1000.0, value=50000.0, step=10000.0)

if st.sidebar.button("🔄 立即重新扫描区块", use_container_width=True):
    st.rerun()

w3 = Web3(Web3.HTTPProvider(net_info["rpc"], request_kwargs={'timeout': 8}))

st.title("⚡ Web3 链上情报与智能合约安全审计中心")
st.caption(f"网络: {selected_net} · 巨鲸大额异动追踪 · 一级市场新池 0 秒抓取 · 自动化防貔貅 (HoneyPot) 检测")

if not w3.is_connected():
    st.error(f"❌ 无法连接到 {selected_net} 节点，请检查网络！")
    st.stop()

try:
    latest_block = w3.eth.block_number
    gas_price_gwei = float(w3.from_wei(w3.eth.gas_price, 'gwei'))
except Exception as e:
    st.error(f"读取链上状态失败: {e}")
    st.stop()

def decode_address(topic_item):
    hex_str = topic_item.hex() if isinstance(topic_item, (bytes, HexBytes)) else str(topic_item)
    clean = hex_str.replace("0x", "")
    return Web3.to_checksum_address("0x" + clean[-40:])

def get_token_info(token_address):
    checksum_addr = Web3.to_checksum_address(token_address)
    if checksum_addr in BASE_TOKENS:
        return BASE_TOKENS[checksum_addr], BASE_TOKENS[checksum_addr]
    contract = w3.eth.contract(address=checksum_addr, abi=ERC20_MINI_ABI)
    try:
        symbol = contract.functions.symbol().call()
    except Exception:
        symbol = "UNKNOWN"
    try:
        name = contract.functions.name().call()
    except Exception:
        name = "Unknown Token"
    return name, symbol

def quick_audit_token(chain_id, token_addr):
    """新币自动化审计快速评估"""
    try:
        hp_url = f"https://api.honeypot.is/v2/IsHoneypot?address={token_addr}&chainID={chain_id}"
        res = requests.get(hp_url, timeout=3).json()
        if "honeypotResult" in res:
            is_hp = res["honeypotResult"].get("isHoneypot", False)
            sim = res.get("simulationResult", {})
            b_tax = sim.get("buyTax", 0.0)
            s_tax = sim.get("sellTax", 0.0)
            if is_hp:
                return "⛔ 貔貅合约", f"买:{b_tax:.0f}% 卖:{s_tax:.0f}%", "CRITICAL"
            elif s_tax > 20:
                return f"⚠️ 高税盘 ({s_tax:.0f}%)", f"买:{b_tax:.0f}% 卖:{s_tax:.0f}%", "WARNING"
            else:
                return "🟢 安全通过", f"买:{b_tax:.0f}% 卖:{s_tax:.0f}%", "SAFE"
    except Exception:
        pass
    return "⚪ 待验证", "税率未知", "NEUTRAL"

# 扫描逻辑
whale_records = []
pair_records = []
start_block = latest_block - scan_depth + 1

with st.spinner(f"正在深度扫描区块 #{start_block} 至 #{latest_block} ..."):
    for b in range(start_block, latest_block + 1):
        try:
            # 1. 扫描原生代币交易
            block = w3.eth.get_block(b, full_transactions=True)
            block_time = datetime.fromtimestamp(block['timestamp']).strftime('%H:%M:%S')
            for tx in block['transactions']:
                if tx.get('to') and tx.get('value'):
                    val_native = float(w3.from_wei(tx['value'], 'ether'))
                    if val_native >= native_threshold:
                        tx_h = tx['hash'].hex() if isinstance(tx['hash'], (bytes, HexBytes)) else str(tx['hash'])
                        tx_h = tx_h if tx_h.startswith("0x") else f"0x{tx_h}"
                        whale_records.append({
                            "捕获时间": block_time,
                            "区块": b,
                            "类型": f"{net_info['symbol']} 异动",
                            "金额 (数值)": val_native,
                            "展示金额": f"{val_native:,.2f} {net_info['symbol']}",
                            "发送方": f"{tx['from'][:6]}...{tx['from'][-4:]}",
                            "接收方": f"{tx['to'][:6]}...{tx['to'][-4:]}",
                            "哈希链接": f"{net_info['explorer']}{tx_h}"
                        })

            # 2. 扫描 USDT 巨鲸
            usdt_addr = Web3.to_checksum_address(net_info["usdt"])
            usdt_logs = w3.eth.get_logs({
                'fromBlock': b, 'toBlock': b,
                'address': usdt_addr, 'topics': [TRANSFER_TOPIC]
            })
            for log in usdt_logs:
                if len(log.get('topics', [])) >= 3:
                    from_addr = decode_address(log['topics'][1])
                    to_addr = decode_address(log['topics'][2])
                    data_bytes = log['data'] if isinstance(log['data'], (bytes, HexBytes)) else HexBytes(log['data'])
                    decimals = 6 if "Ethereum" in selected_net else 18
                    usdt_val = int(data_bytes.hex(), 16) / (10 ** decimals)
                    if usdt_val >= usdt_threshold:
                        tx_h = log['transactionHash'].hex() if isinstance(log['transactionHash'], (bytes, HexBytes)) else str(log['transactionHash'])
                        tx_h = tx_h if tx_h.startswith("0x") else f"0x{tx_h}"
                        whale_records.append({
                            "捕获时间": block_time,
                            "区块": b,
                            "类型": "USDT 巨鲸",
                            "金额 (数值)": usdt_val,
                            "展示金额": f"${usdt_val:,.2f} USDT",
                            "发送方": f"{from_addr[:6]}...{from_addr[-4:]}",
                            "接收方": f"{to_addr[:6]}...{to_addr[-4:]}",
                            "哈希链接": f"{net_info['explorer']}{tx_h}"
                        })

            # 3. 扫描 DEX 新建池并自动审计
            factory_addr = Web3.to_checksum_address(net_info["factory"])
            pair_logs = w3.eth.get_logs({
                'fromBlock': b, 'toBlock': b,
                'address': factory_addr, 'topics': [PAIR_CREATED_TOPIC]
            })
            for log in pair_logs:
                t0 = decode_address(log['topics'][1])
                t1 = decode_address(log['topics'][2])
                target_token = t1 if t0 in BASE_TOKENS else t0
                n0, s0 = get_token_info(t0)
                n1, s1 = get_token_info(t1)
                target_sym = s1 if t0 in BASE_TOKENS else s0
                
                # 自动触发安全审计
                audit_status, tax_info, risk_level = quick_audit_token(net_info["chain_id"], target_token)

                tx_h = log['transactionHash'].hex() if isinstance(log['transactionHash'], (bytes, HexBytes)) else str(log['transactionHash'])
                tx_h = tx_h if tx_h.startswith("0x") else f"0x{tx_h}"

                pair_records.append({
                    "区块": f"#{b}",
                    "代币": target_sym,
                    "配对": f"{s0}/{s1}",
                    "安全审计": audit_status,
                    "买卖税率": tax_info,
                    "合约地址": f"{target_token[:6]}...{target_token[-4:]}",
                    "安全检测": f"{net_info['tokensniffer']}{target_token}",
                    "哈希": f"{net_info['explorer']}{tx_h}"
                })
        except Exception:
            pass

# 顶栏指标卡
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-title">最新区块高度</div><div class="metric-value">#{latest_block}</div><div class="metric-sub">● 正常同步</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-title">实时 Gas 单价</div><div class="metric-value">{gas_price_gwei:.2f} <span style="font-size:15px;color:#9CA3AF;">Gwei</span></div><div class="metric-sub">网络通畅</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-title">巨鲸大额交易</div><div class="metric-value">{len(whale_records)} <span style="font-size:15px;color:#9CA3AF;">笔</span></div><div class="metric-sub">扫描深度 {scan_depth} 块</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="metric-title">新上线 DEX 交易对</div><div class="metric-value">{len(pair_records)} <span style="font-size:15px;color:#9CA3AF;">个</span></div><div class="metric-sub">自动防貔貅审计已开启</div></div>', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# 巨鲸与新池展示
left_tab, right_tab = st.columns([1, 1])

with left_tab:
    st.subheader(f"🐋 巨鲸流动分布 ({len(whale_records)} 笔)")
    if whale_records:
        df_show = pd.DataFrame(whale_records)[["捕获时间", "区块", "类型", "展示金额", "发送方", "接收方", "哈希链接"]]
        df_show['区块浏览器'] = df_show['哈希链接'].apply(lambda x: f'<a href="{x}" target="_blank" style="color:#60A5FA;text-decoration:none;">查看 ↗</a>')
        df_show = df_show.drop(columns=['哈希链接'])
        st.write(df_show.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("所选区块范围内暂无超阈值异动。")

with right_tab:
    st.subheader(f"🚀 一级市场新池与安全审计 ({len(pair_records)} 个)")
    if pair_records:
        df_p = pd.DataFrame(pair_records)
        df_p['审计报告'] = df_p['安全检测'].apply(lambda x: f'<a href="{x}" target="_blank" style="color:#34D399;text-decoration:none;">TokenSniffer ↗</a>')
        df_p['交易'] = df_p['哈希'].apply(lambda x: f'<a href="{x}" target="_blank" style="color:#60A5FA;text-decoration:none;">Etherscan ↗</a>')
        df_p = df_p.drop(columns=['安全检测', '哈希'])
        st.write(df_p.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("所选区块范围内暂无新创建的 DEX 交易对。")

st.divider()

# 手动精准审计工具箱
st.subheader("🛡️ 任意代币智能合约深度审计工具箱")
audit_col1, audit_col2 = st.columns([2.5, 1])

with audit_col1:
    input_contract = st.text_input("输入待检测的代币智能合约地址 (EVM 格式):", placeholder="0x...")

with audit_col2:
    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
    start_audit_btn = st.button("🔍 执行全面安全审计", use_container_width=True)

if start_audit_btn and input_contract:
    if not Web3.is_address(input_contract):
        st.error("请输入合法的以太坊/BSC 合约地址！")
    else:
        with st.spinner("正在连接智能合约、模拟买卖撮合与反编译安全探测..."):
            from contract_auditor import audit_token
            res = audit_token(net_info["chain_id"], input_contract)
            
            c_score, c_grade, c_tax = st.columns(3)
            with c_score:
                st.metric("综合安全评分", f"{res['score']} / 100 分")
            with c_grade:
                st.metric("安全风险等级", res["grade"])
            with c_tax:
                st.metric("买入 / 卖出税率", f"{res['buy_tax']:.1f}% / {res['sell_tax']:.1f}%")

            if res["risk_tags"]:
                st.error("🚨 审计发现以下风险点：\n" + "\n".join([f"- {t}" for t in res["risk_tags"]]))
            else:
                st.success("✅ 合约代码未发现恶意后门，未发现貔貅逻辑，所有权已弃权或无高危操作！")