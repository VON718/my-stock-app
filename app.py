import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
from bs4 import BeautifulSoup
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# 導入局部極值計算 (用於 Auto-Pivot)
try:
    from scipy.signal import argrelextrema
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

# 1. 頁面配置 (全域僅調用一次)
st.set_page_config(
    page_title="專業級美股雙核心終極戰鬥儀表板",
    page_icon="📈",
    layout="wide"
)

# 2. 初始化 Session State 狀態（跨分頁資料與狀態持久化）
DEFAULT_TICKERS = "NVDA, TSLA, AAPL, PLTR, AMD, MSFT, META, GOOGL, CRWD, SMCI"

if "global_ticker_input_box" not in st.session_state:
    st.session_state.global_ticker_input_box = DEFAULT_TICKERS
if "shared_tickers_text" not in st.session_state:
    st.session_state.shared_tickers_text = DEFAULT_TICKERS
if "tab_pro_tickers" not in st.session_state:
    st.session_state.tab_pro_tickers = DEFAULT_TICKERS
if "tab_bc_tickers" not in st.session_state:
    st.session_state.tab_bc_tickers = DEFAULT_TICKERS

if "alerted_stocks" not in st.session_state:
    st.session_state.alerted_stocks = set()
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "barchart_results" not in st.session_state:
    st.session_state.barchart_results = None

def parse_tickers(raw_str):
    return [t.strip().upper() for t in raw_str.replace(',', ' ').split() if t.strip()]

# 快捷按鈕回調函式：點擊時直接寫入輸入框與各分頁 state
def set_preset(preset_str):
    st.session_state.global_ticker_input_box = preset_str
    st.session_state.shared_tickers_text = preset_str
    st.session_state.tab_pro_tickers = preset_str
    st.session_state.tab_bc_tickers = preset_str

# ==================== 側邊欄風控與排程 ====================
with st.sidebar:
    st.header("⚙️ 戰鬥室設定 (Controls)")
    account_capital = st.number_input("帳戶總本金 (USD)", min_value=1000, value=50000, step=5000)
    risk_pct = st.slider("單筆最大承擔風險 (%)", min_value=0.25, max_value=3.0, value=1.0, step=0.25)
    max_risk_amount = account_capital * (risk_pct / 100.0)
    st.caption(f"🛡️ 單筆風險上限：**${max_risk_amount:,.2f}**")
    
    st.divider()
    st.subheader("🔄 盤中自動輪詢")
    enable_autorefresh = st.checkbox("啟用定時自動雙掃描", value=False)
    refresh_interval = st.selectbox("輪詢間隔", [60, 180, 300, 600], index=2, format_func=lambda x: f"{x} 秒")
    if enable_autorefresh and AUTOREFRESH_AVAILABLE:
        st_autorefresh(interval=refresh_interval * 1000, key="auto_scanner_refresh")
        
    st.divider()
    st.subheader("📢 即時推播 (Discord)")
    discord_webhook_url = st.text_input("Discord Webhook URL", type="password", placeholder="https://discord.com/api/webhooks/...")

# ==================== 核心量化模型函式 ====================
@st.cache_data(ttl=300)
def get_market_regime_and_spy():
    try:
        spy = yf.Ticker("SPY").history(period="2y", interval="1d", auto_adjust=True)
        qqq = yf.Ticker("QQQ").history(period="2y", interval="1d", auto_adjust=True)
        if spy.empty or qqq.empty:
            return None, None
        
        spy_c, qqq_c = spy['Close'].iloc[-1], qqq['Close'].iloc[-1]
        spy_ma50, spy_ma200 = ta.sma(spy['Close'], 50).iloc[-1], ta.sma(spy['Close'], 200).iloc[-1]
        qqq_ma50, qqq_ma200 = ta.sma(qqq['Close'], 50).iloc[-1], ta.sma(qqq['Close'], 200).iloc[-1]

        bullish = (spy_c > spy_ma50 > spy_ma200) and (qqq_c > qqq_ma50 > qqq_ma200)
        bearish = (spy_c < spy_ma200) or (qqq_c < qqq_ma200)

        return {"bullish": bullish, "bearish": bearish}, spy
    except Exception:
        return None, None

