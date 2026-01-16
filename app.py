import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Barchart + Google 終極分析儀", layout="wide")
st.title("📊 終極技術指標矩陣 (即時 Google 價格 + Barchart 全功能)")

ticker_input = st.text_input("輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_google_price(symbol):
    """抓取 Google Finance 即時價格"""
    try:
        url = f"https://www.google.com/search?q=stock+price+{symbol}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        price_tags = soup.find_all("span", attrs={"data-precision": True})
        if not price_tags:
            price_div = soup.find("div", attrs={"class": "YMlS7e"})
            if price_div: return float(price_div.text.replace(",", "").replace("$", ""))
        return float(price_tags[0].text.replace(",", "").replace("$", ""))
    except: return None

def get_full_analysis(symbol):
    try:
        # 1. 抓取 Yahoo 數據計算歷史指標
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()

        # 2. 獲取最即時價格
        current_p = get_google_price(symbol)
        if current_p is None: current_p = float(c.iloc[-1])

        # 3. 計算 Barchart 所有的均線指標
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        rsi = ta.rsi(c, length=14)
        bb = ta.bbands(c, length=20, std=2)
        v20 = v.rolling(window=20).mean()

        # 4. 完整的 15 項 Barchart 判定準則 (使用即時價格)
        conds = [
            current_p > ma[20].iloc[-1], ma[20].iloc[-1] > ma[50].iloc[-1], ma[20].iloc[-1] > ma[100].iloc[-1],
            ma[20].iloc[-1] > ma[200].iloc[-1], current_p > ma[50].iloc[-1], ma[50].iloc[-1] > ma[100].iloc[-1],
            ma[50].iloc[-1] > ma[150].iloc[-1], ma[50].iloc[-1] > ma[200].iloc[-1], current_p > ma[100].iloc[-1],
            current_p > ma[150].iloc[-1], current_p > ma[200].iloc[-1], ma[100].iloc[-1] > ma[200].iloc[-1],
            v.iloc[-1] > v20.iloc[-1], rsi.iloc[-1] > 50, current_p > float(bb.iloc[:,0].iloc[-1])
        ]

        # 5. 計算百分比與標籤
        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        
        # 6. 計算 Strength (強度) 與 Direction (方向)
        long_term_score = sum([1 for b in conds[8:12] if b])
        strength = "Strongest" if long_term_score >= 3 else "Average" if long_term_score >= 2 else "Weak"
        direction = "Strengthening" if c.iloc[-1] > c.iloc[-5] else "Weakening"

        def format_sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        # 7. 整理回原本的 Barchart 表格格式
        data = {
            "Indicator": [
                "Overall Opinion", "Current Price (Real-time)", "Middle Band (20 MA)", "Strength", "Direction", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-200 Day MA Crossover", "---",
                "50 Day Moving Average", "50-200 Day MA Crossover", "---",
                "100 Day Moving Average", "200 Day Moving Average", "---",
                "Bollinger Support (下軌)", "Bollinger Resistance (上軌)", "RSI (14)"
            ],
            symbol: [
                f"{opinion_pct}% {'Buy' if opinion_pct >= 60 else 'Sell'}",
                f"${current_p:.2f}", f"${ma[20].iloc[-1]:.2f}", strength, direction, "",
                format_sig(conds[0]), format_sig(conds[1]), format_sig(conds[3]), "",
                format_sig(conds[4]), format_sig(conds[7]), "",
                format_sig(conds[8]), format_sig(conds[10]), "",
                format_sig(conds[14]), 
                "🟢 Below" if current_p < float(bb.iloc[:,2].iloc[-1]) else "🔥 At Resistance",
                f"{rsi.iloc[-1]:.1f}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        return None

if st.button("🚀 執行全功能實時掃描"):
    all_dfs = []
    with st.spinner('同步 Barchart 指標與 Google 即時數據中...'):
        for s in tickers:
            res = get_full_analysis(s)
            if res is not None: all_dfs.append(res)
    
    if all_dfs:
        st.table(pd.concat(all_dfs, axis=1))
    else:
        st.error("獲取失敗，請檢查代碼。")
