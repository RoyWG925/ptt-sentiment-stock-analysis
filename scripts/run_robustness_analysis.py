# 檔案名稱: run_robustness_analysis.py
#
# 目的：執行「穩健性檢定 (Robustness Check)」與「機制分析」
# 產出：圖表 4~8，以及 Tables A~D

import pandas as pd
import sqlite3
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import seaborn as sns
from tqdm import tqdm

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"
HOURLY_PRICE_CSV = "full_hourly_price_data.csv" # 來自之前的步驟

# 輸出設定
OUTPUT_DATA_CSV = "robustness_final_data.csv"
OUTPUT_STATS_TXT = "robustness_stats_report.txt"

# 圖表輸出
IMG_CHART_4 = "chart_4_shock_vs_response.png"
IMG_CHART_5 = "chart_5_lag1_correlation.png"
IMG_CHART_6 = "chart_6_pn_ratio_surge.png"
IMG_CHART_7A = "chart_7A_hourly_surge_0407.png"
IMG_CHART_7B = "chart_7B_hourly_surge_0410.png"
IMG_CHART_8 = "chart_8_total_volume_surge.png"

# 研究期間
RESEARCH_START = '2025-03-27'; RESEARCH_END = '2025-04-16'; YEAR = '2025'

# 時期定義
P1_DATES = pd.to_datetime(['2025-03-27', '2025-03-28', '2025-03-31', '2025-04-01', '2025-04-02'])
P2_DATES = pd.to_datetime(['2025-04-07', '2025-04-08', '2025-04-09'])
P3_DATES = pd.to_datetime(['2025-04-10', '2025-04-11', '2025-04-14', '2025-04-15', '2025-04-16'])

# ===================================================================
# 2. 資料處理函式
# ===================================================================

