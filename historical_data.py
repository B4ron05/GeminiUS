import pandas as pd
from fredapi import Fred
import time

def fetch_fred_history(api_key):
    """
    Pulls historical government macro data.
    Pulls the entire series to protect the API rate limit.
    """
    fred = Fred(api_key=api_key)
    
    metrics = {
        "GDP Growth QoQ (%)": {"id": "GDPC1", "units": "pch", "divide": 1},
        "Retail Sales MoM (%)": {"id": "RSAFS", "units": "pch", "divide": 1},      
        "Personal Income MoM (%)": {"id": "PI", "units": "pch", "divide": 1},
        "Personal Spending MoM (%)": {"id": "PCE", "units": "pch", "divide": 1},  # <--- NEW
        "Personal Savings Rate (%)": {"id": "PSAVERT", "units": "lin", "divide": 1},
        "CPI YoY (%)": {"id": "CPIAUCSL", "units": "pc1", "divide": 1},             
        "PPI YoY (%)": {"id": "PPIFIS", "units": "pc1", "divide": 1},
        "PCE YoY (%)": {"id": "PCEPI", "units": "pc1", "divide": 1},             
        "2 Yr Yield (%)": {"id": "GS2", "units": "lin", "divide": 1},         
        "2 Yr Yield Daily (%)": {"id": "DGS2", "units": "lin", "divide": 1},  
        "Fed Funds Rate (%)": {"id": "FEDFUNDS", "units": "lin", "divide": 1}, # <--- RESTORES THE API DATA
        "Non-Farm Payroll (k)": {"id": "PAYEMS", "units": "chg", "divide": 1},      
        "Unemployment Rate (%)": {"id": "UNRATE", "units": "lin", "divide": 1},
        "Weekly Jobless Claims (k)": {"id": "ICSA", "units": "lin", "divide": 1000},
        "JOLTS Openings (M)": {"id": "JTSJOL", "units": "lin", "divide": 1000}
    }
    
    results = {}
    
    # --- 1. STANDARD METRICS LOOP ---
    for name, config in metrics.items():
        try:
            time.sleep(0.2) # THIS FIXES THE RATE LIMIT CRASH
            data = fred.get_series(config["id"], units=config["units"])
            
            df = pd.DataFrame({
                "Date": data.index,
                "Value": (data / config["divide"]).round(2)
            }).set_index("Date")
            
            results[name] = df
        except Exception as e:
            print(f"Error fetching {name} from FRED: {e}")
            results[name] = pd.DataFrame()

    # --- 2. SYSTEM LIQUIDITY CALCULATION (Business Days) ---
    try:
        time.sleep(0.2)
        walcl = fred.get_series('WALCL') / 1000      
        time.sleep(0.2)
        tga = fred.get_series('WTREGEN') / 1000    
        time.sleep(0.2)
        rrpontsyd = fred.get_series('RRPONTSYD')     

        # Strip timezones
        walcl.index = pd.to_datetime(walcl.index).tz_localize(None)
        tga.index = pd.to_datetime(tga.index).tz_localize(None)
        rrpontsyd.index = pd.to_datetime(rrpontsyd.index).tz_localize(None)

        # Safely combine the time series
        liq_df = pd.concat([walcl, tga, rrpontsyd], axis=1, keys=['WALCL', 'TGA', 'RRPONTSYD'])
        
        # Resample to 'B' (Business Days) to ignore weekends
        liq_df = liq_df.sort_index().resample('B').ffill().dropna()
        
        # Calculate Net Liquidity
        liq_df['Net Liquidity'] = liq_df['WALCL'] - liq_df['TGA'] - liq_df['RRPONTSYD']
        
        results["US Net Liquidity (B)"] = pd.DataFrame({
            "Date": liq_df.index,
            "Value": liq_df['Net Liquidity'].round(2)
        }).set_index("Date")
        
    except Exception as e:
        print(f"\n--- CRITICAL LIQUIDITY ERROR: {e} ---\n")
        results["US Net Liquidity (B)"] = pd.DataFrame()

    return results