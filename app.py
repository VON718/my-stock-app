import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

# 網頁配置
st.set_page_config(page_title="Barchart 專業模擬器 2.0", layout="wide")

st.title("📊 專業技術指標矩陣 2.0 (Barchart 模擬版)")
st.markdown("""
本系統模擬 Barchart Opinion 綜合評分邏輯：
- **指標權重**: 包含 20/50/100/150/200 日均線、RSI 動能與布林帶支撐。
- **資料來源**: Yahoo Finance 實時數據。
""")

# 用戶輸入股票代碼 (預設放幾隻股票，避免一開始顯示錯誤)
ticker_input = st.text_input("請輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, AAPL")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_pro_analysis(symbol):
    try:
        # 下載數據 (增加 threads=False 提高在 Streamlit 上的穩定度)
        df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
        
        if df.empty or len(df) < 200:
            return None

        # 處理資料格式 (相容 yfinance 新舊版本)
        c = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        v = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']

        # 1. 計算均線指標
        ma20 = ta.sma(c, length=20)
        ma50 = ta.sma(c, length=50)
        ma100 = ta.sma(c, length=100)
        ma150 = ta.sma(c, length=150)
        ma200 = ta.sma(c, length=200)
        
        # 2. 計算 RSI 與 布林帶
        rsi = ta.rsi(c, length=14)
        bbands = ta.bbands(c, length=20, std=2)
        
        # 3. 成交量均線
        v20 = v.rolling(window=20).mean()

        last_p = float(c.iloc[-1])
        last_rsi = float(rsi.iloc[-1])
        last_bbl = float(bbands['BBL_20_2.0'].iloc[-1])
        
        # 4. 15 個 Barchart 判斷條件
        conds = [
            last_p > ma20.iloc[-1],           # 1
            ma20.iloc[-1] > ma50.iloc[-1],    # 2
            ma20.iloc[-1] > ma100.iloc[-1],   # 3
            ma20.iloc[-1] > ma200.iloc[-1],   # 4
            last_p > ma50.iloc[-1],           # 5
            ma50.iloc[-1] > ma100.iloc[-1],   # 6
            ma50.iloc[-1] > ma150.iloc[-1],   # 7
            ma50.iloc[-1] > ma200.iloc[-1],   # 8
            last_p > ma100.iloc[-1],          # 9
            last_p > ma150.iloc[-1],          # 10
            last_p > ma200.iloc[-1],          # 11
            ma100.iloc[-1] > ma200.iloc[-1],  # 12
            v.iloc[-1] > v20.iloc[-1],        # 13
            last_rsi > 50,                    # 14
            last_p > last_bbl                 # 15
        ]

        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        
        # 根據 Barchart 標準定義標籤
        if opinion_pct >= 70: opinion_label = "Strong Buy"
        elif opinion_pct >= 55: opinion_label = "Buy"
        elif opinion_pct >= 45: opinion_label = "Hold"
        elif opinion_pct >= 30: opinion_label = "Sell"
        else: opinion_label = "Strong Sell"

        # 強度與方向
        long_term_score = sum([1 for b in conds[8:12] if b])
        strength = "Strongest" if long_term_score >= 3 else "Average" if long_term_score >= 2 else "Weak"
        
        price_change_5d = (c.iloc[-1] - c.iloc[-5]) / c.iloc[-5]
        direction = "Strengthening" if price_change_5d > 0 else "Weakening"

        def format_sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        # 整理成 DataFrame
        data = {
            "Indicator": [
                "Overall Opinion", "Strength", "Direction", "RSI (14)", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-100 Day MA Crossover", "20-200 Day MA Crossover", "---",
                "50 Day Moving Average", "50-100 Day MA Crossover", "50-150 Day MA Crossover", "50-200 Day MA Crossover", "---",
                "100 Day Moving Average", "200 Day Moving Average", "100-200 Day MA Crossover", "---",
                "Bollinger Support", "20D Avg Volume"
            ],
            symbol: [
                f"{opinion_pct}% {opinion_label}", strength, direction, f"{last_rsi:.1f}", "",
                format_sig(conds[0]), format_sig(conds[1]), format_sig(conds[2]), format_sig(conds[3]), "",
                format_sig(conds[4]), format_sig(conds[5]), format_sig(conds[6]), format_sig(conds[7]), "",
                format_sig(conds[8]), format_sig(conds[10]), format_sig(conds[11]), "",
                format_sig(conds[14]), f"{int(v20.iloc[-1]):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception:
        return None

# 按鈕觸發
if st.button("🚀 執行深度分析"):
    all_dfs = []
    with st.spinner('正在分析數據，請稍候...'):
        for s in tickers:
            res = get_barchart_pro_analysis(s)
            if res is not None:
                all_dfs.append(res)
    
    if all_dfs:
        final_df = pd.concat(all_dfs, axis=1)
        st.table(final_df)
    else:
        st.error("⚠️ 無法獲取數據。請檢查網路連接或代碼格式（美股 NVDA，港股 0700.HK）。")
