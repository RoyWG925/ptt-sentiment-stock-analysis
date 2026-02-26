# 檔案名稱: run_visual_daily_neg_prop.py
#
# 目的：
# 1. 視覺化「每日全天負面情緒佔比 (Neg_prop)」
# 2. 驗證「恐慌指數」與市場的（預期）反向關係
# 3. 【檔案管理】：自動建立資料夾存放圖片，不污染根目錄

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "final_prop_surge_data.csv"

# ✅ 設定輸出資料夾 (自動建立)
OUTPUT_DIR = "output_charts_neg"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"📂 已建立資料夾：{OUTPUT_DIR}")
else:
    print(f"📂 資料夾已存在：{OUTPUT_DIR}")

# 設定輸出路徑 (指向資料夾內)
IMG_CHART_10 = os.path.join(OUTPUT_DIR, "chart_10_zscore_daily_neg.png")
IMG_CHART_11 = os.path.join(OUTPUT_DIR, "chart_11_minmax_daily_neg.png")
IMG_CHART_12 = os.path.join(OUTPUT_DIR, "chart_12_diff_daily_neg.png")

# ❗ 關鍵變數：負面情緒佔比
TARGET_SENT = 'Neg_prop'          
TARGET_MKT_CUM = 'Cumulative_Return'

# 背景色塊設定
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
    print("🚀 啟動「每日負面情緒 (Daily Neg_prop)」視覺化分析...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 2. 欄位檢查
    if TARGET_SENT not in df.columns:
        print(f"❌ 錯誤：CSV 中找不到 {TARGET_SENT}"); return

    # 自動偵測每日報酬欄位
    target_mkt_daily = 'R_daily'
    if 'R_daily' in df.columns: pass
    elif 'R_Daily' in df.columns: df.rename(columns={'R_Daily': 'R_daily'}, inplace=True)
    else: df['R_daily'] = df[TARGET_MKT_CUM].diff().fillna(0)
    
    print(f"--- 使用變數：情緒={TARGET_SENT}, 市場={TARGET_MKT_CUM} ---")
    print(f"--- 輸出位置：{OUTPUT_DIR}/ ---")

    # 移除第一天 (NaN)
    df_plot = df.dropna(subset=[TARGET_SENT, TARGET_MKT_CUM]).copy()

    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # =========================================================
    # 圖 10：Z-score 標準化比較 (負面版)
    # =========================================================
    print("--- 繪製 [圖表 10] Z-score (Neg_prop) ---")
    
    df_plot['Sent_Z'] = stats.zscore(df_plot[TARGET_SENT])
    df_plot['Mkt_Z'] = stats.zscore(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    # 情緒用紅色 (Negative)
    ax.plot(df_plot.index, df_plot['Sent_Z'], label='負面佔比 (Z-score)', color='#d62728', marker='o', linewidth=2)
    # 市場用橘色
    ax.plot(df_plot.index, df_plot['Mkt_Z'], label='市場累計報酬 (Z-score)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax.axhline(0, color='black', linewidth=0.8)
    add_background(ax, df_plot)
    
    ax.set_title(f'圖 10：趨勢比較 (Z-score)\n負面情緒({TARGET_SENT}) vs 市場', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_10, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_10}")

    # =========================================================
    # 圖 11：Min-Max 正規化比較 (負面版)
    # =========================================================
    print("--- 繪製 [圖表 11] Min-Max (Neg_prop) ---")
    
    df_plot['Sent_MM'] = minmax_scale(df_plot[TARGET_SENT])
    df_plot['Mkt_MM'] = minmax_scale(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_MM'], label='負面佔比 (0-1)', color='#d62728', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_MM'], label='市場累計報酬 (0-1)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    add_background(ax, df_plot)
    ax.set_title(f'圖 11：波動幅度拉伸 (Min-Max)\n負面情緒 vs 市場', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_ylim(-0.1, 1.1); ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_11, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_11}")

    # =========================================================
    # 圖 12：一階差分 (Diff) 比較 (負面版)
    # =========================================================
    print("--- 繪製 [圖表 12] 變化量 Diff (Neg_prop) ---")
    
    sent_diff = df_plot[TARGET_SENT].diff()
    mkt_diff = df_plot[target_mkt_daily] 
    
    fig, ax1 = plt.subplots(figsize=(12, 6)); ax2 = ax1.twinx()
    
    ax1.plot(df_plot.index, sent_diff, label=f'Δ 負面情緒變化', color='#d62728', marker='o', linewidth=2)
    ax2.plot(df_plot.index, mkt_diff, label='市場每日報酬', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax1.axhline(0, color='black', linewidth=0.8)
    add_background(ax1, df_plot)
    
    ax1.set_ylabel(f'負面情緒變化量', color='#d62728'); ax2.set_ylabel('市場每日報酬', color='orange')
    ax1.set_title('圖 12：變化速度同步性 (Diff)\n負面情緒 vs 市場', fontsize=14)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    lines1, labels1 = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_12, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_12}")
    
    print("\n🎉🎉🎉 負面情緒分析完成！請查看 output_charts_neg 資料夾。 🎉🎉🎉")

if __name__ == "__main__":
    main()