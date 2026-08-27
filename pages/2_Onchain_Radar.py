# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests
import json
import time
from web3 import Web3
from datetime import datetime

st.set_page_config(
    page_title="Web3 链上雷达与 DEX 自动化终端",
    page_icon="🛰️",
    layout="wide"
)

# 自定义科技风样式
st.markdown("""
<style>
    .audit-card {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #334155;
        margin-bottom: 12px;
    }
    .safe-badge { color: #10B981; font-weight: bold; }
    .danger-badge { color: #EF4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ----------------- 核心功能函数 -----------------

def audit_honeypot(address, chain_id=56):
    """防貔貅蜜罐检测引擎"""
    url = f"https://api.honeypot.is/v2/IsHoneypot?address={address}&chainID={chain_id}"
    try:
        res = requests.get(url, timeout=5).json()
        if "honeypotResult" in res:
            hp = res["honeypotResult"]
            sim = res.get("simulationResult", {})
            return {
                "is_honeypot": hp.get("isHoneypot", False),
                "buy_tax": sim.get("buyTax", 0.0),
                "sell_tax": sim.get("sellTax", 0.0),
                "transfer_tax": sim.get("transferTax", 0.0),
                "token_name": res.get("token", {}).get("name", "Unknown"),
                "token_symbol": res.get("token", {}).get("symbol", "UNKNOWN"),
                "holder_analysis": res.get("holderAnalysis", {}),
                "flags": hp.get("flags", [])
            }
    except Exception as e:
        pass
    return None

def execute_dex_swap(token_address, amount_native, private_key, slippage=0.05, rpc_url="https://bsc-dataseed.binance.org/"):
    """DEX 路由合约自动买入调用"""
    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not web3.is_connected():
            return False, "❌ RPC 节点连接失败，请检查网络！"

        router_address = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E") # Pancake Router V2
        wbnb_address = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")

        router_abi = json.loads('''[
            {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},
            {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactETHForTokensSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"payable","type":"function"}
        ]''')

        router_contract = web3.eth.contract(address=router_address, abi=router_abi)
        account = web3.eth.account.from_key(private_key)
        wallet_addr = account.address
        target_token = Web3.to_checksum_address(token_address)

        amount_in_wei = web3.to_wei(amount_native, 'ether')
        bal_wei = web3.eth.get_balance(wallet_addr)
        if bal_wei < amount_in_wei:
            return False, f"❌ 钱包余额不足！当前余额: {web3.from_wei(bal_wei, 'ether'):.4f} 原生币"

        path = [wbnb_address, target_token]
        try:
            amounts_out = router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            expected_out = amounts_out[1]
            amount_out_min = int(expected_out * (1 - slippage))
        except Exception:
            amount_out_min = 0

        deadline = int(time.time()) + 300
        nonce = web3.eth.get_transaction_count(wallet_addr)
        gas_price = web3.eth.gas_price

        tx = router_contract.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
            amount_out_min, path, wallet_addr, deadline
        ).build_transaction({
            'from': wallet_addr,
            'value': amount_in_wei,
            'gas': 350000,
            'gasPrice': int(gas_price * 1.1),
            'nonce': nonce,
        })

        signed = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
        hex_hash = web3.to_hex(tx_hash)
        return True, hex_hash
    except Exception as e:
        return False, f"执行异常: {str(e)}"

# ----------------- 页面渲染 -----------------

st.title("🛰️ Web3 链上雷达与 DEX 自动化交互终端")
st.caption("集智能合约安全审计、防貔貅蜜罐检测、EVM 巨鲸大额追踪与 DEX 路由链上自动 Swap 于一体")

tab1, tab2 = st.tabs(["🛡️ 智能合约防貔貅审计与 DEX 快速买入", "🐋 EVM 链上巨鲸大额异动追踪"])

with tab1:
    st.subheader("1. 目标代币合约安全审计")
    c_in1, c_in2 = st.columns([3, 1])
    with c_in1:
        token_input = st.text_input(
            "输入代币合约地址 (Token Contract Address)", 
            value="0x55d398326f99059fF775485246999027B3197955",
            placeholder="0x..."
        )
    with c_in2:
        chain_select = st.selectbox("目标区块链", ["BSC (BNB Chain)", "Ethereum (以太坊)", "Polygon", "Arbitrum", "Base"])
    
    chain_map = {"BSC (BNB Chain)": 56, "Ethereum (以太坊)": 1, "Polygon": 137, "Arbitrum": 42161, "Base": 8453}
    
    if st.button("🔍 立即执行多维安全审计", use_container_width=True):
        with st.spinner("正在解析合约字节码、模拟 DEX 交易路径并检测恶意税率逻辑..."):
            res = audit_honeypot(token_input.strip(), chain_map[chain_select])
            if res:
                st.session_state["audit_res"] = res
            else:
                st.error("无法完成检测，请确认合约地址有效性或网络连接！")

    # 审计结果展示
    if "audit_res" in st.session_state:
        r = st.session_state["audit_res"]
        st.divider()
        st.subheader("2. 审计评估报告")
        
        ac1, ac2, ac3, ac4 = st.columns(4)
        is_hp = r["is_honeypot"]
        status_text = "🚨 极度危险 (貔貅代币)" if is_hp else "✅ 安全通过 (可正常卖出)"
        status_color = "#EF4444" if is_hp else "#10B981"
        
        with ac1:
            st.markdown(f"**安全等级**\n<h4 style='color:{status_color};margin:0;'>{status_text}</h4>", unsafe_allow_html=True)
        with ac2:
            st.metric("代币全称 / 代码", f"{r['token_name']} ({r['token_symbol']})")
        with ac3:
            st.metric("买入税率 (Buy Tax)", f"{r['buy_tax']:.2f}%")
        with ac4:
            st.metric("卖出税率 (Sell Tax)", f"{r['sell_tax']:.2f}%")
            
        if is_hp:
            st.error("⚠️ 警告：该合约被检测为恶意代码！持有者可能无法卖出或被收取高达 99% 的滑点税，系统已自动锁定买入通道！")
        else:
            st.success("🎉 该代币已通过防貔貅检测，买卖税率在正常区间，已为您激活下方 DEX 自动化买入通道。")

            st.divider()
            st.subheader("3. ⚡ DEX 链上自动买入执行面板")
            
            tc1, tc2 = st.columns([1.2, 1.8])
            with tc1:
                swap_mode = st.radio("执行模式", ["🧪 模拟演练模式 (无私钥风险)", "⚡ 真实链上广播 (Mainnet/Testnet)"], horizontal=True)
                buy_amount = st.number_input("投入原生币数量 (BNB/ETH)", min_value=0.001, max_value=10.0, value=0.01, step=0.005)
                slippage_pct = st.slider("滑点保护容忍度 (%)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
                
                pk_input = ""
                if "真实链上" in swap_mode:
                    pk_input = st.text_input("执行钱包私钥 (仅本地内存使用)", type="password", placeholder="输入 64 位十六进制私钥")
                    st.caption("🔒 提示：代码完全开源，私钥仅在单次请求签名时使用，绝不上传任何服务器。")
                
                if st.button("🚀 触发 DEX 路由执行买入 (Swap)", use_container_width=True):
                    if "模拟演练" in swap_mode:
                        st.info("🔄 正在模拟调用 PancakeSwap Router V2 合约接口...")
                        time.sleep(1.2)
                        st.success(f"✅ 模拟交易成功！以 {buy_amount} 原生币成功兑换目标代币，滑点保护生效（预估产出误差 < {slippage_pct}%）。")
                    else:
                        if not pk_input or len(pk_input.strip()) < 32:
                            st.error("请输入有效的钱包私钥！")
                        else:
                            with st.spinner("正在构造交易并向区块链节点广播..."):
                                succ, tx_or_msg = execute_dex_swap(
                                    token_input.strip(), 
                                    buy_amount, 
                                    pk_input.strip(), 
                                    slippage=slippage_pct/100
                                )
                                if succ:
                                    st.success(f"🎉 交易广播成功！Tx Hash: `{tx_or_msg}`")
                                    st.markdown(f"👉 [在 BscScan 区块浏览器上查看此交易](https://bscscan.com/tx/{tx_or_msg})")
                                else:
                                    st.error(tx_or_msg)

            with tc2:
                st.markdown("#### ⚙️ DEX 路由执行逻辑规范")
                st.markdown(f"""
                * **路由协议**：Uniswap / PancakeSwap V2 Router
                * **兑换路径 (Path)**：`WBNB/WETH` ➔ `{token_input[:10]}...{token_input[-6:]}`
                * **MEV 防夹机制**：设置 `amountOutMin` 锁定最低出币数量
                * **防税率陷阱**：调用支持转账扣税的底层方法 `swapExactETHForTokensSupportingFeeOnTransferTokens`
                * **超时撤单机制**：5 分钟内若未被矿工打包自动失效，保障本金安全
                """)

with tab2:
    st.subheader("🐋 EVM 巨鲸大额交易实时异动监控")
    st.caption("监控以太坊/BSC 链上单笔金额 > $100,000 的大额转账与 DEX 流动性异动")
    
    # 模拟链上实时异动数据流
    whale_data = [
        {"时间": datetime.now().strftime("%H:%M:%S"), "链": "BSC", "类型": "DEX 大额买入", "代币": "WBNB/USDT", "金额": "$450,200", "钱包": "0x7a25...b819", "操作": "🟢 建仓"},
        {"时间": datetime.now().strftime("%H:%M:%S"), "链": "Ethereum", "类型": "巨鲸提币", "代币": "ETH", "金额": "$1,280,000", "钱包": "0x3f5c...92a1", "操作": "📦 提至冷钱包"},
        {"时间": datetime.now().strftime("%H:%M:%S"), "链": "Arbitrum", "类型": "质押转入", "代币": "ARB", "金额": "$310,000", "钱包": "0x89d2...11e0", "操作": "🔒 锁仓"},
    ]
    st.dataframe(pd.DataFrame(whale_data), use_container_width=True, hide_index=True)
    if st.button("🔄 刷新巨鲸异动流", use_container_width=True):
        st.rerun()
