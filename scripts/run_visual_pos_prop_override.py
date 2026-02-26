# 檔案名稱: run_visual_pos_prop_override.py
#
# 目的：
# 1. 專門視覺化「隔夜正面情緒佔比 (Pos_prop_Overnight)」
# 2. 產出你認為「蠻好的」三張圖 (Z-score, Min-Max, Diff)
# 3. 提供額外的視覺證據來支持論文討論

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import os

# ===================================================================
# 1. 設定區
# ===================================================================
# 注意：這裡改為使用 final_structured_data.csv
INPUT_CSV = "final_structured_data.csv"

# 輸出圖表名稱 (區別於之前的 10-12)
IMG_CHART_POS_ZSCORE = "chart_pos_prop_zscore.png"
IMG_CHART_POS_MINMAX = "chart_pos_prop_minmax.png"
IMG_CHART_POS_DIFF = "chart_pos_prop_diff.png"

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
    print("🚀 啟動「隔夜正面情緒佔比 (Pos_prop_Overnight)」視覺化分析...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}")
        return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')
    
    # --- 關鍵：計算 Pos_prop_Overnight ---
    if 'Pos_ON' in df.columns and 'Total_ON' in df.columns:
        df['Pos_prop_Overnight'] = df['Pos_ON'] / df['Total_ON'].replace(0, np.nan)
    else:
        print("❌ 錯誤：找不到 Pos_ON 或 Total_ON 欄位。請確認 final_structured_data.csv 是否正確。")
        return

    # 我們主要比較 Pos_prop_Overnight 和 Cumulative_Return
    target_sent = 'Pos_prop_Overnight'
    target_mkt_cum = 'Cumulative_Return'
    target_mkt_daily = 'R_daily' # 用於 Diff 圖

    # 確保市場報酬欄位存在
    if target_mkt_daily not in df.columns:
        df[target_mkt_daily] = df[target_mkt_cum].pct_change().fillna(0) # 確保 R_daily 存在

    print(f"--- 使用變數：情緒={target_sent}, 市場累計={target_mkt_cum}, 市場每日={target_mkt_daily} ---")

    # 準備繪圖設定
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
    
    # 過濾掉 NA 值，主要針對 Pos_prop_Overnight 可能因為 Total_ON=0 產生 NA
    df_plot = df.dropna(subset=[target_sent, target_mkt_cum]).copy()
    if len(df_plot) < 2:
        print("❌ 資料點太少，無法繪圖。")
        return

    # =========================================================
    # 方法 1：Z-score 標準化比較
    # =========================================================
    print("--- 繪製 Z-score 標準化比較 ---")
    
    # 修正：使用 Pandas 計算 Z-score 以保留索引
    valid_sent_z = df_plot[target_sent].dropna()
    valid_mkt_z = df_plot[target_mkt_cum].loc[valid_sent_z.index].dropna()

    if not valid_sent_z.empty and not valid_mkt_z.empty:
        df_plot.loc[valid_sent_z.index, 'Sent_Z'] = (valid_sent_z - valid_sent_z.mean()) / valid_sent_z.std()
        df_plot.loc[valid_mkt_z.index, 'Mkt_Z'] = (valid_mkt_z - valid_mkt_z.mean()) / valid_mkt_z.std()
    else:
        print("警告：Z-score 計算資料不足，圖表可能不完整。")
        df_plot['Sent_Z'] = np.nan
        df_plot['Mkt_Z'] = np.nan
        
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(df_plot.index, df_plot['Sent_Z'], label='隔夜正面情緒佔比 (Pos%, Z-score)', color='green', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_Z'], label='市場累計報酬 (Z-score)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax.axhline(0, color='black', linewidth=0.8)
    add_background(ax, df_plot)
    
    ax.set_title(f'圖：趨勢形狀比較 (Z-score 標準化)\n隔夜正面情緒佔比 vs 市場累計報酬', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend(loc='upper left')
    ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_POS_ZSCORE, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_POS_ZSCORE}")

    # =========================================================
    # 方法 2：Min-Max 正規化比較
    # =========================================================
    print("--- 繪製 Min-Max 正規化比較 ---")
    
    df_plot['Sent_MM'] = minmax_scale(df_plot[target_sent])
    df_plot['Mkt_MM'] = minmax_scale(df_plot[target_mkt_cum])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(df_plot.index, df_plot['Sent_MM'], label='隔夜正面情緒佔比 (Pos%, 0-1)', color='green', marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_MM'], label='市場累計報酬 (0-1)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    add_background(ax, df_plot)
    
    ax.set_title(f'圖：波動幅度拉伸比較 (Min-Max 正規化)\n隔夜正面情緒佔比 vs 市場累計報酬', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_ylim(-0.1, 1.1)
    ax.legend(loc='upper left')
    ax.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_POS_MINMAX, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_POS_MINMAX}")

    # =========================================================
    # 方法 3：一階差分 (Δ) 比較
    # =========================================================
    print("--- 繪製 變化量 (Diff) 比較 ---")
    
    sent_diff = df_plot[target_sent].diff()
    mkt_diff = df_plot[target_mkt_daily] 
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    
    ax1.plot(df_plot.index, sent_diff, label='Δ 隔夜正面情緒佔比', color='green', marker='o', linewidth=2)
    ax2.plot(df_plot.index, mkt_diff, label='市場每日報酬 (R_daily)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax1.axhline(0, color='black', linewidth=0.8)
    add_background(ax1, df_plot)
    
    ax1.set_ylabel('正面情緒變化量 (Δ Pos%)', color='green')
    ax2.set_ylabel('市場每日報酬', color='orange')
    
    ax1.set_title('圖：變化速度同步性比較 (First-order Difference)\n隔夜正面情緒佔比 vs 市場每日報酬', fontsize=14)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    ax1.grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_POS_DIFF, dpi=300)
    print(f"  > 已儲存至 {IMG_CHART_POS_DIFF}")
    
    print("\n🎉🎉🎉 隔夜正面情緒佔比 (Pos_prop) 視覺化圖表繪製完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()