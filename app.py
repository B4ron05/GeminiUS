import streamlit as st
import pandas as pd
import cot_data
import technical_data
import historical_data
import scoring_logic
import altair as alt
import forecast_manager
import score_logger  # add to the imports at the top of app.py

st.set_page_config(page_title="Project Macro", layout="wide")
st.title("Macro analyzer 🎯")

# --- CUSTOM CSS UI BUILDER ---
def render_combo_chart(nfp_df, retail_df, cpi_df):
    st.markdown("**NFP vs Retail Sales MoM vs CPI YoY**")

    if nfp_df.empty or retail_df.empty or cpi_df.empty:
        st.info("Awaiting sufficient historical data for the combo chart.")
        return

    nfp_data = nfp_df.reset_index()
    retail_data = retail_df.reset_index()
    cpi_data = cpi_df.reset_index()

    # NFP bars on their own right-hand axis (absolute thousands)
    nfp_bar = alt.Chart(nfp_data).mark_bar(
        color="#808080", opacity=0.35, cornerRadiusTopLeft=3, cornerRadiusTopRight=3
    ).encode(
        x=alt.X('yearmonthdate(Date):O', title=None,
                axis=alt.Axis(format="%Y %b %d", labelAngle=-45, grid=False)),
        y=alt.Y('Value:Q', title="Non-Farm Payroll (k)",
                axis=alt.Axis(orient='right', titleColor="#808080")),
        tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'),
                 alt.Tooltip('Value:Q', title="NFP (k)")]
    )

    # Retail Sales MoM line on the shared % axis
    retail_line = alt.Chart(retail_data).mark_line(
        color="#2962FF", strokeWidth=3,
        point=alt.OverlayMarkDef(color="#2962FF", size=60, filled=True)
    ).encode(
        x=alt.X('yearmonthdate(Date):O', title=None),
        y=alt.Y('Value:Q', title="Percent (%)", scale=alt.Scale(zero=False),
                axis=alt.Axis(titleColor="#2962FF")),
        tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'),
                 alt.Tooltip('Value:Q', title="Retail Sales MoM (%)")]
    )

    # CPI YoY line, same % axis, dashed to distinguish from Retail Sales
    cpi_line = alt.Chart(cpi_data).mark_line(
        color="#F44336", strokeWidth=3, strokeDash=[4, 2],
        point=alt.OverlayMarkDef(color="#F44336", size=60, filled=True)
    ).encode(
        x=alt.X('yearmonthdate(Date):O', title=None),
        y=alt.Y('Value:Q', title="Percent (%)", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'),
                 alt.Tooltip('Value:Q', title="CPI YoY (%)")]
    )

# Retail Sales + CPI share one y-axis (nested layer, default shared scale)
    percent_lines = alt.layer(retail_line, cpi_line)

    # NFP bars get their own axis, resolved independently from the percent group
    combo = alt.layer(nfp_bar, percent_lines).resolve_scale(
        y='independent'
    ).properties(height=400)

    st.altair_chart(combo, use_container_width=True)
    st.caption("🩶 Bars = Non-Farm Payroll (k, right axis)  |  "
               "🔵 Line = Retail Sales MoM (%, left axis)  |  "
               "🔴 Dashed = CPI YoY (%, left axis)")
def custom_metric_card(label, value, difference, asset, forecast=None, suffix="", text_override=None, mode="Surprise", ffr_val=None, cpi_val=None):
    bias, color = scoring_logic.evaluate_bias(asset, label, difference, current_value=value, ffr_val=ffr_val, cpi_val=cpi_val)
    diff_str = f"+{difference}" if difference > 0 else f"{difference}"
    
    if text_override:
        bottom_text = f'<span style="font-size: 13px; color: #A0A0A0; margin-left: 8px;">{text_override}</span>'
    elif forecast is not None and forecast != "N/A":
        if mode == "Surprise":
            bottom_text = f'<span style="font-size: 13px; color: #A0A0A0; margin-left: 8px;">Est: {forecast}{suffix} | Surprise: <b style="color: {color};">{diff_str}{suffix}</b></span>'
        else:
            bottom_text = f'<span style="font-size: 13px; color: #A0A0A0; margin-left: 8px;">Prev: {forecast}{suffix} | Trend: <b style="color: {color};">{diff_str}{suffix}</b></span>'
    else:
        bottom_text = f'<span style="font-size: 13px; color: #A0A0A0; margin-left: 8px;">Delta: <b style="color: {color};">{diff_str}{suffix}</b></span>'
            
    content_html = f"""<h2 style="margin: 0px; margin-top: 5px; color: {color}; font-size: 32px;">{value}{suffix}</h2>
<div style="margin-top: 8px;">
<span style="background-color: {color}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">{bias}</span>
{bottom_text}
</div>"""

    html = f"""<div style="margin-bottom: 20px; padding: 10px; border-radius: 8px; background-color: rgba(255,255,255,0.05); min-height: 100px;">
<p style="margin: 0px; font-size: 14px; font-weight: 600; color: #A0A0A0;">{label}</p>
{content_html}
</div>"""
    st.markdown(html, unsafe_allow_html=True)

# --- DASHBOARD RENDERING ENGINE ---
def render_dashboard(macro, tech, cot, selected_asset, mode="Surprise", log_this_run=False):
    """
    Dynamically renders the entire scorecard. 
    Accepts either Finnhub (Surprise) or FRED (Momentum) dictionaries.
    """
    score_map = {"Bullish": 1, "Bearish": -1, "Neutral": 0}
    category_averages = []

