"""
FinBuddy Trading System - Google Cloud Functions Demo
執行回測並推送 recommendation 到 Line
"""
import functions_framework
from libs import SimulatedMarket, MaxSharpeStrategy, Trader
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
import json

# Line Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = 'Es+feMvp7Uwg+nIcgB66iAKWVD1dOKRcXzYwPmSbko+b0Vf21iko3s7dRwEFX1tfToR8mrW78XUACEd/uyecCF/Uqd9LgvkchpPEPiODdX4L8BU4b6pXHzFvlDoAfsP9xIFSMG+rmVzQURS+7uBnegdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'YOUR_CHANNEL_SECRET'  # 需要從 Line Developers 取得
LINE_USER_ID = 'Udba3ff0abbe6607af5a5cfc2e2ddc8a1'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

WELCOME_MESSAGE = """━━━━━━━━━━━━━━━━━━━━━━
🎉 歡迎使用 FinBuddy！
━━━━━━━━━━━━━━━━━━━━━━

👋 您好！我是您的智能投資助手

📊 主要功能：
  • 每日股市操盤建議
  • AI 策略回測分析
  • 即時市場趨勢判讀
  • 個股產業配置推薦

💡 使用說明：
  1️⃣ 每日自動推送：
     系統會在固定時間推送當日
     交易建議給您

  2️⃣ 建議內容包含：
     • 推薦持倉配置
     • 市場概況分析
     • 操作建議提醒

  3️⃣ 策略特色：
     • 基於 Sharpe Ratio 選股
     • 多頻率回測優化
     • 產業趨勢追蹤

⚠️ 風險提示：
本系統提供的建議僅供參考，投資
有風險，請謹慎評估後再做決策。

━━━━━━━━━━━━━━━━━━━━━━
📈 祝您投資順利！
━━━━━━━━━━━━━━━━━━━━━━"""

def LineBotMessage(text='Test', user_id=None):
    """發送 Line 訊息"""
    target_id = user_id or LINE_USER_ID
    line_bot_api.push_message(target_id, TextSendMessage(text=text))

@handler.add(FollowEvent)
def handle_follow(event):
    """處理加好友事件"""
    user_id = event.source.user_id
    LineBotMessage(WELCOME_MESSAGE, user_id=user_id)

@functions_framework.http
def hello_http(request):
    """主要入口 - 處理 webhook 和交易建議推送"""
    
    # 處理 Line Webhook (加好友、訊息等事件)
    if request.method == 'POST':
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)
        
        try:
            handler.handle(body, signature)
            return 'OK'
        except InvalidSignatureError:
            print('Invalid signature')
            return 'Invalid signature', 400
    
    # 處理 GET 請求 - 執行回測並推送建議
    # 解析參數
    topk = int(request.args.get('topk', 10))
    
    # 初始化市場模擬器（只需執行一次）
    _market_simulator = SimulatedMarket(
        watchlist_id="118349730",
        session_id="b379eetq1pojcel6olyymmpo1rd41nng"
    )
    _market_simulator.build_portfolio_data(
        sharpe_window=252, 
        slope_window=365, 
        ma_period=30
    )
    print("✅ Market simulator initialized")
    
    # 執行回測（比較不同 rebalance 頻率）
    print("🔄 Running backtest...")
    traders = [
        Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk), rebalance_frequency='daily'),
        Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk), rebalance_frequency='weekly'),
        Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk), rebalance_frequency='monthly'),
        Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk), rebalance_frequency='quarterly'),
        Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk), rebalance_frequency='yearly')
    ]
    _market_simulator.run(traders)
    print("✅ Backtest completed")
    
    # 生成交易建議
    recommendation = _market_simulator.get_trading_recommendation(MaxSharpeStrategy(topk=topk))
    LineBotMessage(recommendation)
    
    return ""