# 檔案名稱: run_visual_all_props.py
#
# 目的：
# 1. 一次性視覺化「正面」、「負面」、「中性」三種情緒佔比
# 2. 自動建立資料夾分類存檔
# 3. 產出 Z-score, Min-Max, Diff 三種視角的比較圖

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

# 背景色塊設定
P1_DATES = pd.to_datetime(['2025-03-27', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-16'])

# 設定三種情緒的參數
SENTIMENT_CONFIG = {
    'Pos': {
        'col': 'Pos_prop', 
        'name': '正面情緒 (Positive)', 
        'color': '#2ca02c', # 綠色
        'folder': 'output_charts_pos'
    },
    'Neg': {
        'col': 'Neg_prop', 
        'name': '負面情緒 (Negative)', 
        'color': '#d62728', # 紅色
        'folder': 'output_charts_neg'
    },
    'Neu': {
        'col': 'Neu_prop', 
        'name': '中性情緒 (Neutral)', 
        'color': '#7f7f7f', # 灰色
        'folder': 'output_charts_neu'
    }
}

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

def plot_charts_for_sentiment(df, sent_key, config):
    """繪製單一情緒指標的三張圖"""
    
    target_col = config['col']
    sent_name = config['name']
    color = config['color']
    folder = config['folder']
    
    # 檢查欄位是否存在
    if target_col not in df.columns:
        print(f"  > ⚠️ 警告：找不到欄位 {target_col}，跳過 {sent_name}。")
        return

    # 建立資料夾
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    print(f"  正在繪製：{sent_name} -> 存入 {folder}/ ...")
    
    # 準備繪圖數據 (移除 NaN)
    df_plot = df.dropna(subset=[target_col, 'Cumulative_Return', 'R_daily']).copy()

    # 設定中文字型
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # ---------------------------------------------------
    # 1. Z-score 標準化比較
    # ---------------------------------------------------
    df_plot['Sent_Z'] = stats.zscore(df_plot[target_col])
    df_plot['Mkt_Z'] = stats.zscore(df_plot['Cumulative_Return'])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_Z'], label=f'{sent_name} (Z-score)', color=color, marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_Z'], label='市場累計報酬 (Z-score)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax.axhline(0, color='black', linewidth=0.8)
    add_background(ax, df_plot)
    ax.set_title(f'趨勢比較 (Z-score)：{sent_name} vs 市場', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    path_z = os.path.join(folder, f"chart_zscore_{sent_key}.png")
    plt.tight_layout(); plt.savefig(path_z, dpi=300); plt.close()

    # ---------------------------------------------------
    # 2. Min-Max 正規化比較
    # ---------------------------------------------------
    df_plot['Sent_MM'] = minmax_scale(df_plot[target_col])
    df_plot['Mkt_MM'] = minmax_scale(df_plot['Cumulative_Return'])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot.index, df_plot['Sent_MM'], label=f'{sent_name} (0-1)', color=color, marker='o', linewidth=2)
    ax.plot(df_plot.index, df_plot['Mkt_MM'], label='市場累計報酬 (0-1)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    add_background(ax, df_plot)
    ax.set_title(f'波動幅度拉伸 (Min-Max)：{sent_name} vs 市場', fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.set_ylim(-0.1, 1.1); ax.legend(loc='upper left'); ax.grid(True, linestyle=':', alpha=0.5)
    
    path_mm = os.path.join(folder, f"chart_minmax_{sent_key}.png")
    plt.tight_layout(); plt.savefig(path_mm, dpi=300); plt.close()

    # ---------------------------------------------------
    # 3. Diff (變化量) 比較
    # ---------------------------------------------------
    sent_diff = df_plot[target_col].diff()
    mkt_diff = df_plot['R_daily']
    
    fig, ax1 = plt.subplots(figsize=(12, 6)); ax2 = ax1.twinx()
    
    ax1.plot(df_plot.index, sent_diff, label=f'Δ {sent_name}', color=color, marker='o', linewidth=2)
    ax2.plot(df_plot.index, mkt_diff, label='市場每日報酬 (R_daily)', color='orange', marker='s', linewidth=2, linestyle='--')
    
    ax1.axhline(0, color='black', linewidth=0.8)
    add_background(ax1, df_plot)
    ax1.set_ylabel(f'{sent_name} 變化量', color=color); ax2.set_ylabel('市場每日報酬', color='orange')
    ax1.set_title(f'單日{sent_name} 變化量vs 市場單日報酬', fontsize=14)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    lines1, labels1 = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.5)
    
    path_diff = os.path.join(folder, f"chart_diff_{sent_key}.png")
    plt.tight_layout(); plt.savefig(path_diff, dpi=300); plt.close()
    
    print(f"  > ✅ 完成 {sent_key} 繪圖。")

def main():
    print("🚀 啟動「全方位情緒視覺化 (Pos/Neg/Neu)」分析...")

    # 1. 載入資料
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 錯誤：找不到 {INPUT_CSV}"); return
    
    df = pd.read_csv(INPUT_CSV, parse_dates=['Date'], index_col='Date')

    # 2. 確保變數存在 (特別是 Neu_prop, R_daily)
    if 'R_daily' not in df.columns:
        if 'R_Daily' in df.columns: df.rename(columns={'R_Daily': 'R_daily'}, inplace=True)
        elif 'Daily_Return' in df.columns: df.rename(columns={'Daily_Return': 'R_daily'}, inplace=True)
        else: df['R_daily'] = df['Cumulative_Return'].diff().fillna(0)

    # 計算 Neu_prop (如果沒有)
    if 'Neu_prop' not in df.columns:
        print("  > 計算中性情緒 (Neu_prop)...")
        if 'Count_Neu' in df.columns and 'Total' in df.columns:
            df['Neu_prop'] = df['Count_Neu'] / df['Total']
        else:
            # 備案：1 - Pos - Neg
            df['Neu_prop'] = 1 - df['Pos_prop'] - df['Neg_prop']

    # 3. 迴圈執行繪圖
    for key, config in SENTIMENT_CONFIG.items():
        plot_charts_for_sentiment(df, key, config)

    print("\n🎉🎉🎉 所有情緒圖表繪製完成！請查看 output_charts_* 資料夾。 🎉🎉🎉")

if __name__ == "__main__":
    main()