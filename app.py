import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

st.set_page_config(page_title="Barchart 模擬分析器 2.5", layout="wide")
st.title("📊 專業技術指標矩陣 2.5 (支撐與壓力版)")

ticker_input = st.text_input("請輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, AAPL")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_pro_analysis(symbol):
    try:
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200: return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()

        # 1. 均線與 RSI
        ma20, ma50, ma100, ma150, ma200 = [ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]]
        rsi = ta.rsi(c, length=14)
        
        # 2. 布林帶計算與動能抓取
        bbands = ta.bbands(c, length=20, std=2)
        lower_col = [col for col in bbands.columns if 'BBL' in col][0]
        upper_col = [col for col in bbands.columns if 'BBU' in col][0]
        
        last_p = float(c.iloc[-1])
        last_rsi = float(rsi.iloc[-1])
        last_bbl = float(bbands[lower_col].iloc[-1])
        last_bbu = float(bbands[upper_col].iloc[-1])
        
        # 3. 判斷條件 (增加壓力位判定)
        # 支撐：價格 > 下軌 (綠燈)
        # 壓力：價格 < 上軌 (綠燈 = 尚未過熱；紅燈 = 觸及壓力區)
        is_below_resistance = last_p < last_bbu
        
        conds = [
            last_p > ma20.iloc[-1], ma20.iloc[-1] > ma50.iloc[-1], ma20.iloc[-1] > ma100.iloc[-1], 
            ma20.iloc[-1] > ma200.iloc[-1], last_p > ma50.iloc[-1], ma50.iloc[-1] > ma100.iloc[-1], 
            ma50.iloc[-1] > ma150.iloc[-1], ma50.iloc[-1] > ma200.iloc[-1], last_p > ma100.iloc[-1], 
            last_p > ma150.iloc[-1], last_p > ma200.iloc[-1], ma100.iloc[-1] > ma200.iloc[-1], 
            v.iloc[-1] > v.rolling(20).mean().iloc[-1], last_rsi > 50, last_p > last_bbl
        ]

        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        
        # 4. 格式化輸出
        def format_sig(cond): return "🟢 Buy / Safe" if cond else "🔴 Sell / Alert"
        def format_resistance(cond): return "🟢 Below Resistance" if cond else "🔥 At Resistance"

        data = {
            "Indicator": [
                "Overall Opinion", "Strength", "Direction", "RSI (14)", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-200 Day MA Crossover", "---",
                "50 Day Moving Average", "50-200 Day MA Crossover", "---",
                "100 Day Moving Average", "200 Day Moving Average", "---",
                "Bollinger Support (下軌)", "Bollinger Resistance (上軌)", "20D Avg Volume"
            ],
            symbol: [
                f"{opinion_pct}%", 
                "Strongest" if sum([1 for b in conds[8:12] if b]) >= 3 else "Weak",
                "Strengthening" if c.iloc[-1] > c.iloc[-5] else "Weakening",
                f"{last_rsi:.1f}", "",
                format_sig(conds[0]), format_sig(conds[1]), format_sig(conds[3]), "",
                format_sig(conds[4]), format_sig(conds[7]), "",
                format_sig(conds[8]), format_sig(conds[10]), "",
                format_sig(last_p > last_bbl), format_resistance(is_below_resistance), f"{int(v.tail(20).mean()):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        return None

if st.button("🚀 執行深度分析 (含壓力位)"):
    all_dfs = []
    for s in tickers:
        res = get_barchart_pro_analysis(s)
        if res is not None: all_dfs.append(res)
    if all_dfs:
        st.table(pd.concat(all_dfs, axis=1))
    else:
        st.error("無法獲取數據")
