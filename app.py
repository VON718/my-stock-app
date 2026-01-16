import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

# 網頁配置
st.set_page_config(page_title="Barchart 模擬分析器", layout="wide")

st.title("📊 專業技術指標矩陣 (Barchart Style)")
st.markdown("""
本系統模擬 Barchart Opinion 運作原理，計算 13 個核心技術指標。
- **Overall Opinion**: 基於 13 個指標的買入佔比。
- **Strength**: 基於長期均線 (100D/200D) 的排列穩定性。
- **Direction**: 基於過去 5 個交易日的價格走勢。
""")

# 用戶輸入股票代碼
ticker_input = st.text_input("請輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_full_analysis(symbol):
    try:
        # 加入 RSI 和 隨機指標
rsi = ta.rsi(c, length=14)
stoch = ta.stoch(df['High'], df['Low'], c) # 回傳是一個 DataFrame

# 增加 2 個判斷條件
conds.append(rsi.iloc[-1] < 30) # RSI 超賣，視為潛在 Buy (反彈信號)
conds.append(stoch['STOCKk_14_3_3'].iloc[-1] > stoch['STOCKd_14_3_3'].iloc[-1]) # K線穿過D線

        # 下載兩年數據以確保指標計算穩定
        df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 200:
            return None

        # 處理 Multi-index 問題（適配新版 yfinance）
        c = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        v = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']

        # 1. 計算所有均線指標
        ma20 = ta.sma(c, length=20)
        ma50 = ta.sma(c, length=50)
        ma100 = ta.sma(c, length=100)
        ma150 = ta.sma(c, length=150)
        ma200 = ta.sma(c, length=200)
        
        # 2. 計算成交量均線
        v20 = v.rolling(window=20).mean()
        v50 = v.rolling(window=50).mean()
        v100 = v.rolling(window=100).mean()

        last_p = c.iloc[-1]
        
        # 3. 定義 13 個具體的 Barchart 判斷條件
        # [Signal] 買入條件清單
        conds = [
            last_p > ma20.iloc[-1],           # 20 Day MA
            ma20.iloc[-1] > ma50.iloc[-1],    # 20-50 Cross
            ma20.iloc[-1] > ma100.iloc[-1],   # 20-100 Cross
            ma20.iloc[-1] > ma200.iloc[-1],   # 20-200 Cross
            last_p > ma50.iloc[-1],           # 50 Day MA
            ma50.iloc[-1] > ma100.iloc[-1],   # 50-100 Cross
            ma50.iloc[-1] > ma150.iloc[-1],   # 50-150 Cross
            ma50.iloc[-1] > ma200.iloc[-1],   # 50-200 Cross
            last_p > ma100.iloc[-1],          # 100 Day MA
            last_p > ma150.iloc[-1],          # 150 Day MA
            last_p > ma200.iloc[-1],          # 200 Day MA
            ma100.iloc[-1] > ma200.iloc[-1],  # 100-200 Cross
            v.iloc[-1] > v20.iloc[-1]         # Volume Status
        ]

        # 4. 計算 Overall Opinion %
        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        opinion_label = "Buy" if opinion_pct >= 70 else "Sell" if opinion_pct <= 30 else "Hold"

        # 5. 計算 Strength (基於 100/150/200 均線)
        long_term_score = sum([1 for b in conds[8:12] if b])
        strength = "Strongest" if long_term_score >= 3 else "Average" if long_term_score >= 2 else "Weakest"

        # 6. 計算 Direction (最近 5 天走勢)
        price_change_5d = (c.iloc[-1] - c.iloc[-5]) / c.iloc[-5]
        direction = "Strengthening" if price_change_5d > 0 else "Weakening"

        # 7. 格式化輸出
        def format_sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        data = {
            "Indicator": [
                "Overall Opinion", "Strength", "Direction", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-100 Day MA Crossover", "20-200 Day MA Crossover", "20-Day Avg Volume", "---",
                "50 Day Moving Average", "50-100 Day MA Crossover", "50-150 Day MA Crossover", "50-200 Day MA Crossover", "50-Day Avg Volume", "---",
                "100 Day Moving Average", "150 Day Moving Average", "200 Day Moving Average", "100-200 Day MA Crossover", "100-Day Avg Volume"
            ],
            symbol: [
                f"{opinion_pct}% {opinion_label}", strength, direction, "",
                format_sig(conds[0]), format_sig(conds[1]), format_sig(conds[2]), format_sig(conds[3]), f"{int(v20.iloc[-1]):,}", "",
                format_sig(conds[4]), format_sig(conds[5]), format_sig(conds[6]), format_sig(conds[7]), f"{int(v50.iloc[-1]):,}", "",
                format_sig(conds[8]), format_sig(conds[9]), format_sig(conds[10]), format_sig(conds[11]), f"{int(v100.iloc[-1]):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        st.error(f"分析 {symbol} 時發生錯誤: {e}")
        return None

# 按鈕觸發分析
if st.button("🚀 執行全指標分析"):
    all_dfs = []
    with st.spinner('正在計算大數據...'):
        for s in tickers:
            res = get_barchart_full_analysis(s)
            if res is not None:
                all_dfs.append(res)
    
    if all_dfs:
        # 將所有結果橫向合併
        final_df = pd.concat(all_dfs, axis=1)
        
        # 使用自定義樣式顯示表格
        def highlight_opinion(val):
            if 'Buy' in str(val): return 'color: #00FF00; font-weight: bold'
            if 'Sell' in str(val): return 'color: #FF4B4B; font-weight: bold'
            return ''

        st.table(final_df)
    else:
        st.warning("查無數據，請確認股票代碼（如 CLOV, NVDA）。")

st.info("💡 註：100% Buy 意味著當前價格位於所有均線上方，且均線呈現多頭排列。")

