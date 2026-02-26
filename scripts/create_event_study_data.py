import pandas as pd
import sqlite3
import numpy as np
import os
import re

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions" 
STOCK_CSV_PATH = "taiex_open_close.csv" 
OUTPUT_CSV_PATH = "event_study_final_data.csv" # 這是繪圖腳本的資料來源

# 根據你的書面報告
RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025' 

# ===================================================================
# 2. 輔助函式 (Helper Functions)
# ===================================================================

def fix_timestamp_with_time(ts_str):
    """
    修復 PTT 日期戳記，這次保留「時」和「分」。
    '03/24 10:57' -> datetime(2025, 3, 24, 10, 57)
    '2025-04-01T14:30:00' -> datetime(2025, 4, 1, 14, 30)
    """
    if not isinstance(ts_str, str):
        return pd.NaT
    
    # 模式 1: '03/24 10:57' (來自 push_comments)
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        # 手動加上年份和時間
        datetime_str = f"{RESEARCH_YEAR}/{match.group(1)} {match.group(2)}"
        return pd.to_datetime(datetime_str, format='%Y/%m/%d %H:%M', errors='coerce')
    
    # 模式 2: '2025-04-01T...' (來自 sentiments)
    if 'T' in ts_str:
        return pd.to_datetime(ts_str, errors='coerce')

    return pd.to_datetime(ts_str, errors='coerce')

def calculate_net_sentiment(series):
    """
    根據你的新規格 (中性數 - 負面數) / 總數
    其中 label_id (0=Negative, 1=Neutral)
    """
    if series.empty:
        return np.nan # 用 0.0 或 np.nan ? np.nan 在統計上更安全
    
    n_total = len(series)
    n_neutral = series.sum()      # 1 (Neutral) 的總和
    n_negative = n_total - n_neutral  # 0 (Negative) 的總和
    
    return (n_neutral - n_negative) / n_total

# ===================================================================
# 3. 步驟一：載入並處理「股價資料」
# ===================================================================
print(f"--- 步驟 1/4: 正在從 '{STOCK_CSV_PATH}' 載入股價資料... ---")
df_stock = pd.read_csv(
    STOCK_CSV_PATH, usecols=['Date', '收盤價'],
    encoding='cp950', skipinitialspace=True
)
df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
df_stock = df_stock.set_index('Date')
df_stock.sort_index(inplace=True)
df_stock['Close'] = df_stock['收盤價']

# --- 計算報酬率 ---
df_stock['Daily_Return'] = df_stock['Close'].pct_change() # (T / T-1) - 1

# --- 關鍵前處理：計算「累計報酬率」 (Cumulative Return) ---
# (1 + R).cumprod() - 1
# 我們先篩選研究期間，再計算累計報酬
df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE].copy()
df_stock['Daily_Return'].fillna(0, inplace=True) # 第一天 (3/27) 的 NaN 補 0
df_stock['Cumulative_Return'] = (1 + df_stock['Daily_Return']).cumprod() - 1

print(f"股價資料處理完成，共 {len(df_stock)} 筆交易日資料。")

# ===================================================================
# 4. 步驟二：載入並處理「情緒資料」
# ===================================================================
print(f"--- 步驟 2/4: 正在從 '{DB_PATH}' 載入 PTT 推文資料... ---")
conn = sqlite3.connect(DB_PATH)
query = f"""
SELECT timestamp, label_id 
FROM {SENTIMENT_TABLE} 
WHERE type = 'push'
"""
df_sentiment = pd.read_sql_query(query, conn)
conn.close()

# --- 修復並解析所有時間戳記 (包含時/分) ---
print("正在修復 PTT 時間戳記 (包含時/分)...")
df_sentiment['datetime'] = df_sentiment['timestamp'].apply(fix_timestamp_with_time)
df_sentiment.dropna(subset=['datetime'], inplace=True)
df_sentiment = df_sentiment.set_index('datetime').sort_index()
print(f"PTT 推文資料處理完成，共 {len(df_sentiment)} 筆。")

# ===================================================================
# 5. 步驟三：計算 S_Overnight 和 S_Intraday
# ===================================================================
print("--- 步驟 3/4: 正在迭代交易日，計算 S_Overnight 與 S_Intraday... ---")

overnight_scores = []
intraday_scores = []

# 以 df_stock (交易日) 為迴圈基準
trading_days = df_stock.index

for i in range(len(trading_days)):
    T = trading_days[i] # T 日 (Datetime)
    
    # --- 計算 S_Intraday[T] ---
    # (T 日 09:01 ~ T 日 13:30)
    start_intra = T.replace(hour=9, minute=1, second=0)
    end_intra = T.replace(hour=13, minute=30, second=0)
    
    df_intra = df_sentiment.loc[start_intra:end_intra]
    score_intra = calculate_net_sentiment(df_intra['label_id'])
    intraday_scores.append(score_intra)

    # --- 計算 S_Overnight[T] ---
    if i == 0:
        # 第一天 (3/27)，沒有 T-1，無法計算
        overnight_scores.append(np.nan)
        continue
    
    T_minus_1 = trading_days[i-1] # T-1 日 (Datetime)
    
    # (T-1 日 13:31 ~ T 日 09:00)
    # 你的規格「自動包含休市日」會在這裡實現
    start_overnight = T_minus_1.replace(hour=13, minute=31, second=0)
    end_overnight = T.replace(hour=9, minute=0, second=0)
    
    df_overnight = df_sentiment.loc[start_overnight:end_overnight]
    score_overnight = calculate_net_sentiment(df_overnight['label_id'])
    overnight_scores.append(score_overnight)

print("變數計算完成。")

# ===================================================================
# 6. 步驟四：合併並儲存最終資料
# ===================================================================
df_final = df_stock.copy()
df_final['S_Overnight'] = overnight_scores
df_final['S_Intraday'] = intraday_scores

df_final_output = df_final[[
    'Daily_Return',
    'Cumulative_Return', # 繪圖 Y2
    'S_Overnight',       # 繪圖 Y1
    'S_Intraday',
    'Close'
]]

df_final_output.to_csv(OUTPUT_CSV_PATH, encoding='utf-8-sig')

print(f"\n🎉🎉🎉 資料處理完成！🎉🎉🎉")
print(f"已成功建立事件分析最終資料，並儲存至: {OUTPUT_CSV_PATH}")
print("\n--- 最終結果預覽 (前 5 筆) ---")
print(df_final_output.head())