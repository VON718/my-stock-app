import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

st.set_page_config(page_title="Barchart Full Analysis", layout="wide")
st.title("📊 全指標股票技術分析矩陣")

ticker_input = st.text_input("輸入股票代碼 (用逗號分隔):", "BFLY, BAER, NVDA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_logic(symbol):
    try:
        df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
        if df.empty: return None
        c = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        v = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']

        # 計算均線
        ma20, ma50, ma100, ma150, ma200 = [ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]]
        
        # 計算成交量均線
        v20, v50, v100 = [v.rolling(window=l).mean() for l in [20, 50, 100]]

        last_p = c.iloc[-1]
        
        def sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        # 構建數據字典 (這將成為表格的一行)
        data = {
            "指標名稱": [
                "Overall Opinion", "Strength", "Direction", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-100 Day MA Crossover", "20-200 Day MA Crossover", "20-Day Avg Volume", "---",
                "50 Day Moving Average", "50-100 Day MA Crossover", "50-150 Day MA Crossover", "50-200 Day MA Crossover", "50-Day Avg Volume", "---",
                "100 Day Moving Average", "150 Day Moving Average", "200 Day Moving Average", "100-200 Day MA Crossover", "100-Day Avg Volume"
            ],
            symbol: [
                "100% Buy" if last_p > ma50.iloc[-1] else "Wait", "Strongest", "Strengthening", "",
                sig(last_p > ma20.iloc[-1]), sig(ma20.iloc[-1] > ma50.iloc[-1]), sig(ma20.iloc[-1] > ma100.iloc[-1]), sig(ma20.iloc[-1] > ma200.iloc[-1]), f"{int(v20.iloc[-1]):,}", "",
                sig(last_p > ma50.iloc[-1]), sig(ma50.iloc[-1] > ma100.iloc[-1]), sig(ma50.iloc[-1] > ma150.iloc[-1]), sig(ma50.iloc[-1] > ma200.iloc[-1]), f"{int(v50.iloc[-1]):,}", "",
                sig(last_p > ma100.iloc[-1]), sig(last_p > ma150.iloc[-1]), sig(last_p > ma200.iloc[-1]), sig(ma100.iloc[-1] > ma200.iloc[-1]), f"{int(v100.iloc[-1]):,}"
            ]
        }
        return pd.DataFrame(data).set_index("指標名稱")
    except:
        return None

if st.button("生成全數據對照表"):
    all_dfs = []
    with st.spinner('深度掃描中...'):
        for s in tickers:
            df_stock = get_barchart_logic(s)
            if df_stock is not None:
                all_dfs.append(df_stock)
    
    if all_dfs:
        # 將所有股票的 DataFrame 橫向合併 (股票變直行)
        final_df = pd.concat(all_dfs, axis=1)
        
        # 顯示表格
        st.table(final_df)
    else:
        st.error("無法獲取數據，請檢查代碼。")
