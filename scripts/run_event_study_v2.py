# 檔案名稱: run_event_study_V2_new_formula.py
#
# 目的：(二合一)
# 1. 載入你「最強 V2 模型」的預測結果
# 2. (✅ 關鍵更新) 使用新公式 (Positive - Negative) / Total
# 3. (✅ 關鍵更新) 繪製你指定的「核心圖表 A」

import pandas as pd
import sqlite3
import numpy as np
import os
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ===================================================================
# 1. 設定區 (合併自兩個腳本)
# ===================================================================
# --- 資料來源 ---
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only" # ✅ 使用 V2 預測
STOCK_CSV_PATH = "taiex_open_close.csv" 

# --- 輸出路徑 ---
OUTPUT_CSV_PATH = "event_study_final_data_new_formula.csv" # (資料備份)
OUTPUT_CHART_PATH = "event_study_V_shape_chart.png"     # (✅ 最終圖表)

# --- 研究期間設定 ---
RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025' 

# --- 繪圖設定 (✅ 遵照新規格) ---
P1_START = '2025-03-27'; P1_END = '2025-04-02'
P2_START = '2025-04-07'; P2_END = '2025-04-09'
P3_START = '2025-04-10'; P3_END = '2025-04-16'
EVENT_1_DATE = '2025-04-07'; EVENT_1_LABEL = '4/7 關稅衝擊'   # ✅ 新標籤
EVENT_2_DATE = '2025-04-10'; EVENT_2_LABEL = '4/10 宣布暫緩' # ✅ 新標籤

# ===================================================================
# 2. 輔助函式 (Helper Functions)
# ===================================================================

def fix_timestamp_with_time(ts_str):
    """(不變) 修復 PTT 日期戳記，保留「時」和「分」。"""
    if not isinstance(ts_str, str): return pd.NaT
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        datetime_str = f"{RESEARCH_YEAR}/{match.group(1)} {match.group(2)}"
        return pd.to_datetime(datetime_str, format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

# ✅✅✅ --- (關鍵修改) --- ✅✅✅
# 採用你的新公式： (Positive - Negative) / Total
def calculate_net_sentiment_v2(series):
    """
    (V2 新公式) 計算情緒極性指數
    (0=Negative, 1=Neutral, 2=Positive)
    """
    if series.empty:
        return np.nan
    
    n_total = len(series)
    if n_total == 0:
        return np.nan
    
    # 精確計算
    n_negative = (series == 0).sum()
    n_positive = (series == 2).sum()
    # (n_neutral 在此公式中不使用)
        
    return (n_positive - n_negative) / n_total

# ===================================================================
#  PART 1: 建立事件研究資料
# ===================================================================

print(f"========== PART 1: 建立事件研究資料 (使用新公式) ==========")

# ===================================================================
# 3. 步驟一：載入並處理「股價資料」 (不變)
# ===================================================================
print(f"--- 步驟 1/4: 正在從 '{STOCK_CSV_PATH}' 載入股價資料... ---")
try:
    df_stock = pd.read_csv(
        STOCK_CSV_PATH, usecols=['Date', '收盤價'],
        encoding='cp950', skipinitialspace=True
    )
except FileNotFoundError:
    print(f"錯誤：找不到股價檔案 '{STOCK_CSV_PATH}'。"); exit()
    
df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
df_stock = df_stock.set_index('Date')
df_stock.sort_index(inplace=True)
df_stock['Close'] = df_stock['收盤價']
df_stock['Daily_Return'] = df_stock['Close'].pct_change()
df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE].copy()
df_stock['Daily_Return'].fillna(0, inplace=True)
df_stock['Cumulative_Return'] = (1 + df_stock['Daily_Return']).cumprod() - 1
print(f"股價資料處理完成，共 {len(df_stock)} 筆交易日資料。")

# ===================================================================
# 4. 步驟二：載入並處理「V2 情緒資料」 (不變)
# ===================================================================
print(f"--- 步驟 2/4: 正在從 '{DB_PATH}' 的 [{SENTIMENT_TABLE}] 載入 V2 推文... ---")
conn = sqlite3.connect(DB_PATH)
query = f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE type = 'push' AND label_id IS NOT NULL"
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
# 5. 步驟三：計算 S_Overnight 和 S_Intraday (✅ 使用新公式)
# ===================================================================
print("--- 步驟 3/4: 正在迭代交易日，計算 S_Overnight_V2 與 S_Intraday_V2... ---")

overnight_scores = []
intraday_scores = []
trading_days = df_stock.index

for i in range(len(trading_days)):
    T = trading_days[i] # T 日 (Datetime)
    
    # --- 計算 S_Intraday[T] --- (T 日 09:01 ~ T 日 13:30)
    start_intra = T.replace(hour=9, minute=1, second=0)
    end_intra = T.replace(hour=13, minute=30, second=0)
    df_intra = df_sentiment.loc[start_intra:end_intra]
    # ✅ 呼叫新公式
    score_intra = calculate_net_sentiment_v2(df_intra['label_id']) 
    intraday_scores.append(score_intra)

    if i == 0: overnight_scores.append(np.nan); continue
    T_minus_1 = trading_days[i-1] # T-1 日 (Datetime)
    
    # --- 計算 S_Overnight[T] --- (T-1 日 13:31 ~ T 日 09:00)
    start_overnight = T_minus_1.replace(hour=13, minute=31, second=0)
    end_overnight = T.replace(hour=9, minute=0, second=0)
    df_overnight = df_sentiment.loc[start_overnight:end_overnight]
    # ✅ 呼叫新公式
    score_overnight = calculate_net_sentiment_v2(df_overnight['label_id']) 
    overnight_scores.append(score_overnight)