def get_latest_market_data(ticker, fallback_price, fallback_vol):
    latest_price, prev_close, today_volume = None, None, None
    try:
        fast = ticker.fast_info
        p = getattr(fast, 'last_price', None) or getattr(fast, 'lastPrice', None)
        if p and not pd.isna(p) and p > 0: latest_price = float(p)
        pc = getattr(fast, 'previous_close', None) or getattr(fast, 'previousClose', None)
        if pc and not pd.isna(pc) and pc > 0: prev_close = float(pc)
        vol = getattr(fast, 'last_volume', None) or getattr(fast, 'lastVolume', None)
        if vol and not pd.isna(vol) and vol > 0: today_volume = float(vol)
    except Exception:
        pass
    if latest_price is None: latest_price = float(fallback_price)
    if today_volume is None: today_volume = float(fallback_vol)
    return latest_price, prev_close, today_volume

def find_auto_pivot(df):
    if len(df) < 30:
        return float(df['High'].iloc[-20:-1].max())
    recent_highs = df['High'].iloc[-25:-1]
    if SCIPY_AVAILABLE:
        extrema = argrelextrema(recent_highs.values, np.greater, order=2)[0]
        if len(extrema) > 0:
            return float(recent_highs.iloc[extrema[-1]])
    return float(recent_highs.max())

