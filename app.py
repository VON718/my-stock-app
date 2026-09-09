import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 1. 網頁配置
st.set_page_config(page_title="Barchart 終極實時分析儀", layout="wide")
st.title("📊 Barchart Opinion 終極實時分析矩陣")
st.markdown("結合即時報價、Barchart 13 指標計分法與布林帶三軌分析")

# 2. 用戶輸入
ticker_input = st.text_input("輸入股票代碼 (用逗號分隔):", "CLOV, BFLY, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

def get_realtime_price(ticker_obj, symbol):
    """取得最即時價格：優先使用 Yahoo FastInfo，備援使用 Google Finance"""
    try:
        # 1. 優先使用 yfinance fast_info (無延遲且不易被封鎖 IP)
        fast_price = getattr(ticker_obj, 'fast_info', None)
        if fast_price and 'lastPrice' in fast_price:
            price = fast_price['lastPrice']
            if price and not pd.isna(price):
                return float(price)
    except Exception:
        pass

    # 2. 備援：Google Finance 專屬頁面爬蟲 (比 Google Search 穩定)
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:NASDAQ"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            price_div = soup.find("div", class_="YMlS7e")
            if price_div:
                return float(price_div.text.replace("$", "").replace(",", "").strip())
    except Exception:
        pass

    return None

def get_combined_analysis(symbol):
    try:
        ticker = yf.Ticker(symbol)
        
        # A. 抓取歷史日K數據 (使用 Ticker.history 確保為乾淨單層欄位)
        df = ticker.history(period="2y", interval="1d", auto_adjust=True)
        if df.empty or len(df) < 200:
            st.warning(f"代碼 {symbol} 歷史數據不足 200 天，已略過。")
            return None
            
        c = df['Close'].dropna()
        v = df['Volume'].dropna()

        # B. 獲取即時價格 (若皆取不到則退回歷史最新收盤價)
        current_p = get_realtime_price(ticker, symbol)
        if current_p is None:
            current_p = float(c.iloc[-1])

        # C. 技術指標計算
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        rsi_series = ta.rsi(c, length=14)
        rsi = float(rsi_series.dropna().iloc[-1]) if rsi_series is not None and not rsi_series.dropna().empty else 50.0
        
        # 布林帶計算
        bbands = ta.bbands(c, length=20, std=2)
        l_col = [col for col in bbands.columns if 'BBL' in col][0]
        u_col = [col for col in bbands.columns if 'BBU' in col][0]
        last_bbl = float(bbands[l_col].iloc[-1])
        last_bbu = float(bbands[u_col].iloc[-1])
        last_bbm = float(ma[20].iloc[-1]) # 20MA 中軌

        # D. Barchart 13 指標判定
        def sig(cond): 
            return "🟢 Buy" if cond else "🔴 Sell"
        
        # 短期條件 (4項)
        s_conds = [
            current_p > last_bbm,
            ma[20].iloc[-1] > ma[50].iloc[-1],
            ma[20].iloc[-1] > ma[100].iloc[-1],
            ma[20].iloc[-1] > ma[200].iloc[-1]
        ]
        # 中期條件 (4項)
        m_conds = [
            current_p > ma[50].iloc[-1],
            ma[50].iloc[-1] > ma[100].iloc[-1],
            ma[50].iloc[-1] > ma[150].iloc[-1],
            ma[50].iloc[-1] > ma[200].iloc[-1]
        ]
        # 長期條件 (4項)
        l_conds = [
            current_p > ma[100].iloc[-1],
            current_p > ma[150].iloc[-1],
            current_p > ma[200].iloc[-1],
            ma[100].iloc[-1] > ma[200].iloc[-1]
        ]
        
        # 綜合評分
        all_c = s_conds + m_conds + l_conds
        overall_pct = int((sum(all_c) / len(all_c)) * 100)

        # E. 整理輸出數據 (注意：Index 必須每行唯一，此處利用不同長度的空格避免 Pandas Duplicate Index 報錯)
        indicators = [
            "Overall Opinion", "Trend Seeker®", "Current Price", "Middle Band (20 MA)", " ── 1 ── ",
            "Short Term Indicators", "20 Day Moving Average (中軌)", "20 - 50 Day MA Crossover", "20 - 200 Day MA Crossover", "Bollinger Support (下軌)", "Short Term Average", " ── 2 ── ",
            "Medium Term Indicators", "50 Day Moving Average", "50 - 100 Day MA Crossover", "50 - 200 Day MA Crossover", "Medium Term Average", " ── 3 ── ",
            "Long Term Indicators", "100 Day Moving Average", "200 Day Moving Average", "100 - 200 Day MA Crossover", "Long Term Average", " ── 4 ── ",
            "Volatility & Volume", "RSI (14)", "Bollinger Resistance (上軌)", "20D Avg Volume"
        ]

        values = [
            f"{overall_pct}% {'Buy' if overall_pct >= 60 else 'Hold' if overall_pct >= 40 else 'Sell'}",
            sig(current_p > last_bbm and ma[20].iloc[-1] > ma[50].iloc[-1]),
            f"${current_p:.2f}", 
            f"${last_bbm:.2f}", 
            "",
            "", 
            sig(current_p > last_bbm), 
            sig(s_conds[1]), 
            sig(s_conds[3]), 
            sig(current_p > last_bbl), 
            f"{int((sum(s_conds)/4)*100)}%", 
            "",
            "", 
            sig(m_conds[0]), 
            sig(m_conds[1]), 
            sig(m_conds[3]), 
            f"{int((sum(m_conds)/4)*100)}%", 
            "",
            "", 
            sig(l_conds[0]), 
            sig(l_conds[2]), 
            sig(l_conds[3]), 
            f"{int((sum(l_conds)/4)*100)}%", 
            "",
            "", 
            f"{rsi:.1f}", 
            "🟢 Below" if current_p < last_bbu else "🔥 Overbought", 
            f"{int(v.tail(20).mean()):,}"
        ]

        df_res = pd.DataFrame({"Indicator": indicators, symbol: values}).set_index("Indicator")
        return df_res
    except Exception as e:
        st.error(f"解析 {symbol} 失敗，錯誤原因: {e}")
        return None

# 3. 執行按鈕
if st.button("🚀 執行全方位實時數據掃描"):
    if not tickers:
        st.warning("請先輸入股票代碼。")
    else:
        all_results = []
        with st.spinner('同步即時報價與計算 Barchart 指標中...'):
            for s in tickers:
                res = get_combined_analysis(s)
                if res is not None:
                    all_results.append(res)
        
        if all_results:
            final_df = pd.concat(all_results, axis=1)
            st.table(final_df)
        else:
            st.error("無法抓取數據，請檢查代碼或網路連線。")
