# 檔案名稱: run_final_prop_surge_analysis.py
#
# 目的：執行「比例脈衝 (Proportional Surge)」最終分析
# 包含：變數重構、三大統計、三張主圖、迴歸模型、事件視窗表

import pandas as pd
import sqlite3
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.tsa.stattools import ccf
import warnings

# ===================================================================
# 1. 設定區
# ===================================================================
DB_PATH = "ptt_data_m.db"
SENTIMENT_TABLE = "ai_model_predictions_v2_push_only"
STOCK_CSV_PATH = "taiex_open_close.csv"

# 輸出設定
OUTPUT_DATA_CSV = "final_prop_surge_data.csv"
OUTPUT_STATS_TXT = "final_stats_report.txt"
IMG_CHART_1 = "final_chart_1_prop_surge.png"
IMG_CHART_2 = "final_chart_2_composition.png"
IMG_CHART_3 = "final_chart_3_ccf.png"

# 研究設定
RESEARCH_START = '2025-03-27'
RESEARCH_END = '2025-04-16'
YEAR = '2025'

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
    if match:
        return pd.to_datetime(f"{YEAR}/{match.group(1)} {match.group(2)}", format='%Y/%m/%d %H:%M', errors='coerce')
    if 'T' in ts_str: return pd.to_datetime(ts_str, errors='coerce')
    return pd.to_datetime(ts_str, errors='coerce')

def prepare_data():
    print("--- 1. 資料準備與變數計算 ---")
    
    # A. 載入股價
    df_stock = pd.read_csv(STOCK_CSV_PATH, usecols=['Date', '收盤價'], encoding='cp950')
    df_stock['Date'] = pd.to_datetime(df_stock['Date'], format='%Y/%m/%d')
    df_stock = df_stock.set_index('Date').sort_index()
    df_stock = df_stock.loc[RESEARCH_START:RESEARCH_END].copy()
    
    # 計算市場變數
    df_stock['R_daily'] = df_stock['收盤價'].pct_change().fillna(0)
    df_stock['Cumulative_Return'] = (1 + df_stock['R_daily']).cumprod() - 1
    
    # B. 載入情緒 (只取 label_id)
    conn = sqlite3.connect(DB_PATH)
    df_sent = pd.read_sql_query(f"SELECT timestamp, label_id FROM {SENTIMENT_TABLE} WHERE label_id IS NOT NULL", conn)
    conn.close()
    
    df_sent['datetime'] = df_sent['timestamp'].apply(fix_timestamp)
    df_sent.dropna(subset=['datetime'], inplace=True)
    # 這裡我們使用「整天」的日期來計算 Surge (因為我們要看的是 Day-to-Day 的結構改變)
    # 若要更精細，可以用隔夜邏輯，但在 Surge 分析中，整天通常就足夠捕捉趨勢
    df_sent['Date'] = df_sent['datetime'].dt.date 
    
    # C. 計算每日計數 (Counts)
    daily_counts = df_sent.groupby(['Date', 'label_id']).size().unstack(fill_value=0)
    # 補齊欄位 (0:Neg, 1:Neu, 2:Pos)
    for c in [0, 1, 2]:
        if c not in daily_counts.columns: daily_counts[c] = 0
    
    daily_counts.rename(columns={0: 'Count_Neg', 1: 'Count_Neu', 2: 'Count_Pos'}, inplace=True)
    daily_counts['Total'] = daily_counts.sum(axis=1)
    daily_counts.index = pd.to_datetime(daily_counts.index)
    daily_counts = daily_counts.loc[RESEARCH_START:RESEARCH_END]

    # D. 合併
    df = pd.merge(df_stock, daily_counts, left_index=True, right_index=True, how='inner')
    
    # --- 核心變數計算 (依照你的指示) ---
    
    # (1) 情緒比例 (Composition)
    df['Pos_prop'] = df['Count_Pos'] / df['Total']
    df['Neg_prop'] = df['Count_Neg'] / df['Total']
    df['Neu_prop'] = df['Count_Neu'] / df['Total']
    
    # (2) 比例脈衝 (Proportional Surge)
    df['Pos_prop_surge'] = df['Pos_prop'].diff().fillna(0)
    df['Neg_prop_surge'] = df['Neg_prop'].diff().fillna(0)
    
    # (3) Z-score Surge (健全性檢查)
    df['Pos_z'] = stats.zscore(df['Pos_prop'])
    df['Neg_z'] = stats.zscore(df['Neg_prop'])
    df['Pos_z_surge'] = df['Pos_z'].diff().fillna(0)
    df['Neg_z_surge'] = df['Neg_z'].diff().fillna(0)
    
    # 定義 Period
    conditions = [
        df.index.isin(P1_DATES),
        df.index.isin(P2_DATES),
        df.index.isin(P3_DATES)
    ]
    choices = ['P1', 'P2', 'P3']
    df['Period'] = np.select(conditions, choices, default='Other')
    
    # 儲存
    df.to_csv(OUTPUT_DATA_CSV, encoding='utf-8-sig')
    print(f"  > 變數計算完成，已存至 {OUTPUT_DATA_CSV}")
    return df

