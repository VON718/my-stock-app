import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

st.set_page_config(page_title="專業級股票分析儀", layout="wide")
st.title("📊 批量股票分析診斷儀")

# 側邊欄：設定參數
with st.sidebar:
    st.header("設定")
    period = st.selectbox("分析週期", ["1y", "2y", "5y"], index=0)

# 輸入框
ticker_input = st.text_input("輸入股票代碼 (例如: BFLY, NVDA, 0700.HK):", "BFLY, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_analysis(symbol):
    try:
        # 下載數據，增加 threads=False 防止 Streamlit 衝突
        df = yf.download(symbol, period=period, interval="1d", progress=False, threads=False)
        
        # 診斷：如果 df 是空的
        if df.empty or len(df) < 50:
            return {"代碼": symbol, "狀態": "❌ 抓不到數據"}
        
        # 指標計算 (修正 yfinance 新版 multi-index 問題)
        close_prices = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        
        ema20 = ta.ema(close_prices, length=20)
        ema50 = ta.ema(close_prices, length=50)
        rsi = ta.rsi(close_prices, length=14)
        
        last_price = close_prices.iloc[-1]
        last_rsi = rsi.iloc[-1]
        
        # 簡單評分邏輯
        score = 0
        if last_price > ema20.iloc[-1]: score += 1
        if last_price > ema50.iloc[-1]: score += 1
        if last_rsi > 50: score += 1
        
        total_pct = (score / 3) * 100
        
        return {
            "代碼": symbol,
            "狀態": "✅ 成功",
            "現價": f"${last_price:.2f}",
            "評分": f"{total_pct:.0f}%",
            "意見": "買入" if total_pct >= 66 else "持有" if total_pct >= 33 else "賣出",
            "RSI": round(last_rsi, 1)
        }
    except Exception as e:
        return {"代碼": symbol, "狀態": f"⚠️ 錯誤: {str(e)[:20]}"}

if st.button("🚀 開始深度分析"):
    results = []
    status_text = st.empty()
    
    for s in tickers:
        status_text.text(f"正在分析: {s}...")
        data = get_analysis(s)
        if data:
            results.append(data)
    
    status_text.empty()
    
    if results:
        res_df = pd.DataFrame(results)
        
        # 區分成功與失敗
        success_df = res_df[res_df["狀態"] == "✅ 成功"]
        error_df = res_df[res_df["狀態"] != "✅ 成功"]
        
        if not success_df.empty:
            st.subheader("✅ 分析報告")
            # 根據評分排序
            success_df = success_df.sort_values(by="評分", ascending=False)
            st.table(success_df)
            
        if not error_df.empty:
            st.subheader("❌ 讀取失敗名單")
            st.write(error_df)
