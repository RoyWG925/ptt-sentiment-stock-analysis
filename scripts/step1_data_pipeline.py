# 檔案名稱: step1_data_pipeline.py
import pandas as pd
import numpy as np
import sqlite3
import os
import re

# --- 設定 ---
DB_PATH = "ptt_data_m.db"
STOCK_CSV = "taiex_open_close.csv"
OUTPUT_CSV = "thesis_final_data.csv" 

# 嚴格定義 21 天全日曆日 (用於 ANOVA)
ALL_DATES = pd.date_range('2025-03-27', '2025-04-16')
# 定義子時期
P1_DATES = pd.date_range('2025-03-27', '2025-04-02')
P2_DATES = pd.date_range('2025-04-03', '2025-04-09') # 含連假
P3_DATES = pd.date_range('2025-04-10', '2025-04-16')

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match: return pd.to_datetime(f"2025/{match.group(1)} {match.group(2)}", errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def main():
    print("🚀 [Step 1] 啟動資料生成 pipeline...")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到資料庫: {DB_PATH}"); return

    # 1. 讀取情緒資料 (含假日)
    conn = sqlite3.connect(DB_PATH)
    # 這裡假設你用的是 v2_push_only 表格，請確認表名正確
    try:
        df_sent = pd.read_sql_query("SELECT timestamp, label_id FROM ai_model_predictions_v2_push_only WHERE label_id IS NOT NULL", conn)
    except:
        print("❌ 資料表讀取錯誤，請確認 DB 表名"); return
    conn.close()
    
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 2. 統計每日計數 (Aggregation)
    daily = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily.columns: daily[c] = 0
    daily.rename(columns={0:'Count_Neg', 1:'Count_Neu', 2:'Count_Pos'}, inplace=True)
    
    daily['Total'] = daily.sum(axis=1)
    daily['Pos_prop'] = daily['Count_Pos'] / daily['Total']
    daily['Neg_prop'] = daily['Count_Neg'] / daily['Total']
    daily['Neu_prop'] = daily['Count_Neu'] / daily['Total']
    
    # 一階差分 (Diff)
    daily['Pos_diff'] = daily['Pos_prop'].diff()
    daily['Neg_diff'] = daily['Neg_prop'].diff()
    
    daily.index = pd.to_datetime(daily.index)
    
    # 3. 讀取並合併股價 (只會有交易日數據)
    if os.path.exists(STOCK_CSV):
        df_stock = pd.read_csv(STOCK_CSV, usecols=['Date', '收盤價'], encoding='cp950')
        df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
        df_stock = df_stock.set_index('Date')
        df_stock['R_daily'] = df_stock['收盤價'].pct_change()
        df_stock['Abs_R_daily'] = df_stock['R_daily'].abs()
        # 累積報酬 (從資料第一天開始算)
        df_stock['Cumulative_Return'] = (1 + df_stock['R_daily'].fillna(0)).cumprod() - 1
    else:
        print("⚠️ 找不到股價 CSV，將無法計算市場相關指標")
        df_stock = pd.DataFrame()
    
    # 合併 (Left join 保留假日情緒數據，用於 ANOVA)
    df_final = daily.join(df_stock, how='left')
    
    # 4. 篩選 21 天範圍並標註 Period
    df_final = df_final.loc[df_final.index.isin(ALL_DATES)].copy()
    
    conditions = [
        df_final.index.isin(P1_DATES),
        df_final.index.isin(P2_DATES),
        df_final.index.isin(P3_DATES)
    ]
    df_final['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    # 5. 計算高階指標 (Momentum, Volume Ratio)
    # Momentum (Lag-2): 今天的 Pos_prop - 兩天前的 Pos_prop
    # 注意：這裡要用 shift(2) 來算 diff，但因為是時間序列，直接 diff(2) 即可
    df_final['Momentum_2'] = df_final['Pos_prop'].diff(2)
    
    # 計算各 Lag 動能 (用於敏感度分析)
    for k in [1, 3, 4, 5]:
        df_final[f'Momentum_{k}'] = df_final['Pos_prop'].diff(k)
        
    # Volume Ratio (相對於 P1 均值)
    p1_avg_vol = df_final[df_final['Period']=='P1']['Total'].mean()
    df_final['Vol_Ratio'] = df_final['Total'] / p1_avg_vol
    df_final['Vol_Surge'] = df_final['Total'].diff()
    df_final['Log_Volume'] = np.log1p(df_final['Total'])

    # 6. 標記是否為交易日 (有股價數據的才是交易日)
    df_final['Is_Trading_Day'] = df_final['R_daily'].notna()

    # 存檔
    df_final.to_csv(OUTPUT_CSV)
    print(f"✅ 資料已生成：{OUTPUT_CSV}")
    print(f"   總天數 (N): {len(df_final)} (應為 21)")
    print(f"   交易日數: {df_final['Is_Trading_Day'].sum()} (應為 13)")

if __name__ == "__main__":
    main()
