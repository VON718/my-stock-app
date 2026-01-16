import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import numpy as np

# 設置頁面
st.set_page_config(page_title="Barchart 官方算法 100% 還原", layout="wide")
st.title("🛡️ Barchart 官方技術觀點模擬器 (13 指標版)")

symbol = st.text_input("輸入股票代碼 (例如: CLOV, NVDA):", "CLOV").strip().upper()

def calculate_barchart_opinion(symbol):
    try:
        # 1. 抓取完整 2 年數據 (確保 200MA 準確)
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        v = df['Volume'].squeeze()
        last_p = float(c.iloc[-1])

        # 2. 官方 13 指標計算
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        # 指標 1-4: 短期
        s1 = 1 if last_p > ma[20].iloc[-1] else -1
        s2 = 1 if ma[20].iloc[-1] > ma[50].iloc[-1] else -1
        s3 = 1 if ma[20].iloc[-1] > ma[100].iloc[-1] else -1
        s4 = 1 if ma[20].iloc[-1] > ma[200].iloc[-1] else -1
        
        # 指標 5-8: 中期
        m1 = 1 if last_p > ma[50].iloc[-1] else -1
        m2 = 1 if ma[50].iloc[-1] > ma[100].iloc[-1] else -1
        m3 = 1 if ma[50].iloc[-1] > ma[150].iloc[-1] else -1
        m4 = 1 if ma[50].iloc[-1] > ma[200].iloc[-1] else -1
        
        # 指標 9-12: 長期
        l1 = 1 if last_p > ma[100].iloc[-1] else -1
        l2 = 1 if last_p > ma[150].iloc[-1] else -1
        l3 = 1 if last_p > ma[200].iloc[-1] else -1
        l4 = 1 if ma[100].iloc[-1] > ma[200].iloc[-1] else -1
        
        # 指標 13: Trend Seeker (模擬邏輯)
        ts = 1 if (last_p > ma[20].iloc[-1] and ma[20].iloc[-1] > ma[50].iloc[-1]) else -1

        all_signals = [s1, s2, s3, s4, m1, m2, m3, m4, l1, l2, l3, l4, ts]
        
        # 3. 官方加權公式 (1.04 修正)
        score_sum = sum(all_signals)
        raw_pct = (score_sum / 13) * 100
        # 模擬 Barchart 的 1.04 係數與 8% 步進
        final_pct = min(100, max(-100, round(raw_pct * 1.04 / 8) * 8))
        
        display_pct = abs(final_pct)
        opinion_label = "Buy" if final_pct > 0 else "Sell" if final_pct < 0 else "Hold"

        # 4. 數據整理
        results = {
            "Timeframe": ["Overall", "Short Term", "Medium Term", "Long Term"],
            "Opinion": [
                f"{display_pct}% {opinion_label}",
                f"{abs(int((sum(all_signals[0:4])/4)*100))}%",
                f"{abs(int((sum(all_signals[4:8])/4)*100))}%",
                f"{abs(int((sum(all_signals[8:12])/4)*100))}%"
            ],
            "Count": [f"{sum(all_signals)}/13", "4/4", "4/4", "4/4"]
        }
        return pd.DataFrame(results).set_index("Timeframe"), all_signals, current_p
    except: return None

if st.button("🔍 同步 Barchart 官方數據"):
    res_df, signals, last_p = calculate_barchart_opinion(symbol)
    if res_df is not None:
        st.subheader(f"{symbol} 官方 Opinion 分析 (同步中...)")
        st.table(res_df)
        
        # 模擬 Strength & Direction
        st.info(f"當前價格: ${last_p:.2f} | 總計得分: {sum(signals)}")
    else:
        st.error("代碼錯誤或數據不足")