def fix_timestamp(ts_str):
    if not isinstance(ts_str, str): return pd.NaT
    import re
    match = re.match(r'(\d{2}/\d{2})\s(\d{2}:\d{2})', ts_str)
    if match: return pd.to_datetime(f"{YEAR}/{match.group(1)} {match.group(2)}", format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def prepare_daily_robustness_data():
    print("--- 1. 準備每日穩健性資料 ---")
    
    # 1. 載入股價
    df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950')
    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date').sort_index().loc[RESEARCH_START:RESEARCH_END].copy()
    df_stock['R_daily'] = df_stock['收盤價'].pct_change().fillna(0)
    df_stock['Cumulative_Return'] = (1 + df_stock['R_daily']).cumprod() - 1
    
    # 2. 載入情緒
    conn = sqlite3.connect(DB_PATH)
    df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    conn.close()
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    df_sent['Date'] = df_sent['datetime'].dt.date
    
    # 3. 計算每日計數
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in daily_counts.columns: daily_counts[c] = 0
    daily_counts.rename(columns={0: 'Neg', 1: 'Neu', 2: 'Pos'}, inplace=True)
    daily_counts['Total'] = daily_counts.sum(axis=1)
    daily_counts.index = pd.to_datetime(daily_counts.index)
    daily_counts = daily_counts.loc[RESEARCH_START:RESEARCH_END]
    
    df = pd.merge(df_stock, daily_counts, left_index=True, right_index=True, how='inner')
    
    # --- 4. 計算核心變數 (依照你的清單) ---
    
    # (A) Composition (比例)
    df['Pos_prop'] = df['Pos'] / df['Total']
    df['Neg_prop'] = df['Neg'] / df['Total']
    
    # (B) Proportional Surge (比例脈衝)
    df['Pos_prop_surge'] = df['Pos_prop'].diff().fillna(0)
    df['Neg_prop_surge'] = df['Neg_prop'].diff().fillna(0)
    
    # (C) PN Ratio Surge (比值脈衝)
    # (P+1)/(N+1)
    df['PN_Ratio'] = (df['Pos'] + 1) / (df['Neg'] + 1)
    df['PN_Ratio_Surge'] = df['PN_Ratio'].diff().fillna(0)
    
    # (D) Total Volume Surge (討論量脈衝)
    df['Total_Surge'] = df['Total'].diff().fillna(0)
    
    # (E) Absolute Shock Variables (絕對值分析用)
    df['Abs_R_daily'] = df['R_daily'].abs()
    df['Abs_Neg_Surge'] = df['Neg_prop_surge'].abs()
    df['Abs_Pos_Surge'] = df['Pos_prop_surge'].abs()
    df['Abs_Total_Surge'] = df['Total_Surge'].abs()
    
    # (F) Lag Variables (跨日分析用)
    df['Neg_prop_surge_lag1'] = df['Neg_prop_surge'].shift(1).fillna(0)
    df['Pos_prop_surge_lag1'] = df['Pos_prop_surge'].shift(1).fillna(0)
    
    # (G) Period
    conditions = [df.index.isin(P1_DATES), df.index.isin(P2_DATES), df.index.isin(P3_DATES)]
    df['Period'] = np.select(conditions, ['P1', 'P2', 'P3'], default='Other')
    
    df.to_csv(OUTPUT_DATA_CSV, encoding='utf-8-sig')
    print(f"  > 每日資料已存至: {OUTPUT_DATA_CSV}")
    return df

def prepare_hourly_robustness_data(target_date_str):
    """準備特定日期的每小時 Surge 資料"""
    # 1. 載入情緒 (Raw)
    conn = sqlite3.connect(DB_PATH)
    df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    conn.close()
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    
    # 篩選當天
    target_date = pd.to_datetime(target_date_str).date()
    df_day = df_sent[df_sent['datetime'].dt.date == target_date].copy()
    
    # 定義 Time Blocks
    T = pd.to_datetime(target_date_str)
    bins = [
        T.replace(hour=0, minute=0), # Start of day (for overnight capture)
        T.replace(hour=9, minute=0),
        T.replace(hour=10, minute=0),
        T.replace(hour=11, minute=0),
        T.replace(hour=12, minute=0),
        T.replace(hour=13, minute=0),
        T.replace(hour=13, minute=30)
    ]
    labels = ['Overnight', '09-10', '10-11', '11-12', '12-13', '13-13:30']
    
    # 這裡我們把 00:00-09:00 視為 Overnight
    # 注意：這是簡化版，嚴格來說 Overnight 包含前一天的 13:30 以後，但在單日圖中，00:00-09:00 足以代表開盤前的累積
    df_day['Time_Block'] = pd.cut(df_day['datetime'], bins=bins, labels=labels)
    
    # 彙總
    grouped = df_day.groupby('Time_Block', observed=True)['label_id'].value_counts().unstack(fill_value=0)
    for c in [0, 1, 2]: 
        if c not in grouped.columns: grouped[c] = 0
    grouped.rename(columns={0: 'Neg', 1: 'Neu', 2: 'Pos'}, inplace=True)
    grouped['Total'] = grouped.sum(axis=1)
    
    # 計算每小時的 Prop
    grouped['Pos_prop'] = grouped['Pos'] / grouped['Total']
    grouped['Neg_prop'] = grouped['Neg'] / grouped['Total']
    
    # 計算每小時的 Surge (相較於上一小時)
    grouped['Pos_prop_surge'] = grouped['Pos_prop'].diff().fillna(0)
    grouped['Neg_prop_surge'] = grouped['Neg_prop'].diff().fillna(0)
    
    # 載入每小時股價 (只為了 Return)
    try:
        df_price = pd.read_csv(HOURLY_PRICE_CSV)
        df_price['Date'] = pd.to_datetime(df_price['Date']).dt.date
        df_price_day = df_price[df_price['Date'] == target_date].copy()
        
        # Mapping Time_Blocks
        block_map = {
            '09:00-10:00': '09-10', '10:00-11:00': '10-11', 
            '11:00-12:00': '11-12', '12:00-13:00': '12-13', '13:00-13:30': '13-13:30'
        }
        df_price_day['Time_Block'] = df_price_day['Time_Block'].map(block_map)
        
        # Merge
        df_final = pd.merge(grouped, df_price_day[['Time_Block', 'Return_Close_vs_9am', 'Return_Open_vs_9am']], on='Time_Block', how='left')
        
        # 設定 Hourly Return
        df_final['Hourly_Return'] = np.where(
            df_final['Time_Block'] == '13-13:30',
            df_final['Return_Close_vs_9am'],
            df_final['Return_Open_vs_9am']
        )
        df_final.loc[df_final['Time_Block'] == 'Overnight', 'Hourly_Return'] = 0.0
        
        return df_final.set_index('Time_Block')
        
    except Exception as e:
        print(f"  > Warning: 無法載入每小時股價 ({e})，將只畫情緒。")
        return grouped

# ===================================================================
# 3. 統計產出 (Tables)
# ===================================================================

def run_stats_report(df):
    print("--- 2. 產生統計報告 (Tables A-D) ---")
    lines = []
    lines.append("=== Robustness Check Statistical Report ===\n")
    
    # (表 B) Spearman 相關矩陣
    lines.append("--- Table B: Spearman Correlation Matrix (Daily) ---")
    cols_b = ['R_daily', 'Neg_prop_surge', 'Pos_prop_surge', 'PN_Ratio_Surge', 'Total_Surge']
    corr_b = df[cols_b].corr(method='spearman')
    lines.append(corr_b.to_string())
    lines.append("\n")
    
    # (表 C) Lag=1 相關矩陣 (跨日)
    lines.append("--- Table C: Lag=1 Correlation Matrix (Sentiment[t-1] vs R[t]) ---")
    # 這裡我們看 Lag 變數與 R_daily 的相關性
    cols_c_lag = ['Neg_prop_surge_lag1', 'Pos_prop_surge_lag1', 'Total_Surge'] # Total Surge Lag 需要另外算，這裡先用主要的
    # 補算 Total Lag
    df['Total_Surge_lag1'] = df['Total_Surge'].shift(1)
    
    cols_c = ['R_daily', 'Neg_prop_surge_lag1', 'Pos_prop_surge_lag1', 'Total_Surge_lag1']
    corr_c = df[cols_c].corr(method='spearman')
    lines.append(corr_c.to_string())
    lines.append("\n")
    
    # (表 D) 事件視窗平均
    lines.append("--- Table D: Event Window Means (P1/P2/P3) ---")
    cols_d = ['Neg_prop_surge', 'Pos_prop_surge', 'PN_Ratio_Surge', 'Total_Surge', 'R_daily']
    means_d = df.groupby('Period')[cols_d].mean().reindex(['P1', 'P2', 'P3'])
    lines.append(means_d.to_string())
    lines.append("\n")
    
    # (分析 1) 事件強度分析 (Spearman)
    lines.append("--- Analysis 1: Event Impact Magnitude (Spearman) ---")
    sp_shock, p_shock = stats.spearmanr(df['Abs_R_daily'], df['Abs_Total_Surge'])
    lines.append(f"Abs(Market Shock) vs Abs(Total Surge): corr={sp_shock:.4f}, p={p_shock:.4f}")
    
    with open(OUTPUT_STATS_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  > 統計報告已儲存至: {OUTPUT_STATS_TXT}")

# ===================================================================
# 4. 圖表繪製
# ===================================================================

def plot_charts(df):
    print("--- 3. 繪製圖表 4~8 ---")
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass
    
    # --- 圖 4: 事件強度 Scatter (Shock vs Response) ---
    plt.figure(figsize=(8, 6))
    plt.scatter(df['Abs_R_daily'], df['Abs_Total_Surge'], color='purple', s=100, alpha=0.7)
    # 標註 4/7 和 4/10
    try:
        row_0407 = df.loc[pd.to_datetime('2025-04-07')]
        plt.text(row_0407['Abs_R_daily'], row_0407['Abs_Total_Surge'], ' 4/7 恐慌', fontsize=12)
        row_0410 = df.loc[pd.to_datetime('2025-04-10')]
        plt.text(row_0410['Abs_R_daily'], row_0410['Abs_Total_Surge'], ' 4/10 反彈', fontsize=12)
    except: pass
    
    plt.xlabel('絕對市場衝擊 (|R_daily|)', fontsize=12)
    plt.ylabel('絕對情緒反應 (|Total_Surge|)', fontsize=12)
    plt.title('圖 4：事件強度 vs. 社群反應強度', fontsize=14)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.savefig(IMG_CHART_4, dpi=300)
    print("  > 圖 4 完成")
    
    # --- 圖 5: Lag=1 Cross-Day Correlation (Bar) ---
    # 比較 Same Day vs Lag 1 correlation
    corrs_same = [
        df['Neg_prop_surge'].corr(df['R_daily'], method='spearman'),
        df['Pos_prop_surge'].corr(df['R_daily'], method='spearman')
    ]
    corrs_lag = [
        df['Neg_prop_surge_lag1'].corr(df['R_daily'], method='spearman'),
        df['Pos_prop_surge_lag1'].corr(df['R_daily'], method='spearman')
    ]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    x = np.arange(2); width = 0.35
    ax.bar(x - width/2, corrs_same, width, label='同日 (Same Day)', color='skyblue')
    ax.bar(x + width/2, corrs_lag, width, label='滯後一日 (Lag-1)', color='orange')
    ax.set_xticks(x); ax.set_xticklabels(['Neg Surge', 'Pos Surge'])
    ax.set_ylabel('Spearman Correlation with R_daily')
    ax.set_title('圖 5：跨日滯後相關性檢定 (Lag-1 Robustness)', fontsize=14)
    ax.legend()
    plt.axhline(0, color='black', linewidth=0.8)
    plt.savefig(IMG_CHART_5, dpi=300)
    print("  > 圖 5 完成")
    
    # --- 圖 6: PN Ratio Surge vs Market ---
    fig, ax1 = plt.subplots(figsize=(14, 7)); ax2 = ax1.twinx()
    ax1.bar(df.index, df['PN_Ratio_Surge'], color='purple', alpha=0.5, label='P/N Ratio Surge')
    ax2.plot(df.index, df['Cumulative_Return'], color='orange', marker='s', linestyle='--', label='Cumulative Return')
    
    ax1.set_ylabel('P/N 比例變化量 (Δ Ratio)', color='purple', fontsize=12)
    ax2.set_ylabel('累計報酬率', color='orange', fontsize=12)
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    # 背景
    for label, color in [('P1', 'grey'), ('P2', 'red'), ('P3', 'green')]:
        dates = df[df['Period'] == label].index
        if not dates.empty:
            ax1.axvspan(dates[0], dates[-1], color=color, alpha=0.1)

    plt.title('圖 6：正負情緒比值變化 (PN Ratio Surge) 與市場反應', fontsize=16)
    plt.savefig(IMG_CHART_6, dpi=300)
    print("  > 圖 6 完成")
    
    # --- 圖 8: Total Volume Surge vs Market ---
    fig, ax1 = plt.subplots(figsize=(14, 7)); ax2 = ax1.twinx()
    ax1.bar(df.index, df['Total_Surge'], color='grey', alpha=0.6, label='總討論量脈衝 (Total Surge)')
    ax2.plot(df.index, df['Cumulative_Return'], color='orange', marker='s', linestyle='--', label='Cumulative Return')
    
    ax1.set_ylabel('討論量增量 (Δ Posts)', color='grey', fontsize=12)
    ax2.set_ylabel('累計報酬率', color='orange', fontsize=12)
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    # 標註
    try:
        val_0407 = df.loc[pd.to_datetime('2025-04-07'), 'Total_Surge']
        ax1.annotate('4/7 恐慌量爆發', xy=(mdates.date2num(pd.to_datetime('2025-04-07')), val_0407), 
                     xytext=(0, 10), textcoords='offset points', ha='center', color='red', fontweight='bold')
    except: pass
    
    plt.title('圖 8：總討論量脈衝 (Total Volume Surge) 與市場反應', fontsize=16)
    plt.savefig(IMG_CHART_8, dpi=300)
    print("  > 圖 8 完成")

def plot_hourly_surge(date_str, chart_path, title):
    # 取得資料
    df = prepare_hourly_robustness_data(date_str)
    if df.empty: return
    
    fig, ax1 = plt.subplots(figsize=(10, 6)); ax2 = ax1.twinx()
    
    # X 軸 (Time Blocks)
    x = range(len(df))
    
    # Bar: Neg Surge & Pos Surge
    width = 0.35
    ax1.bar(np.array(x) - width/2, df['Neg_prop_surge'], width, color='red', alpha=0.6, label='Neg Prop Surge')
    ax1.bar(np.array(x) + width/2, df['Pos_prop_surge'], width, color='green', alpha=0.6, label='Pos Prop Surge')
    
    # Line: Hourly Return
    if 'Hourly_Return' in df.columns:
        ax2.plot(x, df['Hourly_Return'], color='orange', marker='o', linestyle='-', linewidth=2, label='Hourly Return')
        ax2.set_ylabel('每小時報酬率', color='orange')
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'))
    
    ax1.set_xticks(x)
    ax1.set_xticklabels(df.index, rotation=0)
    ax1.set_ylabel('情緒比例脈衝 (Δ Prop)')
    ax1.axhline(0, color='black', linewidth=0.8)
    
    plt.title(title, fontsize=14)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    plt.legend(lines1+lines2, labels1+labels2, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(chart_path, dpi=300)
    print(f"  > {title} 完成")

# ===================================================================
# 5. 主程式
# ===================================================================
def main():
    print("🚀 啟動「穩健性檢定 (Robustness)」最終分析...")
    
    # 1. 每日資料與統計
    df_daily = prepare_daily_robustness_data()
    run_stats_report(df_daily)
    plot_charts(df_daily)
    
    # 2. 每小時資料與圖表
    print("\n--- 4. 繪製高頻脈衝圖 (圖 7) ---")
    plot_hourly_surge('2025-04-07', IMG_CHART_7A, '圖 7A：4/7 恐慌日盤中脈衝')
    plot_hourly_surge('2025-04-10', IMG_CHART_7B, '圖 7B：4/10 反彈日盤中脈衝')
    
    print("\n🎉🎉🎉 穩健性分析全數完成！ 🎉🎉🎉")

if __name__ == "__main__":
    main()