# 1. Technicals & Sentiment Calculation
    tech_score = 0

    for t_metric in ["4H / Daily Trend", "Seasonality Trend"]:
        bias, _ = scoring_logic.evaluate_bias(
        selected_asset,
        t_metric,
        tech[t_metric]['difference']
    )

    # Each technical metric = ±1 point
        tech_score += score_map.get(bias, 0)

    tech_score = round(tech_score, 2)
    category_averages.append(tech_score)
# 2. COT Data Calculation
    cot_score = 0.0

    if cot:
        bias, _ = scoring_logic.evaluate_bias(
            selected_asset,
            "Net Change (WoW)",
            cot['change_pct']
    )

    # COT gets double weight = ±2 points
        cot_score = round(float(score_map.get(bias, 0)) * 3, 3)
        category_averages.append(cot_score)
    else:
        category_averages.append(0.0)        
# 3. Macro Data Calculation
    macro_score = 0.0
    
    # --- NEW: Extract Global Regime Variables ---
    try:
        # 1. Load the live manual override from your JSON file
        ffr_override = float(forecast_manager.load_forecasts().get("Fed Funds Rate", 0.0))
        
        # 2. If you entered a live rate (> 0), use it. Otherwise, use FRED's lagging 'value'.
        current_ffr = ffr_override if ffr_override > 0 else macro.get("Fed Funds Rate", {}).get("value", None)
        
        current_cpi = macro.get("CPI YoY", {}).get("value", None)
    except:
        current_ffr, current_cpi = None, None
       
    metric_groups = {
    "Growth": [
        "GDP Growth QoQ",
        "Retail Sales MoM",
        "Manufacturing PMI",
        "Services PMI"
    ],
    "Consumer": [
        "Personal Income MoM",
        "Personal Savings Rate",
        "Michigan Consumer Sentiment"
    ],
    "Inflation": [
        "CPI YoY",
        "PPI YoY",
        "PCE YoY",
        "2 Yr Yield (30d SMA)"
    ],
    "Jobs": [
        "Non-Farm Payroll",
        "Unemployment Rate %",
        "Weekly Jobless Claims",
        "JOLTS Job Openings"
    ]
}
    for group_name, metrics in metric_groups.items():
        group_sum = 0
        for metric in metrics:
            
            # --- THE FIX: We must pass ffr_val and cpi_val into the logic engine ---
            bias, _ = scoring_logic.evaluate_bias(
                selected_asset, 
                metric, 
                macro[metric]['difference'], 
                current_value=macro[metric]['value'],
                ffr_val=current_ffr,     # <--- This bridges the data!
                cpi_val=current_cpi      # <--- This bridges the data!
            )
            
            points = score_map.get(bias, 0) 
                
            group_sum += points
            
        # Each macro metric contributes ±1 directly
        macro_score += group_sum

    macro_score = round(macro_score, 2)
    category_averages.append(macro_score)

    
