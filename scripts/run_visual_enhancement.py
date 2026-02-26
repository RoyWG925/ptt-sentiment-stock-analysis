# 檔案名稱: run_visual_enhancement_overnight.py
#
# (✅ V3 - 強制修復 KeyError: 'R_daily')
# 1. 自動標準化欄位名稱
# 2. 若缺少每日報酬率，自動從累計報酬反推
# 3. 確保圖 10, 11, 12 都能順利產出

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
INPUT_CSV = "event_study_final_data_PN_Ratio.csv"

# 輸出圖表名稱
IMG_CHART_10 = "chart_10_zscore_overnight.png"
IMG_CHART_11 = "chart_11_minmax_overnight.png"
IMG_CHART_12 = "chart_12_diff_overnight.png"

# 目標變數
TARGET_SENT = 'S_Overnight_PN_Ratio'
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
    print("🚀 啟動「隔夜情緒 (Overnight)」視覺化增強分析 (V3)...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # 2. 欄位檢查與修復 (強制標準化)
    if TARGET_SENT not in df.columns:
        print(f"❌ 錯誤：CSV 中找不到 {TARGET_SENT}"); return

    # ✅ 強制修正每日報酬欄位
    if 'R_daily' in df.columns:
        pass # 已存在，不用做
    elif 'R_Daily' in df.columns:
        df.rename(columns={'R_Daily': 'R_daily'}, inplace=True)
    elif 'Daily_Return' in df.columns:
        df.rename(columns={'Daily_Return': 'R_daily'}, inplace=True)
    else:
        print("  > 警告：找不到 R_daily 欄位，正在從 Cumulative_Return 反推...")
        # 近似計算：Diff
        df['R_daily'] = df[TARGET_MKT_CUM].diff().fillna(0)
    
    print(f"--- 使用變數：情緒={TARGET_SENT}, 市場累計={TARGET_MKT_CUM}, 市場每日=R_daily ---")

    # 移除第一天 (NaN)
    df_plot = df.dropna(subset=[TARGET_SENT, TARGET_MKT_CUM]).copy()
    print(f"  > 有效資料筆數 N={len(df_plot)}")

    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # =========================================================
    # 方法 1：Z-score 標準化比較 (圖 10)
    # =========================================================
    print("--- 繪製 [圖表 10] Z-score (Overnight) ---")
    
    df_plot['Sent_Z'] = stats.zscore(df_plot[TARGET_SENT])
    df_plot['Mkt_Z'] = stats.zscore(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_Z'], label='隔夜情緒 P/N (Z-score)', color='blue', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_Z'], label='市場累計報酬 (Z-score)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax.axhline(0, color='black', linewidth=0.8)
    add_background(ax, df_plot)
    
    ax.set_title('圖 10：趨勢形狀比較 (Z-score)\nPTT 隔夜情緒 vs 市場報酬', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_10, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_10}")

    # =========================================================
    # 方法 2：Min-Max 正規化比較 (圖 11)
    # =========================================================
    print("--- 繪製 [圖表 11] Min-Max (Overnight) ---")
    
    df_plot['Sent_MM'] = minmax_scale(df_plot[TARGET_SENT])
    df_plot['Mkt_MM'] = minmax_scale(df_plot[TARGET_MKT_CUM])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_MM'], label='隔夜情緒 P/N (0-1)', color='blue', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_MM'], label='市場累計報酬 (0-1)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    add_background(ax, df_plot)
    ax.set_title('圖 11：波動幅度拉伸比較 (Min-Max)\nPTT 隔夜情緒 vs 市場報酬', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_ylim(-0.1, 1.1); ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_11, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_11}")

    # =========================================================
    # 方法 3：一階差分 (Δ) 比較 (圖 12)
    # =========================================================
    print("--- 繪製 [圖表 12] 變化量 Diff (Overnight) ---")
    
    # 計算差分
    sent_diff = df_plot[TARGET_SENT].diff()
    # ✅ 使用標準化後的 R_daily
    mkt_diff = df_plot['R_daily'] 
    
    fig, ax1 = plt.subplots(figsize=(12, 6)); ax2 = ax1.twinx()
    
    ax1.plot(df_plot.index, sent_diff, label='Δ 隔夜情緒 (Change)', color='blue', marker='o', linewidth=2)
    ax2.plot(df_plot.index, mkt_diff, label='市場每日報酬 (R_daily)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax1.axhline(0, color='black', linewidth=0.8)
    add_background(ax1, df_plot)
    
    ax1.set_ylabel('情緒變化量 (Δ)', color='blue'); ax2.set_ylabel('市場每日報酬', color='orange')
    ax1.set_title('圖 12：變化速度同步性比較 (First-order Difference)\nPTT 隔夜情緒 vs 市場報酬', fontsize=14)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    lines1, labels1 = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout(); plt.savefig(IMG_CHART_12, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_12}")
    
    print("\n🎉🎉🎉 隔夜情緒視覺化增強完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()