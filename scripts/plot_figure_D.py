# 檔案名稱: plot_figure_D.py
#
# 目的：
# 1. 產生 [圖表 D：每日情緒三色組成圖]
# 2. 視覺化 P1, P2, P3 期間，「隔夜情緒」的「組成」變化
# 3. 驗證 4/7 (P2) 負面佔比暴增, 4/10 (P3) 正面佔比暴增

import pandas as pd
import sqlite3
import numpy as np
import os
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
# 來源：V2 模型的預測結果
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only" 
# 來源：交易日曆
STOCK_CSV_PATH = "taiex_open_close.csv" 
# 輸出：圖表 D
OUTPUT_CHART_PATH = "chart_D_daily_sentiment_composition.png"

# --- 研究期間設定 ---
RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025' 

# --- 繪圖設定 (同 圖表 A) ---
P1_START = '2025-03-27'; P1_END = '2025-04-02'
P2_START = '2025-04-07'; P2_END = '2025-04-09'
P3_START = '2025-04-10'; P3_END = '2025-04-16'

# ===================================================================
# 2. 輔助函式 (Helper Functions)
# ===================================================================
def fix_timestamp_with_time(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        datetime_str = f"{RESEARCH_YEAR}/{match.group(1)} {match.group(2)}"
        return pd.to_datetime(datetime_str, format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

# ===================================================================
# 3. 步驟一：載入「交易日」
# ===================================================================
print(f"--- 步驟 1/4: 正在從 '{STOCK_CSV_PATH}' 載入「交易日」... ---")
try:
    df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date'], encoding='cp950', skipinitialspace=True)
except FileNotFoundError:
    print(f"錯誤：找不到股價檔案 '{STOCK_CSV_PATH}'。"); exit()
    
df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
df_stock = df_stock.set_index('Date')
df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE]
trading_days = df_stock.index
print(f"成功載入 {len(trading_days)} 個交易日。")

# ===================================================================
# 4. 步驟二：載入並處理「V2 情緒資料」
# ===================================================================
print(f"--- 步驟 2/4: 正在從 [{SENTIMENT_TABLE}] 載入所有 V2 推文... ---")
conn = sqlite3.connect(DB_PATH)
query = f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL"
try:
    df_sentiment = pd.read_sql_query(query, conn)
except Exception as e:
    print(f"錯誤：讀取資料庫表格 '{SENTIMENT_TABLE}' 失敗。 {e}"); conn.close(); exit()
conn.close()

df_sentiment['datetime'] = df_sentiment['timestamp'].apply(fix_timestamp_with_time)
df_sentiment.dropna(subset=['datetime'], inplace=True)
df_sentiment = df_sentiment.set_index('datetime').sort_index()
print(f"V2 PTT 推文資料處理完成，共 {len(df_sentiment)} 筆。")

# ===================================================================
# 5. 步驟三：(新) 逐日彙總為「情緒組成」
# ===================================================================
print(f"--- 步驟 3/4: 正在計算「每日隔夜情緒組成」... ---")

daily_composition = [] # 用來收集每天的統計

for i, T in enumerate(trading_days):
    # --- 只計算「隔夜 (Overnight)」資料 ---
    if i == 0:
        # 第一天 (3/27)，沒有 T-1，無法計算
        daily_composition.append({'Date': T, 'Negative': 0, 'Neutral': 0, 'Positive': 0})
        continue
    
    T_minus_1 = trading_days[i-1]
    
    # (T-1 日 13:31 ~ T 日 09:00)
    start_overnight = T_minus_1.replace(hour=13, minute=31, second=0)
    end_overnight = T.replace(hour=9, minute=0, second=0)
    
    df_overnight = df_sentiment.loc[start_overnight:end_overnight]
    
    # 計算 P, N, Neu 的「數量」
    counts = df_overnight['label_id'].value_counts()
    
    n_neg = counts.get(0, 0)
    n_neu = counts.get(1, 0)
    n_pos = counts.get(2, 0)
    
    daily_composition.append({
        'Date': T, 
        'Negative': n_neg, 
        'Neutral': n_neu, 
        'Positive': n_pos
    })

# 將 list 轉為 DataFrame
df_comp = pd.DataFrame(daily_composition).set_index('Date')

# (關鍵) 轉換為「百分比」
df_comp_pct = df_comp.divide(df_comp.sum(axis=1), axis=0).fillna(0)
df_comp_pct = df_comp_pct.loc[trading_days[1]:] # 移除第一天 (NaN)

print("情緒組成計算完成。")

# ===================================================================
# 6. 步驟四：繪製「圖表 D」
# ===================================================================
print("--- 步驟 4/4: 正在繪製「圖表 D：每日情緒組成圖」... ---")

try:
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    print("警告：中文字體設定失敗。")

fig, ax = plt.subplots(figsize=(16, 8))

# 繪製 100% 堆疊柱狀圖
df_comp_pct.plot(
    kind='bar', 
    stacked=True, 
    color=['#d62728', '#ff7f0e', '#2ca02c'], # 紅, 橘, 綠
    ax=ax,
    width=0.8
)

# 格式化 Y 軸為 %
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
ax.set_ylabel('情緒組成百分比 (Composition %)', fontsize=14)
ax.set_ylim(0, 1)

# 格式化 X 軸
ax.set_xlabel('交易日 (Trading Date)', fontsize=14)
ax.set_xticklabels([d.strftime('%m/%d') for d in df_comp_pct.index], rotation=45, ha='right')

# 標題與圖例
ax.set_title('圖表 D：每日「隔夜情緒」組成百分比 (P/N/N) (V2 模型)', fontsize=18, pad=20)
ax.legend(['Negative (0)', 'Neutral (1)', 'Positive (2)'], loc='center left', bbox_to_anchor=(1, 0.5), fontsize=12)

# 加上 P1, P2, P3 背景色塊 (X 軸是 0 到 11，對應 12 天)
# P1 (前期): 03/28 (0) ~ 04/02 (3)
ax.axvspan(-0.5, 3.5, color='grey', alpha=0.15, label='P1: 前期')
# P2 (衝擊): 04/07 (4) ~ 04/09 (6)
ax.axvspan(3.5, 6.5, color='red', alpha=0.1, label='P2: 衝擊期')
# P3 (暫緩): 04/10 (7) ~ 04/16 (11)
ax.axvspan(6.5, 11.5, color='green', alpha=0.1, label='P3: 暫緩期')

plt.tight_layout(rect=[0, 0.05, 0.9, 0.95]) # 留出右側圖例空間
plt.savefig(OUTPUT_CHART_PATH, dpi=300, bbox_inches='tight')

print(f"\n🎉🎉🎉 [圖表 D] 繪製完成！ 🎉🎉🎉")
print(f"圖表已儲存至: {OUTPUT_CHART_PATH}")