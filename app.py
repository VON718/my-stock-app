import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import numpy as np

st.set_page_config(page_title="Barchart Style Analyzer", layout="wide")
st.title("📊 專業級趨勢強度分析儀")

ticker_input = st.text_input("輸入股票代碼 (例如: BFLY, BAER, TSLA):", "BFLY, NVDA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def analyze_stock(symbol):
    try:
        # 抓取足夠長度的數據以計算 200MA
        df = yf.download(symbol, period="2y", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 200: return None

        # 處理 Multi-index 問題
        c = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        
        # --- 計算指標 ---
        ma20 = ta.sma(c, length=20)
        ma50 = ta.sma(c, length=50)
        ma100 = ta.sma(c, length=100)
        ma200 = ta.sma(c, length=200)
        
        last_price = c.iloc[-1]
        prev_price_5d = c.iloc[-5]
        
        # --- 1. Strength (強度) 邏輯 ---
        # 判斷標準：價格高於均線的層次
        strength_score = 0
        if last_price > ma200.iloc[-1]: strength_score += 40
        if last_price > ma100.iloc[-1]: strength_score += 30
        if ma50.iloc[-1] > ma200.iloc[-1]: strength_score += 30
        
        strength_label = "Very Strong" if strength_score >= 90 else "Strong" if strength_score >= 60 else "Average" if strength_score >= 30 else "Weak"

        # --- 2. Direction (方向) 邏輯 ---
        # 比較今日價格與 5 日前價格的斜率
        diff_5d = ((last_price - prev_price_5d) / prev_price_5d) * 100
        if diff_5d > 2: direction = "🚀 Strengthening"
        elif diff_5d < -2: direction = "📉 Weakening"
        else: direction = "➡️ Steady"

        # --- 3. 趨勢線意見 ---
        def get_op(price, ma):
            return "✅ Buy" if price > ma else "❌ Sell"

        return {
            "代碼": symbol,
            "現價": f"${last_price:.2f}",
            "Overall Opinion": f"{strength_score}% {'Buy' if strength_score > 50 else 'Sell'}",
            "Strength": strength_label,
            "Direction": direction,
            "20D 短期趨勢": get_op(last_price, ma20.iloc[-1]),
            "50D 中期趨勢": get_op(last_price, ma50.iloc[-1]),
            "100D 長期趨勢": get_op(last_price, ma100.iloc[-1]),
        }
    except:
        return None

if st.button("執行 Barchart 風格分析"):
    data_list = []
    with st.spinner('分析中...'):
        for s in tickers:
            res = analyze_stock(s)
            if res: data_list.append(res)
    
    if data_list:
        res_df = pd.DataFrame(data_list)
        
        # 根據 Opinion 著色
        def color_op(val):
            if 'Buy' in str(val): color = '#228B22' # 森林綠
            elif 'Sell' in str(val): color = '#DC143C' # 猩紅
            else: color = 'white'
            return f'background-color: {color}; color: white; font-weight: bold'

        st.table(res_df.style.applymap(color_op, subset=["Overall Opinion", "20D 短期趨勢", "50D 中期趨勢", "100D 長期趨勢"]))
    else:
        st.warning("查無數據，請確認代碼。")
