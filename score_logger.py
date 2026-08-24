"""
score_logger.py

Appends every computed Edge Score to a local CSV so you build an
auditable, timestamped history from day one — this is the raw material
for the public track record discussed for the content/business side of
the project. Call log_score(...) once per render, after the master
score is computed in render_dashboard().

Design notes:
- Append-only, one row per (timestamp, asset, mode) — never edits past
  rows, so the log can't be quietly "cleaned up" later, which matters
  for credibility.
- CSV rather than the forecasts.json pattern used elsewhere, because
  this file will grow indefinitely and you'll eventually want to load
  it into pandas for review/charting, or migrate it into a real DB
  once this moves off a single machine.
"""

import csv
import os
from datetime import datetime, timezone

LOG_FILE = "score_history.csv"
FIELDS = ["timestamp_utc", "asset", "mode", "total_score", "master_bias",
          "macro_score", "tech_score", "cot_score"]


def log_score(asset, mode, total_score, master_bias, macro_score, tech_score, cot_score):
    file_exists = os.path.exists(LOG_FILE)
    try:
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "asset": asset,
                "mode": mode,
                "total_score": total_score,
                "master_bias": master_bias,
                "macro_score": macro_score,
                "tech_score": tech_score,
                "cot_score": cot_score,
            })
        return True
    except Exception as e:
        print(f"Score logging failed: {e}")
        return False


def load_score_history():
    """Returns the full log as a pandas DataFrame, or an empty one if none exists yet."""
    import pandas as pd
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=FIELDS)
    return pd.read_csv(LOG_FILE, parse_dates=["timestamp_utc"])
