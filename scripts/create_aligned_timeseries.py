import pandas as pd
import sqlite3
import numpy as np
import os
import re # 匯入正規表達式

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions" 
STOCK_CSV_PATH = "taiex_open_close.csv" 
OUTPUT_CSV_PATH = "aligned_timeseries.csv"

RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025' # ✅ 關鍵：定義研究年份

# ===================================================================
# 0. 前置檢查 (同前)
# ===================================================================
print("--- 步驟 0/5: 正在進行前置檢查... ---")
if not os.path.exists(DB_PATH): print(f"錯誤：找不到 {DB_PATH}"); exit()
if not os.path.exists(STOCK_CSV_PATH): print(f"錯誤：找不到 {STOCK_CSV_PATH}"); exit()
print("前置檢查通過，必要的檔案皆存在。")

# ===================================================================
# 1. 載入並處理「股價資料」 (同前)
# ===================================================================
print(f"--- 步驟 1/5: 正在從 '{STOCK_CSV_PATH}' 載入股價資料... ---")
df_stock = pd.read_csv(
    STOCK_CSV_PATH, usecols=['Date', '收盤價'],
    encoding='cp950', skipinitialspace=True
)
df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
df_stock = df_stock.set_index('Date')
df_stock.sort_index(inplace=True)
df_stock['Close'] = df_stock['收盤價'] 
df_stock['Close_T-1'] = df_stock['Close'].shift(1) 
df_stock['Daily_Return'] = (df_stock['Close'] - df_stock['Close_T-1']) / df_stock['Close_T-1']
trading_days = set(df_stock.index)
print(f"股價資料處理完成，共 {len(df_stock)} 筆交易日資料。")

# ===================================================================
# 2. 載入並處理「情緒資料」 (v3 修正版)
# ===================================================================
print(f"--- 步驟 2/5: 正在從 '{SENTIMENT_TABLE}' 表格載入情緒資料... ---")
print(f"    (範圍: {RESEARCH_START_DATE} 至 {RESEARCH_END_DATE})")

conn = sqlite3.connect(DB_PATH)
# 1. 依然只撈取 push
# 2. 這次我們撈 'timestamp' (字串) 和 'label_id'
# 3. 我們在 SQL 中「大致」篩選日期，但主要篩選交給 Pandas
query = f"""
SELECT timestamp, label_id 
FROM {SENTIMENT_TABLE} 
WHERE type = 'push'
"""
df_sentiment = pd.read_sql_query(query, conn)
conn.close()

# ✅✅✅ 關鍵修正 (v3) ✅✅✅
# 我們建立一個輔助函式來「修復」缺少年份的日期

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str):
        return pd.NaT
    
    # 模式 1: '03/24 10:57' (來自 push_comments)
    # 我們用正規表達式找出 MM/DD HH:MM 格式
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        date_part = match.group(1) # '03/24'
        # 手動加上研究年份
        return pd.to_datetime(f"{RESEARCH_YEAR}/{date_part}", format='%Y/%m/%d', errors='coerce')
    
    # 模式 2: '2025-04-01T...' (來自 sentiments)
    if 'T' in ts_str:
        return pd.to_datetime(ts_str.split('T')[0], format='%Y-%m-%d', errors='coerce')

    # 其他可能的完整日期格式
    return pd.to_datetime(ts_str, errors='coerce')

print("正在修復缺少年份的日期...")
# 1. 應用我們的修復函式，將字串轉為 datetime 物件
df_sentiment['Date'] = df_sentiment['timestamp'].apply(fix_timestamp)

# 2. 移除「真的」無法修復的日期 (例如 'https://imgur...' 或其他垃圾資料)
df_sentiment.dropna(subset=['Date'], inplace=True)

# 3. 我們只關心「日期」，去掉「時:分:秒」 (標準化)
df_sentiment['Date'] = df_sentiment['Date'].dt.normalize()

# 4. ✅ 在這裡才篩選研究範圍
df_sentiment = df_sentiment[
    (df_sentiment['Date'] >= pd.to_datetime(RESEARCH_START_DATE)) &
    (df_sentiment['Date'] <= pd.to_datetime(RESEARCH_END_DATE))
]

# --- 計算「每日平均情緒指標」 ---
# (0=Negative, 1=Neutral) -> 分數會在 0.0 ~ 1.0 之間
df_daily_scores = df_sentiment.groupby('Date')['label_id'].mean().to_frame()
df_daily_scores.rename(columns={'label_id': 'Daily_Sentiment_Avg'}, inplace=True)

print(f"情緒資料處理完成，共 {len(df_daily_scores)} 天有 PTT 推文資料。")
if len(df_daily_scores) == 0:
    print("警告：仍然沒有讀取到任何情緒資料！請檢查資料庫和日期範圍。")
else:
    print(df_daily_scores.head(3))

# ===================================================================
# 3. 執行「時間序列對齊」 (同 v2)
# ===================================================================
print("--- 步驟 3/5: 正在執行時間序列對齊 (處理週末與假日)... ---")

min_date = min(df_stock.index.min(), df_daily_scores.index.min())
max_date = max(df_stock.index.max(), df_daily_scores.index.max())

all_calendar_days = pd.date_range(start=min_date, end=max_date)
df_aligner = pd.DataFrame(index=all_calendar_days)

df_aligner['trading_day_marker'] = pd.Series(df_stock.index, index=df_stock.index)
df_aligner['next_trading_day'] = df_aligner['trading_day_marker'].bfill()

df_aligner = df_aligner.join(df_daily_scores['Daily_Sentiment_Avg'])
# ✅ 修正：我們應該填充 'NaN'，而不是 0。
# 如果某天 PTT 沒文章，它的情緒不該是 0 (Negative)，而是「沒有資料」
# .mean() 會自動忽略 NaN，這才是正確的
# df_aligner['Daily_Sentiment_Avg'].fillna(0, inplace=True) # <- 舊的 v2 邏輯

# 以「下一交易日」為群組，計算「平均值」 (.mean() 會自動忽略 NaN)
s_aligned_sentiment = df_aligner.groupby('next_trading_day')['Daily_Sentiment_Avg'].mean()
s_aligned_sentiment.name = 'Agg_Sentiment_Avg' 

print("時間對齊完成。")

# ===================================================================
# 4. 建立並儲存「最終對齊資料表」 (同 v2)
# ===================================================================
print(f"--- 步驟 4/5: 正在合併並儲存至 '{OUTPUT_CSV_PATH}'... ---")

df_final = df_stock.join(s_aligned_sentiment)

# 對於「早於」PTT 資料的交易日，其情緒分數會是 NaN，我們補 0
df_final['Agg_Sentiment_Avg'].fillna(0, inplace=True)
df_final.dropna(subset=['Daily_Return'], inplace=True) # 移除第一天

df_final_output = df_final[[
    'Daily_Return', 
    'Agg_Sentiment_Avg', # 新的情緒指標
    'Close', 
    'Close_T-1'
]]
df_final_output.to_csv(OUTPUT_CSV_PATH, encoding='utf-8-sig')

# ===================================================================
# 5. 任務完成
# ===================================================================
print("\n🎉🎉🎉 任務完成！🎉🎉🎉")
print(f"已成功建立對齊時間序列 (v3)，並儲存至: {OUTPUT_CSV_PATH}")
print("\n--- 最終結果預覽 (前 5 筆) ---")
print(df_final_output.head())