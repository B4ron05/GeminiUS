import json
import os

FORECAST_FILE = "forecasts.json"

DEFAULT_FORECASTS = {
    "GDP Growth QoQ": 0.0,
    "Retail Sales MoM": 0.0,
    "Personal Income MoM": 0.0,
    "Personal Spending MoM": 0.0, # <--- NEW
    "Personal Savings Rate": 0.0,  # <--- NEW
    "CPI YoY": 0.0,
    "PPI YoY": 0.0,
    "PCE YoY": 0.0,
    "Non-Farm Payroll": 0.0,
    "Unemployment Rate %": 0.0,
    "Weekly Jobless Claims": 0.0,
    "JOLTS Job Openings": 0.0,
    "US Net Liquidity (B)": 0.0,
    "Fed Funds Rate": 0.0,  
    "Manufacturing PMI Forecast": 50.0,
    "Manufacturing PMI Actual": 50.0,
    "Manufacturing PMI Previous": 50.0,
    "Services PMI Forecast": 50.0,
    "Services PMI Actual": 50.0,
    "Services PMI Previous": 50.0,
    "Michigan Consumer Sentiment Forecast": 70.0, # <--- NEW
    "Michigan Consumer Sentiment Actual": 70.0,   # <--- NEW
    "Michigan Consumer Sentiment Previous": 70.0  # <--- NEW
}

def load_forecasts():
    if not os.path.exists(FORECAST_FILE):
        return DEFAULT_FORECASTS.copy()
    try:
        with open(FORECAST_FILE, "r") as file:
            return json.load(file)
    except Exception:
        return DEFAULT_FORECASTS.copy()

def save_forecasts(forecast_dict):
    try:
        with open(FORECAST_FILE, "w") as file:
            json.dump(forecast_dict, file, indent=4)
        return True
    except Exception:
        return False