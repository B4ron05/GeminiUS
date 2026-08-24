# Add ffr_val and cpi_val to the end of the arguments
def evaluate_bias(asset, metric_name, difference, current_value=None, ffr_val=None, cpi_val=None):
    """
    Evaluates macro data based on the specific asset class.
    Returns a tuple: (Bias Text, Hex Color)
    """
    BULLISH = "#2962FF"
    BEARISH = "#F44336"
    NEUTRAL = "#808080"

    equities = ["S&P 500", "NASDAQ 100", "RUSSELL 2000",
            "COM SVCS", "CONS DISC",
            "CONS STAP", "FINANCIALS", "HEALTH CARE",
            "INDUSTRIALS", "MATERIALS", "TECHNOLOGY"]
    metals = ("GOLD", "SILVER")
    energy = ["CRUDE OIL", "ENERGY"]
    usd = ["US DOLLAR INDEX"]
    bonds = ["10-YR TREASURY", "REAL ESTATE", "UTILITIES"]

    FFR = None
    if metric_name == "Fed Funds Rate" and current_value is not None and current_value != "N/A":
        FFR = current_value

    if metric_name == "Fed Funds Rate":
        if difference > 0:  # Rate Hike
            if asset in equities or asset in metals or asset in bonds: return "Bearish", BEARISH
            if asset in usd: return "Bullish", BULLISH
        elif difference < 0:  # Rate Cut
            if asset in equities or asset in metals or asset in bonds: return "Bullish", BULLISH
            if asset in usd: return "Bearish", BEARISH
        elif FFR is not None:  # Unchanged — fall back to absolute restrictiveness
            if FFR > 4.5:
                if asset in equities or asset in metals or asset in bonds: return "Bearish", BEARISH
                if asset in usd: return "Bullish", BULLISH
            else:
                return "Neutral", NEUTRAL

    # --- 1. GROWTH & CONSUMPTION BLOCK ---
    elif metric_name in ["GDP Growth QoQ", "Retail Sales MoM", "Personal Income MoM", "Manufacturing PMI", "Services PMI"]:
        if difference > 0:
            if asset in equities or asset in energy or asset in usd: return "Bullish", BULLISH
            if asset in metals or asset in bonds: return "Bearish", BEARISH
        elif difference < 0:
            if asset in equities or asset in energy or asset in usd: return "Bearish", BEARISH
            if asset in metals or asset in bonds: return "Bullish", BULLISH

    # --- 1.b. INVERSE CONSUMER BLOCK (Savings) ---
    elif metric_name == "Personal Savings Rate":
        if difference > 0:
            if asset in usd: return "Bearish", BEARISH
            if asset in metals or asset in bonds or asset in equities or asset in energy: return "Bullish", BULLISH
        elif difference < 0:
            if asset in usd: return "Bullish", BULLISH
            if asset in metals or asset in bonds or asset in equities or asset in energy: return "Bearish", BEARISH
    # --- 1.c. SOFT DATA THRESHOLD (Michigan Sentiment) ---
    # Survey-based data is noisier than hard data — small month-to-month
    # wiggles are mostly statistical noise, not signal. Require a bigger
    # move before it's allowed to flip the bias away from Neutral.
    elif metric_name == "Michigan Consumer Sentiment":
        MICHIGAN_THRESHOLD = 3.0  # index points — tune this as you gather more history

        if difference > MICHIGAN_THRESHOLD:
            if asset in equities or asset in energy or asset in usd: return "Bullish", BULLISH
            if asset in metals or asset in bonds: return "Bearish", BEARISH
        elif difference < -MICHIGAN_THRESHOLD:
            if asset in equities or asset in energy or asset in usd: return "Bearish", BEARISH
            if asset in metals or asset in bonds: return "Bullish", BULLISH
        else:
            return "Neutral", NEUTRAL

    # --- 2. INFLATION BLOCK ---
    elif metric_name in ["CPI YoY", "PPI YoY", "PCE YoY"]:
        if difference > 0:
            if asset in equities or asset in bonds or asset in metals or asset in energy: return "Bearish", BEARISH
            if asset in usd: return "Bullish", BULLISH
        elif difference < 0:
            if asset in equities or asset in bonds or asset in metals or asset in energy: return "Bullish", BULLISH
            if asset in usd: return "Bearish", BEARISH

    # --- 3. LABOR MARKET BLOCK ---
    elif metric_name in ["Non-Farm Payroll", "JOLTS Job Openings", "Unemployment Rate %", "Weekly Jobless Claims"]:

        if difference == 0:
            return "Neutral", NEUTRAL

        if metric_name in ["Non-Farm Payroll", "JOLTS Job Openings"]:
            is_labor_strong = difference > 0
        else:
            is_labor_strong = difference < 0

        if ffr_val is not None and cpi_val is not None and ffr_val != "N/A" and cpi_val != "N/A":

            # Regime A: Fed is Behind the Curve (FFR < CPI) — "good news is bad news"
            if ffr_val < cpi_val:
                if is_labor_strong:
                    if asset in equities or asset in bonds or asset in metals or asset in energy: return "Bearish", BEARISH
                    if asset in usd: return "Bullish", BULLISH
                else:
                    if asset in equities or asset in bonds or asset in metals or asset in energy: return "Bullish", BULLISH
                    if asset in usd: return "Bearish", BEARISH

            # Regime B: Fed is Restrictive (FFR >= CPI) — "good news is good news"
            else:
                if is_labor_strong:
                    if asset in equities or asset in usd or asset in energy: return "Bullish", BULLISH
                    if asset in bonds or asset in metals: return "Bearish", BEARISH
                else:
                    if asset in equities or asset in usd or asset in energy: return "Bearish", BEARISH
                    if asset in bonds or asset in metals: return "Bullish", BULLISH

        else:
            if is_labor_strong:
                if asset in usd or asset in energy or asset in equities: return "Bullish", BULLISH
                if asset in metals or asset in bonds: return "Bearish", BEARISH
            else:
                if asset in usd or asset in energy or asset in equities: return "Bearish", BEARISH
                if asset in metals or asset in bonds: return "Bullish", BULLISH

    # --- 4. ANCHORING MECHANISM (2 Yr Yield via 30d SMA) ---
    elif metric_name == "2 Yr Yield (30d SMA)":
        if difference > 0:
            if asset in equities or asset in metals or asset in bonds or asset in energy: return "Bearish", BEARISH
            if asset in usd: return "Bullish", BULLISH
        elif difference < 0:
            if asset in equities or asset in metals or asset in bonds or asset in energy: return "Bullish", BULLISH
            if asset in usd: return "Bearish", BEARISH

    # --- 5. INSTITUTIONAL COT & TECHNICALS ---
    elif metric_name in ["Net Change (WoW)", "4H / Daily Trend", "Seasonality Trend"]:
        if difference > 0: return "Bullish", BULLISH
        elif difference < 0: return "Bearish", BEARISH

    return "Neutral", NEUTRAL


# --- Scoring range reference, kept in sync with app.py's category weighting ---
# Tech sub-score:  max ±0.5   (2 metrics, weighted to ±0.5 total)
# COT sub-score:   max ±0.5   (1 metric, weighted to ±0.5 total)
# Macro sub-score: max ±4.0   (4 groups x max ±1.0 each: Growth, Consumer, Inflation, Jobs)
# Master total:    max ±5.0
# NOTE: app.py's UI currently displays "±4.25" and "±5.25" — these labels
# are stale and don't match the actual group/metric counts. Update the
# hardcoded strings in app.py's custom_metric_card HTML to ±4.0 / ±5.0,
# or better, compute them from len(metric_groups) at render time so they
# can never drift out of sync again.
