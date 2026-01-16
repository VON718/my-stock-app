import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

# 網頁配置
st.set_page_config(page_title="Barchart 專業模擬器 2.0", layout="wide")

st.title("📊 專業技術指標矩陣 2.0 (含震盪與波動指標)")
st.markdown("""
本系統模擬 Barchart Opinion 綜合評分邏輯：
- **趨勢指標**: 包含 20/50/100/150/200 日均線及交叉。
- **動能指標 (新)**: 引入 **RSI (14)**，判斷是否超買或超賣。
- **波動指標 (新)**: 引入 **Bollinger Bands**，判斷價格相對於標準差的位置。
""")

# 用戶輸入股票代碼
ticker_input = st.text_input("請輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_pro_analysis(symbol):
    try:
        # 下載數據
        df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 200:
            return None

        # 處理資料格式
        c = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        h = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
        l = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']
        v = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']

        # 1. 計算均線指標
        ma20, ma50, ma100, ma150, ma200 = [ta.sma(c, length=len_) for len_ in [20, 50, 100, 150, 200]]
        
        # 2. 計算新指標：RSI 與 布林帶
        rsi = ta.rsi(c, length=14)
        bbands = ta.bbands(c, length=20, std=2) # 回傳包含 BBL (下軌), BBM (中軌), BBU (上軌)
        
        # 3. 計算成交量均線
        v20 = v.rolling(window=20).mean()

        last_p = c.iloc[-1]
        last_rsi = rsi.iloc[-1]
        last_bbl = bbands['BBL_20_2.0'].iloc[-1]
        last_bbu = bbands['BBU_20_2.0'].iloc[-1]
        
        # 4. 定義 15 個判斷條件 (增加 RSI 與 BB)
        conds = [
            last_p > ma20.iloc[-1],           # 1. 20 Day MA
            ma20.iloc[-1] > ma50.iloc[-1],    # 2. 20-50 Cross
            ma20.iloc[-1] > ma100.iloc[-1],   # 3. 20-100 Cross
            ma20.iloc[-1] > ma200.iloc[-1],   # 4. 20-200 Cross
            last_p > ma50.iloc[-1],           # 5. 50 Day MA
            ma50.iloc[-1] > ma100.iloc[-1],   # 6. 50-100 Cross
            ma50.iloc[-1] > ma150.iloc[-1],   # 7. 50-150 Cross
            ma50.iloc[-1] > ma200.iloc[-1],   # 8. 50-200 Cross
            last_p > ma100.iloc[-1],          # 9. 100 Day MA
            last_p > ma150.iloc[-1],          # 10. 150 Day MA
            last_p > ma200.iloc[-1],          # 11. 200 Day MA
            ma100.iloc[-1] > ma200.iloc[-1],  # 12. 100-200 Cross
            v.iloc[-1] > v20.iloc[-1],        # 13. Volume Status
            last_rsi > 50,                    # 14. RSI Momentum (新)
            last_p > last_bbl                 # 15. BB Support (價格在下軌之上) (新)
        ]

        # 5. 綜合評分計算
        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        opinion_label = "Buy" if opinion_pct >= 60 else "Sell" if opinion_pct <= 40 else "Hold"

        # 6. 強度與方向
        long_term_score = sum([1 for b in conds[8:12] if b])
        strength = "Strongest" if long_term_score >= 3 else "Average" if long_term_score >= 2 else "Weak"
        
        price_change_5d = (c.iloc[-1] - c.iloc[-5]) / c.iloc[-5]
        direction = "Strengthening" if price_change_5d > 0 else "Weakening"

        # 7. 格式化輸出
        def format_sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        data = {
            "Indicator": [
                "Overall Opinion", "Strength", "Direction", "Relative Strength Index (14)", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-100 Day MA Crossover", "20-200 Day MA Crossover", "---",
                "50 Day Moving Average", "50-100 Day MA Crossover", "50-150 Day MA Crossover", "50-200 Day MA Crossover", "---",
                "100 Day Moving Average", "200 Day Moving Average", "100-200 Day MA Crossover", "---",
                "Bollinger Bands Support", "20-Day Avg Volume"
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
    except Exception as e:
        return None

# 按鈕與顯示
if st.button("🚀 執行 2.0 深度分析"):
    all_dfs = []
    with st.spinner('計算多維度技術指標中...'):
        for s in tickers:
            res = get_barchart_pro_analysis(s)
            if res is not None:
                all_dfs.append(res)
    
    if all_dfs:
        final_df = pd.concat(all_dfs, axis=1)
        st.table(final_df)
    else:
        st.warning("請輸入正確的代碼。")