# 4. Master Net Calculation (Matches original math baseline perfectly)
    total_score = sum(category_averages)
    total_score_rounded = round(total_score, 2)

    # --- NEW: DYNAMIC MAX RANGE BASED ON COT AVAILABILITY ---
    master_max = 20 if cot else 17

    # --- NEW: MAGNITUDE PERCENTAGE CALCULATION ---
    # Negative case: score / negative end | Positive/0 case: score / positive end
    def calc_edge(score, max_val):
        divisor = -max_val if score < 0 else max_val
        return round((score / divisor) * 100, 1)

    total_pct = calc_edge(total_score_rounded, master_max)
    macro_pct = calc_edge(macro_score, 15)
    tech_pct = calc_edge(tech_score, 2)
    cot_pct = calc_edge(cot_score, 3) if cot else 0.0

    if total_score >= 8: master_bias, master_color = "VERY BULLISH", "#2962FF"
    elif total_score <= -8: master_bias, master_color = "VERY BEARISH", "#F44336"
    elif total_score >= 3: master_bias, master_color = "BULLISH", "#2962FF"
    elif total_score <= -3: master_bias, master_color = "BEARISH", "#F44336"
    else:
        master_bias, master_color = "NEUTRAL", "#808080"

    if log_this_run:
        score_logger.log_score(
            asset=selected_asset,
            mode=mode,
            total_score=total_score_rounded,
            master_bias=master_bias,
            macro_score=macro_score,
            tech_score=tech_score,
            cot_score=cot_score
        )
        
    # --- SUB-SCORE LABEL ENGINE ---
    SUB_SCORE_THRESHOLDS = {
        "macro": 4,
        "tech": 1,
        "cot": 2,
    }

    def get_sub_badge(score, category):
        threshold = SUB_SCORE_THRESHOLDS[category]

        if score >= threshold:
            return "BULLISH", "#2962FF"
        elif score <= -threshold:
            return "BEARISH", "#F44336"
        return "NEUTRAL", "#808080"

    macro_bias, macro_color = get_sub_badge(macro_score, "macro")
    tech_bias, tech_color = get_sub_badge(tech_score, "tech")
    cot_bias, cot_color = get_sub_badge(cot_score, "cot")
    
    # --- RENDER MASTER SCORE BANNER ---
    st.markdown(f"""
    <div style="text-align: center; margin-top: 10px; margin-bottom: 20px; padding: 25px; border-radius: 12px; background-color: rgba(255,255,255,0.02); border: 2px solid {master_color};">
        <p style="margin: 0; color: #A0A0A0; font-size: 16px; font-weight: bold; text-transform: uppercase;">{mode} Edge Score</p>
        <h1 style="margin: 10px 0; color: {master_color}; font-size: 52px; letter-spacing: 2px;">{master_bias}</h1>
        <p style="margin: 0; color: white; font-size: 18px;">Normalized Net Score: <b style="color: {master_color};">{total_score_rounded}</b> <span style="color: #A0A0A0; font-size: 14px;">(Max Range: -{master_max} to +{master_max})</span></p>
        <p style="margin: 6px 0 0 0; color: #A0A0A0; font-size: 15px;">{master_bias.title()} Edge: <b style="color: {master_color}; font-size: 17px;">{total_pct}%</b></p>
    </div>
    """, unsafe_allow_html=True)

    # --- NEW: RENDER TRIPLE CATEGORY SCORECARDS ---
    sc1, sc2, sc3 = st.columns(3)
    
    with sc1:
        st.markdown(f"""
        <div style="padding: 18px; border-radius: 8px; background-color: rgba(255,255,255,0.04); border-top: 4px solid {macro_color}; text-align: center; margin-bottom: 35px;">
            <p style="margin: 0; font-size: 12px; color: #A0A0A0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Fundamental Macro</p>
            <h3 style="margin: 8px 0; color: {macro_color}; font-size: 24px; font-weight: 800;">{macro_bias}</h3>
            <p style="margin: 0; color: white; font-size: 14px;">Sub-Score: <b style="color: {macro_color};">{macro_score}</b> <span style="color: #A0A0A0; font-size: 11px;">(Max: ±15)</span></p>
            <p style="margin: 5px 0 0 0; color: #A0A0A0; font-size: 13px;">{macro_bias.title()} Edge: <b style="color: {macro_color};">{macro_pct}%</b></p>
        </div>
        """, unsafe_allow_html=True)
        
    with sc2:
        st.markdown(f"""
        <div style="padding: 18px; border-radius: 8px; background-color: rgba(255,255,255,0.04); border-top: 4px solid {tech_color}; text-align: center; margin-bottom: 35px;">
            <p style="margin: 0; font-size: 12px; color: #A0A0A0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Technicals & Sentiment</p>
            <h3 style="margin: 8px 0; color: {tech_color}; font-size: 24px; font-weight: 800;">{tech_bias}</h3>
            <p style="margin: 0; color: white; font-size: 14px;">Sub-Score: <b style="color: {tech_color};">{tech_score}</b> <span style="color: #A0A0A0; font-size: 11px;">(Max: ±2)</span></p>
            <p style="margin: 5px 0 0 0; color: #A0A0A0; font-size: 13px;">{tech_bias.title()} Edge: <b style="color: {tech_color};">{tech_pct}%</b></p>
        </div>
        """, unsafe_allow_html=True)
        
    with sc3:
        if cot:
            st.markdown(f"""
            <div style="padding: 18px; border-radius: 8px; background-color: rgba(255,255,255,0.04); border-top: 4px solid {cot_color}; text-align: center; margin-bottom: 35px;">
                <p style="margin: 0; font-size: 12px; color: #A0A0A0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Institutional Flow (COT)</p>
                <h3 style="margin: 8px 0; color: {cot_color}; font-size: 24px; font-weight: 800;">{cot_bias}</h3>
                <p style="margin: 0; color: white; font-size: 14px;">Sub-Score: <b style="color: {cot_color};">{cot_score}</b> <span style="color: #A0A0A0; font-size: 11px;">(Max: ±3)</span></p>
                <p style="margin: 5px 0 0 0; color: #A0A0A0; font-size: 13px;">{cot_bias.title()} Edge: <b style="color: {cot_color};">{cot_pct}%</b></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="padding: 18px; border-radius: 8px; background-color: rgba(255,255,255,0.04); border-top: 4px solid #808080; text-align: center; margin-bottom: 35px;">
                <p style="margin: 0; font-size: 12px; color: #A0A0A0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Institutional Flow (COT)</p>
                <h3 style="margin: 8px 0; color: #808080; font-size: 24px; font-weight: 800;">OFFLINE</h3>
                <p style="margin: 0; color: #A0A0A0; font-size: 13px;">No Asset CFTC Mapping</p>
            </div>
            """, unsafe_allow_html=True)
            
    st.subheader("📊 Technical Bias & Crowd Sentiment")
    t1, t2, t3, t4 = st.columns(4)
    with t1: custom_metric_card("4H / Daily Trend", tech['4H / Daily Trend']['value'], tech['4H / Daily Trend']['difference'], selected_asset)
    with t2: custom_metric_card("Seasonality Trend", tech['Seasonality Trend']['value'], tech['Seasonality Trend']['difference'], selected_asset, suffix="%")
    
    sentiment = tech['Fear & Greed Index']
    if sentiment['value'] == "N/A": 
        sent_text = "Awaiting CNN data..."
    else: 
        # Display the 0-100 score cleanly
        sent_text = f"Fear & Greed Index Score: {sentiment['retail_long']} / 100"
        
    # Change the card title to CNN Fear & Greed
    with t3: custom_metric_card("Fear & Greed Index", sentiment['value'], sentiment['difference'], selected_asset, text_override=sent_text, suffix="")

    st.divider()
    st.subheader("🏢 Institutional Activity Bias (COT)")
    if cot:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Long %", f"{cot['long_pct']}%")
        with c2: st.metric("Short %", f"{cot['short_pct']}%")
        with c3: custom_metric_card("Net Change (WoW)", f"{cot['change_pct']}", cot['change_pct'], selected_asset, suffix="%")
    else:
        st.warning(f"No COT data found for {selected_asset}.")
    
    st.divider()
    st.subheader("📈 Economic Growth & Production Bias")
    g1, g2, g3, g4 = st.columns(4)
    with g1: custom_metric_card("GDP Growth QoQ", macro['GDP Growth QoQ']['value'], macro['GDP Growth QoQ']['difference'], selected_asset, forecast=macro['GDP Growth QoQ']['forecast'], suffix="%", mode=mode)
    with g2: custom_metric_card("Retail Sales MoM", macro['Retail Sales MoM']['value'], macro['Retail Sales MoM']['difference'], selected_asset, forecast=macro['Retail Sales MoM']['forecast'], suffix="%", mode=mode)
    with g3: custom_metric_card("Manufacturing PMI", macro['Manufacturing PMI']['value'], macro['Manufacturing PMI']['difference'], selected_asset, forecast=macro['Manufacturing PMI']['forecast'], suffix="", mode=mode)
    with g4: custom_metric_card("Services PMI", macro['Services PMI']['value'], macro['Services PMI']['difference'], selected_asset, forecast=macro['Services PMI']['forecast'], suffix="", mode=mode)

    st.divider()
    st.subheader("🛒 State of the Consumer")
    c1, c2, c3, c4 = st.columns(4)
    with c1: custom_metric_card("Personal Income MoM", macro['Personal Income MoM']['value'], macro['Personal Income MoM']['difference'], selected_asset, forecast=macro['Personal Income MoM']['forecast'], suffix="%", mode=mode)
    with c2: custom_metric_card("Personal Savings Rate", macro['Personal Savings Rate']['value'], macro['Personal Savings Rate']['difference'], selected_asset, forecast=macro['Personal Savings Rate']['forecast'], suffix="%", mode=mode)
    with c3: custom_metric_card("Michigan Consumer Sentiment", macro['Michigan Consumer Sentiment']['value'], macro['Michigan Consumer Sentiment']['difference'], selected_asset, forecast=macro['Michigan Consumer Sentiment']['forecast'], suffix="", mode=mode)
    
    st.divider()
    st.subheader("🔥 Inflation Bias")
    i1, i2, i3, i4 = st.columns(4)
    with i1: custom_metric_card("CPI YoY", macro['CPI YoY']['value'], macro['CPI YoY']['difference'], selected_asset, forecast=macro['CPI YoY']['forecast'], suffix="%", mode=mode)
    with i2: custom_metric_card("PPI YoY", macro['PPI YoY']['value'], macro['PPI YoY']['difference'], selected_asset, forecast=macro['PPI YoY']['forecast'], suffix="%", mode=mode)
    with i3: custom_metric_card("PCE YoY", macro['PCE YoY']['value'], macro['PCE YoY']['difference'], selected_asset, forecast=macro['PCE YoY']['forecast'], suffix="%", mode=mode)
    
    if macro['2 Yr Yield (30d SMA)']['value'] == "N/A":
        yield_text = "Awaiting 2Y yield data..."
    elif macro['2 Yr Yield (30d SMA)']['difference'] > 0:
        yield_text = f"Yield is rising > 30 SMA ({macro['2 Yr Yield (30d SMA)']['forecast']}%)"
    elif macro['2 Yr Yield (30d SMA)']['difference'] < 0:
        yield_text = f"Yield is falling < 30 SMA ({macro['2 Yr Yield (30d SMA)']['forecast']}%)"
    else:
        yield_text = f"Yield is flat on SMA ({macro['2 Yr Yield (30d SMA)']['forecast']}%)"
        
    with i4: custom_metric_card("2 Yr Yield (30d SMA)", macro['2 Yr Yield (30d SMA)']['value'], macro['2 Yr Yield (30d SMA)']['difference'], selected_asset, text_override=yield_text, suffix="%")

    st.divider()
    st.subheader("💼 Jobs Market Bias")
    j1, j2, j3, j4 = st.columns(4)
    
    # Send the live FFR and CPI variables into the UI cards so they know which Regime to render
    with j1: custom_metric_card("Non-Farm Payroll", macro['Non-Farm Payroll']['value'], macro['Non-Farm Payroll']['difference'], selected_asset, forecast=macro['Non-Farm Payroll']['forecast'], suffix="k", mode=mode, ffr_val=current_ffr, cpi_val=current_cpi)
    with j2: custom_metric_card("Unemployment Rate %", macro['Unemployment Rate %']['value'], macro['Unemployment Rate %']['difference'], selected_asset, forecast=macro['Unemployment Rate %']['forecast'], suffix="%", mode=mode, ffr_val=current_ffr, cpi_val=current_cpi)
    with j3: custom_metric_card("Weekly Jobless Claims", macro['Weekly Jobless Claims']['value'], macro['Weekly Jobless Claims']['difference'], selected_asset, forecast=macro['Weekly Jobless Claims']['forecast'], suffix="", mode=mode, ffr_val=current_ffr, cpi_val=current_cpi)
    with j4: custom_metric_card("JOLTS Job Openings", macro['JOLTS Job Openings']['value'], macro['JOLTS Job Openings']['difference'], selected_asset, forecast=macro['JOLTS Job Openings']['forecast'], suffix="M", mode=mode, ffr_val=current_ffr, cpi_val=current_cpi)