def analyze_stock(symbol, capital, risk_budget, spy_history):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2y", interval="1d", auto_adjust=True)
        if df.empty or len(df) < 200:
            return None

        df['MA50'] = ta.sma(df['Close'], length=50)
        df['MA150'] = ta.sma(df['Close'], length=150)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df = df.dropna()
        if len(df) < 25: return None

        curr = df.iloc[-1]
        prev_day = df.iloc[-2]
        prev_22 = df.iloc[-22]

        current_price, prev_close, current_vol = get_latest_market_data(ticker, curr['Close'], curr['Volume'])
        if prev_close is None: prev_close = float(prev_day['Close'])

        change_pct = ((current_price - prev_close) / prev_close) * 100
        avg_vol_20 = float(df['Volume'].iloc[-21:-1].mean()) if len(df) >= 21 else float(df['Volume'].mean())
        vol_multiple = (current_vol / avg_vol_20) if avg_vol_20 > 0 else 1.0

        past_year = df.tail(252)
        high_52w = float(past_year['High'].max())
        low_52w = float(past_year['Low'].min())
        pct_above_low = ((current_price - low_52w) / low_52w) * 100
        pct_below_high = ((high_52w - current_price) / high_52w) * 100

        rs_status = "普通"
        if spy_history is not None and not spy_history.empty:
            aligned_stock = df['Close'].tail(252)
            aligned_spy = spy_history['Close'].reindex(aligned_stock.index).ffill()
            rs_series = aligned_stock / aligned_spy
            rs_52w_high = float(rs_series.max())
            curr_rs = float(rs_series.iloc[-1])
            
            if curr_rs >= rs_52w_high * 0.995:
                if pct_below_high > 3.0:
                    rs_status = "⭐ RS 領先突圍"
                else:
                    rs_status = "🔥 RS 雙創新高"

        earnings_warning = "安全"
        days_to_earnings = 999
        try:
            cal = ticker.calendar
            e_date = None
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                if 'Earnings Date' in cal.index:
                    e_date = pd.to_datetime(cal.loc['Earnings Date'].iloc[0])
                elif 'Earnings Date' in cal.columns:
                    e_date = pd.to_datetime(cal['Earnings Date'].iloc[0])
            elif isinstance(cal, dict) and 'Earnings Date' in cal:
                val = cal['Earnings Date']
                e_date = pd.to_datetime(val[0] if isinstance(val, (list, tuple)) else val)
            
            if e_date is not None:
                e_date = pd.to_datetime(e_date).tz_localize(None).normalize()
                today = pd.Timestamp.now().normalize()
                days_to_earnings = (e_date - today).days
                if 0 <= days_to_earnings <= 10:
                    earnings_warning = f"⚠️ 倒數 {days_to_earnings} 天"
                elif days_to_earnings < 0:
                    earnings_warning = "近期已公佈"
        except Exception:
            earnings_warning = "無資料"

        sector = "其他/未分類"
        try:
            sec = ticker.info.get('sector')
            if sec: sector = sec
        except Exception:
            pass

        score = 0
        if current_price > float(curr['MA150']) and current_price > float(curr['MA200']): score += 1
        if float(curr['MA150']) > float(curr['MA200']): score += 1
        if float(curr['MA200']) > float(prev_22['MA200']): score += 1
        if float(curr['MA50']) > float(curr['MA150']): score += 1
        if pct_above_low >= 25.0: score += 1
        if pct_below_high <= 25.0: score += 1

        w1 = df.tail(60); d1 = (w1['High'].max() - w1['Low'].min()) / w1['High'].max()
        w2 = df.tail(30); d2 = (w2['High'].max() - w2['Low'].min()) / w2['High'].max()
        w3 = df.tail(10); d3 = (w3['High'].max() - w3['Low'].min()) / w3['High'].max()
        vcp_tight = (d1 > d2 and d2 > d3)

        atr_value = float(curr['ATR'])
        stop_loss = max(0.01, current_price - (atr_value * 1.5))
        risk_per_share = current_price - stop_loss
        suggested_shares = int(risk_budget // risk_per_share) if risk_per_share > 0 else 0
        pivot_price = find_auto_pivot(df)

        action = "觀察中"
        if score >= 5 and vcp_tight:
            if d3 < 0.15:
                if current_price > float(prev_day['High']):
                    action = "🔥 立即買入 (Buy)"
                else:
                    action = "🚀 準備突破 (Ready)"
            else:
                action = "⌛ 等待進一步收斂"
        elif score >= 4:
            action = "📈 趨勢尚可"
        else:
            action = "🚫 趨勢偏弱"

        if 0 <= days_to_earnings <= 10 and "買入" in action:
            action = f"⚠️ 避開財報 (倒數{days_to_earnings}天)"

        return {
            "代碼": symbol, "板塊": sector, "最新價": round(current_price, 2),
            "漲跌幅 (%)": round(change_pct, 2), "量能倍數": round(vol_multiple, 2),
            "RS狀態": rs_status, "財報預警": earnings_warning, "趨勢分數": f"{score}/6",
            "距52W高點": round(pct_below_high, 1), "VCP狀態": "✅ 正在收斂" if vcp_tight else "❌ 波動較大",
            "建議行動": action, "樞紐高點": round(pivot_price, 2), "建議停損": round(stop_loss, 2),
            "建議股數": suggested_shares, "預估總值": round(suggested_shares * current_price, 2)
        }
    except Exception:
        return None

def run_micro_backtest(df):
    if len(df) < 100: return None
    df = df.copy()
    df['MA50'] = ta.sma(df['Close'], 50)
    df['MA150'] = ta.sma(df['Close'], 150)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], 14)
    df = df.dropna()

    trades, in_pos, entry_p, stop_p, target_p, days_held = [], False, 0, 0, 0, 0
    for i in range(1, len(df)):
        curr_bar = df.iloc[i]
        prev_bar = df.iloc[i-1]
        if not in_pos:
            if (curr_bar['Close'] > curr_bar['MA50'] > curr_bar['MA150']) and (curr_bar['High'] > prev_bar['High']):
                in_pos = True
                entry_p = float(prev_bar['High'])
                risk = float(curr_bar['ATR']) * 1.5
                stop_p = max(0.01, entry_p - risk)
                target_p = entry_p + (risk * 2.5)
                days_held = 0
        else:
            days_held += 1
            if curr_bar['Low'] <= stop_p:
                trades.append((stop_p - entry_p) / entry_p)
                in_pos = False
            elif curr_bar['High'] >= target_p:
                trades.append((target_p - entry_p) / entry_p)
                in_pos = False
            elif days_held >= 15:
                trades.append((curr_bar['Close'] - entry_p) / entry_p)
                in_pos = False

    if not trades: return None
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = (len(wins) / len(trades)) * 100
    gross_profits = sum(wins)
    gross_losses = abs(sum(losses)) if abs(sum(losses)) > 0 else 0.001
    profit_factor = gross_profits / gross_losses

    return {
        "總交易次數": len(trades), "歷史勝率 (%)": round(win_rate, 1),
        "盈虧比 (Profit Factor)": round(profit_factor, 2),
        "平均報酬 (%)": round(np.mean(trades) * 100, 2),
        "最大單筆獲利 (%)": round(max(trades) * 100, 2),
        "最大單筆虧損 (%)": round(min(trades) * 100, 2)
    }

