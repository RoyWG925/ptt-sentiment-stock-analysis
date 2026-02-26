import yfinance as yf
import pandas as pd

def fetch_taiex_data(start_date, end_date):
    taiex = yf.Ticker("^TWII")
    data = taiex.history(start=start_date, end=end_date)
    data.to_csv("taiex_data_20250324_20250423.csv")
    return data

start_date = "2025-03-24"
end_date = "2025-04-24"  # 包含4月23日
taiex_data = fetch_taiex_data(start_date, end_date)