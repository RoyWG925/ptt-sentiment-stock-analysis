# 檔案名稱: run_visual_pos_prop.py
#
# 目的：
# 1. 專門視覺化「隔夜正面情緒佔比 (Pos_prop_Overnight)」
# 2. 驗證「信心回歸」是否與「市場反彈」同步
# 3. 產出：圖 13, 14, 15 (針對 Positive Prop)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_structured_data.csv"

# 輸出圖表
IMG_CHART_13 = "chart_13_zscore_pos_overnight.png"
IMG_CHART_14 = "chart_14_minmax_pos_overnight.png"
IMG_CHART_15 = "chart_15_diff_pos_overnight.png"

# 目標變數名稱
TARGET_SENT_NAME = 'Pos_prop_Overnight'
TARGET_MKT_CUM = 'Cumulative_Return'

# 背景色塊
P1_DATES = pd.to_datetime(['2025-03-27', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-16'])

# ===================================================================
# 2. 核心邏輯
# ===================================================================

def add_background(ax, df):
    valid_start = df.index[0]; valid_end = df.index[-1]
    p1_s = max(P1_DATES[0], valid_start); p1_e = min(P1_DATES[1], valid_end)
    if p1_s <= p1_e: ax.axvspan(p1_s, p1_e, color='grey', alpha=0.1, label='P1')
    p2_s = max(P2_DATES[0], valid_start); p2_e = min(P2_DATES[1], valid_end)
    if p2_s <= p2_e: ax.axvspan(p2_s, p2_e, color='red', alpha=0.1, label='P2')
    p3_s = max(P3_DATES[0], valid_start); p3_e = min(P3_DATES[1], valid_end)
    if p3_s <= p3_e: ax.axvspan(p3_s, p3_e, color='green', alpha=0.1, label='P3')

def minmax_scale(series):
    return (series - series.min()) / (series.max() - series.min())

def main():
    print("🚀 啟動「隔夜正面情緒 (Positive Prop)」視覺化分析...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 2. 計算 Pos_prop_Overnight
    # 我們需要 Pos_ON 和 Total_ON
    if 'Pos_ON' in df.columns and 'Total_ON' in df.columns:
        df[TARGET_SENT_NAME] = df['Pos_ON'] / df['Total_ON'].replace(0, np.nan)
        print(f"  > 成功計算 {TARGET_SENT_NAME}")
    else:
        print("❌ 錯誤：找不到 Pos_ON 或 Total_ON 欄位。請確認 final_structured_data.csv 是否正確。")
        return

    # 處理每日報酬 (若無則計算)
    target_mkt_daily = 'R_daily'
    if 'R_daily' not in df.columns:
        df['R_daily'] = df[TARGET_MKT_CUM].diff().fillna(0)

    # 移除 NaN (第一天)
    df_plot = df.dropna(subset=[TARGET_SENT_NAME, TARGET_MKT_CUM]).copy()
    print(f"  > 有效資料 N={len(df_plot)}")

    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # =========================================================
    # 圖 13：Z-score 標準化比較
    # =========================================================
    print("--- 繪製 [圖表 13] Z-score (Positive Prop) ---")
    
    df_plot['Sent_Z'] = stats.zscore(df_plot[TARGET_SENT_NAME])
    df_plot['Mkt_Z'] = stats.zscore(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_Z'], label='隔夜正面佔比 (Pos%, Z-score)', color='green', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_Z'], label='市場累計報酬 (Z-score)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax.axhline(0, color='black', linewidth=0.8)
    add_background(ax, df_plot)
    
    ax.set_title('圖 13：信心回歸指標 (Pos%) 與市場趨勢比較 (Z-score)', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_13, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_13}")

    # =========================================================
    # 圖 14：Min-Max 正規化比較
    # =========================================================
    print("--- 繪製 [圖表 14] Min-Max (Positive Prop) ---")
    
    df_plot['Sent_MM'] = minmax_scale(df_plot[TARGET_SENT_NAME])
    df_plot['Mkt_MM'] = minmax_scale(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_MM'], label='隔夜正面佔比 (Pos%, 0-1)', color='green', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_MM'], label='市場累計報酬 (0-1)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    add_background(ax, df_plot)
    ax.set_title('圖 14：波動幅度拉伸比較 (Min-Max)\n隔夜正面佔比 vs 市場報酬', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_ylim(-0.1, 1.1); ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_14, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_14}")

    # =========================================================
    # 圖 15：一階差分 (Diff) 比較
    # =========================================================
    print("--- 繪製 [圖表 15] 變化量 Diff (Positive Prop) ---")
    
    sent_diff = df_plot[TARGET_SENT_NAME].diff()
    mkt_diff = df_plot['R_daily']
    
    fig, ax1 = plt.subplots(figsize=(12, 6)); ax2 = ax1.twinx()
    
    ax1.plot(df_plot.index, sent_diff, label='Δ 隔夜正面佔比', color='green', marker='o', linewidth=2)
    ax2.plot(df_plot.index, mkt_diff, label='市場每日報酬', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax1.axhline(0, color='black', linewidth=0.8)
    add_background(ax1, df_plot)
    
    ax1.set_ylabel('正面情緒變化量', color='green'); ax2.set_ylabel('市場每日報酬', color='orange')
    ax1.set_title('圖 15：變化速度同步性 (Diff)\n隔夜正面佔比 vs 市場報酬', fontsize=14)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    lines1, labels1 = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_15, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_15}")
    
    print("\n🎉🎉🎉 正面情緒 (Pos Prop) 視覺化完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()