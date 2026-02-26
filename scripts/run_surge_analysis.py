# 檔案名稱: run_surge_analysis.py
#
# 目的：
# 1. [第三部曲] 計算情緒脈衝 (Surge/Impulse) 指標
# 2. 驗證：市場是對「情緒的變化量 (Δ)」產生反應，而非「存量」
# 3. 產出：圖表 E (Sentiment Surge vs Market)

import pandas as pd
import sqlite3
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"
OUTPUT_CHART_E = "chart_E_sentiment_surge.png"
OUTPUT_CSV = "event_study_surge_data.csv"

RESEARCH_START_DATE = '2025-03-27'
RESEARCH_END_DATE = '2025-04-16'
RESEARCH_YEAR = '2025'

# 繪圖區間設定
P1_START = '2025-03-27'; P1_END = '2025-04-02'
P2_START = '2025-04-07'; P2_END = '2025-04-09'
P3_START = '2025-04-10'; P3_END = '2025-04-16'

# ===================================================================
# 2. 資料處理邏輯
# ===================================================================

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce') # 處理 ISO 格式
    # 處理 PTT 原始格式 (MM/DD HH:MM)
    import re
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match:
        datetime_str = f"{RESEARCH_YEAR}/{match.group(1)} {match.group(2)}"
        return pd.to_datetime(datetime_str, format='%Y/%m/%d %H:%M', errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def main():
    print("🚀 啟動「情緒脈衝 (Surge)」分析...")

    # --- 1. 載入股價資料 ---
    print("--- 1/4: 載入股價... ---")
    df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950', skipinitialspace=True)
    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date').sort_index()
    df_stock = df_stock.loc[RESEARCH_START_DATE:RESEARCH_END_DATE].copy()
    
    # 計算累計報酬 (視覺化用) 和 每日報酬 (計算用)
    df_stock['R_Daily'] = df_stock['收盤價'].pct_change().fillna(0)
    df_stock['Cumulative_Return'] = (1 + df_stock['R_Daily']).cumprod() - 1
    trading_days = df_stock.index

    # --- 2. 載入情緒資料並計算「每日計數」 ---
    print("--- 2/4: 載入情緒並計算每日計數... ---")
    conn = sqlite3.connect(DB_PATH)
    # 只撈取需要的欄位
    df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    conn.close()
    
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    
    # 為了計算 Surge，我們需要「絕對日期」(不分盤中/隔夜，直接算整天)
    # 或者，依照你的「隔夜壓力鍋」理論，我們應該看「隔夜累積量」
    # 這裡我們先做「整天」的計數，因為 Surge 通常是大尺度的
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 計算每日 P, N 數量
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    # 確保欄位存在 (0: Neg, 1: Neu, 2: Pos)
    for c in [0, 1, 2]:
        if c not in daily_counts.columns: daily_counts[c] = 0
        
    daily_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    
    # 過濾出研究期間
    daily_counts.index = pd.to_datetime(daily_counts.index)
    daily_counts = daily_counts.loc[RESEARCH_START_DATE:RESEARCH_END_DATE]

    # --- 3. 計算脈衝 (Surge) ---
    print("--- 3/4: 計算 Surge (Δ = Today - Yesterday)... ---")
    # 這裡的 diff() 就是 GPT 說的 "Surge"
    daily_counts['Neg_Surge'] = daily_counts['Count_Neg'].diff().fillna(0)
    daily_counts['Pos_Surge'] = daily_counts['Count_Pos'].diff().fillna(0)
    
    # 合併股價
    df_final = pd.merge(df_stock, daily_counts, left_index=True, right_index=True, how='left')

    # 簡單統計檢定 (Correlation)
    corr_neg, p_neg = stats.spearmanr(df_final['Neg_Surge'], df_final['R_Daily'])
    corr_pos, p_pos = stats.spearmanr(df_final['Pos_Surge'], df_final['R_Daily'])
    
    print(f"\n[統計驗證] Surge vs. Daily Return (Spearman)")
    print(f"Neg_Surge vs Return: corr={corr_neg:.3f}, p={p_neg:.3f} (預期負相關)")
    print(f"Pos_Surge vs Return: corr={corr_pos:.3f}, p={p_pos:.3f} (預期正相關)")
    
    df_final.to_csv(OUTPUT_CSV, encoding='utf-8-sig')

    # --- 4. 繪圖 (圖表 E) ---
    print("--- 4/4: 繪製「圖表 E：情緒脈衝」... ---")
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()

    # 繪製 Bar Chart (脈衝)
    width = 0.35
    # 負面脈衝 (紅色柱狀)
    ax1.bar(df_final.index - pd.Timedelta(hours=4), df_final['Neg_Surge'], width, color='red', alpha=0.6, label='負面情緒脈衝 (Neg Surge)')
    # 正面脈衝 (綠色柱狀)
    ax1.bar(df_final.index + pd.Timedelta(hours=4), df_final['Pos_Surge'], width, color='green', alpha=0.6, label='正面情緒脈衝 (Pos Surge)')
    
    ax1.set_ylabel('情緒脈衝強度 (貼文數增量 Δ)', fontsize=12)
    ax1.axhline(0, color='black', linewidth=0.8) # 零軸
    
    # 繪製 Line Chart (市場)
    ax2.plot(df_final.index, df_final['Cumulative_Return'], color='orange', marker='s', linewidth=2, linestyle='--', label='市場累計報酬 (Cumulative Return)')
    ax2.set_ylabel('市場累計報酬率', color='orange', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='orange')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))

    # X 軸設定
    ax1.set_xlabel('交易日', fontsize=12)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax1.set_xticks(df_final.index)
    
    # 背景色塊
    ax1.axvspan(P1_START, P1_END, color='grey', alpha=0.1, label='P1')
    ax1.axvspan(P2_START, P2_END, color='red', alpha=0.1, label='P2: 衝擊')
    ax1.axvspan(P3_START, P3_END, color='green', alpha=0.1, label='P3: 暫緩')

    # 標題與圖例
    plt.title('圖表 E：情緒脈衝 (Surge) 與市場反應之關聯', fontsize=16)
    
    # 合併圖例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    plt.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig(OUTPUT_CHART_E, dpi=300)
    print(f"✅ 圖表 E 已儲存至: {OUTPUT_CHART_E}")

if __name__ == "__main__":
    main()