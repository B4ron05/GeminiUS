import yfinance as yf
import pandas as pd
from datetime import datetime
import fear_and_greed


def _default_results():
    return {
        "4H / Daily Trend": {"value": "N/A", "difference": 0},
        "Seasonality Trend": {"value": "N/A", "difference": 0},
        "Fear & Greed Index": {"value": "N/A", "difference": 0, "retail_long": 0, "retail_short": 0}
    }


def fetch_technicals_and_sentiment(ticker, opt_ticker, asset_name):
    results = _default_results()
    tk = None

    # 1. 4H / Daily Trend (50 SMA)
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="6mo")
        if not hist.empty:
            hist = hist.dropna(subset=['Close'])
            if len(hist) >= 50:
                current_price = hist['Close'].iloc[-1]
                sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                delta = round(current_price - sma_50, 2)
                results["4H / Daily Trend"] = {"value": round(current_price, 2), "difference": delta}
    except Exception as e:
        print(f"Trend Error ({asset_name}): {e}")

    # 2. Seasonality Trend (10-Year Historical Average)
    # Guarded on tk being set — previously this silently relied on the first
    # try block having succeeded; if ticker fetch failed, this raised NameError
    # (caught, but wastefully, and without a clear log message).
    if tk is not None:
        try:
            hist_10y = tk.history(period="10y")
            if not hist_10y.empty:
                monthly_data = hist_10y['Close'].resample('ME').last()
                monthly_returns = monthly_data.pct_change() * 100

                now = datetime.now()
                current_month_num = now.month
                current_year = now.year
                current_month_name = now.strftime('%b')

                seasonal_returns = monthly_returns[monthly_returns.index.month == current_month_num]
                seasonal_returns = seasonal_returns[seasonal_returns.index.year < current_year]

                if len(seasonal_returns) > 0:
                    avg_return = round(seasonal_returns.mean(), 2)
                    results["Seasonality Trend"] = {
                        "value": f"{current_month_name} Avg",
                        "difference": avg_return
                    }
                else:
                    print(f"Seasonality: no prior-year history for month {current_month_num} ({asset_name})")
        except Exception as e:
            print(f"Seasonality Error ({asset_name}): {e}")
    else:
        print(f"Seasonality skipped — ticker fetch failed earlier ({asset_name})")

    # 3. CNN Fear & Greed Index (Broad Market Retail Sentiment)
    try:
        fg_data = fear_and_greed.get()
        score = round(fg_data.value, 1)
        description = fg_data.description

        if score < 25:
            bias_text = "Contra BUY"
            contrarian_score = 20
        elif score > 75:
            bias_text = "Contra SELL"
            contrarian_score = -20
        else:
            bias_text = "Neutral"
            contrarian_score = 0

        results["Fear & Greed Index"] = {
            "value": description,
            "difference": contrarian_score,
            "retail_long": score,
            "retail_short": 100 - score
        }
    except Exception as e:
        # FIX: this previously wrote to the misspelled key "Fear @ Greed Index",
        # which meant a failed fetch never actually reset the real key —
        # the dashboard just silently kept showing whatever was last in `results`.
        print(f"CNN F&G Error ({asset_name}): {e}")
        results["Fear & Greed Index"] = {"value": "N/A", "difference": 0, "retail_long": 0, "retail_short": 0}

    return results


def fetch_yield_trend(ticker="^TNX"):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo")
        if hist.empty or len(hist) < 30:
            return {"value": "N/A", "difference": 0, "sma": "N/A"}
        current = hist['Close'].iloc[-1]
        sma_30 = hist['Close'].rolling(window=30).mean().iloc[-1]
        diff = round(current - sma_30, 2)
        return {"value": round(current, 2), "difference": diff, "sma": round(sma_30, 2)}
    except Exception as e:
        print(f"Yield trend error: {e}")
        return {"value": "N/A", "difference": 0, "sma": "N/A"}