def plot_stock_chart(symbol, stop_price=None, pivot_price=None):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="2y", interval="1d", auto_adjust=True)
    if df.empty or len(df) < 50:
        st.error(f"無法取得 {symbol} 足夠的 K 線資料。")
        return df

    for p in [5, 20, 50, 100, 200]:
        df[f'MA{p}'] = ta.sma(df['Close'], length=p)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="K線", increasing_line_color="#22C57E", decreasing_line_color="#FF6060"
    ), row=1, col=1)

    ma_settings = [
        ('MA5', '#FF8D1E', 1.2, "5 MA (橙)"), ('MA20', '#E970DC', 1.4, "20 MA (紫)"),
        ('MA50', '#22C57E', 1.6, "50 MA (綠)"), ('MA100', '#13FFFF', 1.8, "100 MA (藍)"),
        ('MA200', '#FF6060', 2.0, "200 MA (紅)")
    ]
    for col_name, color, width, label in ma_settings:
        if df[col_name].dropna().shape[0] > 0:
            fig.add_trace(go.Scatter(x=df.index, y=df[col_name], line=dict(color=color, width=width), name=label), row=1, col=1)

    if pivot_price:
        fig.add_hline(y=pivot_price, line_dash="dashdot", line_color="#FF8D1E", line_width=1.8,
                      annotation_text=f"🔑 Pivot: ${pivot_price:.2f}", annotation_position="top right", row=1, col=1)
    if stop_price:
        fig.add_hline(y=stop_price, line_dash="dash", line_color="#FF6060", line_width=1.5,
                      annotation_text=f"🛑 停損: ${stop_price:.2f}", annotation_position="bottom right", row=1, col=1)

    bar_colors = ['#22C57E' if c >= o else '#FF6060' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=bar_colors, name="成交量"), row=2, col=1)

    start_date = df.index[-1] - pd.DateOffset(months=6)
    fig.update_layout(
        title=f"📈 {symbol} 專業多均線分析系統", xaxis_rangeslider_visible=False, height=580,
        margin=dict(l=10, r=10, t=40, b=10), template="plotly_dark", hovermode="x unified",
        xaxis=dict(range=[start_date, df.index[-1]])
    )
    st.plotly_chart(fig, use_container_width=True)
    return df

def get_barchart_realtime_price(ticker_obj, symbol):
    try:
        fast_price = getattr(ticker_obj, 'fast_info', None)
        if fast_price and 'lastPrice' in fast_price:
            price = fast_price['lastPrice']
            if price and not pd.isna(price): return float(price)
    except Exception:
        pass
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:NASDAQ"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            price_div = soup.find("div", class_="YMlS7e")
            if price_div:
                return float(price_div.text.replace("$", "").replace(",", "").strip())
    except Exception:
        pass
    return None

def get_barchart_analysis(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2y", interval="1d", auto_adjust=True)
        if df.empty or len(df) < 200:
            return None
            
        c = df['Close'].dropna()
        v = df['Volume'].dropna()
        current_p = get_barchart_realtime_price(ticker, symbol)
        if current_p is None: current_p = float(c.iloc[-1])

        ma = {l: ta.sma(c, length=l) for l in [20, 50, 100, 150, 200]}
        rsi_series = ta.rsi(c, length=14)
        rsi = float(rsi_series.dropna().iloc[-1]) if rsi_series is not None and not rsi_series.dropna().empty else 50.0
        
        bbands = ta.bbands(c, length=20, std=2)
        l_col = [col for col in bbands.columns if 'BBL' in col][0]
        u_col = [col for col in bbands.columns if 'BBU' in col][0]
        last_bbl, last_bbu, last_bbm = float(bbands[l_col].iloc[-1]), float(bbands[u_col].iloc[-1]), float(ma[20].iloc[-1])

        def sig(cond): return "🟢 Buy" if cond else "🔴 Sell"
        
        s_conds = [current_p > last_bbm, ma[20].iloc[-1] > ma[50].iloc[-1], ma[20].iloc[-1] > ma[100].iloc[-1], ma[20].iloc[-1] > ma[200].iloc[-1]]
        m_conds = [current_p > ma[50].iloc[-1], ma[50].iloc[-1] > ma[100].iloc[-1], ma[50].iloc[-1] > ma[150].iloc[-1], ma[50].iloc[-1] > ma[200].iloc[-1]]
        l_conds = [current_p > ma[100].iloc[-1], current_p > ma[150].iloc[-1], current_p > ma[200].iloc[-1], ma[100].iloc[-1] > ma[200].iloc[-1]]
        
        all_c = s_conds + m_conds + l_conds
        overall_pct = int((sum(all_c) / len(all_c)) * 100)

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
            f"${current_p:.2f}", f"${last_bbm:.2f}", "", "",
            sig(current_p > last_bbm), sig(s_conds[1]), sig(s_conds[3]), sig(current_p > last_bbl),
            f"{int((sum(s_conds)/4)*100)}%", "", "",
            sig(m_conds[0]), sig(m_conds[1]), sig(m_conds[3]),
            f"{int((sum(m_conds)/4)*100)}%", "", "",
            sig(l_conds[0]), sig(l_conds[2]), sig(l_conds[3]),
            f"{int((sum(l_conds)/4)*100)}%", "", "",
            f"{rsi:.1f}", "🟢 Below" if current_p < last_bbu else "🔥 Overbought", f"{int(v.tail(20).mean()):,}"
        ]

        return pd.DataFrame({"Indicator": indicators, symbol: values}).set_index("Indicator")
    except Exception:
        return None

