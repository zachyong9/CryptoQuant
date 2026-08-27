# -*- coding: utf-8 -*-
"""
Crypto Radar - 多通道实时通知引擎 (Telegram & Webhook)
"""
import requests
from datetime import datetime

class AlertNotifier:
    def __init__(self, tg_bot_token=None, tg_chat_id=None, webhook_url=None):
        self.tg_bot_token = tg_bot_token
        self.tg_chat_id = tg_chat_id
        self.webhook_url = webhook_url

    def send_telegram(self, text: str):
        """发送 Telegram 消息"""
        if not self.tg_bot_token or not self.tg_chat_id:
            return False, "未配置 Telegram Token 或 Chat ID"
        
        url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
        payload = {
            "chat_id": self.tg_chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=5)
            res = r.json()
            if res.get("ok"):
                return True, "Telegram 推送成功"
            else:
                return False, res.get("description", "发送失败")
        except Exception as e:
            return False, f"网络请求异常: {str(e)}"

    def send_webhook(self, title: str, text: str):
        """支持飞书 / 钉钉 / 自定义 Webhook 推送"""
        if not self.webhook_url:
            return False, "未配置 Webhook URL"
        
        # 兼容飞书 Webhook 格式
        payload = {
            "msg_type": "text",
            "content": {"text": f"🔔 【{title}】\n{text}"}
        }
        try:
            r = requests.post(self.webhook_url, json=payload, timeout=5)
            return True, "Webhook 推送成功"
        except Exception as e:
            return False, f"Webhook 推送失败: {str(e)}"

    def notify_trade(self, coin, side, price, amount, leverage=1, pnl=0.0, channel="tg"):
        """统一成交通知模板"""
        now_t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        side_icon = "🟢 做多/买入" if "BUY" in side or "LONG" in side else "🔴 做空/平仓"
        
        msg = f"""⚡ <b>Crypto Radar - 策略成交提醒</b>
━━━━━━━━━━━━━━━━━
📌 <b>交易标的</b>: <code>{coin}</code> ({leverage}X 杠杆)
🎯 <b>操作方向</b>: <b>{side_icon}</b>
💵 <b>成交均价</b>: ${price:,.2f}
📦 <b>成交数量</b>: {amount:.4f}
💰 <b>结算盈亏</b>: ${pnl:+,.2f}
⏰ <b>执行时间</b>: {now_t}
━━━━━━━━━━━━━━━━━
<i>🤖 来自 Crypto Radar 24H 自动量化交易引擎</i>"""
        
        if channel == "tg" and self.tg_bot_token:
            return self.send_telegram(msg)
        elif self.webhook_url:
            return self.send_webhook("交易撮合成交", f"{coin} {side_icon} @ ${price:,.2f}")
        return False, "未配置有效推送通道"

    def notify_whale(self, chain, coin, amount_usd, tx_hash):
        """巨鲸大额异动通知模板"""
        msg = f"""🐋 <b>Crypto Radar - 链上巨鲸异动警报</b>
━━━━━━━━━━━━━━━━━
🌐 <b>公链网络</b>: {chain}
💎 <b>异动币种</b>: {coin}
💰 <b>涉及金额</b>: <b>{amount_usd}</b>
🔍 <b>交易哈希</b>: <code>{tx_hash[:16]}...{tx_hash[-8:]}</code>
━━━━━━━━━━━━━━━━━
<i>🛰️ 来自 EVM 智能合约安全雷达</i>"""
        if self.tg_bot_token:
            return self.send_telegram(msg)
        return False, "未配置有效推送通道"

# 默认全局实例
notifier = AlertNotifier()
