import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# ===================================================================
# 1. 設定區
# ===================================================================
DATA_FILE_PATH = "event_study_final_data.csv"
OUTPUT_CHART_PATH = "event_study_shock_reversal_chart.png"

# --- 視覺輔助設定 (根據你的規格) ---
# P1 (前期)
P1_START = '2025-03-27'
P1_END = '2025-04-02'
# P2 (衝擊期)
P2_START = '2025-04-07' # 4/3 宣布, 4/4 假期, 4/7 開盤
P2_END = '2025-04-09'
# P3 (暫緩期)
P3_START = '2025-04-10'
P3_END = '2025-04-16'

# --- 事件標註點 ---
EVENT_1_DATE = '2025-04-07'
EVENT_1_LABEL = 'P2 衝擊 (4/3 宣布, 4/7 開盤)'
EVENT_2_DATE = '2025-04-10'
EVENT_2_LABEL = 'P3 暫緩 (4/10 宣布)'

# ===================================================================
# 2. 載入資料
# ===================================================================
print(f"--- 正在載入資料: {DATA_FILE_PATH} ---")
if not os.path.exists(DATA_FILE_PATH):
    print(f"錯誤：找不到資料檔案 '{DATA_FILE_PATH}'")
    print("請先執行 create_event_study_data.py 腳本。")
    exit()

df = pd.read_csv(DATA_FILE_PATH, parse_dates=['Date'], index_col='Date')

# 移除 S_Overnight 是 NaN 的資料 (通常是第一天)
df.dropna(subset=['S_Overnight'], inplace=True)
print(f"資料載入成功，共 {len(df)} 筆交易日。")

# ===================================================================
# 3. 開始繪圖 (遵照你的 9 點規格)
# ===================================================================
print("--- 正在繪製雙軸折線圖... ---")

# 設定中文字體 (若你系統沒有，會顯示方框，請自行更換)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
plt.rcParams['axes.unicode_minus'] = False # 解決負號顯示問題

# 1. 建立圖表與雙 Y 軸
fig, ax1 = plt.subplots(figsize=(16, 8))
ax2 = ax1.twinx() # Y2 軸 (右)

# 2. 繪製 Y1 (左 - 情緒)
ax1.plot(
    df.index, 
    df['S_Overnight'], 
    color='blue', 
    marker='o', 
    linestyle='-', 
    linewidth=2,
    label='隔夜情緒穩定度 (S_Overnight)'
)
ax1.set_ylabel('隔夜情緒穩定度 (S_Overnight, 藍線)', color='blue', fontsize=14)
ax1.tick_params(axis='y', labelcolor='blue')
# ax1.set_ylim(-1, 1) # 情緒分數在 -1 到 +1 之間

# 3. 繪製 Y2 (右 - 市場)
ax2.plot(
    df.index, 
    df['Cumulative_Return'], 
    color='orange', 
    marker='s', 
    linestyle='--', 
    linewidth=2,
    label='累計市場報酬率 (Cumulative Return)'
)
ax2.set_ylabel('累計市場報酬率 (Cumulative Return, 橘線)', color='orange', fontsize=14)
ax2.tick_params(axis='y', labelcolor='orange')
# 將累計報酬率格式化為 %
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))


# 4. 設定 X 軸 (時間)
ax1.set_xlabel('交易日 (Trading Date)', fontsize=14)
# 格式化 X 軸日期為 'MM/DD'
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
# 顯示所有 X 軸刻度
ax1.set_xticks(df.index)
plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
ax1.grid(axis='x', linestyle=':', alpha=0.5) # 加上垂直格線

# 5. 背景著色 (關鍵視覺輔助)
# P1 (前期)
ax1.axvspan(P1_START, P1_END, color='grey', alpha=0.15, label='P1: 前期')
# P2 (衝擊期)
ax1.axvspan(P2_START, P2_END, color='red', alpha=0.1, label='P2: 衝擊期')
# P3 (暫緩期)
ax1.axvspan(P3_START, P3_END, color='green', alpha=0.1, label='P3: 暫緩期')

# 6. 關鍵事件標註 (垂直虛線)
ax1.axvline(pd.to_datetime(EVENT_1_DATE), color='red', linestyle='--', linewidth=1.5, label=EVENT_1_LABEL)
ax1.axvline(pd.to_datetime(EVENT_2_DATE), color='green', linestyle='--', linewidth=1.5, label=EVENT_2_LABEL)

# 7. 標題與圖例
plt.title('情緒穩定度與市場累計報酬率之事件分析 (2025/03/27 - 04/16)', fontsize=18, pad=20)
# 整合兩軸的圖例，統一放在圖表下方
lines, labels = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
# 移除 axvspan 的重複標籤
unique_labels = {}
for line, label in zip(lines + lines2, labels + labels2):
    if label not in unique_labels:
        unique_labels[label] = line
        
fig.legend(
    unique_labels.values(),
    unique_labels.keys(),
    loc='lower center', 
    bbox_to_anchor=(0.5, -0.15), # 放在圖表下方
    ncol=4, 
    fontsize=12
)

# 8. 儲存
plt.tight_layout(rect=[0, 0.05, 1, 0.95]) # 調整佈局以容納標題和圖例
plt.savefig(OUTPUT_CHART_PATH, dpi=300, bbox_inches='tight')

print(f"\n🎉🎉🎉 繪圖完成！🎉🎉🎉")
print(f"圖表已儲存至: {OUTPUT_CHART_PATH}")