print("變數計算完成。")

# ===================================================================
# 6. 步驟四：合併並「傳遞」最終資料 (✅ 使用新變數名)
# ===================================================================
df_final = df_stock.copy()
# ✅ 使用新的變數名稱
df_final['S_Overnight_V2'] = overnight_scores
df_final['S_Intraday_V2'] = intraday_scores # (雖然沒畫，但保留)

df_for_plotting = df_final[[
    'Daily_Return',
    'Cumulative_Return', # 繪圖 Y2
    'S_Overnight_V2',    # 繪圖 Y1
    'S_Intraday_V2',
    'Close'
]].copy()

df_for_plotting.to_csv(OUTPUT_CSV_PATH, encoding='utf-8-sig')
print(f"\n🎉🎉🎉 資料處理完成！🎉🎉🎉")
print(f"已成功建立事件分析最終資料，並儲存至: {OUTPUT_CSV_PATH}")

# ===================================================================
#  PART 2: 繪製事件分析圖表 (✅ 已遵照新規格)
# ===================================================================

print(f"\n========== PART 2: 繪製「核心圖表 A」 ==========")

# ===================================================================
# 2. 載入資料
# ===================================================================
print(f"--- 正在從記憶體載入資料... ---")
df = df_for_plotting
df.dropna(subset=['S_Overnight_V2'], inplace=True) # ✅ 根據新變數移除 NaN
print(f"資料載入成功，共 {len(df)} 筆交易日。")

# ===================================================================
# 3. 開始繪圖 (✅ 遵照新規格)
# ===================================================================
print("--- 正在繪製雙軸折線圖... ---")

try:
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    print("警告：中文字體設定失敗，圖表可能顯示方框。")

# B. 建立圖表與雙 Y 軸
fig, ax1 = plt.subplots(figsize=(16, 8))
ax2 = ax1.twinx() 

# C. 繪製 Y1 (左 - 情緒)
ax1.plot(
    df.index, 
    df['S_Overnight_V2'], # ✅ C. 變數
    color='blue',        # ✅ C. 顏色
    marker='o', 
    linestyle='-', 
    linewidth=2,
    label='情緒極性指數 (S_Overnight)' # ✅ C. 標籤
)
ax1.set_ylabel('情緒極性指數 (S_Overnight)', color='blue', fontsize=14) # ✅ C. 標籤
ax1.tick_params(axis='y', labelcolor='blue')

# D. 繪製 Y2 (右 - 市場)
ax2.plot(
    df.index, 
    df['Cumulative_Return'], # ✅ D. 變數
    color='orange',          # ✅ D. 顏色
    marker='s', 
    linestyle='--', 
    linewidth=2,
    label='累計市場報酬率 (Cumulative Return)' # ✅ D. 標籤
)
ax2.set_ylabel('累計市場報酬率 (Cumulative Return)', color='orange', fontsize=14) # ✅ D. 標籤
ax2.tick_params(axis='y', labelcolor='orange')
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))


# B. 設定 X 軸 (時間)
ax1.set_xlabel('交易日 (Trading Date)', fontsize=14)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax1.set_xticks(df.index) # ✅ 確保 X 軸符合 ['3/27', ..., '4/16']
plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
ax1.grid(axis='x', linestyle=':', alpha=0.5) 

# E1. 背景著色
ax1.axvspan(P1_START, P1_END, color='grey', alpha=0.2, label='P1: 前期')     # ✅ E1
ax1.axvspan(P2_START, P2_END, color='red', alpha=0.2, label='P2: 衝擊期')   # ✅ E1
ax1.axvspan(P3_START, P3_END, color='green', alpha=0.2, label='P3: 暫緩期') # ✅ E1

# E2. 關鍵事件標註
ax1.axvline(pd.to_datetime(EVENT_1_DATE), color='red', linestyle='--', linewidth=1.5, label=EVENT_1_LABEL)    # ✅ E2
ax1.axvline(pd.to_datetime(EVENT_2_DATE), color='green', linestyle='--', linewidth=1.5, label=EVENT_2_LABEL) # ✅ E2

# F. 標題與圖例
plt.title('核心圖表 A：PTT 隔夜情緒 vs. 累計市場報酬率 (V 型反轉)', fontsize=18, pad=20) # ✅ F. 標題
lines, labels = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
unique_labels = {}
for line, label in zip(lines + lines2, labels + labels2):
    if label not in unique_labels:
        unique_labels[label] = line
        
fig.legend(
    unique_labels.values(),
    unique_labels.keys(),
    loc='lower center', 
    bbox_to_anchor=(0.5, -0.15), 
    ncol=4, 
    fontsize=12
)

# 8. 儲存
plt.tight_layout(rect=[0, 0.05, 1, 0.95])
plt.savefig(OUTPUT_CHART_PATH, dpi=300, bbox_inches='tight')

print(f"\n🎉🎉🎉 繪圖完成！🎉🎉🎉")
print(f"圖表已儲存至: {OUTPUT_CHART_PATH}")

# (可選) 在 .ipynb 中直接顯示
# plt.show()