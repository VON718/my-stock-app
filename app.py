import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

st.set_page_config(page_title="我的股票分析系統", layout="wide")

st.title("📈 批量股票技術分析儀表板")
st.write("模仿 Barchart Opinion 原理的多維度評分系統")

# 輸入框
ticker_input = st.text_input("輸入股票代碼 (例如: BFLY, NVDA, TSLA):", "BFLY, NVDA, AAPL")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_analysis(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if len(df) < 50: return None
        
        # 指標計算
        df['ema20'] = ta.ema(df['Close'], length=20)
        df['ema50'] = ta.ema(df['Close'], length=50)
        df['ema200'] = ta.ema(df['Close'], length=200)
        macd = ta.macd(df['Close'])
        rsi = ta.rsi(df['Close'], length=14)
        
        # 評分系統
        score = 0
        last = df.iloc[-1]
        
        if last['Close'] > last['ema20']: score += 1
        if last['Close'] > last['ema50']: score += 1
        if last['Close'] > last['ema200']: score += 1
        if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1]: score += 1
        if 40 < rsi.iloc[-1] < 70: score += 1
        
        total_pct = (score / 5) * 100
        
        return {
            "代碼": symbol,
            "現價": round(float(last['Close']), 2),
            "分析意見": f"{total_pct:.0f}% {'買入' if total_pct >= 60 else '持有' if total_pct >= 40 else '賣出'}",
            "RSI": round(float(rsi.iloc[-1]), 1),
            "趨勢": "向上" if last['Close'] > last['ema50'] else "向下"
        }
    except:
        return None

# ... 前面的 get_analysis 函數保持不變 ...

if st.button("開始批量分析"):
    results = []
    # 增加一個進度條，讓你知道網頁有在動
    progress_bar = st.progress(0)
    for i, s in enumerate(tickers):
        data = get_analysis(s)
        if data:
            results.append(data)
        progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        res_df = pd.DataFrame(results)
        # 使用更漂亮的顯示方式
        st.subheader("分析結果")
        st.dataframe(
            res_df.style.background_gradient(cmap='RdYlGn', subset=['RSI'])
            .format({"現價": "${:.2f}"})
        )
    else:
        st.warning("⚠️ 找不到數據，請確認代碼格式是否正確（例如美股用 NVDA，港股用 0700.HK）")