# ==================== 大盤信號展示 ====================
regime, spy_df = get_market_regime_and_spy()

if regime:
    if regime["bullish"]:
        st.success("🟢 **大盤信號：強勢多頭 (Risk-On)** ｜ SPY 與 QQQ 均站上 50MA 與 200MA，多頭突破勝率最高。")
    elif regime["bearish"]:
        st.error("🔴 **大盤信號：空頭修正警戒 (Risk-Off)** ｜ 指數跌破 200MA 年線，建議嚴控部位或空倉觀望！")
    else:
        st.warning("🟡 **大盤信號：震盪整理期 (Caution)** ｜ 大盤跌破短期均線或兩指步調不一，操作以防守為主。")

# ==================== 🎯 全域股票池與跨分頁同步中心 ====================
with st.container():
    st.markdown("### 🎯 全域股票池與跨分頁同步中心 (Global Ticker Hub)")
    
    preset_col1, preset_col2, preset_col3, _ = st.columns([1.2, 1.2, 1.2, 2.4])
    with preset_col1:
        st.button(
            "💎 科技巨頭 (Mag 7)", 
            on_click=set_preset, 
            args=("AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA",), 
            use_container_width=True
        )
    with preset_col2:
        st.button(
            "⚡ AI 算力半導體", 
            on_click=set_preset, 
            args=("NVDA, AMD, TSM, AVGO, MRVL, ARM, MU, SMCI, PLTR",), 
            use_container_width=True
        )
    with preset_col3:
        st.button(
            "🚀 動能/短線成長", 
            on_click=set_preset, 
            args=("CLOV, BFLY, SOFI, PLTR, IONQ, CRWD, HOOD, RKLB",), 
            use_container_width=True
        )

    # 輸入列與按鈕
    input_col, sync_btn_col, dual_scan_col = st.columns([3.5, 1.1, 1.4])
    with input_col:
        global_input = st.text_input(
            "輸入股票代碼 (逗號或空格隔開):",
            key="global_ticker_input_box"
        )
    with sync_btn_col:
        st.write("") 
        if st.button("🔄 僅同步名單", use_container_width=True):
            st.session_state.shared_tickers_text = global_input
            st.session_state.tab_pro_tickers = global_input
            st.session_state.tab_bc_tickers = global_input
            st.toast("✅ 代碼已同步至所有分頁！", icon="🔄")
            st.rerun()
    with dual_scan_col:
        st.write("") 
        btn_dual_scan = st.button("⚡ 一鍵掃描所有分頁", type="primary", use_container_width=True)

    active_tickers = parse_tickers(st.session_state.global_ticker_input_box)
    st.caption(f"📌 當前全域觀察池共有 **{len(active_tickers)}** 檔標的: `{', '.join(active_tickers)}`")

    # 執行一鍵全分頁雙核心掃描
    if btn_dual_scan or enable_autorefresh:
        if not active_tickers:
            st.warning("⚠️ 觀察名單為空，請先輸入股票代碼。")
        else:
            st.session_state.shared_tickers_text = st.session_state.global_ticker_input_box
            st.session_state.tab_pro_tickers = st.session_state.global_ticker_input_box
            st.session_state.tab_bc_tickers = st.session_state.global_ticker_input_box

            with st.status("🚀 正在啟動雙核心全維度實時掃描...", expanded=True) as status_box:
                st.write("📊 階段 1/2：計算 VCP 型態、52W 樞紐、RS 相對強度與避雷預警...")
                pro_results = []
                for sym in active_tickers:
                    res = analyze_stock(sym, account_capital, max_risk_amount, spy_df)
                    if res:
                        pro_results.append(res)
                
                if pro_results:
                    df_temp = pd.DataFrame(pro_results)
                    df_temp = df_temp.sort_values(by=['建議行動', '距52W高點'], ascending=[False, True])
                    st.session_state.scan_results = df_temp
                else:
                    st.session_state.scan_results = None

                st.write("📈 階段 2/2：計算 Barchart 13 均線指標與布林帶三軌...")
                bc_results = []
                for sym in active_tickers:
                    bc_res = get_barchart_analysis(sym)
                    if bc_res is not None:
                        bc_results.append(bc_res)
                
                if bc_results:
                    st.session_state.barchart_results = pd.concat(bc_results, axis=1)
                else:
                    st.session_state.barchart_results = None

                status_box.update(label="✅ 雙核心掃描完成！所有分頁數據已同步更新。", state="complete", expanded=False)
                st.toast("🎉 雙核心掃描已完成，點擊下方各分頁即可檢視！", icon="⚡")

