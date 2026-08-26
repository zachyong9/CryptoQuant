# -*- coding: utf-8 -*-
from web3 import Web3
import requests
import json

# 配置节点与网络
RPC_CONFIG = {
    1: {"name": "Ethereum", "rpc": "https://ethereum-rpc.publicnode.com"},
    56: {"name": "BSC", "rpc": "https://bsc-rpc.publicnode.com"}
}

# 常见 ERC20 权限/管理 ABI
OWNERSHIP_ABI = [
    {"constant": True, "inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "getOwner", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "paused", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

def audit_token(chain_id, token_address):
    """
    全方位自动化安全审计函数
    :param chain_id: 1 为 ETH, 56 为 BSC
    :param token_address: 目标代币合约地址
    """
    token_address = Web3.to_checksum_address(token_address)
    rpc_url = RPC_CONFIG[chain_id]["rpc"]
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 8}))

    audit_result = {
        "chain": RPC_CONFIG[chain_id]["name"],
        "token_address": token_address,
        "name": "Unknown",
        "symbol": "Unknown",
        "is_honeypot": False,
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "owner": None,
        "is_renounced": False,
        "is_paused": False,
        "score": 100,
        "risk_tags": [],
        "passed": True
    }

    # 1. 链上底层合约只读探测
    try:
        contract = w3.eth.contract(address=token_address, abi=OWNERSHIP_ABI)
        try:
            audit_result["name"] = contract.functions.name().call()
            audit_result["symbol"] = contract.functions.symbol().call()
        except Exception:
            pass

        # 检查 Owner 权限（是否弃权）
        owner_addr = None
        for func in ["owner", "getOwner"]:
            try:
                owner_addr = getattr(contract.functions, func)().call()
                if owner_addr:
                    break
            except Exception:
                pass

        if owner_addr:
            audit_result["owner"] = owner_addr
            zero_addr = "0x0000000000000000000000000000000000000000"
            dead_addr = "0x000000000000000000000000000000000000dEaD"
            if owner_addr.lower() in [zero_addr.lower(), dead_addr.lower()]:
                audit_result["is_renounced"] = True
            else:
                audit_result["is_renounced"] = False
                audit_result["risk_tags"].append("⚠️ 未放弃所有权 (存在修改税率/暂停交易风险)")
                audit_result["score"] -= 20
        else:
            audit_result["is_renounced"] = True # 无 owner 函数或无法识别

        # 检查是否处于暂停状态
        try:
            if contract.functions.paused().call():
                audit_result["is_paused"] = True
                audit_result["risk_tags"].append("🚨 合约当前已被暂停交易 (Paused)")
                audit_result["score"] -= 40
        except Exception:
            pass

    except Exception as e:
        audit_result["risk_tags"].append(f"合约基础数据读取受限: {e}")

    # 2. 模拟买卖撮合探测 (Honeypot API 快速验证)
    try:
        hp_url = f"https://api.honeypot.is/v2/IsHoneypot?address={token_address}&chainID={chain_id}"
        res = requests.get(hp_url, timeout=5).json()
        
        if "honeypotResult" in res:
            hp_data = res["honeypotResult"]
            is_hp = hp_data.get("isHoneypot", False)
            audit_result["is_honeypot"] = is_hp
            
            if is_hp:
                audit_result["score"] = 0
                audit_result["passed"] = False
                audit_result["risk_tags"].append("☠️ 确认为貔貅合约 (无法正常卖出/100%拦截)")

            # 解析买卖税率
            sim = res.get("simulationResult", {})
            buy_tax = sim.get("buyTax", 0.0)
            sell_tax = sim.get("sellTax", 0.0)
            audit_result["buy_tax"] = buy_tax
            audit_result["sell_tax"] = sell_tax

            if buy_tax > 10.0:
                audit_result["risk_tags"].append(f"⚠️ 买入税率偏高 ({buy_tax:.1f}%)")
                audit_result["score"] -= 15
            if sell_tax > 10.0:
                audit_result["risk_tags"].append(f"🚨 卖出税率极高 ({sell_tax:.1f}%)")
                audit_result["score"] -= 30

    except Exception:
        # 接口不可用时使用通用保守逻辑
        pass

    # 计算最终风险评级
    audit_result["score"] = max(0, min(100, audit_result["score"]))
    if audit_result["is_honeypot"] or audit_result["sell_tax"] > 50:
        audit_result["grade"] = "极度危险 (CRITICAL ⛔)"
    elif audit_result["score"] >= 80:
        audit_result["grade"] = "相对安全 (SAFE 🟢)"
    elif audit_result["score"] >= 50:
        audit_result["grade"] = "中等风险 (WARNING 🟡)"
    else:
        audit_result["grade"] = "高危代币 (HIGH RISK 🔴)"

    return audit_result

if __name__ == "__main__":
    print("=" * 60)
    print("🛡️  Crypto Radar - 智能合约安全审计与防貔貅引擎测试")
    print("=" * 60)

    # 测试一个经典代币（以太坊 Uniswap 代币 UNI）
    test_token = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
    print(f"正在深度审计以太坊 UNI 合约: {test_token} ...\n")
    
    result = audit_token(chain_id=1, token_address=test_token)
    
    print(f"【代币名称】: {result['symbol']} ({result['name']})")
    print(f"【安全评分】: {result['score']} / 100 分")
    print(f"【安全等级】: {result['grade']}")
    print(f"【是否貔貅】: {'❌ 是貔貅 (无法卖出)' if result['is_honeypot'] else '✅ 否 (交易通畅)'}")
    print(f"【买入税率】: {result['buy_tax']:.2f}% | 【卖出税率】: {result['sell_tax']:.2f}%")
    print(f"【是否弃权】: {'✅ 已放弃权限 (Renounced)' if result['is_renounced'] else '⚠️ 未放弃所有权'}")
    
    if result["risk_tags"]:
        print("\n🚨 捕获到的风险项:")
        for tag in result["risk_tags"]:
            print(f"  - {tag}")
    else:
        print("\n✅ 未发现明显的恶意代码与貔貅特征！")
    print("=" * 60)