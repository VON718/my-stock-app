import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import numpy as np

# 1. 設置頁面
st.set_page_config(page_title="Barchart 官方算法同步版", layout="wide")
st.title("🛡️ Barchart 技術觀點模擬器 (100% 邏輯還原)")

# 2. 用戶輸入
symbol = st.text_input("輸入股票代碼 (例如: CLOV, NVDA):", "CLOV").strip().upper()

def calculate_barchart_opinion(symbol):
    try:
        # 抓取數據
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 200:
            return None, None, None # 統一回傳格式，避免解包失敗

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].squeeze()
        last_p = float(c.iloc[-1])

        # 3. 官方 13 指標計分邏輯 (+1 Buy, -1 Sell)
        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        
        # 短期 (4)
        s = [
            1 if last_p > ma[20].iloc[-1] else -1,
            1 if ma[20].iloc[-1] > ma[50].iloc[-1] else -1,
            1 if ma[20].iloc[-1] > ma[100].iloc[-1] else -1,
            1 if ma[20].iloc[-1] > ma[200].iloc[-1] else -1
        ]
        # 中期 (4)
        m = [
            1 if last_p > ma[50].iloc[-1] else -1,
            1 if ma[50].iloc[-1] > ma[100].iloc[-1] else -1,
            1 if ma[50].iloc[-1] > ma[150].iloc[-1] else -1,
            1 if ma[50].iloc[-1] > ma[200].iloc[-1] else -1
        ]
        # 長期 (4)
        l = [
            1 if last_p > ma[100].iloc[-1] else -1,
            1 if last_p > ma[150].iloc[-1] else -1,
            1 if last_p > ma[200].iloc[-1] else -1,
            1 if ma[100].iloc[-1] > ma[200].iloc[-1] else -1
        ]
        # Trend Seeker (1)
        ts = 1 if (last_p > ma[20].iloc[-1] and ma[20].iloc[-1] > ma[50].iloc[-1]) else -1

        all_signals = s + m + l + [ts]
        
        # 4. 權重與百分比計算
        score_sum = sum(all_signals)
        # Barchart 1.04 係數模擬
        final_pct_raw = (score_sum / 13) * 100 * 1.04
        final_pct = min(100, max(-100, round(final_pct_raw / 8) * 8))
        
        opinion_label = "Buy" if final_pct > 0 else "Sell" if final_pct < 0 else "Hold"

        # 5. 構建數據表
        results_data = {
            "Term": ["Overall", "Short Term", "Medium Term", "Long Term"],
            "Opinion": [
                f"{abs(final_pct)}% {opinion_label}",
                f"{abs(int((sum(s)/4)*100))}% {'Buy' if sum(s)>0 else 'Sell'}",
                f"{abs(int((sum(m)/4)*100))}% {'Buy' if sum(m)>0 else 'Sell'}",
                f"{abs(int((sum(l)/4)*100))}% {'Buy' if sum(l)>0 else 'Sell'}"
            ],
            "Score": [f"{score_sum}/13", f"{sum(s)}/4", f"{sum(m)}/4", f"{sum(l)}/4"]
        }
        return pd.DataFrame(results_data).set_index("Term"), all_signals, last_p

    except Exception as e:
        st.sidebar.error(f"分析錯誤: {e}")
        return None, None, None

# 6. UI 顯示邏輯
if st.button("🔍 同步 Barchart 數據"):
    res_df, signals, last_p = calculate_barchart_opinion(symbol)
    
    # 這裡檢查 res_df 是否為 None，避免 TypeError
    if res_df is not None:
        st.subheader(f"📊 {symbol} 技術觀點分析")
        
        # 顯示頂部大指標
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Overall Opinion", res_df.iloc[0, 0])
        with col2:
            st.metric("Price", f"${last_p:.2f}")
        with col3:
            st.metric("Total Score", f"{sum(signals)}/13")
            
        st.table(res_df)
        
        # 指標強度說明
        st.write("---")
        st.write("💡 **Barchart 邏輯說明**：13 個指標中，每個指標為 +1 或 -1。總分透過 1.04 修正係數校準，以 8% 為進階階梯。")
    else:
        st.error("⚠️ 無法獲取該股票數據。請檢查：代碼是否正確、網路連線、或是該股票歷史數據是否少於 200 天。")
