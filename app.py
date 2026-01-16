import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 1. 網頁配置
st.set_page_config(page_title="Barchart 終極實時分析儀", layout="wide")
st.title("📊 Barchart Opinion 終極實時分析矩陣")
st.markdown("結合 Google Finance 實時報價、Barchart 13 指標計分法與布林帶三軌分析")

# 2. 用戶輸入
ticker_input = st.text_input("輸入股票代碼 (用逗號分隔):", "CLOV, BFLY, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_google_price(symbol):
    """從 Google 獲取最即時報價"""
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

def get_combined_analysis(symbol):
    try:
        # A. 抓取 Yahoo 歷史數據 (2年期確保 200MA 準確)
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()

        # B. 獲取 Google 實時價格
        current_p = get_google_price(symbol)
        if current_p is None: current_p = float(c.iloc[-1])

        # C. 技術指標計算
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        rsi = ta.rsi(c, length=14).iloc[-1]
        
        # 布林帶計算
        bbands = ta.bbands(c, length=20, std=2)
        l_col = [col for col in bbands.columns if 'BBL' in col][0]
        u_col = [col for col in bbands.columns if 'BBU' in col][0]
        last_bbl = float(bbands[l_col].iloc[-1])
        last_bbu = float(bbands[u_col].iloc[-1])
        last_bbm = float(ma[20].iloc[-1]) # 中軌就是 20MA

        # D. Barchart 13 指標判定 (使用實時價格)
        def sig(cond): return "🟢 Buy" if cond else "🔴 Sell"
        
        # 短期 (4)
        s_conds = [current_p > last_bbm, ma[20].iloc[-1] > ma[50].iloc[-1], ma[20].iloc[-1] > ma[100].iloc[-1], ma[20].iloc[-1] > ma[200].iloc[-1]]
        # 中期 (4)
        m_conds = [current_p > ma[50].iloc[-1], ma[50].iloc[-1] > ma[100].iloc[-1], ma[50].iloc[-1] > ma[150].iloc[-1], ma[50].iloc[-1] > ma[200].iloc[-1]]
        # 長期 (4)
        l_conds = [current_p > ma[100].iloc[-1], current_p > ma[150].iloc[-1], current_p > ma[200].iloc[-1], ma[100].iloc[-1] > ma[200].iloc[-1]]
        
        # 綜合評分 (加上 1.04 係數模擬)
        all_c = s_conds + m_conds + l_conds
        score_sum = sum([1 if x else -1 for x in all_c])
        overall_pct = min(100, max(0, int(((sum(all_c) / 12) * 100))))

        # E. 整理輸出數據
        data = {
            "Indicator": [
                "Overall Opinion", "Trend Seeker®", "Current Price", "Middle Band (20 MA)", "---",
                "Short Term Indicators", "20 Day Moving Average (中軌)", "20 - 50 Day MA Crossover", "20 - 200 Day MA Crossover", "Bollinger Support (下軌)", "Short Term Average", "---",
                "Medium Term Indicators", "50 Day Moving Average", "50 - 100 Day MA Crossover", "50 - 200 Day MA Crossover", "Medium Term Average", "---",
                "Long Term Indicators", "100 Day Moving Average", "200 Day Moving Average", "100 - 200 Day MA Crossover", "Long Term Average", "---",
                "Volatility & Volume", "RSI (14)", "Bollinger Resistance (上軌)", "20D Avg Volume"
            ],
            symbol: [
                f"{overall_pct}% {'Buy' if overall_pct >= 60 else 'Hold' if overall_pct >= 40 else 'Sell'}",
                sig(current_p > last_bbm and ma[20].iloc[-1] > ma[50].iloc[-1]),
                f"${current_p:.2f}", f"${last_bbm:.2f}", "",
                "", sig(current_p > last_bbm), sig(s_conds[1]), sig(s_conds[3]), sig(current_p > last_bbl), f"{int((sum(s_conds)/4)*100)}%", "",
                "", sig(m_conds[0]), sig(m_conds[1]), sig(m_conds[3]), f"{int((sum(m_conds)/4)*100)}%", "",
                "", sig(l_conds[0]), sig(l_conds[2]), sig(l_conds[3]), f"{int((sum(l_conds)/4)*100)}%", "",
                "", f"{rsi:.1f}", "🟢 Below" if current_p < last_bbu else "🔥 Overbought", f"{int(v.tail(20).mean()):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        return None

# 3. 執行按鈕
if st.button("🚀 執行全方位實時數據掃描"):
    all_results = []
    with st.spinner('同步 Google Finance 報價與 Barchart 指標中...'):
        for s in tickers:
            res = get_combined_analysis(s)
            if res is not None:
                all_results.append(res)
    
    if all_results:
        final_df = pd.concat(all_results, axis=1)
        st.table(final_df)
    else:
        st.error("無法抓取數據，請檢查代碼或網路。")