# --- CACHING FUNCTIONS ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_cot(ticker): return cot_data.fetch_cot_data(ticker)

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_technicals(ticker, opt_ticker, asset_name): return technical_data.fetch_technicals_and_sentiment(ticker, opt_ticker, asset_name)

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_history(api_key): return historical_data.fetch_fred_history(api_key)

# --- CACHING FUNCTIONS ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_cot(ticker): return cot_data.fetch_cot_data(ticker)

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_cot_history(ticker, weeks_to_fetch): return cot_data.fetch_cot_history(ticker, weeks_to_fetch=weeks_to_fetch)


# --- SIDEBAR ---
with st.sidebar:
    st.header("🧠 Quant Brain Settings")
    with st.form("api_settings_form"):
        st.subheader("API Connections")
        
        # --- THE FIX: Add .strip() to the end of this line ---
        fred_key = st.text_input("FRED Key (Powers Models 1 & 2):", type="password").strip() 
        
        st.divider()
        st.subheader("Dashboard Settings")
        
        ASSET_MAPPING = {
            "S&P 500": {"cftc": "13874A", "yf": "^GSPC", "opt": "SPY"}, 
            "NASDAQ 100": {"cftc": "209742", "yf": "^NDX", "opt": "QQQ"}, 
            "GOLD": {"cftc": "088691", "yf": "GC=F", "opt": "GLD"}, 
            "SILVER": {"cftc": "084691", "yf": "SI=F", "opt": "SLV"}, 
            "CRUDE OIL": {"cftc": "067651", "yf": "CL=F", "opt": "USO"}, 
            "US DOLLAR INDEX": {"cftc": "098662", "yf": "DX-Y.NYB", "opt": "UUP"}, 
            "10-YR TREASURY": {"cftc": "043602", "yf": "^TNX", "opt": "IEF"},
            "RUSSELL 2000": {"cftc": "239742", "yf": "^RUT", "opt": "IWM"},

    # --- SPDR Sector ETFs: no CFTC futures contract exists for these,
    # so "cftc" is None — the COT sub-score will simply be skipped
    # for these assets (see the app.py guard below).
            "COM SVCS": {"cftc": "13874P", "yf": "XLC", "opt": "XLC"},
            "CONS DISC": {"cftc": None, "yf": "XLY", "opt": "XLY"},  # code not yet found
            "CONS STAP": {"cftc": "138748", "yf": "XLP", "opt": "XLP"},
            "ENERGY": {"cftc": "138749", "yf": "XLE", "opt": "XLE"},
            "FINANCIALS": {"cftc": "13874C", "yf": "XLF", "opt": "XLF"},
            "HEALTH CARE": {"cftc": "13874E", "yf": "XLV", "opt": "XLV"},
            "INDUSTRIALS": {"cftc": "13874F", "yf": "XLI", "opt": "XLI"},
            "MATERIALS": {"cftc": None, "yf": "XLB", "opt": "XLB"},  # code not yet found
            "REAL ESTATE": {"cftc": None, "yf": "XLRE", "opt": "XLRE"},  # code not yet found
            "TECHNOLOGY": {"cftc": "13874I", "yf": "XLK", "opt": "XLK"},
            "UTILITIES": {"cftc": "13874J", "yf": "XLU", "opt": "XLU"},
        }
        
        selected_asset = st.selectbox("Choose an Asset to Analyze:", list(ASSET_MAPPING.keys()))
        history_bar = st.slider("Historical Data Range (Prints):", min_value=3, max_value=24, value=6)
        
        submit_button = st.form_submit_button("⚡ Apply Settings & Fetch Data")

    cftc_ticker = ASSET_MAPPING[selected_asset]["cftc"]
    yf_ticker = ASSET_MAPPING[selected_asset]["yf"]
    opt_ticker = ASSET_MAPPING[selected_asset]["opt"]
    
    # --- NEW: MANUAL FORECAST EDITOR ---
    st.divider()
    with st.expander("📝 Edit Manual Forecasts"):
        st.caption("Update your baseline estimates. Changes save locally to JSON.")
        
        current_forecasts = forecast_manager.load_forecasts()
        new_forecasts = {}
        
        with st.form("forecast_editor_form"):
            for metric, current_val in current_forecasts.items():
                new_forecasts[metric] = st.number_input(f"{metric} Est:", value=float(current_val), step=0.1)
            
            save_clicked = st.form_submit_button("💾 Save Forecasts to Disk")
            
            if save_clicked:
                forecast_manager.save_forecasts(new_forecasts)
                st.success("Locked in! Click 'Apply Settings' above to refresh the dashboard.")