# ===================================================================
# 3. 統計分析函式
# ===================================================================

def run_statistics(df):
    print("\n--- 2. 執行統計分析 ---")
    results = []
    
    # 準備資料 (移除第一天 NaN Surge 造成的影響，雖然fillna(0)了但統計上可考慮移除)
    # 這裡我們保留，因為 fillna(0) 代表無變化
    
    # B1. Spearman Correlation
    sp_pos, p_sp_pos = stats.spearmanr(df['Pos_prop_surge'], df['R_daily'])
    sp_neg, p_sp_neg = stats.spearmanr(df['Neg_prop_surge'], df['R_daily'])
    
    results.append("=== B1. Spearman 相關 (比例脈衝 vs 日報酬) ===")
    results.append(f"Pos_prop_surge vs R_daily: corr={sp_pos:.4f}, p={p_sp_pos:.4f} (預期正相關)")
    results.append(f"Neg_prop_surge vs R_daily: corr={sp_neg:.4f}, p={p_sp_neg:.4f} (預期負相關)")
    
    # B2. Pearson Correlation
    pe_pos, p_pe_pos = stats.pearsonr(df['Pos_prop_surge'], df['R_daily'])
    pe_neg, p_pe_neg = stats.pearsonr(df['Neg_prop_surge'], df['R_daily'])
    
    results.append("\n=== B2. Pearson 相關 (補充) ===")
    results.append(f"Pos_prop_surge vs R_daily: corr={pe_pos:.4f}, p={p_pe_pos:.4f}")
    results.append(f"Neg_prop_surge vs R_daily: corr={pe_neg:.4f}, p={p_pe_neg:.4f}")
    
    # D. 迴歸分析
    results.append("\n=== D. 迴歸模型 (R_daily ~ Pos_surge + Neg_surge) ===")
    # 標準化係數比較好看
    model = smf.ols("R_daily ~ Pos_prop_surge + Neg_prop_surge", data=df).fit()
    results.append(str(model.summary()))
    
    # 寫入報告
    with open(OUTPUT_STATS_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print(f"  > 統計報告已產出至 {OUTPUT_STATS_TXT}")
    print(f"  > Spearman Neg: {sp_neg:.3f} (p={p_sp_neg:.3f}) | Pos: {sp_pos:.3f} (p={p_sp_pos:.3f})")

# ===================================================================
# 4. 視覺化函式
# ===================================================================

def plot_charts(df):
    print("\n--- 3. 繪製圖表 ---")
    try:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS'] 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    # --- 圖 1: Proportional Surge vs Market ---
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()
    
    # 繪製 Surge (Bar)
    width = 0.4
    # 稍微錯開位置以免重疊
    ax1.bar(df.index - pd.Timedelta(hours=3), df['Neg_prop_surge'], width, color='#d62728', alpha=0.7, label='負面比例脈衝 (Neg Prop Surge)')
    ax1.bar(df.index + pd.Timedelta(hours=3), df['Pos_prop_surge'], width, color='#2ca02c', alpha=0.7, label='正面比例脈衝 (Pos Prop Surge)')
    
    ax1.set_ylabel('情緒比例變化量 (Δ Prop)', fontsize=12)
    ax1.axhline(0, color='black', linewidth=0.8)
    
    # 繪製 Market (Line)
    ax2.plot(df.index, df['Cumulative_Return'], color='#ff7f0e', marker='s', linestyle='--', linewidth=2, label='累計市場報酬 (Cumulative Return)')
    ax2.set_ylabel('累計市場報酬率', color='#ff7f0e', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='#ff7f0e')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))
    
    # 格式與背景
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax1.set_xlabel('交易日', fontsize=12)
    
    # 背景
    for label, color in [('P1', 'grey'), ('P2', 'red'), ('P3', 'green')]:
        dates = df[df['Period'] == label].index
        if not dates.empty:
            # 擴展一點範圍讓色塊好看
            start = dates[0] - pd.Timedelta(hours=12)
            end = dates[-1] + pd.Timedelta(hours=12)
            ax1.axvspan(start, end, color=color, alpha=0.1, label=f'{label} 背景')

    plt.title('圖 1：情緒比例脈衝 (Proportional Surge) 與市場反應', fontsize=16)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    # 過濾重複的 label (尤其是背景色塊)
    by_label = dict(zip(labels1 + labels2, lines1 + lines2))
    # 只顯示主要變數
    target_keys = ['負面比例脈衝 (Neg Prop Surge)', '正面比例脈衝 (Pos Prop Surge)', '累計市場報酬 (Cumulative Return)']
    plt.legend([by_label[k] for k in target_keys], target_keys, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(IMG_CHART_1, dpi=300)
    print(f"  > 圖 1 已存: {IMG_CHART_1}")
    
    # --- 圖 2: Sentiment Composition (100% Stacked) ---
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # 準備堆疊資料
    df_comp = df[['Neg_prop', 'Neu_prop', 'Pos_prop']]
    
    df_comp.plot(kind='bar', stacked=True, color=['#d62728', '#7f7f7f', '#2ca02c'], ax=ax, width=0.8)
    
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    ax.set_ylabel('情緒組成佔比', fontsize=12)
    ax.set_xticklabels([d.strftime('%m/%d') for d in df.index], rotation=45, ha='right')
    ax.set_title('圖 2：每日情緒組成變化 (Composition Shift)', fontsize=16)
    ax.legend(['Negative', 'Neutral', 'Positive'], loc='upper left', bbox_to_anchor=(1, 1))
    
    # 標註關鍵日
    # 4/3 (假設是 P2 前一天，資料可能只有到 4/2，視你的 csv 而定)
    # 這裡我們標註 4/7 和 4/10
    # 找到 4/7 的 index 位置
    try:
        loc_0407 = df.index.get_loc('2025-04-07')
        ax.annotate('4/7 衝擊\n(Neg 佔比高)', xy=(loc_0407, 1.02), xytext=(loc_0407, 1.1), 
                    ha='center', arrowprops=dict(arrowstyle='->', color='red'), color='red')
        
        loc_0410 = df.index.get_loc('2025-04-10')
        ax.annotate('4/10 暫緩\n(Pos 佔比升)', xy=(loc_0410, 1.02), xytext=(loc_0410, 1.1), 
                    ha='center', arrowprops=dict(arrowstyle='->', color='green'), color='green')
    except: pass

    plt.tight_layout()
    plt.savefig(IMG_CHART_2, dpi=300)
    print(f"  > 圖 2 已存: {IMG_CHART_2}")
    
    # --- 圖 3: Cross Correlation (CCF) ---
    # 計算 CCF
    lags = np.arange(-5, 6) # -5 to +5
    # Pos Surge vs Return
    ccf_pos = ccf(df['R_daily'], df['Pos_prop_surge'], adjusted=False)[:6] # positive lags (Sentiment leads)
    # statsmodels ccf 只有正向 lag，我們需要手動做負向
    # 或者使用 plt.xcorr 最快
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # xcorr: x leads y (negative lag) or y leads x
    # 我們想看 Sentiment (x) 是否領先 Return (y)
    # 如果 Sentiment 在 t-1 影響 Return 在 t -> Lag 應該是負的? 
    # plt.xcorr(x, y): lags are k. R[k] = sum(x[n] * y[n+k])
    # if k > 0, y shifted left. 
    # Let's stick to standard interpretation:
    # Lag < 0: Sentiment Leads Market
    # Lag > 0: Market Leads Sentiment
    
    ax.xcorr(df['Pos_prop_surge'], df['R_daily'], maxlags=5, usevlines=True, normed=True, color='green', label='Pos Surge vs Return', lw=2)
    ax.xcorr(df['Neg_prop_surge'], df['R_daily'], maxlags=5, usevlines=True, normed=True, color='red', alpha=0.6, label='Neg Surge vs Return', lw=2)
    
    ax.axhline(0, color='black', lw=1)
    ax.grid(True, linestyle=':')
    ax.set_xlabel('滯後天數 (Lag Days)', fontsize=12)
    ax.set_ylabel('相關係數', fontsize=12)
    ax.set_title('圖 3：情緒脈衝與市場報酬之領先落後分析 (CCF)', fontsize=16)
    
    # 加入註釋
    ax.text(-3, 0.5, 'Lag < 0\n情緒領先', fontsize=12, ha='center', bbox=dict(facecolor='white', alpha=0.7))
    ax.text(3, 0.5, 'Lag > 0\n市場領先', fontsize=12, ha='center', bbox=dict(facecolor='white', alpha=0.7))
    
    ax.legend()
    plt.tight_layout()
    plt.savefig(IMG_CHART_3, dpi=300)
    print(f"  > 圖 3 已存: {IMG_CHART_3}")

# ===================================================================
# 5. 事件視窗表格 (E)
# ===================================================================

def generate_event_table(df):
    print("\n--- 4. 產生事件視窗表格 ---")
    grouped = df.groupby('Period')
    table = grouped[['R_daily', 'Neg_prop_surge', 'Pos_prop_surge']].mean()
    # 累計報酬需要個別計算 (最後一天的累計 - 前一天的累計)
    # 這裡簡單用 R_daily mean 呈現即可，或者 sum
    
    # 格式化
    print("\n【表 E：事件視窗統計】")
    print(table.to_string(float_format="%.4f"))
    
    # 儲存到報告
    with open(OUTPUT_STATS_TXT, "a", encoding="utf-8") as f:
        f.write("\n\n=== E. 事件視窗表格 (Means) ===\n")
        f.write(table.to_string(float_format="%.4f"))

# ===================================================================
# 主程式
# ===================================================================

def main():
    print("🚀 開始執行「比例脈衝 (Proportional Surge)」最終分析...")
    
    # 1. 準備變數
    df = prepare_data()
    
    # 2. 統計
    run_statistics(df)
    
    # 3. 繪圖
    plot_charts(df)
    
    # 4. 表格
    generate_event_table(df)
    
    print("\n🎉🎉🎉 全部完成！請查看產出的 CSV, PNG 和 TXT 檔案。 🎉🎉🎉")

if __name__ == "__main__":
    main()