st.divider()

# ==================== 分頁佈局 ====================
tab_pro, tab_barchart = st.tabs([
    "🚀 機構級突破掃描儀 (Institutional Pro)", 
    "📊 Barchart 13 指標矩陣 (Opinion Screener)"
])

# ----------------- 分頁 1: 機構級突破掃描儀 -----------------
with tab_pro:
    st.subheader("🎯 VCP 型態、RS 強度與多維度突破掃描")
    
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        auto_sync_pro = st.checkbox("與全域股票清單保持即時聯動", value=True, key="sync_toggle_pro")
        if auto_sync_pro:
            input_val_pro = st.session_state.shared_tickers_text
        else:
            input_val_pro = st.text_input("本分頁專用代碼:", value=st.session_state.tab_pro_tickers, key="custom_pro_input")
            st.session_state.tab_pro_tickers = input_val_pro
    
    with col_t2:
        if not auto_sync_pro:
            if st.button("📥 重新載入全域名單", key="pull_global_pro"):
                st.session_state.tab_pro_tickers = st.session_state.shared_tickers_text
                st.rerun()

    tickers_pro = parse_tickers(input_val_pro)

    if st.button("🚀 單獨執行本分頁掃描", key="btn_run_pro"):
        if not tickers_pro:
            st.warning("請先輸入股票代碼。")
        else:
            with st.spinner("同步全球即時行情、計算 RS 強度與掃描財報中..."):
                scan_data = [res for s in tickers_pro if (res := analyze_stock(s, account_capital, max_risk_amount, spy_df))]
                if scan_data:
                    df_temp = pd.DataFrame(scan_data)
                    df_temp = df_temp.sort_values(by=['建議行動', '距52W高點'], ascending=[False, True])
                    st.session_state.scan_results = df_temp
                else:
                    st.session_state.scan_results = None
                    st.error("未能獲取有效分析數據，請檢查代碼或網路連線。")

    if st.session_state.scan_results is not None:
        final_df = st.session_state.scan_results

        # 板塊動能
        sector_group = final_df.groupby('板塊').agg(
            總數=('代碼', 'count'),
            強勢數=('趨勢分數', lambda x: sum(int(str(s).split('/')[0]) >= 5 for s in x)),
            突圍數=('RS狀態', lambda x: sum("RS" in str(s) for s in x))
        ).reset_index()
        sector_group['多頭佔比'] = (sector_group['強勢數'] / sector_group['總數']) * 100

        sec_cols = st.columns(min(len(sector_group), 4))
        for idx, row in sector_group.iterrows():
            with sec_cols[idx % 4]:
                st.metric(
                    label=f"板塊: {row['板塊']}",
                    value=f"{row['多頭佔比']:.0f}% 多頭",
                    delta=f"{row['強勢數']}/{row['總數']} 檔符合強勢"
                )

        st.divider()

        # 篩選矩陣
        st.subheader("📊 專業篩選矩陣 (自動排序)")

        def highlight_row(row):
            if "立即買入" in str(row['建議行動']): return ['background-color: #4a1515; color: white'] * len(row)
            elif "準備突破" in str(row['建議行動']): return ['background-color: #1b3d22; color: white'] * len(row)
            elif "避開財報" in str(row['建議行動']): return ['background-color: #4a3c15; color: white'] * len(row)
            return [''] * len(row)

        def style_rs(val):
            if "RS 領先突圍" in str(val): return 'color: #00e5ff; font-weight: bold;'
            elif "RS 雙創新高" in str(val): return 'color: #76ff03; font-weight: bold;'
            return ''

        styled_df = (
            final_df.style
            .apply(highlight_row, axis=1)
            .map(style_rs, subset=['RS狀態'])
            .format({
                "最新價": "${:.2f}", "漲跌幅 (%)": "{:+.2f}%", "量能倍數": "{:.2f}x",
                "距52W高點": "-{:.1f}%", "樞紐高點": "${:.2f}", "建議停損": "${:.2f}",
                "建議股數": "{:,} 股", "預估總值": "${:,.2f}"
            })
        )
        st.dataframe(styled_df, use_container_width=True)

        st.divider()
        st.subheader("🔬 標的型態二次確認與量化微回測")

        stock_list = final_df['代碼'].tolist()
        selected_symbol = st.selectbox("選擇要深入驗證的個股：", options=stock_list, key="target_stock_picker")

        matched_row = final_df[final_df['代碼'] == selected_symbol].iloc[0]
        stock_history_df = plot_stock_chart(selected_symbol, matched_row['建議停損'], matched_row['樞紐高點'])

        st.markdown(f"#### 🧪 {selected_symbol} 過去 2 年動能突破策略微回測 (Micro-Backtest)")
        if stock_history_df is not None and not stock_history_df.empty:
            bt_results = run_micro_backtest(stock_history_df)
            if bt_results:
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("總樣本交易次數", f"{bt_results['總交易次數']} 次")
                c2.metric("歷史勝率 (Win Rate)", f"{bt_results['歷史勝率 (%)']}%")
                c3.metric("盈虧比 (Profit Factor)", f"{bt_results['盈虧比 (Profit Factor)']}")
                c4.metric("平均每筆報酬", f"{bt_results['平均報酬 (%)']}%")
                c5.metric("最大獲利 / 最大虧損", f"{bt_results['最大單筆獲利 (%)']}% / {bt_results['最大單筆虧損 (%)']}%")
            else:
                st.info("該標的在過去 2 年內樣本訊號不足。")