# --- MAIN APP ROUTING (TABS) ---
if fred_key: # --- NO MORE FINNHUB GATEKEEPER ---
    tab_surprises, tab_momentum, tab_charts = st.tabs([
        "⚡ Model 1: Wall St Surprises", 
        "🌊 Model 2: Structural Momentum", 
        "📈 Historical Charts"
    ])
    
    with st.spinner("Compiling multi-model quantitative data..."):
        try:
            # 1. Base Logic
            cot = get_cached_cot(cftc_ticker) if cftc_ticker else None
            tech = get_cached_technicals(yf_ticker, opt_ticker, selected_asset)

            # 2. Pull FRED Historical Data
            all_hist_full = get_cached_history(fred_key) 
            all_hist = {k: v.tail(max(history_bar, 6)) for k, v in all_hist_full.items()}
            
            # --- NEW: Calculate 2-Year Yield 30d SMA natively from FRED ---
            daily_yield = all_hist_full.get("2 Yr Yield Daily (%)", pd.DataFrame())
            if not daily_yield.empty and len(daily_yield) >= 30:
                daily_yield = daily_yield.dropna() # Drop weekend/holiday NaNs
                current_y = daily_yield['Value'].iloc[-1]
                sma_30 = daily_yield['Value'].rolling(window=30).mean().iloc[-1]
                yield_data = {
                    "value": round(current_y, 2), 
                    "difference": round(current_y - sma_30, 2), 
                    "forecast": round(sma_30, 2)
                }
            else:
                yield_data = {"value": "N/A", "difference": 0, "forecast": "N/A"}
            
            mapping_keys = {
                "GDP Growth QoQ": "GDP Growth QoQ (%)", "Retail Sales MoM": "Retail Sales MoM (%)",
                "Personal Income MoM": "Personal Income MoM (%)", 
                "Personal Spending MoM": "Personal Spending MoM (%)", 
                "Personal Savings Rate": "Personal Savings Rate (%)",   
                "CPI YoY": "CPI YoY (%)",
                "PPI YoY": "PPI YoY (%)", "PCE YoY": "PCE YoY (%)",
                "Non-Farm Payroll": "Non-Farm Payroll (k)", "Unemployment Rate %": "Unemployment Rate (%)",
                "Weekly Jobless Claims": "Weekly Jobless Claims (k)", "JOLTS Job Openings": "JOLTS Openings (M)",
                "Fed Funds Rate": "Fed Funds Rate (%)" 
            }
            
