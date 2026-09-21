import pandas as pd

def load_forecasts():
    # Replace with your actual Google Sheet ID
    sheet_id = "1ae3ph6Qzjp8OfjwUNI_aRqtiwLVRuaBRZUzKrNtYacU"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    # Read the Google Sheet data
    df = pd.read_csv(url)
    
    # Convert the dataframe to a list of dictionaries
    forecasts_list = df.to_dict(orient='records')
    
    # Return the first (and only) dictionary to perfectly match your old JSON structure
    return forecasts_list[0]
