import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Barchart 完整還原分析儀", layout="wide")
st.title("📊 Barchart Opinion 完整數據矩陣")

ticker_input = st.text_input("輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, BAER")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_google_price(symbol):
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

def get_full_barchart_logic(symbol):
    try:
        # 下載數據
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()

        # 即時價格
        current_p = get_google_price(symbol)
        if current_p is None: current_p = float(c.iloc[-1])

        # 指標計算
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        v_avg = {l: v.rolling(window=l).mean().iloc[-1] for l in [20, 50, 100]}
        rsi = ta.rsi(c, length=14).iloc[-1]

        def sig(cond): return "🟢 Buy" if cond else "🔴 Sell"

        # 分段計算 Opinion
        short_conds = [current_p > ma[20].iloc[-1], ma[20].iloc[-1] > ma[50].iloc[-1], ma[20].iloc[-1] > ma[100].iloc[-1], ma[20].iloc[-1] > ma[200].iloc[-1]]
        med_conds = [current_p > ma[50].iloc[-1], ma[50].iloc[-1] > ma[100].iloc[-1], ma[50].iloc[-1] > ma[150].iloc[-1], ma[50].iloc[-1] > ma[200].iloc[-1]]
        long_conds = [current_p > ma[100].iloc[-1], current_p > ma[150].iloc[-1], current_p > ma[200].iloc[-1], ma[100].iloc[-1] > ma[200].iloc[-1]]

        short_avg = int((sum(short_conds) / 4) * 100)
        med_avg = int((sum(med_conds) / 4) * 100)
        long_avg = int((sum(long_conds) / 4) * 100)
        overall_avg = int(((sum(short_conds + med_conds + long_conds)) / 12) * 100)

        # 構建顯示列表
        data = {
            "Indicator": [
                "Overall Opinion", "Trend Seeker®", "Strength", "Direction", "Current Price", "---",
                "Short Term Indicators", "20 Day Moving Average", "20 - 50 Day MA Crossover", "20 - 100 Day MA Crossover", "20 - 200 Day MA Crossover", "20-Day Average Volume", "Short Term Average", "---",
                "Medium Term Indicators", "50 Day Moving Average", "50 - 100 Day MA Crossover", "50 - 150 Day MA Crossover", "50 - 200 Day MA Crossover", "50-Day Average Volume", "Medium Term Average", "---",
                "Long Term Indicators", "100 Day Moving Average", "150 Day Moving Average", "200 Day Moving Average", "100 - 200 Day MA Crossover", "100-Day Average Volume", "Long Term Average"
            ],
            symbol: [
                f"{overall_avg}% {'Buy' if overall_avg >= 60 else 'Sell'}",
                sig(current_p > ma[20].iloc[-1] and ma[20].iloc[-1] > ma[50].iloc[-1]),
                "Strongest" if overall_avg >= 80 else "Weak",
                "Strengthening" if current_p > c.iloc[-5] else "Weakening",
                f"${current_p:.2f}", "",
                "", sig(short_conds[0]), sig(short_conds[1]), sig(short_conds[2]), sig(short_conds[3]), f"{int(v_avg[20]):,}", f"{short_avg}%", "",
                "", sig(med_conds[0]), sig(med_conds[1]), sig(med_conds[2]), sig(med_conds[3]), f"{int(v_avg[50]):,}", f"{med_avg}%", "",
                "", sig(long_conds[0]), sig(long_conds[1]), sig(long_conds[2]), sig(long_conds[3]), f"{int(v_avg[100]):,}", f"{long_avg}%"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except: return None

if st.button("🚀 執行 Barchart 全數據掃描"):
    all_dfs = []
    with st.spinner('計算長/中/短期指標...'):
        for s in tickers:
            res = get_full_barchart_logic(s)
            if res is not None: all_dfs.append(res)
    if all_dfs:
        st.table(pd.concat(all_dfs, axis=1))
    else:
        st.error("獲取失敗")
