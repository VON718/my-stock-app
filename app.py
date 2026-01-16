import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Google Finance 實時分析儀", layout="wide")
st.title("📊 實時數據分析矩陣 (Google Finance API-less)")

ticker_input = st.text_input("輸入股票代碼 (例如: CLOV, BFLY, NVDA):", "BFLY, CLOV, NVDA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_google_realtime_price(symbol):
    """從 Google 搜尋直接抓取實時報價"""
    try:
        url = f"https://www.google.com/search?q=stock+price+{symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 尋找 Google 價格標籤
        price_tags = soup.find_all("span", attrs={"data-precision": True})
        if not price_tags:
            # 備用選擇器
            price_div = soup.find("div", attrs={"class": "YMlS7e"})
            if price_div:
                price = float(price_div.text.replace(",", "").replace("$", ""))
                return price
        
        price = float(price_tags[0].text.replace(",", "").replace("$", ""))
        return price
    except:
        return None

def get_analysis(symbol):
    try:
        # 1. 抓取歷史數據 (Yahoo Finance)
        df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        close_series = df['Close'].squeeze()
        
        # 2. 獲取實時價格 (Google Finance)
        current_p = get_google_realtime_price(symbol)
        if current_p is None:
            current_p = float(close_series.iloc[-1]) # 備援方案

        # 3. 計算技術指標
        ma20 = close_series.rolling(window=20).mean()
        std20 = close_series.rolling(window=20).std()
        
        mid_band = float(ma20.iloc[-1])
        upper_band = mid_band + (float(std20.iloc[-1]) * 2)
        lower_band = mid_band - (float(std20.iloc[-1]) * 2)
        
        rsi = ta.rsi(close_series, length=14).iloc[-1]
        
        # 4. 判定邏輯
        is_above_mid = current_p > mid_band
        is_above_lower = current_p > lower_band
        is_below_upper = current_p < upper_band
        
        # 5. 綜合評分 (改為 100% 制)
        score = 0
        if is_above_mid: score += 20
        if is_above_lower: score += 20
        if is_below_upper: score += 20
        if rsi > 50: score += 20
        if current_p > ta.sma(close_series, length=50).iloc[-1]: score += 20
        
        def format_sig(cond, true_msg, false_msg):
            return f"🟢 {true_msg}" if cond else f"🔴 {false_msg}"

        # 6. 整理數據結構 (確保「當前股價」排在顯眼位置)
        data = {
            "Indicator": [
                "Overall Opinion",
                "Current Price (Google)",  # 新增這一行
                "Middle Band (20 MA)",
                "---",
                "Bollinger Mid-Band (強弱勢)",
                "Bollinger Support (下軌支撐)",
                "Bollinger Resistance (上軌壓力)",
                "RSI (14)",
                "20D Avg Volume"
            ],
            symbol: [
                f"{score}% {'Buy' if score >= 60 else 'Hold' if score >= 40 else 'Sell'}",
                f"${current_p:.2f}",   # 顯示數值
                f"${mid_band:.2f}",    # 顯示數值
                "",
                format_sig(is_above_mid, "Bullish (中軌上)", "Bearish (中軌下)"),
                format_sig(is_above_lower, "Safe (支撐有效)", "Broken (破位)"),
                format_sig(is_below_upper, "Below Resistance", "At Resistance (超漲)"),
                f"{rsi:.1f}",
                f"{int(df['Volume'].tail(20).mean()):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        return None

if st.button("🚀 執行實時同步分析"):
    results = []
    with st.spinner('正在同步 Google Finance 即時數據...'):
        for s in tickers:
            res = get_analysis(s)
            if res is not None:
                results.append(res)
    
    if results:
        final_df = pd.concat(results, axis=1)
        st.table(final_df)
    else:
        st.error("無法獲取數據，請檢查網路連線。")