# --- NEW: COMPILE CUSTOM MODEL 1 (FRED ACTUALS VS JSON FORECASTS) ---
            my_forecasts = forecast_manager.load_forecasts()
            custom_model_1 = {}
            
            for standard_name, fred_name in mapping_keys.items():
                df = all_hist_full.get(fred_name, pd.DataFrame()) 
                if not df.empty:
                    actual_value = round(df['Value'].iloc[-1], 2)
                    manual_est = float(my_forecasts.get(standard_name, 0.0))
                    
                    custom_model_1[standard_name] = {
                        "value": actual_value, 
                        "difference": round(actual_value - manual_est, 2), 
                        "forecast": manual_est
                    }
                else:
                    custom_model_1[standard_name] = {"value": "N/A", "difference": 0, "forecast": "N/A"}

            # --- MUST NOT DELETE: Inject Yield & PMIs into Model 1 ---
            custom_model_1["2 Yr Yield (30d SMA)"] = {
                "value": yield_data["value"], "difference": yield_data["difference"], "forecast": yield_data["forecast"]
            }
            custom_model_1["Manufacturing PMI"] = {
                "value": my_forecasts.get("Manufacturing PMI Actual", 50.0), 
                "difference": round(my_forecasts.get("Manufacturing PMI Actual", 50.0) - my_forecasts.get("Manufacturing PMI Forecast", 50.0), 2), 
                "forecast": my_forecasts.get("Manufacturing PMI Forecast", 50.0)
            }
            custom_model_1["Services PMI"] = {
                "value": my_forecasts.get("Services PMI Actual", 50.0), 
                "difference": round(my_forecasts.get("Services PMI Actual", 50.0) - my_forecasts.get("Services PMI Forecast", 50.0), 2), 
                "forecast": my_forecasts.get("Services PMI Forecast", 50.0)
            }
            custom_model_1["Michigan Consumer Sentiment"] = {
                "value": my_forecasts.get("Michigan Consumer Sentiment Actual", 70.0), 
                "difference": round(my_forecasts.get("Michigan Consumer Sentiment Actual", 70.0) - my_forecasts.get("Michigan Consumer Sentiment Forecast", 70.0), 2), 
                "forecast": my_forecasts.get("Michigan Consumer Sentiment Forecast", 70.0)
            }
            
            # --- COMPILE MODEL 2 (STRUCTURAL MOMENTUM) ---
            fred_macro = {}
            for standard_name, fred_name in mapping_keys.items():
                df = all_hist.get(fred_name, pd.DataFrame())
                if not df.empty and len(df) >= 2:
                    latest_val = df['Value'].iloc[-1]
                    
                    # Since Liquidity is weekly data, iloc[-2] is exactly 1 week ago.
                    # Other metrics use iloc[-2] for standard month-over-month.
                    prev_val = df['Value'].iloc[-2] 
                        
                    fred_macro[standard_name] = {
                        "value": latest_val, "difference": round(latest_val - prev_val, 2), "forecast": prev_val
                    }
                else:
                    fred_macro[standard_name] = {"value": "N/A", "difference": 0, "forecast": "N/A"}

            # --- MUST NOT DELETE: Inject Yield & PMIs into Model 2 ---
            fred_macro["2 Yr Yield (30d SMA)"] = {
                "value": yield_data["value"], "difference": yield_data["difference"], "forecast": yield_data["forecast"]
            }
            fred_macro["Manufacturing PMI"] = {
                "value": my_forecasts.get("Manufacturing PMI Actual", 50.0), 
                "difference": round(my_forecasts.get("Manufacturing PMI Actual", 50.0) - my_forecasts.get("Manufacturing PMI Previous", 50.0), 2), 
                "forecast": my_forecasts.get("Manufacturing PMI Previous", 50.0)
            }
            fred_macro["Services PMI"] = {
                "value": my_forecasts.get("Services PMI Actual", 50.0), 
                "difference": round(my_forecasts.get("Services PMI Actual", 50.0) - my_forecasts.get("Services PMI Previous", 50.0), 2), 
                "forecast": my_forecasts.get("Services PMI Previous", 50.0)
            }
            fred_macro["Michigan Consumer Sentiment"] = {
                "value": my_forecasts.get("Michigan Consumer Sentiment Actual", 70.0), 
                "difference": round(my_forecasts.get("Michigan Consumer Sentiment Actual", 70.0) - my_forecasts.get("Michigan Consumer Sentiment Previous", 70.0), 2), 
                "forecast": my_forecasts.get("Michigan Consumer Sentiment Previous", 70.0)
            }
            
            # --- RENDER TAB 1 ---
            with tab_surprises:
                st.markdown(f"### Custom Surprise Analysis: **{selected_asset}**")
                # Now passing your Custom Model instead of Finnhub
                render_dashboard(custom_model_1, tech, cot, selected_asset, mode="Surprise", log_this_run=submit_button)
                
            # --- RENDER TAB 2 ---
            with tab_momentum:
                st.markdown(f"### FRED Momentum Analysis: **{selected_asset}**")
                render_dashboard(fred_macro, tech, cot, selected_asset, mode="Trend", log_this_run=submit_button)

        except Exception as e:
            st.error(f"Error compiling models: {e}")