# ----------------- 分頁 2: Barchart 13 指標矩陣 -----------------
with tab_barchart:
    st.subheader("📊 Barchart Opinion 實時分析矩陣")
    st.caption("結合即時報價、Barchart 13 均線指標與布林帶三軌強弱勢判定")

    col_bc1, col_bc2 = st.columns([4, 1])
    with col_bc1:
        auto_sync_bc = st.checkbox("與全域股票清單保持即時聯動", value=True, key="sync_toggle_bc")
        if auto_sync_bc:
            input_val_bc = st.session_state.shared_tickers_text
        else:
            input_val_bc = st.text_input("本分頁專用代碼:", value=st.session_state.tab_bc_tickers, key="custom_bc_input")
            st.session_state.tab_bc_tickers = input_val_bc

    with col_bc2:
        if not auto_sync_bc:
            if st.button("📥 重新載入全域名單", key="pull_global_bc"):
                st.session_state.tab_bc_tickers = st.session_state.shared_tickers_text
                st.rerun()

    tickers_bc = parse_tickers(input_val_bc)

    if st.button("🚀 單獨執行本分頁掃描", key="btn_run_barchart"):
        if not tickers_bc:
            st.warning("請先輸入股票代碼。")
        else:
            all_results = []
            with st.spinner('同步即時報價與計算 Barchart 指標中...'):
                for s in tickers_bc:
                    res = get_barchart_analysis(s)
                    if res is not None:
                        all_results.append(res)
                
                if all_results:
                    st.session_state.barchart_results = pd.concat(all_results, axis=1)
                else:
                    st.session_state.barchart_results = None
                    st.error("無法抓取數據，請檢查代碼或網路連線。")

    if st.session_state.barchart_results is not None:
        st.table(st.session_state.barchart_results)
