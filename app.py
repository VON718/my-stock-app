import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd

st.set_page_config(page_title="Barchart 專業分析器 2.6", layout="wide")
st.title("📊 專業技術指標矩陣 2.6 (布林帶全方位版)")

ticker_input = st.text_input("請輸入股票代碼 (用逗號分隔):", "BFLY, CLOV, NVDA, TSLA")
tickers = [t.strip().upper() for t in ticker_input.split(",")]

def get_barchart_pro_analysis(symbol):
    try:
        # 抓取數據
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200: return None

        # 處理資料格式
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()

        # 1. 基礎指標計算
        ma20, ma50, ma100, ma150, ma200 = [ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]]
        rsi = ta.rsi(c, length=14)
        
        # 2. 布林帶三軌計算
        bbands = ta.bbands(c, length=20, std=2)
        l_col = [col for col in bbands.columns if 'BBL' in col][0] # 下軌
        m_col = [col for col in bbands.columns if 'BBM' in col][0] # 中軌
        u_col = [col for col in bbands.columns if 'BBU' in col][0] # 上軌
        
        last_p = float(c.iloc[-1])
        last_rsi = float(rsi.iloc[-1])
        last_bbl = float(bbands[l_col].iloc[-1])
        last_bbm = float(bbands[m_col].iloc[-1])
        last_bbu = float(bbands[u_col].iloc[-1])
        
        # 3. 判定邏輯
        # 中軌判定：價格 > 中軌 (代表進入強勢區)
        is_above_mid = last_p > last_bbm
        # 壓力判定：價格 < 上軌 (代表尚未過熱)
        is_below_upper = last_p < last_bbu
        # 支撐判定：價格 > 下軌 (代表支撐有效)
        is_above_lower = last_p > last_bbl

        conds = [
            last_p > ma20.iloc[-1], ma20.iloc[-1] > ma50.iloc[-1], ma20.iloc[-1] > ma100.iloc[-1], 
            ma20.iloc[-1] > ma200.iloc[-1], last_p > ma50.iloc[-1], ma50.iloc[-1] > ma100.iloc[-1], 
            ma50.iloc[-1] > ma150.iloc[-1], ma50.iloc[-1] > ma200.iloc[-1], last_p > ma100.iloc[-1], 
            last_p > ma150.iloc[-1], last_p > ma200.iloc[-1], ma100.iloc[-1] > ma200.iloc[-1], 
            v.iloc[-1] > v.rolling(20).mean().iloc[-1], last_rsi > 50, is_above_lower
        ]

        buy_count = sum([1 for b in conds if b])
        opinion_pct = int((buy_count / len(conds)) * 100)
        
        def format_sig(cond, true_msg="🟢 Buy / Safe", false_msg="🔴 Sell / Alert"):
            return true_msg if cond else false_msg

        data = {
            "Indicator": [
                "Overall Opinion", "Strength", "Direction", "RSI (14)", "---",
                "20 Day Moving Average", "20-50 Day MA Crossover", "20-200 Day MA Crossover", "---",
                "50 Day Moving Average", "50-200 Day MA Crossover", "---",
                "100 Day Moving Average", "200 Day Moving Average", "---",
                "Bollinger Support (下軌)", "Bollinger Mid-Band (強弱勢)", "Bollinger Resistance (上軌)", "---",
                "20D Avg Volume"
            ],
            symbol: [
                f"{opinion_pct}% {'Buy' if opinion_pct >= 50 else 'Sell'}", 
                "Strongest" if sum([1 for b in conds[8:12] if b]) >= 3 else "Weak",
                "Strengthening" if c.iloc[-1] > c.iloc[-5] else "Weakening",
                f"{last_rsi:.1f}", "",
                format_sig(conds[0]), format_sig(conds[1]), format_sig(conds[3]), "",
                format_sig(conds[4]), format_sig(conds[7]), "",
                format_sig(conds[8]), format_sig(conds[10]), "",
                format_sig(is_above_lower), 
                format_sig(is_above_mid, "🟢 Bullish (中軌上)", "🔴 Bearish (中軌下)"),
                format_sig(is_below_upper, "🟢 Below Resistance", "🔥 At Resistance"), "",
                f"{int(v.tail(20).mean()):,}"
            ]
        }
        return pd.DataFrame(data).set_index("Indicator")
    except Exception as e:
        return None

if st.button("🚀 執行全方位技術掃描"):
    all_dfs = []
    with st.spinner('正在分析布林軌道結構...'):
        for s in tickers:
            res = get_barchart_pro_analysis(s)
            if res is not None: all_dfs.append(res)
    
    if all_dfs:
        st.table(pd.concat(all_dfs, axis=1))
    else:
        st.error("無法獲取數據，請確認代碼。")
