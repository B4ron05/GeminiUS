import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

REQUIRED_COLS = ['noncomm_positions_long_all', 'noncomm_positions_short_all']


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get(url, params, timeout=10):
    """Isolated network call so retry logic doesn't accidentally retry parsing bugs too."""
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response


def fetch_cot_data(cftc_ticker, weeks_to_fetch=2):
    """
    Fetches COT data and calculates Long/Short Percentages.
    Returns None (rather than raising) on any data-quality problem, so callers
    can render an "offline" state instead of crashing the dashboard.
    """
    url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    params = {
        "cftc_contract_market_code": cftc_ticker,
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": weeks_to_fetch
    }

    try:
        response = _get(url, params)
    except requests.exceptions.RequestException as e:
        print(f"COT API request failed after retries: {e}")
        return None

    try:
        data = response.json()
    except ValueError as e:
        print(f"COT API returned invalid JSON: {e}")
        return None

    if not data or len(data) < 2:
        return None

    df = pd.DataFrame(data)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        # CFTC has renamed fields before without notice — fail loud in logs, soft in UI
        print(f"COT response missing expected columns: {missing}")
        return None

    try:
        df[REQUIRED_COLS] = df[REQUIRED_COLS].apply(pd.to_numeric)
    except (ValueError, TypeError) as e:
        print(f"COT numeric conversion failed: {e}")
        return None

    # --- Current Week ---
    curr_long = df['noncomm_positions_long_all'].iloc[0]
    curr_short = df['noncomm_positions_short_all'].iloc[0]
    curr_total = curr_long + curr_short

    if curr_total <= 0:
        print("COT current-week long+short total is zero — cannot compute percentages.")
        return None

    curr_long_pct = round((curr_long / curr_total) * 100, 2)
    curr_short_pct = round((curr_short / curr_total) * 100, 2)

    # --- Previous Week ---
    prev_long = df['noncomm_positions_long_all'].iloc[1]
    prev_short = df['noncomm_positions_short_all'].iloc[1]
    prev_total = prev_long + prev_short

    if prev_total <= 0:
        print("COT previous-week long+short total is zero — cannot compute change.")
        return None

    prev_long_pct = round((prev_long / prev_total) * 100, 2)

    change_pct = round(curr_long_pct - prev_long_pct, 2)

    return {
        "long_pct": curr_long_pct,
        "short_pct": curr_short_pct,
        "change_pct": change_pct
    }
def fetch_cot_history(cftc_ticker, weeks_to_fetch=26):
    """
    Fetches a time series of non-commercial long/short positioning (%) for
    charting, as opposed to fetch_cot_data() which only returns the latest
    week-over-week change for scoring.
    """
    url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    params = {
        "cftc_contract_market_code": cftc_ticker,
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": weeks_to_fetch
    }

    try:
        response = _get(url, params)
    except requests.exceptions.RequestException as e:
        print(f"COT history request failed: {e}")
        return pd.DataFrame()

    try:
        data = response.json()
    except ValueError as e:
        print(f"COT history returned invalid JSON: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        print(f"COT history missing expected columns: {missing}")
        return pd.DataFrame()

    try:
        df[REQUIRED_COLS] = df[REQUIRED_COLS].apply(pd.to_numeric)
    except (ValueError, TypeError) as e:
        print(f"COT history numeric conversion failed: {e}")
        return pd.DataFrame()

    df['Date'] = pd.to_datetime(df['report_date_as_yyyy_mm_dd'])
    df['total'] = df['noncomm_positions_long_all'] + df['noncomm_positions_short_all']
    df = df[df['total'] > 0]  # guard against a zero-total week
    df['Long %'] = round((df['noncomm_positions_long_all'] / df['total']) * 100, 2)
    df['Short %'] = round((df['noncomm_positions_short_all'] / df['total']) * 100, 2)

    return df[['Date', 'Long %', 'Short %']].sort_values('Date').set_index('Date')
