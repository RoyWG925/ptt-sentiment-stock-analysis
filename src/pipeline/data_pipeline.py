# 檔案名稱: data_pipeline.py
import pandas as pd
import numpy as np
import sqlite3
import os
import re
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# --- 設定 ---
DB_PATH = os.getenv("DB_PATH_M", "database/ptt_data_m.db")
STOCK_CSV = os.getenv("STOCK_CSV", "data/raw/taiex_open_close.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "data/processed/thesis_final_data.csv")

# 嚴格定義日期 (21天)
P1_DATES = pd.date_range('2025-03-27', '2025-04-02')
P2_DATES = pd.date_range('2025-04-03', '2025-04-09')
P3_DATES = pd.date_range('2025-04-10', '2025-04-16')
ALL_DATES = pd.date_range('2025-03-27', '2025-04-16')

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match: return pd.to_datetime(f"2025/{match.group(1)} {match.group(2)}", errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def main():
    print("🚀 [Step 1] 啟動資料生成 pipeline...")
    
    # 1. 讀取情緒資料 (含假日)
    conn = sqlite3.connect(DB_PATH)
    df_sent = pd.read_sql_query("SELECT timestamp, label_id FROM ai_model_predictions_v2_push_only WHERE label_id IS NOT NULL", conn)
    conn.close()
    
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 2. 統計每日計數
    daily = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily.columns: daily[c] = 0
    daily.rename(columns={0:'Count_Neg', 1:'Count_Neu', 2:'Count_Pos'}, inplace=True)
    
    daily['Total'] = daily.sum(axis=1)
    daily['Pos_prop'] = daily['Count_Pos'] / daily['Total']
    daily['Neg_prop'] = daily['Count_Neg'] / daily['Total']
    daily['Neu_prop'] = daily['Count_Neu'] / daily['Total']
    daily.index = pd.to_datetime(daily.index)
    
    # 3. 讀取並合併股價
    df_stock = pd.read_csv(STOCK_CSV, usecols=['Date', '收盤價'], encoding='cp950')
    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date')
    df_stock['R_daily'] = df_stock['收盤價'].pct_change()
    df_stock['Cumulative_Return'] = (1 + df_stock['R_daily'].fillna(0)).cumprod() - 1
    
    # 合併 (Left join 保留假日情緒)
    df_final = daily.join(df_stock, how='left')
    
    # 4. 篩選 21 天並標註 Period
    df_final = df_final.loc[df_final.index.isin(ALL_DATES)].copy()
    
    conditions = [df_final.index.isin(P1_DATES), df_final.index.isin(P2_DATES), df_final.index.isin(P3_DATES)]
    df_final['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    # 5. 計算高階指標 (Momentum, Volatility, Volume Ratio)
    df_final['Momentum_2'] = df_final['Pos_prop'].diff(2) # Lag-2 動能
    df_final['Abs_R_daily'] = df_final['R_daily'].abs()   # 波動率
    
    p1_avg_vol = df_final[df_final['Period']=='P1']['Total'].mean()
    df_final['Vol_Ratio'] = df_final['Total'] / p1_avg_vol # 量能倍數
    df_final['Total_Surge'] = df_final['Total'].diff()     # 量能變化
    
    # 存檔
    df_final.to_csv(OUTPUT_CSV)
    print(f"✅ 資料已生成：{OUTPUT_CSV} (共 {len(df_final)} 天)")

if __name__ == "__main__":
    main()