# --- RENDER TAB 3 (CHARTS) ---
    with tab_charts:
        st.markdown("### Historical Market Trajectory")
        st.caption("Visualizing the historical prints of US macroeconomic data to track underlying trend shifts.")
        
        def render_chart(title, df, chart_type="bar", y_domain=None):
            st.markdown(f"**{title}**")
            if not df.empty: 
                chart_data = df.reset_index()
                
                if y_domain:
                    y_scale = alt.Scale(domain=y_domain, clamp=True)
                elif chart_type == "line":
                    y_scale = alt.Scale(zero=False)
                else:
                    y_scale = alt.Scale(zero=True)
                
                base = alt.Chart(chart_data).encode(
                    x=alt.X('yearmonthdate(Date):O', 
                            title=None, 
                            axis=alt.Axis(format="%Y %b %d", labelAngle=-45, grid=False)
                    ),
                    y=alt.Y('Value:Q', title=None, scale=y_scale),
                    tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'), alt.Tooltip('Value:Q')]
                ).properties(height=350)

                if chart_type == "line":
                    chart = base.mark_line(
                        color="#2962FF", 
                        strokeWidth=4, 
                        point=alt.OverlayMarkDef(color="#2962FF", size=80, filled=True)
                    )
                else:
                    chart = base.mark_bar(
                        color="#2962FF", 
                        cornerRadiusTopLeft=4, 
                        cornerRadiusTopRight=4
                    ).encode(
                        x=alt.X('yearmonthdate(Date):O', 
                                title=None, 
                                axis=alt.Axis(format="%Y %b %d", labelAngle=-45, grid=False),
                                scale=alt.Scale(paddingInner=0.15) 
                        )
                    )
                
                st.altair_chart(chart, use_container_width=True)
            else: 
                st.info("Awaiting sufficient historical data.")

        def render_cot_positioning_chart(cot_hist_df, asset_name):
            st.markdown(f"**Non-Commercial Long vs Short Positioning (%): {asset_name}**")

            if cot_hist_df.empty:
                st.info(f"No COT futures data available for {asset_name} — either it has no listed futures contract, or the data is temporarily unavailable.")
                return
     
            plot_data = cot_hist_df.reset_index()

            long_line = alt.Chart(plot_data).mark_line(
                color="#2962FF", strokeWidth=3,
                point=alt.OverlayMarkDef(color="#2962FF", size=50, filled=True)
            ).encode(
                x=alt.X('yearmonthdate(Date):O', title=None,
                    axis=alt.Axis(format="%Y %b %d", labelAngle=-45)),
                y=alt.Y('Long %:Q', title="Share of Non-Commercial Positions (%)",
                    scale=alt.Scale(domain=[0, 100])),
                tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'), alt.Tooltip('Long %:Q')]
            )

            short_line = alt.Chart(plot_data).mark_line(
                color="#F44336", strokeWidth=3, strokeDash=[4, 2],
                point=alt.OverlayMarkDef(color="#F44336", size=50, filled=True)
            ).encode(
                x=alt.X('yearmonthdate(Date):O', title=None),
                y=alt.Y('Short %:Q', scale=alt.Scale(domain=[0, 100])),
                tooltip=[alt.Tooltip('Date:T', format='%Y-%m-%d'), alt.Tooltip('Short %:Q')]
            )

            st.altair_chart((long_line + short_line).properties(height=350), use_container_width=True)
            st.caption("🔵 Long % — 🔴 Short % (dashed). Share of non-commercial (speculative) futures positioning. Source: CFTC COT.")

        st.subheader("🔥 Inflation Trends")
        i1, i2, i3, i4 = st.columns(4)
        with i1: render_chart("CPI YoY (%)", all_hist.get("CPI YoY (%)", pd.DataFrame()), chart_type="line")
        with i2: render_chart("PPI YoY (%)", all_hist.get("PPI YoY (%)", pd.DataFrame()), chart_type="line")
        with i3: render_chart("PCE YoY (%)", all_hist.get("PCE YoY (%)", pd.DataFrame()), chart_type="line")
        with i4: render_chart("2 Yr Yield (Monthly Avg %)", all_hist.get("2 Yr Yield (%)", pd.DataFrame()), chart_type="line")

        st.divider()
        st.subheader("🎯 Growth vs Inflation Composite")
        render_combo_chart(
            all_hist.get("Non-Farm Payroll (k)", pd.DataFrame()),
            all_hist.get("Retail Sales MoM (%)", pd.DataFrame()),
            all_hist.get("CPI YoY (%)", pd.DataFrame())
        )    

        st.divider()
        st.subheader("📈 Economic Growth & Production")
        g1, g2 = st.columns(2)
        with g1: render_chart("GDP Growth QoQ (%)", all_hist.get("GDP Growth QoQ (%)", pd.DataFrame()))
        with g2: render_chart("Retail Sales MoM (%)", all_hist.get("Retail Sales MoM (%)", pd.DataFrame()))
        
        st.divider()
        st.subheader("🛒 State of the Consumer")
        c1, c2, c3 = st.columns(3)
        with c1: render_chart("Personal Income MoM (%)", all_hist.get("Personal Income MoM (%)", pd.DataFrame()))
        with c2: render_chart("Personal Spending MoM (%)", all_hist.get("Personal Spending MoM (%)", pd.DataFrame()))
        with c3: render_chart("Personal Savings Rate (%)", all_hist.get("Personal Savings Rate (%)", pd.DataFrame()))

        st.divider()
        st.subheader("💼 Labor Market")
        j1, j2, j3, j4 = st.columns(4)
        with j1: render_chart("Non-Farm Payroll (k)", all_hist.get("Non-Farm Payroll (k)", pd.DataFrame()))
        with j2: render_chart("Unemployment Rate (%)", all_hist.get("Unemployment Rate (%)", pd.DataFrame()))
        with j3: render_chart("Weekly Jobless Claims (k)", all_hist.get("Weekly Jobless Claims (k)", pd.DataFrame()), chart_type="line", y_domain=(150, 250))
        with j4: render_chart("JOLTS Openings (M)", all_hist.get("JOLTS Openings (M)", pd.DataFrame()), chart_type="line", y_domain=(6, 8))
        
        st.divider()
        st.subheader("💧 System Liquidity")
        render_chart(
            "US Net Liquidity (Billions)", 
            all_hist.get("US Net Liquidity (B)", pd.DataFrame()), 
            chart_type="line", 
            y_domain=[5500, 6000]
        )
        st.divider() 
        st.subheader("📊 Institutional COT Positioning")
        
        # --- NEW: GLOBAL COT OVERVIEW (Stacked Bar Chart) ---
        st.markdown("**Global Asset Comparison (Latest Positions)**")
        
        # 1. Gather the latest COT data for all mapped assets
        global_cot_data = []
        for asset_name, config in ASSET_MAPPING.items():
            current_cftc = config.get("cftc")
            if current_cftc:
                # We use the existing cached function so it loads instantly!
                cot_latest = get_cached_cot(current_cftc)
                if cot_latest:
                    # Append Long row
                    global_cot_data.append({"Asset": asset_name, "Position": "Long %", "Percentage": cot_latest['long_pct']})
                    # Append Short row
                    global_cot_data.append({"Asset": asset_name, "Position": "Short %", "Percentage": cot_latest['short_pct']})
        # 2. Build the Altair 100% Stacked Bar Chart
        if global_cot_data:
            df_global = pd.DataFrame(global_cot_data)
            
            # THE FIX 1: Removed 'size=25' so Altair can dynamically size the bars
            global_cot_chart = alt.Chart(df_global).mark_bar(cornerRadius=2).encode(
                x=alt.X('Percentage:Q', title="Positioning (%)", scale=alt.Scale(domain=[0, 100])),
                
                # THE FIX 2: Added 'paddingInner=0.4' to force empty space between the rows
                y=alt.Y('Asset:N', title=None, scale=alt.Scale(paddingInner=0.4)),
                
                color=alt.Color('Position:N', 
                                scale=alt.Scale(domain=['Long %', 'Short %'], range=['#2962FF', '#F44336']),
                                legend=alt.Legend(orient='bottom', title=None)),
                order=alt.Order('Position:N', sort='ascending'), 
                tooltip=[alt.Tooltip('Asset:N'), alt.Tooltip('Position:N'), alt.Tooltip('Percentage:Q')]
            ).properties(height=450) # THE FIX 3: Increased overall height to 450 to give it more breathing room
            
            st.altair_chart(global_cot_chart, use_container_width=True)
        else:
            st.info("No global COT data available to build the overview chart.")
            
        st.markdown("<br>", unsafe_allow_html=True) # Visual spacer
        
        # --- EXISTING INDIVIDUAL ASSET HISTORY ---
        if cftc_ticker:
            cot_history_df = get_cached_cot_history(cftc_ticker, weeks_to_fetch=history_bar)
        else:
            cot_history_df = pd.DataFrame()
        render_cot_positioning_chart(cot_history_df, selected_asset)

else:
    st.info("👈 Please enter your FRED API key in the sidebar and click **Apply Settings** to begin.")